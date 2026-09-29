"""Contract tests for the shared extraction module.

This module has to behave identically in two runtimes: `scripts/blog_ingest.py` locally and
`wecare-seo-tools` in Lambda. So the tests pin two separate things - the extraction
behaviour, and the dependency budget that makes running it in Lambda possible at all.

`test_no_third_party_imports_beyond_pypdf` is the load-bearing one. If lxml or requests ever
creeps back in, the module still passes every behavioural test locally and then fails at
runtime in Lambda with an ImportError, which is the worst possible place to find out.
"""
from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import blog_pipeline as bp  # noqa: E402
from blog_pdf_fixture import make_pdf, wrap  # noqa: E402

MODULE_PATH = SHARED / "blog_pipeline.py"


# ── The dependency budget ───────────────────────────────────────────────────────

#: Everything the Lambda runtime provides without vendoring, plus the one wheel we ship.
ALLOWED_IMPORTS = {
    "hashlib", "html", "io", "re", "urllib", "collections", "dataclasses",
    "typing", "__future__",
    "pypdf",
}


def _imported_roots(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_third_party_imports_beyond_pypdf():
    """lxml and requests must never come back.

    Both are good libraries and both are pinned in requirements-dev.txt. Neither can be
    zipped from a Mac into a Linux Lambda without building it there, so using one here would
    mean the CLI and the Lambda extract differently - the same PDF producing different
    article text depending on which door it came through.
    """
    unexpected = _imported_roots(MODULE_PATH) - ALLOWED_IMPORTS
    assert unexpected == set(), unexpected


def test_pypdf_is_imported_lazily():
    """So the module imports even where pypdf is absent, e.g. a URL-only code path."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    module_level = {
        alias.name.split(".")[0]
        for node in tree.body if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "pypdf" not in module_level


def test_missing_pypdf_is_a_clean_failure_not_a_crash(monkeypatch):
    real_import = builtins.__import__

    def deny(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("no pypdf here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny)
    extract = bp.extract_pdf(b"%PDF-1.4 whatever")
    assert extract.ok is False
    assert "pypdf" in extract.error


# ── PDF extraction ──────────────────────────────────────────────────────────────

PARAGRAPHS = [
    "A person gives their word and then does not honour it. The ordinary response is to "
    "reach for morality: they were wrong, they should feel bad, they are untrustworthy. "
    "That response is available immediately and it explains nothing about what broke.",
    "Consider instead what the unhonoured word did to the situation. Something was "
    "counting on it. A schedule, a decision someone else made, a resource that was "
    "committed. The word was load-bearing, and when it came out the structure moved.",
    "This is a different question from whether the person is good. It asks what became "
    "possible and what stopped being possible. A colleague who reliably says what will "
    "happen creates a condition in which other people can plan against it properly.",
]


def build_pdf(header: str = "THE GIVEN WORD", pages: int = 2) -> bytes:
    page_list = []
    for index in range(pages):
        lines = [header, ""]
        for paragraph in PARAGRAPHS:
            lines += wrap(paragraph) + [""]
        lines += ["Workability", ""] + wrap(PARAGRAPHS[2]) + ["", str(index + 11)]
        page_list.append(lines)
    return make_pdf(page_list)


@pytest.fixture(scope="module")
def sample_pdf() -> bytes:
    return build_pdf()


def test_pdf_extracts_with_a_content_hash(sample_pdf):
    extract = bp.extract_pdf(sample_pdf, ref="given-word.pdf")
    assert extract.ok, extract.error
    assert extract.pages == 2
    assert len(extract.content_sha256) == 64


def test_the_content_hash_is_stable_for_identical_text(sample_pdf):
    assert bp.extract_pdf(sample_pdf).content_sha256 == bp.extract_pdf(sample_pdf).content_sha256


def test_the_content_hash_ignores_a_changed_running_header(sample_pdf):
    """Retypesetting is not an edit, and the hash should say so.

    Written expecting the opposite, and the code was right: a changed running header
    produces an IDENTICAL hash because the header is dropped as furniture before hashing.
    That is the more useful property - it means re-exporting the same chapter from a
    template with a different header does not read as changed content.
    """
    reheaded = build_pdf(header="A DIFFERENT HEAD")
    assert bp.extract_pdf(sample_pdf).content_sha256 == bp.extract_pdf(reheaded).content_sha256


def test_the_content_hash_changes_when_the_prose_changes(sample_pdf):
    edited = make_pdf([["THE GIVEN WORD", ""] + wrap(
        "An entirely different argument occupies this document, long enough to clear the "
        "extraction floor and different enough that no sentence survives from the original "
        "at all. It concerns the difference between an apology and a restoration, and it "
        "makes that distinction without reference to anything above."
    ) + [""] + wrap(
        "The second paragraph continues the same new argument so the body is comfortably "
        "past the four hundred character minimum that extraction requires before it will "
        "accept a document as carrying a text layer at all."
    )])
    assert bp.extract_pdf(sample_pdf).content_sha256 != bp.extract_pdf(edited).content_sha256


def test_running_headers_dropped_and_headings_recovered(sample_pdf):
    text = bp.extract_pdf(sample_pdf).text
    assert "GIVEN WORD" not in text
    assert "## Workability" in text
    assert "moved. Workability" not in text
    assert not [word for word in text.split() if word.endswith("-")]


def test_a_scan_is_refused_rather_than_stubbed():
    extract = bp.extract_pdf(make_pdf([["x"]]))
    assert extract.ok is False
    assert "no text layer" in extract.error


def test_extract_bytes_dispatches_on_the_magic_number(sample_pdf):
    """A wrong Content-Type must not decide how the bytes are parsed."""
    extract = bp.extract_bytes(sample_pdf, content_type="text/html", ref="mislabelled")
    assert extract.ok, extract.error
    assert extract.pages == 2


# ── HTML extraction, stdlib only ────────────────────────────────────────────────

ARTICLE_HTML = b"""<html><head><title>On Resentment | Some Site</title>
<meta property="og:title" content="On Resentment">
<meta property="article:published_time" content="2021-06-02T10:00:00Z"></head>
<body>
<nav>Home About Contact Subscribe Now</nav><header>SITE CHROME HEADER</header>
<article><h1>On Resentment</h1>
<p>Resentment is described as a poison a person swallows while hoping it will harm somebody
else. The image is vivid and it is also precise about where the damage actually lands.</p>
<p>What makes it persist is not the original injury but the retelling. Each rehearsal
refreshes the grievance and presents it as new evidence, so the account grows while the
event itself stays exactly where it was.</p>
<h2>What it costs</h2><ul><li>attention</li><li>time that is not recoverable</li></ul>
<p>Notice what the rehearsal is protecting. Dropping the grievance would mean giving up the
account of oneself that the grievance supports, and that is a larger loss than it first
appears to be from outside.</p>
</article>
<aside>RELATED LINKS SIDEBAR</aside><footer>FOOTER JUNK</footer>
<script>var tracking = 1;</script></body></html>"""


def test_html_extracts_the_article():
    extract = bp.extract_html(ARTICLE_HTML, ref="https://example.com/a")
    assert extract.ok, extract.error
    assert len(extract.text) > bp.MIN_EXTRACT_CHARS


@pytest.mark.parametrize("furniture", [
    "SITE CHROME HEADER", "FOOTER JUNK", "RELATED LINKS SIDEBAR", "var tracking",
    "Subscribe Now",
])
def test_page_furniture_is_excluded(furniture):
    assert furniture not in bp.extract_html(ARTICLE_HTML).text


def test_og_title_beats_the_document_title():
    """`<title>` is usually "Article | Site", and that suffix would travel into the slug."""
    assert bp.extract_html(ARTICLE_HTML).title == "On Resentment"


def test_document_title_is_the_fallback():
    page = (b"<html><head><title>Only A Title</title></head><body><p>"
            + b"Sustained prose that runs well past the minimum floor here. " * 12
            + b"</p></body></html>")
    assert bp.extract_html(page).title == "Only A Title"


def test_publication_date_is_read():
    assert bp.extract_html(ARTICLE_HTML).date.startswith("2021-06-02")


def test_headings_and_lists_survive():
    text = bp.extract_html(ARTICLE_HTML).text
    assert "## What it costs" in text
    assert "- attention" in text


def test_paragraphs_are_separated_by_blank_lines():
    """Without this the post publishes as one wall, which is a documented past defect."""
    text = bp.extract_html(ARTICLE_HTML).text
    assert "\n\n" in text
    paragraphs = [block for block in text.split("\n\n")
                  if block.strip() and not block.startswith(("##", "- "))]
    assert len(paragraphs) >= 3, paragraphs


def test_a_thin_page_is_refused():
    extract = bp.extract_html(b"<html><body><p>Too short.</p></body></html>")
    assert extract.ok is False
    assert "characters of article text" in extract.error


def test_malformed_html_does_not_raise():
    assert isinstance(
        bp.extract_html(b"<html><body><p>unclosed <div><span>" + b"x" * 500), bp.Extract)


def test_entities_are_unescaped():
    page = (b"<html><body><article><p>It&rsquo;s &amp; it was "
            + b"a sustained sentence carrying enough prose to clear the floor. " * 12
            + b"</p></article></body></html>")
    text = bp.extract_html(page).text
    assert "&amp;" not in text
    assert "&rsquo;" not in text


# ── Fetch ───────────────────────────────────────────────────────────────────────

def test_fetch_refuses_a_non_http_scheme():
    payload, _content_type, error = bp.fetch("file:///etc/passwd")
    assert payload is None
    assert "not an http" in error


def test_extract_url_refuses_a_non_http_scheme():
    assert bp.extract_url("file:///etc/passwd").ok is False


def test_fetch_never_raises_on_an_unroutable_host():
    payload, _content_type, error = bp.fetch("https://this-host-does-not-exist.invalid/x")
    assert payload is None
    assert error


# ── Helpers, and the shared-identity guarantee ──────────────────────────────────

def test_word_count_ignores_markdown_scaffolding():
    # "Heading" + "one two" + "three four" = 5. The `##` and `-` markers are not words.
    assert bp.word_count("## Heading\n\n- one two\n\nthree four") == 5


def test_content_hash_of_empty_is_stable():
    assert bp.content_hash("") == bp.content_hash(None)


def test_the_cli_uses_this_module_rather_than_its_own_copy():
    """A rename here must break the CLI loudly rather than leaving two extractors behind."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import blog_ingest

    assert blog_ingest.reflow is bp.reflow
    assert blog_ingest.extract_pdf is bp.extract_pdf
    assert blog_ingest.extract_url is bp.extract_url
    assert blog_ingest.Extract is bp.Extract
    assert blog_ingest.MIN_EXTRACT_CHARS == bp.MIN_EXTRACT_CHARS
