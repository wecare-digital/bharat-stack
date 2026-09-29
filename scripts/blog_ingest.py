#!/usr/bin/env python3
"""Bulk ingestion: many PDFs and many URLs to blog source records, in one run.

WHAT THIS DOES, AND THE ONE THING IT WILL NOT DO.

It takes thousands of sources in a single invocation - a directory of PDFs, a file of
URLs, or a work order exported from the admin page - and for each one it:

  1. resolves it against the ledger, so a source already ingested is skipped rather
     than converted a second time (see `blog_ledger` for why that is the whole game),
  2. extracts the text (pypdf for a PDF, lxml for a page),
  3. reflows that text into clean markdown: de-hyphenated, paragraphs rejoined,
     running headers and page numbers dropped, headings recovered,
  4. writes the full extract to disk so a human can actually read the source, which
     section 2 of the standard requires before anything is written,
  5. emits a draft article record pre-filled with every mechanically derivable field -
     slug candidate, canonical, category, author, class, source provenance, source hash.

What it will not do is write the article. Section 31 of the standard is explicit about
the sequence - understand the source, remove the obsolete wrapper, preserve the real
distinction, reconstruct independently in Anew voice - and its closing line forbids the
shortcut: "old essay -> rename -> replace I with we -> lightly paraphrase -> publish".
A generated paraphrase carrying an auto-stamped READY_TO_PUBLISH is exactly that
shortcut wearing a pipeline. So every record lands on SOURCE_REVIEW with
`sourceReviewedFully` unset, and `blog_quality_v2` keeps it there until a person has
done the reading and recorded the human gates.

The mechanical half is what scales to thousands. The editorial half does not, and
pretending it does is how 250-article waves turn into 250 identical articles.

Usage:
    # a whole directory of PDFs plus a list of URLs, one run
    python scripts/blog_ingest.py ingest \\
        --pdf-dir ~/sources/conversations --url-file ~/sources/urls.txt \\
        --category Conversations --article-class ARCHIVE_DERIVED

    # a work order exported from /workspace/seo/blog-studio
    python scripts/blog_ingest.py ingest --work-order ~/Downloads/work-order.json \\
        --pdf-dir ~/sources

    python scripts/blog_ingest.py draft --ledger content/conversations/ledger.json \\
        --out content/conversations/drafts/CONV-001-CONV-025.json --limit 25
    python scripts/blog_ingest.py status --ledger content/conversations/ledger.json
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from blog_ledger import (  # noqa: E402
    Ledger,
    LedgerRow,
    normalize_url,
    now_iso,
    sha256_bytes,
    sha256_text,
    source_identity,
)
import blog_quality_v2 as q  # noqa: E402

DEFAULT_LEDGER = Path("content/conversations/ledger.json")
DEFAULT_EXTRACT_DIR = Path("content/conversations/extracts")
USER_AGENT = "WECARE.DIGITAL-blog-ingest/1.0 (+https://wecare.digital)"
FETCH_TIMEOUT = 20
MAX_FETCH_BYTES = 8 * 1024 * 1024

#: Below this, a PDF almost certainly has no text layer (a scan). Producing an article
#: from 40 characters is worse than refusing: the refusal is visible, the stub is not.
MIN_EXTRACT_CHARS = 400


# ── Extraction result ───────────────────────────────────────────────────────────

@dataclass
class Extract:
    ok: bool
    text: str = ""
    title: str = ""
    date: str = ""
    pages: int = 0
    content_sha256: str = ""
    error: str = ""


# ── Text reflow: the part that decides whether the output is readable ───────────

_SENTENCE_END = re.compile(r"[.!?:;\"\u201d\u2019)]$")
_BULLET = re.compile(r"^\s*(?:[-*\u2022\u25cf\u00b7\u2013]|\d{1,2}[.)])\s+")
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s*)?[-\u2014\s]*\d{1,4}[-\u2014\s]*$", re.IGNORECASE)
_ROMAN_PAGE = re.compile(r"^\s*[ivxlcdm]{1,7}\s*$", re.IGNORECASE)


def _running_lines(pages: Sequence[str], threshold: float = 0.4) -> set:
    """Lines that repeat across pages are the header and footer, not the text.

    A book PDF puts the title on every verso and the chapter on every recto. Left in,
    they land mid-paragraph in the extract and read as the author's own words, which is
    both wrong and the kind of wrong a reviewer skims past.

    Two pages is enough to act on, and the guard used to require three. A two-page
    extract with the same line at the top of both is the commonest single case in this
    corpus - a journal article, a chapter reprint - and skipping detection there left the
    header in the body as a spurious `## heading`, which is what the smoke test caught.
    At two pages the threshold below demands the line appear on BOTH, so a real heading
    that happens to repeat once is not at risk.
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


def _looks_like_heading(line: str, next_line: str = "") -> bool:
    """Heading-shaped, once the font information is gone.

    `next_line` is consulted only for the single-word case. "Workability" on its own line
    is a section heading in a print source and a wrapped fragment in a broken extract, and
    the two are indistinguishable from the line alone - so a single word only counts as a
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
    #: ALL CAPS is unambiguous.
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


def _join_across_hyphen(line: str, continuation: str, vocabulary: set) -> str:
    """Rejoin a word split by a line-final hyphen, deciding whether the hyphen survives.

    THIS IS NOT A COSMETIC CHOICE. Dropping the hyphen unconditionally turned
    "load-\\nbearing" into "loadbearing" - a word that does not exist, sitting in a body
    that reads as finished prose. A reviewer scanning for quality will not catch that,
    because nothing looks broken. Keeping it unconditionally gives "exam-ple", which is
    ugly but obvious, and obvious is the safer failure.

    So the document decides, and the default leans to keeping. If the merged form appears
    elsewhere in the same source, the hyphen was typesetting and it goes. If the
    hyphenated form appears elsewhere, it is a real compound and it stays. With no
    evidence either way the hyphen stays, because a preserved hyphen is recoverable
    information and a silently merged word is not.

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
        #: A one-to-three character stem is a split syllable far more often than it is a
        #: compound element, and prefixes like "un-", "re-" and "pre-" read correctly
        #: merged in either case.
        joined = merged_word
    else:
        joined = last_word + "-" + first_word

    return prefix + joined + (separator + tail if tail else "")


def reflow(raw: str, drop_lines: Optional[Iterable[str]] = None) -> str:
    """Extracted text to clean markdown.

    PDF text extraction returns hard-wrapped lines: a paragraph arrives as eight lines
    broken at the column width, and words are split across them with a hyphen. Left
    alone, every one of those line breaks becomes a separate Ricos paragraph - which is
    precisely the "wall of single lines" the Gastronomy gate added a paragraph-spacing
    assertion to catch. Reflowing here is cheaper than catching it there.
    """
    drop = {line.strip() for line in (drop_lines or ())}
    out_blocks: List[str] = []
    buffer: List[str] = []
    text = str(raw or "").replace("\r\n", "\n")
    lines = text.split("\n")
    #: Every token in the source, used by `_join_across_hyphen` to tell a typeset break
    #: from a real compound. Built once; the documents here are a few hundred kB at most.
    vocabulary = {re.sub(r"[^a-z0-9-]", "", token)
                  for token in re.findall(r"[A-Za-z0-9-]+", text.lower())}
    vocabulary.discard("")

    def flush() -> None:
        if not buffer:
            return
        text = " ".join(buffer)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out_blocks.append(text)
        buffer.clear()

    for position, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        stripped = line.strip()
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
        if _looks_like_heading(stripped, following) and (
                not buffer or _SENTENCE_END.search(buffer[-1])):
            flush()
            out_blocks.append("## " + stripped.rstrip(":").strip())
            continue

        #: Rejoin a word split across the line break. Whether the hyphen survives is
        #: decided per word against the document's own vocabulary - see the helper.
        if buffer and buffer[-1].endswith("-") and not buffer[-1].endswith("--"):
            buffer[-1] = _join_across_hyphen(buffer[-1], stripped, vocabulary)
            continue

        buffer.append(stripped)

        #: A line that ends a sentence AND is short is the end of a paragraph, not a
        #: wrap. A full-width line ending in a period is usually mid-paragraph.
        if _SENTENCE_END.search(stripped) and len(stripped) < 55:
            flush()

    flush()

    #: Collapse the runs of one-line blocks a bad extraction still produces, so the
    #: result has real paragraphs rather than 200 one-sentence ones.
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


# ── PDF ─────────────────────────────────────────────────────────────────────────

def extract_pdf(payload: bytes, ref: str = "") -> Extract:
    try:
        from pypdf import PdfReader
    except ImportError:
        return Extract(False, error="pypdf is not installed (pip install -r requirements-dev.txt)")

    import io
    try:
        reader = PdfReader(io.BytesIO(payload))
    except Exception as exc:  # noqa: BLE001 - any malformed PDF lands here
        return Extract(False, error=f"unreadable PDF: {type(exc).__name__}")

    if getattr(reader, "is_encrypted", False):
        try:
            #: An empty user password is common on "protected" exports and is not a
            #: bypass: it is the password the file actually carries.
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

    text = reflow("\n".join(pages), drop_lines=_running_lines(pages))
    if len(text) < MIN_EXTRACT_CHARS:
        return Extract(
            False, pages=len(pages), text=text,
            error=f"only {len(text)} characters of text recovered from {len(pages)} page(s); "
                  "this is almost certainly a scan with no text layer, and OCR is a separate "
                  "decision rather than something to do silently")

    info = {}
    try:
        info = reader.metadata or {}
    except Exception:  # noqa: BLE001
        info = {}
    title = str(info.get("/Title") or "").strip()
    if not title or len(title) < 3 or title.lower().endswith((".pdf", ".docx", ".indd")):
        title = _first_heading(text) or Path(ref).stem.replace("_", " ").replace("-", " ").strip()
    date = str(info.get("/CreationDate") or "").strip()
    if date.startswith("D:") and len(date) >= 10:
        date = f"{date[2:6]}-{date[6:8]}-{date[8:10]}"
    else:
        date = ""

    return Extract(True, text=text, title=title[:200], date=date, pages=len(pages),
                   content_sha256=sha256_text(text))


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("## "):
            return line[3:].strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:120]
    return ""


# ── URL ─────────────────────────────────────────────────────────────────────────

#: Everything that is page furniture rather than the article.
_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "aside", "form", "noscript",
               "iframe", "svg", "button", "figure", "figcaption")


def extract_url(url: str) -> Extract:
    try:
        import requests
    except ImportError:
        return Extract(False, error="requests is not installed")
    try:
        from lxml import html as lxml_html
    except ImportError:
        return Extract(False, error="lxml is not installed")

    target = normalize_url(url)
    if not target.startswith(("http://", "https://")):
        return Extract(False, error=f"not an http(s) URL: {url!r}")
    try:
        response = requests.get(
            target, timeout=FETCH_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            stream=True, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        return Extract(False, error=f"fetch failed: {type(exc).__name__}")
    if response.status_code != 200:
        return Extract(False, error=f"HTTP {response.status_code}")

    content_type = str(response.headers.get("Content-Type") or "").lower()
    body = response.raw.read(MAX_FETCH_BYTES, decode_content=True) or b""
    response.close()

    if "pdf" in content_type or body[:5] == b"%PDF-":
        #: A URL that serves a PDF is a PDF source. Treating it as HTML would extract
        #: nothing and report an empty page instead of a readable document.
        extract = extract_pdf(body, ref=target)
        extract.content_sha256 = sha256_bytes(body)
        return extract
    if "html" not in content_type and "xml" not in content_type and content_type:
        return Extract(False, error=f"unsupported content type {content_type!r}")

    try:
        tree = lxml_html.fromstring(body)
    except Exception as exc:  # noqa: BLE001
        return Extract(False, error=f"unparseable HTML: {type(exc).__name__}")

    title = ""
    for path in ("//meta[@property='og:title']/@content", "//h1//text()", "//title/text()"):
        values = tree.xpath(path)
        if values:
            title = re.sub(r"\s+", " ", str(values[0])).strip()
            if title:
                break

    date = ""
    for path in ("//meta[@property='article:published_time']/@content",
                 "//meta[@name='date']/@content", "//time/@datetime"):
        values = tree.xpath(path)
        if values:
            date = str(values[0]).strip()[:25]
            break

    for element in tree.xpath("|".join(f"//{tag}" for tag in _STRIP_TAGS)):
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    #: Prefer a semantic container. Falling straight to <body> pulls in sidebars and
    #: cookie banners, which then read as the article's own prose.
    root = None
    for path in ("//article", "//main", "//*[@role='main']",
                 "//*[contains(@class,'post-content')]", "//*[contains(@class,'entry-content')]"):
        found = tree.xpath(path)
        if found:
            root = found[0]
            break
    if root is None:
        root = tree

    parts: List[str] = []
    for element in root.iter():
        tag = str(getattr(element, "tag", "") or "").lower()
        if tag in ("h1", "h2", "h3", "h4"):
            text = re.sub(r"\s+", " ", element.text_content()).strip()
            if text:
                parts.append("## " + text)
        elif tag in ("p", "blockquote"):
            text = re.sub(r"\s+", " ", element.text_content()).strip()
            if text:
                parts.append(text)
        elif tag == "li":
            text = re.sub(r"\s+", " ", element.text_content()).strip()
            if text:
                parts.append("- " + text)

    if not parts:
        parts = [re.sub(r"[ \t]+", " ", line).strip()
                 for line in root.text_content().splitlines() if line.strip()]

    text = reflow("\n\n".join(parts))
    if len(text) < MIN_EXTRACT_CHARS:
        return Extract(False, text=text,
                       error=f"only {len(text)} characters of article text found at {target}")
    return Extract(True, text=text, title=(title or _first_heading(text))[:200], date=date,
                   pages=0, content_sha256=sha256_text(text))


# ── Source collection ───────────────────────────────────────────────────────────

@dataclass
class SourceSpec:
    source_type: str
    ref: str
    category: str
    article_class: str
    path: Optional[Path] = None


def collect_sources(args: argparse.Namespace) -> List[SourceSpec]:
    """Every source named on the command line or in a work order, de-duplicated by ref."""
    category = args.category
    article_class = args.article_class
    specs: List[SourceSpec] = []
    seen: set = set()

    def add(spec: SourceSpec) -> None:
        key = (spec.source_type, str(spec.path or spec.ref))
        if key in seen:
            return
        seen.add(key)
        specs.append(spec)

    for raw in args.pdf or ():
        path = Path(raw).expanduser()
        add(SourceSpec("pdf", str(path), category, article_class, path))

    for raw in args.pdf_dir or ():
        root = Path(raw).expanduser()
        if not root.is_dir():
            print(f"warning: {root} is not a directory", file=sys.stderr)
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() == ".pdf":
                add(SourceSpec("pdf", str(path), category, article_class, path))

    for raw in args.url or ():
        add(SourceSpec("url", normalize_url(raw), category, article_class))

    for raw in args.url_file or ():
        path = Path(raw).expanduser()
        if not path.is_file():
            print(f"warning: {path} is not a file", file=sys.stderr)
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                add(SourceSpec("url", normalize_url(line), category, article_class))

    for raw in args.work_order or ():
        specs_from_order, problems = read_work_order(
            Path(raw).expanduser(), category, article_class,
            search_dirs=[Path(p).expanduser() for p in (args.pdf_dir or ())])
        for problem in problems:
            print(f"warning: {problem}", file=sys.stderr)
        for spec in specs_from_order:
            add(spec)

    return specs


def read_work_order(path: Path, default_category: str, default_class: str,
                    search_dirs: Sequence[Path] = ()) -> Tuple[List[SourceSpec], List[str]]:
    """A work order exported from the admin page.

    The page cannot upload bytes anywhere (the site is a static export with no ingest
    backend yet), so it exports the operator's intent: which files, which category, which
    class, and the SHA-256 it computed in the browser. This function relocates each file
    on disk and checks the hash matches.

    THE HASH CHECK IS THE POINT. Browser and script compute the same SHA-256 over the
    same bytes, so a mismatch means the operator selected a different file than the one
    on disk - which is the failure that would otherwise attach the wrong provenance to an
    article, permanently and invisibly.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    items = document.get("sources") if isinstance(document, dict) else document
    order_category = str((document or {}).get("category") or "").strip() \
        if isinstance(document, dict) else ""
    specs: List[SourceSpec] = []
    problems: List[str] = []

    for item in items or []:
        kind = str(item.get("sourceType") or ("url" if item.get("url") else "pdf")).lower()
        category = str(item.get("category") or order_category or default_category).strip()
        article_class = str(item.get("articleClass") or default_class).strip().upper()
        if category not in q.CATEGORIES:
            problems.append(f"{path}: category {category!r} is not one of {list(q.CATEGORIES)}")
            continue
        if kind == "url":
            ref = normalize_url(item.get("url") or item.get("ref") or "")
            if not ref:
                problems.append(f"{path}: a url entry has no url")
                continue
            specs.append(SourceSpec("url", ref, category, article_class))
            continue

        name = str(item.get("fileName") or item.get("ref") or "").strip()
        expected = str(item.get("sha256") or "").strip().lower()
        located: Optional[Path] = None
        candidate = Path(name).expanduser()
        if candidate.is_file():
            located = candidate
        else:
            for directory in search_dirs:
                for found in directory.rglob(Path(name).name):
                    if found.is_file():
                        located = found
                        break
                if located:
                    break
        if located is None:
            problems.append(f"{path}: {name!r} not found on disk; pass --pdf-dir so it can "
                            "be located")
            continue
        if expected:
            actual = sha256_bytes(located.read_bytes())
            if actual != expected:
                problems.append(
                    f"{path}: {located} hashes to {actual[:12]}... but the work order "
                    f"recorded {expected[:12]}...; refusing to attach the wrong source")
                continue
        specs.append(SourceSpec("pdf", str(located), category, article_class, located))

    return specs, problems


# ── Ingestion ───────────────────────────────────────────────────────────────────

def _extract_one(spec: SourceSpec) -> Tuple[SourceSpec, Optional[bytes], Extract]:
    if spec.source_type == "pdf":
        path = spec.path or Path(spec.ref)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            return spec, None, Extract(False, error=f"unreadable file: {type(exc).__name__}")
        return spec, payload, extract_pdf(payload, ref=str(path))
    return spec, None, extract_url(spec.ref)


def ingest(specs: Sequence[SourceSpec], ledger: Ledger, extract_dir: Path,
           workers: int = 8, dry_run: bool = False,
           progress: bool = True) -> Dict[str, Any]:
    """Extract every source that is not already in the ledger.

    Resolution happens BEFORE extraction, not after: on a re-run over 2,000 PDFs the
    skip must be free, and a design that extracts first and then discovers the row
    already exists pays the full cost every time.
    """
    pending: List[SourceSpec] = []
    skipped: List[str] = []

    for spec in specs:
        payload: Optional[bytes] = None
        if spec.source_type == "pdf":
            path = spec.path or Path(spec.ref)
            try:
                payload = path.read_bytes()
            except OSError as exc:
                if not dry_run:
                    row, _ = ledger.register(
                        "text", str(path), category=spec.category,
                        articleClass=spec.article_class, status="EXTRACTION_FAILED",
                        error=f"unreadable file: {type(exc).__name__}")
                continue
        existing = ledger.resolve_source(spec.source_type, spec.ref, payload)
        if existing is not None and existing.status != "EXTRACTION_FAILED":
            skipped.append(existing.sourceRef)
            continue
        pending.append(spec)

    results = {"requested": len(specs), "skipped": len(skipped), "ingested": 0,
               "failed": 0, "failures": [], "rows": []}
    if dry_run:
        results["wouldIngest"] = [spec.ref for spec in pending]
        return results

    extract_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for spec, payload, extract in pool.map(_extract_one, pending):
            done += 1
            if progress and (done % 25 == 0 or done == len(pending)):
                print(f"  extracted {done}/{len(pending)}", file=sys.stderr)

            row, created = ledger.register(
                spec.source_type, spec.ref, payload,
                category=spec.category, articleClass=spec.article_class)

            if not extract.ok:
                ledger.update(row.sourceId, status="EXTRACTION_FAILED",
                              error=extract.error, sourcePages=extract.pages)
                results["failed"] += 1
                results["failures"].append({"ref": spec.ref, "error": extract.error})
                continue

            stem = (q.slugify(extract.title) or row.sourceId[:16])[:80]
            extract_path = extract_dir / f"{stem}-{row.sourceId[:8]}.md"
            extract_path.write_text(extract.text + "\n", encoding="utf-8")

            ledger.update(
                row.sourceId,
                status="INGESTED",
                error="",
                sourceTitle=extract.title,
                sourceDate=extract.date,
                sourcePages=extract.pages,
                extractedChars=len(extract.text),
                extractedWords=q.word_count(extract.text),
                extractPath=str(extract_path),
                contentSha256=extract.content_sha256,
                fetchedAt=now_iso() if spec.source_type == "url" else "",
            )
            results["ingested"] += 1
            results["rows"].append(row.sourceId)

    return results


# ── Draft records ───────────────────────────────────────────────────────────────

def draft_record(row: LedgerRow, extract_text: str) -> Dict[str, Any]:
    """A draft article record with every mechanical field filled and no editorial claim.

    Read what is NOT set here. `sourceReviewedFully` is absent, the section 5 uniqueness
    booleans are absent, and `gate` is absent. Those are the fields a human fills after
    doing the reading, and `blog_quality_v2.decide_status` will hold this record on
    SOURCE_REVIEW until they are. Pre-filling them with YES would produce a record that
    validates and means nothing.
    """
    title = row.sourceTitle or Path(row.extractPath or row.sourceRef).stem
    slug = q.slugify(title)
    words = q.word_count(extract_text)
    if words <= 420:
        article_type = "DISTINCTION"
    elif words <= 820:
        article_type = "REFLECTION"
    elif words <= 1500:
        article_type = "ARTICLE"
    else:
        article_type = "DEEP_ARTICLE"

    record: Dict[str, Any] = {
        "sourceId": row.sourceId,
        "articleClass": row.articleClass or "ARCHIVE_DERIVED",
        "status": "SOURCE_REVIEW",

        # Section 2 - provenance, machine-derived and therefore trustworthy.
        "sourceFile": row.sourceRef,
        "originalSourceTitle": row.sourceTitle,
        "originalSourceDate": row.sourceDate,
        "sourceType": row.sourceType,
        "sourceHash": row.sourceSha256,

        # Sections 21-25 - candidates, to be replaced by editorial decisions.
        "title": title,
        "slug": slug,
        "category": row.category or q.DEFAULT_CATEGORY,
        "author": q.AUTHOR,
        "canonical": q.expected_canonical(slug),
        "tags": [],
        "seoTitle": f"{title} | {q.PUBLISHER}" if title else "",
        "metaDescription": "",

        # Sections 10-11 - a suggestion from the source's own length.
        "articleType": article_type,

        # Section 27.
        "imageStatus": "none",

        # The body starts as the FAITHFUL EXTRACT, not as a rewrite. Section 3: understand
        # the source before editing it. This field is what the editor works from.
        "sourceExtract": extract_text,
        "contentMarkdown": "",

        # Sections 4 and 5 - left empty on purpose. See the docstring.
        "centralDistinction": "",
        "distinctPurpose": "",
    }
    return record


def _disambiguate_slugs(records: List[Dict[str, Any]]) -> None:
    """Make candidate slugs unique within a batch, and refuse to invent one.

    Two PDFs exported from the same template share a `/Title`, so both produced the slug
    `fixture-source-document` and the second would have collided the moment it was
    published. Section 22 forbids appending an arbitrary number to force uniqueness, so
    the fallback order is: the document's own filename stem, then NOTHING.

    An empty slug is the correct last resort. The gate blocks on SLUG_MISSING, which puts
    the decision in front of the editor who is reading the source anyway - whereas a
    machine-invented `-2` suffix is a URL nobody chose, and section 22 names it.
    """
    seen: Dict[str, int] = {}
    for record in records:
        slug = str(record.get("slug") or "")
        if slug and slug not in seen:
            seen[slug] = 1
            continue
        fallback = q.slugify(Path(str(record.get("sourceFile") or "")).stem)
        if fallback and fallback not in seen:
            record["slug"] = fallback
            record["canonical"] = q.expected_canonical(fallback)
            record.setdefault("ingestNotes", []).append(
                f"slug candidate {slug!r} collided; used the filename stem instead")
            seen[fallback] = 1
            continue
        record["slug"] = ""
        record["canonical"] = ""
        record.setdefault("ingestNotes", []).append(
            f"slug candidate {slug!r} collided and no distinct fallback existed; an editor "
            "must name this one (section 22 forbids appending a number to force uniqueness)")


def build_drafts(ledger: Ledger, out: Path, limit: Optional[int] = None,
                 category: Optional[str] = None) -> Dict[str, Any]:
    rows = [row for row in ledger.pending() if row.status == "INGESTED"]
    if category:
        rows = [row for row in rows if row.category == category]
    if limit:
        rows = rows[:limit]

    records: List[Dict[str, Any]] = []
    missing: List[str] = []
    for row in rows:
        path = Path(row.extractPath) if row.extractPath else None
        if path is None or not path.is_file():
            missing.append(row.sourceRef)
            continue
        records.append(draft_record(row, path.read_text(encoding="utf-8")))
    _disambiguate_slugs(records)

    document = {
        "generatedAt": now_iso(),
        "standard": "WECARE.DIGITAL Conversations Content Quality Standard v2",
        "note": ("Draft records. Every body is the faithful source extract, not an "
                 "article. Editorial reconstruction, the section 4/5 fields and the "
                 "section 29 human gates are all outstanding."),
        "posts": records,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"drafted": len(records), "missingExtract": missing, "out": str(out)}


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _add_source_args(node: argparse.ArgumentParser) -> None:
    node.add_argument("--pdf", nargs="*", default=[], help="one or more PDF paths")
    node.add_argument("--pdf-dir", nargs="*", default=[],
                     help="directories searched recursively for *.pdf")
    node.add_argument("--url", nargs="*", default=[], help="one or more URLs")
    node.add_argument("--url-file", nargs="*", default=[],
                     help="text files of URLs, one per line, # comments allowed")
    node.add_argument("--work-order", nargs="*", default=[],
                     help="work orders exported from /workspace/seo/blog-studio")
    node.add_argument("--category", default=q.DEFAULT_CATEGORY, choices=list(q.CATEGORIES))
    node.add_argument("--article-class", default="ARCHIVE_DERIVED",
                     choices=list(q.ARTICLE_CLASSES))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bulk PDF and URL blog ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_cmd = sub.add_parser("ingest")
    _add_source_args(ingest_cmd)
    ingest_cmd.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ingest_cmd.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_DIR)
    ingest_cmd.add_argument("--workers", type=int, default=8)
    ingest_cmd.add_argument("--limit", type=int, default=0)
    ingest_cmd.add_argument("--dry-run", action="store_true")
    ingest_cmd.add_argument("--json", action="store_true")

    draft_cmd = sub.add_parser("draft")
    draft_cmd.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    draft_cmd.add_argument("--out", required=True, type=Path)
    draft_cmd.add_argument("--limit", type=int, default=0)
    draft_cmd.add_argument("--category", default=None, choices=list(q.CATEGORIES))
    draft_cmd.add_argument("--json", action="store_true")

    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    status_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    ledger = Ledger.load(args.ledger)

    if args.command == "status":
        report = ledger.rollup()
        print(json.dumps(report, indent=2) if args.json else
              "\n".join(f"{k:<18} {v}" for k, v in report.items()))
        return 0

    if args.command == "draft":
        result = build_drafts(ledger, args.out, args.limit or None, args.category)
        ledger.save()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"wrote {result['drafted']} draft record(s) to {result['out']}")
            for ref in result["missingExtract"]:
                print(f"  warning: no extract on disk for {ref}")
            print("\nEvery record is SOURCE_REVIEW. Next: read each extract, reconstruct the "
                  "article in Anew voice, fill centralDistinction and distinctPurpose, then "
                  "run scripts/blog_quality_v2.py validate.")
        return 0

    specs = collect_sources(args)
    if args.limit:
        specs = specs[:args.limit]
    if not specs:
        print("no sources given; pass --pdf, --pdf-dir, --url, --url-file or --work-order",
              file=sys.stderr)
        return 2

    print(f"{len(specs)} source(s) collected", file=sys.stderr)
    result = ingest(specs, ledger, args.extract_dir, workers=args.workers,
                    dry_run=args.dry_run)
    if not args.dry_run:
        ledger.save()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"requested {result['requested']}  "
              f"already known {result['skipped']}  "
              f"ingested {result['ingested']}  failed {result['failed']}")
        for failure in result["failures"]:
            print(f"  FAILED {failure['ref']}: {failure['error']}")
        if args.dry_run:
            for ref in result.get("wouldIngest", []):
                print(f"  would ingest {ref}")
        else:
            print(f"\nledger: {args.ledger}")
    #: A failed extraction is reportable, not fatal: on a 2,000-source run a handful of
    #: scans is expected, and exiting non-zero would make the whole run look failed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
