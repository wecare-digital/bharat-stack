"""Contract tests for the source-to-article ledger.

The tests that matter here are the resolve-before-generate ones. Everything else is
bookkeeping; those are what stop the same PDF becoming two published articles, which is
the one failure in this pipeline that cannot be undone after the fact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import blog_ledger as bl  # noqa: E402


@pytest.fixture()
def ledger(tmp_path):
    return bl.Ledger(tmp_path / "ledger.json")


# ── Resolve before generate ─────────────────────────────────────────────────────

def test_same_pdf_bytes_register_once(ledger):
    payload = b"%PDF-1.4 the same document"
    first, created_first = ledger.register("pdf", "a/one.pdf", payload)
    second, created_second = ledger.register("pdf", "a/one.pdf", payload)
    assert created_first is True
    assert created_second is False
    assert first is second
    assert len(ledger.rows) == 1


def test_a_renamed_pdf_is_the_same_source(ledger):
    """Identity is the bytes, so a re-export with different filenames does not duplicate."""
    payload = b"%PDF-1.4 identical content"
    ledger.register("pdf", "batch-a/integrity.pdf", payload)
    _, created = ledger.register("pdf", "batch-b/integrity-final-v2.pdf", payload)
    assert created is False
    assert len(ledger.rows) == 1


def test_different_pdfs_register_separately(ledger):
    ledger.register("pdf", "one.pdf", b"%PDF-1.4 first")
    ledger.register("pdf", "two.pdf", b"%PDF-1.4 second")
    assert len(ledger.rows) == 2


def test_url_identity_ignores_tracking_parameters(ledger):
    ledger.register("url", "https://example.com/post?utm_source=twitter&id=7")
    _, created = ledger.register("url", "https://example.com/post?id=7&fbclid=abc")
    assert created is False
    assert len(ledger.rows) == 1


@pytest.mark.parametrize("left,right", [
    ("https://Example.com/Post/", "https://example.com/Post"),
    ("https://example.com/post#section", "https://example.com/post"),
    ("example.com/post", "https://example.com/post"),
    # The slash sits BEFORE the query, so an rstrip on the assembled URL cannot reach it.
    # These two registered as separate sources and would have converted one article twice.
    ("https://example.com/post/?id=7", "https://example.com/post?id=7"),
    ("https://example.com/post/?id=7&utm_source=x", "https://example.com/post?id=7"),
    ("https://Example.com/Post/?a=1#frag", "https://example.com/Post?a=1"),
])
def test_url_normalisation_collapses_equivalent_forms(left, right):
    assert bl.normalize_url(left) == bl.normalize_url(right)


def test_the_ledger_and_the_lambda_normalise_urls_identically():
    """Two implementations of source identity would give one URL two rows."""
    import sys
    sys.path.insert(0, str(ROOT / "amplify" / "functions" / "operations" / "seo-tools"))
    import blog_sources as bs

    for url in ("https://example.com/post/?id=7&utm_source=x",
                "Example.com/Post/",
                "https://example.com/a/b/c#frag",
                "https://example.com/?only=query"):
        assert bl.normalize_url(url) == bs.normalize_url(url), url


def test_a_bare_host_does_not_lose_itself_to_the_slash_strip():
    assert bl.normalize_url("https://example.com/") == "https://example.com"
    assert bl.normalize_url("example.com") == "https://example.com"


def test_url_path_case_is_preserved():
    """Only the host is case-insensitive. A path is not, and lowercasing it 404s."""
    assert bl.normalize_url("https://example.com/CaseSensitive").endswith("/CaseSensitive")


def test_pdf_identity_requires_bytes():
    with pytest.raises(ValueError):
        bl.source_identity("pdf", "one.pdf")


def test_unknown_source_type_is_refused(ledger):
    with pytest.raises(ValueError):
        ledger.register("docx", "one.docx", b"x")


# ── Attaching an article ────────────────────────────────────────────────────────

def test_attach_article_records_the_join(ledger):
    row, _ = ledger.register("pdf", "one.pdf", b"%PDF-1.4 a", category="Conversations")
    ledger.attach_article(row.sourceId, "a-fresh-slug", "A Fresh Title", "Conversations",
                          batch_file="batches/CONV-001.json")
    assert row.slug == "a-fresh-slug"
    assert row.batchFile == "batches/CONV-001.json"
    assert row.status == "EDITORIAL_QA"
    assert ledger.by_slug("a-fresh-slug") is row


def test_repointing_a_source_at_a_different_article_is_refused(ledger):
    row, _ = ledger.register("pdf", "one.pdf", b"%PDF-1.4 a")
    ledger.attach_article(row.sourceId, "first-slug", "First", "Conversations")
    with pytest.raises(ValueError, match="already attached"):
        ledger.attach_article(row.sourceId, "second-slug", "Second", "Conversations")


def test_reattaching_the_same_slug_is_idempotent(ledger):
    row, _ = ledger.register("pdf", "one.pdf", b"%PDF-1.4 a")
    ledger.attach_article(row.sourceId, "slug", "T", "Conversations")
    ledger.attach_article(row.sourceId, "slug", "T", "Conversations")
    assert row.slug == "slug"


def test_two_sources_cannot_claim_one_slug(ledger):
    first, _ = ledger.register("pdf", "one.pdf", b"%PDF-1.4 a")
    second, _ = ledger.register("pdf", "two.pdf", b"%PDF-1.4 b")
    ledger.attach_article(first.sourceId, "shared", "T", "Conversations")
    with pytest.raises(ValueError, match="already produced by"):
        ledger.attach_article(second.sourceId, "shared", "T", "Conversations")


def test_attaching_to_an_unknown_source_raises(ledger):
    with pytest.raises(KeyError):
        ledger.attach_article("deadbeef", "slug", "T", "Conversations")


def test_update_rejects_an_unknown_field(ledger):
    row, _ = ledger.register("pdf", "one.pdf", b"%PDF-1.4 a")
    with pytest.raises(KeyError):
        ledger.update(row.sourceId, notAField="x")


# ── Persistence ─────────────────────────────────────────────────────────────────

def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = bl.Ledger(path)
    row, _ = ledger.register("pdf", "one.pdf", b"%PDF-1.4 a", category="Gastronomy",
                             articleClass="ARCHIVE_DERIVED")
    ledger.update(row.sourceId, sourceTitle="One", extractedWords=420)
    ledger.attach_article(row.sourceId, "one", "One", "Gastronomy")
    ledger.save()

    reloaded = bl.Ledger.load(path)
    assert len(reloaded.rows) == 1
    restored = reloaded.rows[0]
    assert restored.sourceId == row.sourceId
    assert restored.slug == "one"
    assert restored.extractedWords == 420
    assert restored.category == "Gastronomy"
    assert reloaded.resolve_source("pdf", "any-name.pdf", b"%PDF-1.4 a") is restored


def test_load_of_a_missing_file_is_empty_not_an_error(tmp_path):
    assert bl.Ledger.load(tmp_path / "nope.json").rows == []


def test_unknown_fields_in_a_stored_ledger_are_ignored(tmp_path):
    """A field added by a later version must not make the file unreadable."""
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"version": 99, "sources": [{
        "sourceId": "a" * 64, "sourceType": "pdf", "sourceRef": "x.pdf",
        "sourceSha256": "a" * 64, "ingestedAt": "2026-09-29T00:00:00+00:00",
        "somethingFromTheFuture": {"nested": True},
    }]}), encoding="utf-8")
    ledger = bl.Ledger.load(path)
    assert len(ledger.rows) == 1
    assert ledger.rows[0].sourceRef == "x.pdf"


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "sub" / "ledger.json"
    ledger = bl.Ledger(path)
    ledger.register("pdf", "one.pdf", b"%PDF-1.4 a")
    ledger.save()
    assert path.is_file()
    assert [p.name for p in path.parent.iterdir()] == ["ledger.json"]


def test_saved_document_is_valid_json_with_a_count(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = bl.Ledger(path)
    ledger.register("url", "https://example.com/a")
    ledger.register("url", "https://example.com/b")
    ledger.save()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["count"] == 2
    assert document["version"] == bl.LEDGER_VERSION
    assert len(document["sources"]) == 2


# ── Reporting ───────────────────────────────────────────────────────────────────

def test_pending_excludes_converted_and_failed(ledger):
    a, _ = ledger.register("pdf", "a.pdf", b"%PDF-1.4 a")
    b, _ = ledger.register("pdf", "b.pdf", b"%PDF-1.4 b")
    c, _ = ledger.register("pdf", "c.pdf", b"%PDF-1.4 c")
    ledger.attach_article(a.sourceId, "a", "A", "Conversations")
    ledger.update(c.sourceId, status="EXTRACTION_FAILED", error="no text layer")
    assert [row.sourceId for row in ledger.pending()] == [b.sourceId]
    assert [row.sourceId for row in ledger.failed()] == [c.sourceId]


def test_rollup_counts_every_axis(ledger):
    a, _ = ledger.register("pdf", "a.pdf", b"%PDF-1.4 a", category="Conversations")
    ledger.register("url", "https://example.com/x", category="Gastronomy")
    ledger.attach_article(a.sourceId, "a", "A", "Conversations")
    ledger.update(a.sourceId, publishedAt="2026-09-29T00:00:00+00:00")
    report = ledger.rollup()
    assert report["total"] == 2
    assert report["withArticle"] == 1
    assert report["pending"] == 1
    assert report["published"] == 1
    assert report["bySourceType"] == {"pdf": 1, "url": 1}
    assert report["byCategory"] == {"Conversations": 1, "Gastronomy": 1}


# ── Reconciliation against the committed batches ────────────────────────────────

def _write_batch(path: Path, slugs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"posts": [{"slug": s, "title": s} for s in slugs]}),
                    encoding="utf-8")


def test_verify_flags_an_article_with_no_ledger_row(tmp_path):
    _write_batch(tmp_path / "batches" / "CONV-001.json", ["orphan-article"])
    ledger = bl.Ledger(tmp_path / "ledger.json")
    problems = ledger.verify_against_batches([str(tmp_path / "batches" / "*.json")])
    assert any("has no ledger row" in p for p in problems)


def test_verify_flags_a_ledger_row_with_no_article(tmp_path):
    _write_batch(tmp_path / "batches" / "CONV-001.json", [])
    ledger = bl.Ledger(tmp_path / "ledger.json")
    row, _ = ledger.register("pdf", "a.pdf", b"%PDF-1.4 a")
    ledger.attach_article(row.sourceId, "vanished", "V", "Conversations")
    problems = ledger.verify_against_batches([str(tmp_path / "batches" / "*.json")])
    assert any("is in no committed batch" in p for p in problems)


def test_verify_flags_a_slug_in_two_batches(tmp_path):
    _write_batch(tmp_path / "batches" / "CONV-001.json", ["dup"])
    _write_batch(tmp_path / "batches" / "CONV-002.json", ["dup"])
    ledger = bl.Ledger(tmp_path / "ledger.json")
    row, _ = ledger.register("pdf", "a.pdf", b"%PDF-1.4 a")
    ledger.attach_article(row.sourceId, "dup", "D", "Conversations")
    problems = ledger.verify_against_batches([str(tmp_path / "batches" / "*.json")])
    assert any("appears in both" in p for p in problems)


def test_verify_passes_when_both_sides_agree(tmp_path):
    _write_batch(tmp_path / "batches" / "CONV-001.json", ["one", "two"])
    ledger = bl.Ledger(tmp_path / "ledger.json")
    for index, slug in enumerate(("one", "two")):
        row, _ = ledger.register("pdf", f"{slug}.pdf", f"%PDF-1.4 {index}".encode())
        ledger.attach_article(row.sourceId, slug, slug, "Conversations")
    assert ledger.verify_against_batches([str(tmp_path / "batches" / "*.json")]) == []


def test_the_committed_ledger_if_present_reconciles():
    """The real ledger, once it has content, must agree with the real batches."""
    path = ROOT / "content/conversations/ledger.json"
    if not path.exists():
        pytest.skip("no Conversations ledger committed yet")
    ledger = bl.Ledger.load(path)
    problems = ledger.verify_against_batches(
        [str(ROOT / "content/conversations/batches/*.json")])
    assert problems == [], problems
