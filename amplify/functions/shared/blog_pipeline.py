"""Source extraction for the PDF/URL blog pipeline. One implementation, two runtimes.

WHY THIS LIVES IN shared/ AND WHY IT IS STDLIB-ONLY.

The same extraction has to run in two places: `scripts/blog_ingest.py` for bulk local runs
of thousands of sources, and `wecare-seo-tools` for the upload-from-the-browser path. Two
copies would drift, and the drift would be invisible - the same PDF would produce different
article text depending on which door it came through, and nobody would notice until a
reviewer compared two extracts of one document.

So the dependency budget is set by the harder of the two runtimes, which is Lambda:

- `pypdf` is a pure-python wheel with no compiled parts, so it zips into the function
  package directly. No layer, no build step, no Amazon Linux cross-compile.
- HTML parsing uses the stdlib `html.parser`, NOT lxml or BeautifulSoup. lxml is a C
  extension and cannot be zipped from a Mac into a Linux Lambda without building it there.
  Choosing lxml locally and html.parser in Lambda is exactly the drift described above, so
  the stdlib wins in both places even though lxml would extract slightly more cleanly.
- Fetching uses `urllib.request`, not `requests`, for the same reason.

The reflow logic below is the part that decides whether the output is readable prose or a
wall of hard-wrapped fragments. Each rule in it exists because a real extraction produced a
real defect - the comments name them.
"""
from __future__ import annotations

import hashlib
import html
import io
import re
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterable, List, Optional, Sequence, Tuple

USER_AGENT = "WECARE.DIGITAL-blog-ingest/1.0 (+https://wecare.digital)"
FETCH_TIMEOUT = 20
MAX_FETCH_BYTES = 8 * 1024 * 1024

#: Below this, a PDF almost certainly has no text layer (a scan). Producing an article from
#: 40 characters is worse than refusing: the refusal is visible, the stub is not.
MIN_EXTRACT_CHARS = 400


@dataclass
class Extract:
    ok: bool
    text: str = ""
    title: str = ""
    date: str = ""
    pages: int = 0
    content_sha256: str = ""
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "text": self.text, "title": self.title, "date": self.date,
            "pages": self.pages, "contentSha256": self.content_sha256, "error": self.error,
        }


# ── Reflow ──────────────────────────────────────────────────────────────────────

_SENTENCE_END = re.compile(r"[.!?:;\"\u201d\u2019)]$")
_BULLET = re.compile(r"^\s*(?:[-*\u2022\u25cf\u00b7\u2013]|\d{1,2}[.)])\s+")
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s*)?[-\u2014\s]*\d{1,4}[-\u2014\s]*$", re.IGNORECASE)
_ROMAN_PAGE = re.compile(r"^\s*[ivxlcdm]{1,7}\s*$", re.IGNORECASE)


def running_lines(pages: Sequence[str], threshold: float = 0.4) -> set:
    """Lines that repeat across pages are the header and footer, not the text.

    A book PDF puts the title on every verso and the chapter on every recto. Left in, they
    land mid-paragraph in the extract and read as the author's own words, which is both
    wrong and the kind of wrong a reviewer skims past.

    Two pages is enough to act on. The guard used to require three, and a two-page extract
    with the same line at the top of both - a journal article, a chapter reprint, the
    commonest single case here - kept its header as a spurious `## heading`. At two pages
    the threshold below demands the line appear on BOTH, so a real heading that happens to
    repeat once is not at risk.
    """
    if len(pages) < 2:
        return set()
    counts: Counter = Counter()
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        for line in set(lines[:3] + lines[-3:]):
            if 3 <= len(line) <= 90:
                counts[line] += 1
    limit = max(2, int(len(pages) * threshold))
    return {line for line, count in counts.items() if count >= limit}


def looks_like_heading(line: str, next_line: str = "") -> bool:
    """Heading-shaped, once the font information is gone.

    `next_line` is consulted only for the single-word case. "Workability" on its own line is
    a section heading in a print source and a wrapped fragment in a broken extract, and the
    two are indistinguishable from the line alone - so a single word only counts as a
    heading when the following line opens a fresh sentence with a capital.
    """
    stripped = line.strip()
    if not 3 <= len(stripped) <= 80:
        return False
    if _SENTENCE_END.search(stripped) and not stripped.endswith(":"):
        return False
    if _BULLET.match(stripped):
        return False
    words = stripped.split()
    if len(words) > 12:
        return False
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    if sum(1 for c in letters if c.isupper()) / len(letters) > 0.8:
        return True
    capitalised = sum(1 for w in words if w[:1].isupper())
    if len(words) >= 2:
        return capitalised / len(words) >= 0.75
    if not capitalised or len(stripped) < 4:
        return False
    following = str(next_line or "").strip()
    return bool(following) and following[:1].isupper()


def _normalise_token(value: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", str(value).lower())


def join_across_hyphen(line: str, continuation: str, vocabulary: set) -> str:
    """Rejoin a word split by a line-final hyphen, deciding whether the hyphen survives.

    THIS IS NOT A COSMETIC CHOICE. Dropping the hyphen unconditionally turned
    "load-\\nbearing" into "loadbearing" - a word that does not exist, sitting in a body
    that reads as finished prose. A reviewer scanning for quality will not catch that,
    because nothing looks broken. Keeping it unconditionally gives "exam-ple", which is ugly
    but obvious, and obvious is the safer failure.

    So the document decides, and the default leans to keeping. If the merged form appears
    elsewhere in the same source, the hyphen was typesetting and it goes. If the hyphenated
    form appears elsewhere, it is a real compound and it stays. With no evidence either way
    the hyphen stays, because a preserved hyphen is recoverable information and a silently
    merged word is not.

    Note the split on WORDS rather than on the whole line. An earlier version passed the
    entire buffered line as the stem, so every lookup was against a key like
    "hereisasecondexample" and no evidence could ever match - the vocabulary test looked
    like it worked and in fact never fired once.
    """
    head, _, last_word = line[:-1].rpartition(" ")
    first_word, separator, tail = continuation.partition(" ")
    prefix = head + " " if head else ""

    merged_word = last_word + first_word
    if _normalise_token(merged_word) in vocabulary:
        joined = merged_word
    elif _normalise_token(last_word + "-" + first_word) in vocabulary:
        joined = last_word + "-" + first_word
    elif len(last_word) <= 3:
        #: A one-to-three character stem is a split syllable far more often than a compound
        #: element, and prefixes like "un-", "re-" and "pre-" read correctly merged anyway.
        joined = merged_word
    else:
        joined = last_word + "-" + first_word

    return prefix + joined + (separator + tail if tail else "")


def reflow(raw: str, drop_lines: Optional[Iterable[str]] = None) -> str:
    """Extracted text to clean markdown.

    PDF text extraction returns hard-wrapped lines: a paragraph arrives as eight lines
    broken at the column width, and words are split across them with a hyphen. Left alone,
    every one of those line breaks becomes a separate Ricos paragraph - which is precisely
    the "wall of single lines" the Gastronomy gate added a paragraph-spacing assertion to
    catch. Reflowing here is cheaper than catching it there.
    """
    drop = {line.strip() for line in (drop_lines or ())}
    out_blocks: List[str] = []
    buffer: List[str] = []
    text = str(raw or "").replace("\r\n", "\n")
    lines = text.split("\n")
    #: Every token in the source, used by `join_across_hyphen` to tell a typeset break from
    #: a real compound. Built once; these documents are a few hundred kB at most.
    vocabulary = {_normalise_token(token)
                  for token in re.findall(r"[A-Za-z0-9-]+", text.lower())}
    vocabulary.discard("")

    def flush() -> None:
        if not buffer:
            return
        joined = re.sub(r"\s+", " ", " ".join(buffer)).strip()
        if joined:
            out_blocks.append(joined)
        buffer.clear()

    for position, raw_line in enumerate(lines):
        stripped = raw_line.rstrip().strip()
        following = next((lines[i].strip() for i in range(position + 1, len(lines))
                          if lines[i].strip()), "")

        if not stripped:
            flush()
            continue
        if stripped in drop or _PAGE_NUMBER.match(stripped) or _ROMAN_PAGE.match(stripped):
            continue

        if _BULLET.match(stripped):
            flush()
            out_blocks.append("- " + _BULLET.sub("", stripped).strip())
            continue

        #: A heading is recognised even mid-buffer when the buffered text has closed a
        #: sentence. PDF extraction routinely loses the blank line before a heading, and
        #: requiring an empty buffer meant the heading was absorbed into the paragraph
        #: above it - it published as "...the structure moved. Workability This is a..."
        if looks_like_heading(stripped, following) and (
                not buffer or _SENTENCE_END.search(buffer[-1])):
            flush()
            out_blocks.append("## " + stripped.rstrip(":").strip())
            continue

        #: Rejoin a word split across the line break. Whether the hyphen survives is decided
        #: per word against the document's own vocabulary - see the helper.
        if buffer and buffer[-1].endswith("-") and not buffer[-1].endswith("--"):
            buffer[-1] = join_across_hyphen(buffer[-1], stripped, vocabulary)
            continue

        buffer.append(stripped)

        #: A line that ends a sentence AND is short is the end of a paragraph, not a wrap. A
        #: full-width line ending in a period is usually mid-paragraph.
        if _SENTENCE_END.search(stripped) and len(stripped) < 55:
            flush()

    flush()

    #: Collapse the runs of one-line blocks a bad extraction still produces, so the result
    #: has real paragraphs rather than 200 one-sentence ones.
    merged: List[str] = []
    for block in out_blocks:
        if (merged
                and not block.startswith(("##", "- "))
                and not merged[-1].startswith(("##", "- "))
                and len(merged[-1]) < 220
                and not _SENTENCE_END.search(merged[-1])):
            merged[-1] = (merged[-1] + " " + block).strip()
            continue
        merged.append(block)

    return "\n\n".join(merged).strip()


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("## "):
            return line[3:].strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:120]
    return ""


def content_hash(text: str) -> str:
    """Hash of the EXTRACTED text, which is a different question from source identity.

    `blog_ledger` keys a source on the sha256 of its raw bytes. This is the hash of what
    came out, and the two are deliberately separate: a URL has no stable bytes, so its
    identity is its normalised address while its content hash is what changes when the page
    is edited. Comparing content hashes is how a re-fetched page is seen to have moved
    rather than silently becoming a second source.
    """
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def word_count(body: str) -> int:
    plain = re.sub(r"^\s{0,3}#{1,6}\s+", "", str(body or ""), flags=re.MULTILINE)
    plain = re.sub(r"^\s{0,3}[-*+]\s+", "", plain, flags=re.MULTILINE)
    return len([token for token in re.split(r"\s+", plain) if token])


# ── PDF ─────────────────────────────────────────────────────────────────────────

def extract_pdf(payload: bytes, ref: str = "") -> Extract:
    try:
        from pypdf import PdfReader
    except ImportError:
        return Extract(False, error="pypdf is not available in this runtime")

    try:
        reader = PdfReader(io.BytesIO(payload))
    except Exception as exc:  # noqa: BLE001 - any malformed PDF lands here
        return Extract(False, error=f"unreadable PDF: {type(exc).__name__}")

    if getattr(reader, "is_encrypted", False):
        try:
            #: An empty user password is common on "protected" exports and is not a bypass:
            #: it is the password the file actually carries.
            if reader.decrypt("") == 0:
                return Extract(False, error="PDF is password protected")
        except Exception as exc:  # noqa: BLE001
            return Extract(False, error=f"PDF is encrypted: {type(exc).__name__}")

    pages: List[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - one bad page must not lose the document
            pages.append("")

    text = reflow("\n".join(pages), drop_lines=running_lines(pages))
    if len(text) < MIN_EXTRACT_CHARS:
        return Extract(
            False, pages=len(pages), text=text,
            error=f"only {len(text)} characters of text recovered from {len(pages)} page(s); "
                  "this is almost certainly a scan with no text layer, and OCR is a separate "
                  "decision rather than something to do silently")

    try:
        info = reader.metadata or {}
    except Exception:  # noqa: BLE001
        info = {}
    title = str(info.get("/Title") or "").strip()
    if not title or len(title) < 3 or title.lower().endswith((".pdf", ".docx", ".indd")):
        stem = ref.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        title = first_heading(text) or stem.replace("_", " ").replace("-", " ").strip()
    date = str(info.get("/CreationDate") or "").strip()
    date = f"{date[2:6]}-{date[6:8]}-{date[8:10]}" if date.startswith("D:") and len(date) >= 10 else ""

    return Extract(True, text=text, title=title[:200], date=date, pages=len(pages),
                   content_sha256=content_hash(text))


# ── HTML, stdlib only ───────────────────────────────────────────────────────────

#: Everything that is page furniture rather than the article.
_SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript",
              "iframe", "svg", "button", "figure", "figcaption", "template", "select"}
_BLOCK_TAGS = {"p", "div", "section", "article", "li", "br", "tr", "blockquote", "pre"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4"}


class _ArticleParser(HTMLParser):
    """Pull article-shaped text out of a page with no third-party parser.

    Deliberately simple: it emits a block break for block-level tags, prefixes headings with
    `##` and list items with `- `, and ignores the contents of anything in `_SKIP_TAGS`.
    That is enough for `reflow` to do the rest, and it has no compiled dependency - which is
    the property that lets this same code run in Lambda. It will keep some navigation text
    that lxml's semantic-container selection would have dropped; that is the accepted cost
    of having ONE extractor rather than two that disagree.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip_depth = 0
        self._in_heading = False
        self._in_list_item = False
        self.date = ""
        self._in_title_tag = False
        #: Tracked separately so og:title can WIN rather than merely fill a gap. `<title>`
        #: is usually "Article Name | Site Name", and that suffix would travel into the blog
        #: title and then into the slug. og:title is the author's own clean form.
        self._og_title = ""
        self._doc_title = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "meta":
            prop = (attributes.get("property") or attributes.get("name") or "").lower()
            content = (attributes.get("content") or "").strip()
            if prop in ("og:title", "twitter:title") and content and not self._og_title:
                self._og_title = content
            elif prop in ("article:published_time", "date", "pubdate") and content and not self.date:
                self.date = content[:25]
            return
        if tag == "time" and not self.date:
            self.date = (attributes.get("datetime") or "").strip()[:25]
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title_tag = True
        if tag in _HEADING_TAGS:
            self.parts.append("\n\n## ")
            self._in_heading = True
        elif tag == "li":
            self.parts.append("\n\n- ")
            self._in_list_item = True
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title_tag = False
        if tag in _HEADING_TAGS:
            self._in_heading = False
            self.parts.append("\n\n")
        elif tag == "li":
            self._in_list_item = False
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title_tag:
            if not self._doc_title:
                self._doc_title = re.sub(r"\s+", " ", data).strip()
            return
        cleaned = re.sub(r"[ \t\r\f\v]+", " ", data)
        if cleaned.strip():
            self.parts.append(cleaned)

    @property
    def title(self) -> str:
        return self._og_title or self._doc_title

    def text(self) -> str:
        return html.unescape("".join(self.parts))


def extract_html(payload: bytes, ref: str = "") -> Extract:
    try:
        markup = payload.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return Extract(False, error="could not decode the page as text")
    parser = _ArticleParser()
    try:
        parser.feed(markup)
        parser.close()
    except Exception as exc:  # noqa: BLE001 - a malformed page must not raise out of here
        return Extract(False, error=f"unparseable HTML: {type(exc).__name__}")

    text = reflow(parser.text())
    if len(text) < MIN_EXTRACT_CHARS:
        return Extract(False, text=text,
                       error=f"only {len(text)} characters of article text found at {ref}")
    title = (parser.title or first_heading(text))[:200]
    return Extract(True, text=text, title=title, date=parser.date, pages=0,
                   content_sha256=content_hash(text))


def fetch(url: str) -> Tuple[Optional[bytes], str, str]:
    """`(payload, content_type, error)`. Never raises."""
    if not str(url or "").startswith(("http://", "https://")):
        return None, "", f"not an http(s) URL: {url!r}"
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT,
                      "Accept": "text/html,application/xhtml+xml,application/pdf"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            payload = response.read(MAX_FETCH_BYTES)
    except urllib.error.HTTPError as exc:
        return None, "", f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, "", f"fetch failed: {type(exc).__name__}"
    return payload, content_type, ""


def extract_url(url: str) -> Extract:
    payload, content_type, error = fetch(url)
    if error or payload is None:
        return Extract(False, error=error or "no content")
    #: A URL that serves a PDF is a PDF source. Treating it as HTML would extract nothing
    #: and report an empty page instead of a readable document.
    if "pdf" in content_type or payload[:5] == b"%PDF-":
        return extract_pdf(payload, ref=url)
    if content_type and "html" not in content_type and "xml" not in content_type:
        return Extract(False, error=f"unsupported content type {content_type!r}")
    return extract_html(payload, ref=url)


def extract_bytes(payload: bytes, content_type: str = "", ref: str = "") -> Extract:
    """Dispatch on what the bytes actually are, not on what the caller claimed.

    The magic number wins over the declared content type for the same reason
    `secure-files` re-reads the type from S3 rather than trusting the browser: a wrong
    Content-Type is a hint, and acting on it produces an empty extract that looks like a
    bad document rather than a misrouted one.
    """
    if payload[:5] == b"%PDF-":
        return extract_pdf(payload, ref=ref)
    if "pdf" in (content_type or "").lower():
        return extract_pdf(payload, ref=ref)
    return extract_html(payload, ref=ref)
