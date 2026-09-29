"""Contract tests for bulk PDF and URL ingestion.

Extraction is exercised against REAL PDFs built by `blog_pdf_fixture`, not against a
mocked extractor. The defects worth catching here - hyphens split across a line break,
paragraphs arriving as eight hard-wrapped lines, a running header repeating on every page,
a heading absorbed into the paragraph above it - only exist once a real PDF is parsed, so
a mock would test the mock.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import blog_ingest as bi  # noqa: E402
import blog_ledger as bl  # noqa: E402
import blog_quality_v2 as q  # noqa: E402
from blog_pdf_fixture import make_pdf, wrap  # noqa: E402


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


#: Distinct prose per page. A real PDF's page 2 CONTINUES the document; byte-identical pages
#: make every line inside the header-detection window look like a running header, which
#: exercises the give-up backstop rather than the detection. `tests/test_blog_pipeline.py`
#: covers that pathological case on purpose.
CONTINUATIONS = [
    "Restoration is not apology. An apology addresses the feeling while restoration "
    "addresses the structure: saying what was not done, acknowledging what it cost, and "
    "saying what will happen now instead of that.",
    "Notice how rarely that third part appears. What appears instead is explanation, aimed "
    "at the listener's judgement rather than at the thing that came apart, and it asks to "
    "be excused rather than asking what is needed.",
]


def build_pdf(header: str = "THE INTEGRITY OF ONE'S WORD", pages: int = 2) -> bytes:
    page_list = []
    for index in range(pages):
        lines = [header, ""]
        if index == 0:
            for paragraph in PARAGRAPHS:
                lines += wrap(paragraph) + [""]
            lines += ["Workability", ""] + wrap(PARAGRAPHS[2]) + [""]
        else:
            body = CONTINUATIONS[(index - 1) % len(CONTINUATIONS)]
            lines += wrap(body) + [""] + wrap(f"Page {index + 1} continues: " + body) + [""]
        lines += [str(index + 11)]
        page_list.append(lines)
    return make_pdf(page_list)


@pytest.fixture(scope="module")
def sample_pdf() -> bytes:
    return build_pdf()


# ── PDF extraction ──────────────────────────────────────────────────────────────

def test_a_real_pdf_extracts(sample_pdf):
    extract = bi.extract_pdf(sample_pdf, ref="integrity.pdf")
    assert extract.ok, extract.error
    assert extract.pages == 2
    assert len(extract.text) > bi.MIN_EXTRACT_CHARS
    assert extract.content_sha256


def test_hyphens_split_across_a_line_break_are_rejoined(sample_pdf):
    text = bi.extract_pdf(sample_pdf).text
    assert not [word for word in text.split() if word.endswith("-")], text


def test_hard_wrapped_lines_become_real_paragraphs(sample_pdf):
    text = bi.extract_pdf(sample_pdf).text
    paragraphs = [b for kind, b in q.blocks(text) if kind == "paragraph"]
    assert paragraphs, text
    #: A failure to reflow shows up as many very short paragraphs, one per wrapped line.
    assert max(len(p) for p in paragraphs) > 200, [len(p) for p in paragraphs]


def test_running_headers_are_dropped(sample_pdf):
    text = bi.extract_pdf(sample_pdf).text
    assert "INTEGRITY OF ONE" not in text


def test_a_two_page_source_still_gets_header_detection():
    """The guard used to require three pages, leaving the header in on a two-page source."""
    assert bi._running_lines(["HEADER\nbody one", "HEADER\nbody two"]) == {"HEADER"}


def test_page_numbers_are_dropped(sample_pdf):
    text = bi.extract_pdf(sample_pdf).text
    assert "\n11" not in text and not text.rstrip().endswith("12")


def test_a_heading_is_not_absorbed_into_the_paragraph_above_it(sample_pdf):
    """PDF extraction loses the blank line before a heading; recovery must not need it."""
    text = bi.extract_pdf(sample_pdf).text
    assert "## Workability" in text
    assert "moved. Workability" not in text


def test_pdf_metadata_title_is_used(sample_pdf):
    assert bi.extract_pdf(sample_pdf).title == "Fixture Source Document"


def test_a_scan_with_no_text_layer_is_refused_not_stubbed():
    """An empty article is worse than a visible refusal: the stub publishes."""
    extract = bi.extract_pdf(make_pdf([["x"]]))
    assert extract.ok is False
    assert "no text layer" in extract.error


def test_a_corrupt_pdf_fails_cleanly():
    extract = bi.extract_pdf(b"not a pdf at all")
    assert extract.ok is False
    assert extract.error


def test_extraction_failure_carries_no_exception_text_that_could_leak():
    extract = bi.extract_pdf(b"%PDF-1.4 truncated")
    assert extract.ok is False
    assert "Traceback" not in extract.error


# ── Reflow, directly ────────────────────────────────────────────────────────────

def test_reflow_joins_a_wrapped_sentence():
    raw = "The word was load-\nbearing, and when it came out the structure\nmoved."
    assert bi.reflow(raw) == "The word was load-bearing, and when it came out the structure moved."


def test_a_real_compound_hyphen_survives_the_line_break():
    """Blind de-hyphenation produced "loadbearing" - a non-word, invisible to a reviewer."""
    assert "load-bearing" in bi.reflow("something load-\nbearing here")
    assert "loadbearing" not in bi.reflow("something load-\nbearing here")


def test_a_typeset_hyphen_is_removed_when_the_document_proves_it():
    """The merged form appearing elsewhere is the evidence that the hyphen was typesetting."""
    raw = "This is one example of it.\n\nHere is a second exam-\nple of the same thing."
    out = bi.reflow(raw)
    assert "example of the same thing" in out
    assert "exam-ple" not in out


def test_a_hyphenated_form_seen_elsewhere_keeps_its_hyphen():
    raw = "A load-bearing wall matters.\n\nThe word was load-\nbearing throughout."
    assert bi.reflow(raw).count("load-bearing") == 2


def test_a_short_stem_is_treated_as_a_split_syllable():
    assert "unexpected" in bi.reflow("it was un-\nexpected entirely")


def test_reflow_keeps_bullets():
    raw = "Ingredients\n\n- two carrots\n- one lemon\n\nMethod follows."
    out = bi.reflow(raw)
    assert "- two carrots" in out
    assert "- one lemon" in out


def test_reflow_normalises_unicode_bullets():
    assert "- item one" in bi.reflow("\u2022 item one")


def test_reflow_recognises_numbered_items():
    assert "- first step" in bi.reflow("1. first step")


def test_reflow_promotes_an_all_caps_line_to_a_heading():
    assert bi.reflow("THE GIVEN WORD\n\nSome prose here.").startswith("## THE GIVEN WORD")


def test_reflow_does_not_promote_a_sentence():
    assert "## " not in bi.reflow("This is an ordinary sentence of prose.")


def test_reflow_single_word_heading_needs_a_capitalised_follower():
    assert "## Workability" in bi.reflow("Ended here.\nWorkability\nThis follows on.")
    #: A lone word followed by lowercase continuation is a wrapped fragment, not a heading.
    assert "## Workability" not in bi.reflow("Ended here.\nWorkability\nand then more.")


def test_reflow_is_idempotent_on_clean_markdown():
    clean = "## Heading\n\nA full paragraph of prose that already reads correctly here.\n\n- one"
    assert bi.reflow(bi.reflow(clean)) == bi.reflow(clean)


def test_reflow_of_empty_input_is_empty():
    assert bi.reflow("") == ""
    assert bi.reflow(None) == ""


# ── Ingestion over a directory ──────────────────────────────────────────────────

@pytest.fixture()
def workspace(tmp_path, sample_pdf):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "integrity.pdf").write_bytes(sample_pdf)
    (source_dir / "second.pdf").write_bytes(build_pdf(header="ANOTHER RUNNING HEAD"))
    return tmp_path, source_dir


def _args(**overrides):
    import argparse
    base = dict(pdf=[], pdf_dir=[], url=[], url_file=[], work_order=[],
                category="Conversations", article_class="ARCHIVE_DERIVED")
    base.update(overrides)
    return argparse.Namespace(**base)


def test_a_directory_of_pdfs_is_collected_recursively(workspace):
    tmp_path, source_dir = workspace
    nested = source_dir / "deeper"
    nested.mkdir()
    (nested / "third.pdf").write_bytes(build_pdf(header="THIRD HEAD"))
    specs = bi.collect_sources(_args(pdf_dir=[str(source_dir)]))
    assert len(specs) == 3
    assert all(spec.source_type == "pdf" for spec in specs)


def test_non_pdf_files_are_ignored(workspace):
    tmp_path, source_dir = workspace
    (source_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
    assert len(bi.collect_sources(_args(pdf_dir=[str(source_dir)]))) == 2


def test_a_url_file_is_read_with_comments_skipped(tmp_path):
    listing = tmp_path / "urls.txt"
    listing.write_text("# a comment\nhttps://example.com/a\n\nhttps://example.com/b\n",
                       encoding="utf-8")
    specs = bi.collect_sources(_args(url_file=[str(listing)]))
    assert [spec.ref for spec in specs] == ["https://example.com/a", "https://example.com/b"]


def test_pdfs_and_urls_are_collected_in_one_run(workspace, tmp_path):
    _, source_dir = workspace
    listing = tmp_path / "urls.txt"
    listing.write_text("https://example.com/a\n", encoding="utf-8")
    specs = bi.collect_sources(_args(pdf_dir=[str(source_dir)], url_file=[str(listing)]))
    assert {spec.source_type for spec in specs} == {"pdf", "url"}
    assert len(specs) == 3


def test_ingest_extracts_and_records_every_source(workspace):
    tmp_path, source_dir = workspace
    ledger = bl.Ledger(tmp_path / "ledger.json")
    specs = bi.collect_sources(_args(pdf_dir=[str(source_dir)]))
    result = bi.ingest(specs, ledger, tmp_path / "extracts", workers=2, progress=False)
    assert result["ingested"] == 2
    assert result["failed"] == 0
    assert len(ledger.rows) == 2
    for row in ledger.rows:
        assert row.status == "INGESTED"
        assert row.category == "Conversations"
        assert row.articleClass == "ARCHIVE_DERIVED"
        assert row.extractedWords > 50
        assert Path(row.extractPath).is_file()


def test_rerunning_ingest_skips_everything(workspace):
    """A 2,000-source re-run must be free, which is what makes it resumable."""
    tmp_path, source_dir = workspace
    ledger = bl.Ledger(tmp_path / "ledger.json")
    specs = bi.collect_sources(_args(pdf_dir=[str(source_dir)]))
    bi.ingest(specs, ledger, tmp_path / "extracts", workers=2, progress=False)
    again = bi.ingest(specs, ledger, tmp_path / "extracts", workers=2, progress=False)
    assert again["skipped"] == 2
    assert again["ingested"] == 0
    assert len(ledger.rows) == 2


def test_dry_run_writes_nothing(workspace):
    tmp_path, source_dir = workspace
    ledger = bl.Ledger(tmp_path / "ledger.json")
    specs = bi.collect_sources(_args(pdf_dir=[str(source_dir)]))
    result = bi.ingest(specs, ledger, tmp_path / "extracts", dry_run=True, progress=False)
    assert len(result["wouldIngest"]) == 2
    assert ledger.rows == []
    assert not (tmp_path / "extracts").exists()


def test_a_failed_source_is_recorded_rather_than_dropped(tmp_path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "scan.pdf").write_bytes(make_pdf([["x"]]))
    ledger = bl.Ledger(tmp_path / "ledger.json")
    specs = bi.collect_sources(_args(pdf_dir=[str(source_dir)]))
    result = bi.ingest(specs, ledger, tmp_path / "extracts", progress=False)
    assert result["failed"] == 1
    assert len(ledger.failed()) == 1
    assert "no text layer" in ledger.failed()[0].error


def test_a_re_exported_scan_is_ingested_as_a_new_source(tmp_path, sample_pdf):
    """Re-exporting a scan with a text layer changes the bytes, so it is a new source.

    The failed row for the original bytes is KEPT, and that is correct rather than untidy:
    it records that those bytes were tried and could not be read. The new export is a
    different document by identity, so it converts normally instead of being skipped.
    """
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    target = source_dir / "doc.pdf"
    target.write_bytes(make_pdf([["x"]]))
    ledger = bl.Ledger(tmp_path / "ledger.json")
    bi.ingest(bi.collect_sources(_args(pdf_dir=[str(source_dir)])), ledger,
              tmp_path / "extracts", progress=False)
    assert len(ledger.failed()) == 1

    target.write_bytes(sample_pdf)
    result = bi.ingest(bi.collect_sources(_args(pdf_dir=[str(source_dir)])), ledger,
                       tmp_path / "extracts", progress=False)
    assert result["ingested"] == 1
    assert len(ledger.rows) == 2
    assert len([row for row in ledger.rows if row.status == "INGESTED"]) == 1


def test_the_same_failed_bytes_are_retried_rather_than_skipped(tmp_path):
    """A transient failure must not permanently blacklist a source."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "doc.pdf").write_bytes(make_pdf([["x"]]))
    ledger = bl.Ledger(tmp_path / "ledger.json")
    specs = bi.collect_sources(_args(pdf_dir=[str(source_dir)]))
    bi.ingest(specs, ledger, tmp_path / "extracts", progress=False)
    again = bi.ingest(specs, ledger, tmp_path / "extracts", progress=False)
    assert again["skipped"] == 0
    assert again["failed"] == 1
    assert len(ledger.rows) == 1


# ── Work orders from the admin page ─────────────────────────────────────────────

def test_a_work_order_locates_files_and_checks_the_hash(workspace, sample_pdf):
    tmp_path, source_dir = workspace
    order = tmp_path / "order.json"
    order.write_text(json.dumps({
        "category": "Conversations",
        "sources": [{"sourceType": "pdf", "fileName": "integrity.pdf",
                     "sha256": bl.sha256_bytes(sample_pdf),
                     "articleClass": "ARCHIVE_DERIVED"}],
    }), encoding="utf-8")
    specs, problems = bi.read_work_order(order, "Conversations", "ARCHIVE_DERIVED",
                                         search_dirs=[source_dir])
    assert problems == []
    assert len(specs) == 1
    assert specs[0].path.name == "integrity.pdf"


def test_a_work_order_with_a_wrong_hash_is_refused(workspace):
    """Selecting the wrong file must be caught here, not become permanent provenance."""
    tmp_path, source_dir = workspace
    order = tmp_path / "order.json"
    order.write_text(json.dumps({"sources": [
        {"sourceType": "pdf", "fileName": "integrity.pdf", "sha256": "b" * 64}]}),
        encoding="utf-8")
    specs, problems = bi.read_work_order(order, "Conversations", "ARCHIVE_DERIVED",
                                         search_dirs=[source_dir])
    assert specs == []
    assert any("refusing to attach the wrong source" in p for p in problems)


def test_a_work_order_reports_a_file_it_cannot_find(tmp_path):
    order = tmp_path / "order.json"
    order.write_text(json.dumps({"sources": [
        {"sourceType": "pdf", "fileName": "absent.pdf", "sha256": "c" * 64}]}),
        encoding="utf-8")
    specs, problems = bi.read_work_order(order, "Conversations", "ARCHIVE_DERIVED")
    assert specs == []
    assert any("not found on disk" in p for p in problems)


def test_a_work_order_rejects_an_invalid_category(tmp_path):
    order = tmp_path / "order.json"
    order.write_text(json.dumps({"sources": [
        {"sourceType": "url", "url": "https://example.com/a", "category": "Insights"}]}),
        encoding="utf-8")
    specs, problems = bi.read_work_order(order, "Conversations", "ARCHIVE_DERIVED")
    assert specs == []
    assert any("is not one of" in p for p in problems)


def test_a_work_order_carries_urls_too(tmp_path):
    order = tmp_path / "order.json"
    order.write_text(json.dumps({"category": "Gastronomy", "sources": [
        {"sourceType": "url", "url": "https://example.com/recipe?utm_source=x"}]}),
        encoding="utf-8")
    specs, problems = bi.read_work_order(order, "Conversations", "ARCHIVE_DERIVED")
    assert problems == []
    assert specs[0].ref == "https://example.com/recipe"
    assert specs[0].category == "Gastronomy"


# ── Draft records ───────────────────────────────────────────────────────────────

def test_a_draft_is_pre_filled_but_makes_no_editorial_claim(workspace):
    tmp_path, source_dir = workspace
    ledger = bl.Ledger(tmp_path / "ledger.json")
    specs = bi.collect_sources(_args(pdf_dir=[str(source_dir)]))
    bi.ingest(specs, ledger, tmp_path / "extracts", progress=False)
    out = tmp_path / "drafts.json"
    result = bi.build_drafts(ledger, out, limit=1)

    assert result["drafted"] == 1
    document = json.loads(out.read_text(encoding="utf-8"))
    record = document["posts"][0]

    # Mechanical fields present.
    assert record["author"] == q.AUTHOR
    assert record["category"] in q.CATEGORIES
    assert record["canonical"] == q.expected_canonical(record["slug"])
    assert record["imageStatus"] == "none"
    assert len(record["sourceHash"]) == 64
    assert record["sourceExtract"]

    # Editorial claims absent, and that is the contract.
    assert record["status"] == "SOURCE_REVIEW"
    assert "sourceReviewedFully" not in record
    assert "gate" not in record
    assert record["centralDistinction"] == ""
    assert record["distinctPurpose"] == ""


def test_a_draft_cannot_reach_the_publish_queue(workspace):
    tmp_path, source_dir = workspace
    ledger = bl.Ledger(tmp_path / "ledger.json")
    bi.ingest(bi.collect_sources(_args(pdf_dir=[str(source_dir)])), ledger,
              tmp_path / "extracts", progress=False)
    out = tmp_path / "drafts.json"
    bi.build_drafts(ledger, out)
    wave = q.assess_wave(q.load_posts(out))
    assert q.publish_queue(wave) == []
    assert all(record["status"] == "SOURCE_REVIEW" for record in wave["records"])


def test_draft_article_type_follows_the_source_length(workspace):
    tmp_path, source_dir = workspace
    ledger = bl.Ledger(tmp_path / "ledger.json")
    row, _ = ledger.register("pdf", "x.pdf", b"%PDF-1.4 x")
    ledger.update(row.sourceId, sourceTitle="A Source", status="INGESTED")
    assert bi.draft_record(row, "word " * 200)["articleType"] == "DISTINCTION"
    assert bi.draft_record(row, "word " * 600)["articleType"] == "REFLECTION"
    assert bi.draft_record(row, "word " * 1200)["articleType"] == "ARTICLE"
    assert bi.draft_record(row, "word " * 2000)["articleType"] == "DEEP_ARTICLE"


def test_two_sources_with_the_same_pdf_title_get_distinct_slugs(workspace):
    """Two exports from one template share a /Title, and both drafted the same slug."""
    tmp_path, source_dir = workspace
    ledger = bl.Ledger(tmp_path / "ledger.json")
    bi.ingest(bi.collect_sources(_args(pdf_dir=[str(source_dir)])), ledger,
              tmp_path / "extracts", progress=False)
    out = tmp_path / "drafts.json"
    bi.build_drafts(ledger, out)
    slugs = [record["slug"] for record in json.loads(out.read_text(encoding="utf-8"))["posts"]]
    assert len(slugs) == 2
    assert len(set(slugs)) == 2, slugs


def test_a_disambiguated_slug_is_never_a_machine_appended_number():
    """Section 22 forbids appending a number merely to force uniqueness."""
    records = [
        {"slug": "same-title", "sourceFile": "a/one.pdf", "canonical": "x"},
        {"slug": "same-title", "sourceFile": "a/two.pdf", "canonical": "x"},
    ]
    bi._disambiguate_slugs(records)
    assert records[1]["slug"] == "two"
    assert not records[1]["slug"].endswith("-2")


def test_an_undisambiguable_slug_is_left_empty_for_an_editor():
    """Empty is correct: the gate blocks on it, rather than a URL nobody chose.

    Both the title-derived slug AND the filename fallback are already taken here, which is
    the only case with no honest answer left.
    """
    records = [
        {"slug": "one", "sourceFile": "one.pdf", "canonical": "x"},
        {"slug": "one", "sourceFile": "one.pdf", "canonical": "x"},
    ]
    bi._disambiguate_slugs(records)
    assert records[1]["slug"] == ""
    assert records[1]["canonical"] == ""
    assert records[1]["ingestNotes"]
    assert "SLUG_MISSING" in {f.code for f in q.check_slug_and_dates(records[1])}


def test_a_draft_reports_not_yet_written_rather_than_empty_body(workspace):
    """An editor reads the message; "no body" on 250 rows looks like a broken export."""
    tmp_path, source_dir = workspace
    ledger = bl.Ledger(tmp_path / "ledger.json")
    bi.ingest(bi.collect_sources(_args(pdf_dir=[str(source_dir)])), ledger,
              tmp_path / "extracts", progress=False)
    out = tmp_path / "drafts.json"
    bi.build_drafts(ledger, out)
    record = q.load_posts(out)[0]
    found = {f.code for f in q.check_type_and_length(record)}
    assert "NOT_YET_WRITTEN" in found
    assert "EMPTY_BODY" not in found


def test_a_genuinely_empty_record_still_reports_empty_body():
    record = {"slug": "x", "title": "X", "contentMarkdown": ""}
    assert "EMPTY_BODY" in {f.code for f in q.check_type_and_length(record)}


def test_draft_reports_a_missing_extract_rather_than_writing_an_empty_record(tmp_path):
    ledger = bl.Ledger(tmp_path / "ledger.json")
    row, _ = ledger.register("pdf", "gone.pdf", b"%PDF-1.4 x")
    ledger.update(row.sourceId, status="INGESTED", extractPath=str(tmp_path / "nope.md"))
    result = bi.build_drafts(ledger, tmp_path / "drafts.json")
    assert result["drafted"] == 0
    assert result["missingExtract"] == ["gone.pdf"]


def test_draft_can_be_filtered_by_category(tmp_path, sample_pdf):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "a.pdf").write_bytes(sample_pdf)
    (source_dir / "b.pdf").write_bytes(build_pdf(header="OTHER HEAD"))
    ledger = bl.Ledger(tmp_path / "ledger.json")
    bi.ingest([bi.SourceSpec("pdf", str(source_dir / "a.pdf"), "Conversations",
                             "ARCHIVE_DERIVED", source_dir / "a.pdf"),
               bi.SourceSpec("pdf", str(source_dir / "b.pdf"), "Gastronomy",
                             "ARCHIVE_DERIVED", source_dir / "b.pdf")],
              ledger, tmp_path / "extracts", progress=False)
    result = bi.build_drafts(ledger, tmp_path / "drafts.json", category="Gastronomy")
    assert result["drafted"] == 1


# ── URL extraction, offline ─────────────────────────────────────────────────────

def test_url_extraction_rejects_a_non_http_scheme():
    extract = bi.extract_url("file:///etc/passwd")
    assert extract.ok is False
    assert "not an http" in extract.error


def test_ingest_of_an_unreadable_path_does_not_raise(tmp_path):
    ledger = bl.Ledger(tmp_path / "ledger.json")
    specs = [bi.SourceSpec("pdf", str(tmp_path / "absent.pdf"), "Conversations",
                           "ARCHIVE_DERIVED", tmp_path / "absent.pdf")]
    result = bi.ingest(specs, ledger, tmp_path / "extracts", progress=False)
    assert result["ingested"] == 0
