"""Contract tests for the Conversations continuous publishing runner.

Three of these carry most of the weight:

  `test_a_record_without_human_gates_is_never_published` - the runner exists to publish
  automatically, which is exactly the circumstance in which a human gate gets quietly
  dropped. If that test starts passing records through, the standard is decoration.

  `test_publishing_twice_creates_nothing_the_second_time` - a duplicate paid publication is
  the one failure in this pipeline that cannot be undone after the fact.

  `test_the_runner_owns_no_wix_client_of_its_own` - the acceptance criterion is reuse, and
  reuse is easy to claim and easy to drift away from. This asserts it against the source.

Everything is exercised through plain data or a recording fake, so no test touches Wix,
Lambda or Secrets Manager.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "conversations_batch.py"
sys.path.insert(0, str(ROOT / "scripts"))

import blog_ledger  # noqa: E402
import blog_quality_v2 as quality  # noqa: E402
import wix_blog_migrate as real_wix  # noqa: E402


def load_module():
    spec = importlib.util.spec_from_file_location("conversations_batch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GOOD_BODY = """A person gives their word and then does not honour it. The ordinary response reaches for morality: they were wrong, they should feel bad, they are not to be trusted. That reading arrives instantly and explains nothing about what actually broke.

Something was counting on the word. A schedule, a decision someone else made on the strength of it, a resource committed. The word was load-bearing. When it came out, the structure moved, and the movement is visible whether or not anybody feels guilty about it afterwards.

## What workability asks instead

Workability asks a different question from whether the person is good. It asks what became possible, and what stopped being possible. A colleague who reliably says what will happen creates a condition in which other people can plan against it. One whose word is decorative forces everybody around them to carry a private second plan, and that cost is paid quietly, in duplicated effort nobody ever logs.

Restoring a broken word is not apologising for it. An apology addresses the feeling. Restoration addresses the structure: saying plainly what was not done, acknowledging what it cost the people who were relying on it, and saying what will happen now instead. Notice how rarely that third part appears anywhere.

What appears instead is explanation, aimed at the listener's judgement rather than at the thing that broke. Explanation asks to be excused. Restoration asks what is needed. The difference is not one of tone, and a listener can usually tell which is happening within a sentence or two of the attempt beginning."""


# ── fixtures that the duplication gate accepts ──────────────────────────────────
#
# EVERY RECORD NEEDS ITS OWN BODY, TITLE AND CENTRAL DISTINCTION. Section 28 compares each
# record against the ones before it in the wave at three thresholds - 0.60 on body
# shingles, 0.80 on title tokens, 0.55 on distinction tokens - so a fixture that reuses one
# body is correctly rejected as a cosmetic rewrite. That is the gate working, and the right
# response is a better fixture rather than a suppressed check.
#
# Uniqueness is guaranteed rather than hoped for: the record number is a token in its own
# right (`shingle_hashes` splits on `[a-z0-9']+`), and it recurs every few words, so almost
# no 8-word window is shared between two records. The prose is stilted because it is
# generated; it only has to be structurally sound, not good.

#: Pool sizes are coprime and each exceeds the largest fixture wave, so two records in one
#: wave collide in at most one pool. Smaller pools produced a pair whose distinctions
#: scored 56% against a 55% threshold - the gate was right and the fixture was too narrow.
NOUNS = ("promise", "schedule", "estimate", "handover", "rehearsal", "agreement",
         "commitment", "deadline", "assurance", "undertaking", "arrangement", "pledge",
         "booking", "referral", "waiver", "invoice", "renewal", "escalation", "rollout",
         "migration", "briefing", "retainer", "shipment", "inspection", "settlement",
         "warranty", "tenancy", "subscription", "licence", "clearance", "appraisal",
         "secondment", "embargo", "moratorium", "indemnity", "covenant", "guarantee",
         "concession", "franchise", "endorsement", "certification", "accreditation",
         "attestation", "affidavit", "undertaking-note", "memorandum", "protocol")
QUALITIES = ("structural", "quiet", "load-bearing", "unnoticed", "deferred", "explicit",
             "informal", "conditional", "shared", "provisional", "standing", "implicit",
             "reciprocal", "unilateral", "verbal", "documented", "witnessed", "tacit",
             "binding", "revocable", "perpetual", "seasonal", "contingent", "layered",
             "nested", "delegated", "inherited", "assumed", "negotiated", "imposed",
             "voluntary", "reluctant", "enthusiastic", "grudging", "formalised",
             "undocumented", "rehearsed", "improvised", "habitual", "novel", "fragile",
             "durable", "elastic", "rigid", "porous", "opaque", "transparent",
             "auditable", "traceable", "reversible", "terminal", "recurring")
EFFECTS = ("planning", "trust", "sequencing", "capacity", "attention", "budget",
           "handoff", "cadence", "review", "staffing", "forecast", "queue", "backlog",
           "roadmap", "throughput", "latency", "morale", "goodwill", "credit", "runway",
           "slack", "buffer", "contingency", "overtime", "rework", "escalation-cost",
           "churn", "attrition", "onboarding", "handover-time", "coverage", "rota",
           "availability", "utilisation", "billing", "collections", "renewals",
           "retention", "reputation", "referrals", "pipeline", "conversion",
           "compliance", "audit-trail", "reporting", "reconciliation", "settlement-time",
           "float", "exposure", "concentration", "diversification", "resilience",
           "redundancy")


ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
        "seventeen", "eighteen", "nineteen")
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty",
        "ninety")


def spell(n: int) -> str:
    """The record number as a WORD, not a digit.

    Section 22 forbids a slug ending in a number when the number is only there to force
    uniqueness, and it is right to: `-1` tells a reader nothing. Spelling it also keeps the
    token unique for the duplication sketch, so the fixture satisfies both rules at once.
    """
    if n < 20:
        return ONES[n]
    tail = ONES[n % 10] if n % 10 else ""
    return TENS[n // 10] + (f"-{tail}" if tail else "")


def _pick(pool, n: int, offset: int = 0) -> str:
    return pool[(n + offset) % len(pool)]


def distinct_slug(n: int) -> str:
    return f"when-a-{_pick(NOUNS, n)}-turns-{_pick(QUALITIES, n, 3)}-{spell(n)}"


def distinct_title(n: int) -> str:
    return (f"When a {_pick(NOUNS, n).title()} Turns "
            f"{_pick(QUALITIES, n, 3).title()}, Reading {spell(n).title()}")


def distinct_distinction(n: int) -> str:
    """Deliberately scaffolding-light.

    Section 28 compares distinctions on token overlap at 0.55, and a template made mostly
    of connective words scores high however much the nouns are varied. Four fixed tokens
    against nine varying ones keeps any two of these comfortably apart.
    """
    return (f"Reading {spell(n)}: {_pick(QUALITIES, n)} {_pick(NOUNS, n)} versus "
            f"{_pick(QUALITIES, n, 5)} {_pick(NOUNS, n, 4)}; {_pick(EFFECTS, n)} hides "
            f"{_pick(EFFECTS, n, 7)}, {_pick(EFFECTS, n, 11)} reveals "
            f"{_pick(EFFECTS, n, 3)}.")


#: Three sentence shapes of deliberately different lengths. A generator that emits one
#: shape produces near-uniform cadence, which section 15 flags - correctly, since an
#: article with no rhythm of its own reads as machine-made.
def distinct_body(n: int) -> str:
    """Four paragraphs whose vocabulary and cadence belong to record `n`."""
    word = spell(n)
    paragraphs: List[str] = []
    for para in range(5):
        sentences: List[str] = []
        for index in range(6):
            seed = n + para * 3 + index
            shape = (para + index) % 3
            if shape == 0:
                sentences.append(
                    f"Reading {word} treats the {_pick(NOUNS, seed)} as "
                    f"{_pick(QUALITIES, seed)}.")
            elif shape == 1:
                sentences.append(
                    f"A {_pick(QUALITIES, seed, 2)} {_pick(NOUNS, seed, 1)} in reading "
                    f"{word} carries {_pick(EFFECTS, seed, 2)}, and the "
                    f"{_pick(NOUNS, seed, 5)} moves {_pick(EFFECTS, seed, 9)} with it.")
            else:
                sentences.append(
                    f"Where reading {word} finds a {_pick(QUALITIES, seed, 6)} "
                    f"{_pick(NOUNS, seed, 7)}, the {_pick(EFFECTS, seed, 4)} it was "
                    f"holding turns out to have been {_pick(QUALITIES, seed, 8)} all "
                    f"along, which is why {_pick(EFFECTS, seed, 13)} in reading {word} "
                    f"cannot be read off the {_pick(NOUNS, seed, 9)} alone and has to be "
                    f"traced through the {_pick(EFFECTS, seed, 15)} that depended on it.")
        paragraphs.append(" ".join(sentences))
    return "\n\n".join(paragraphs)


def record(n: int = 1, *, gated: bool = True, **overrides):
    slug = distinct_slug(n)
    row = {
        "sourceId": "",
        "articleClass": "ARCHIVE_DERIVED",
        "status": "EDITORIAL_QA",
        "sourceReviewedFully": "YES",
        "sourceFile": f"sources/integrity-{n}.pdf",
        "originalSourceTitle": f"The Integrity of One's Word {n}",
        "sourceType": "pdf",
        "sourceHash": f"{n:064d}",
        "originalSourceDate": "2019-04-02",
        "title": distinct_title(n),
        "slug": slug,
        "sourceSlug": f"integrity-of-word-{n}",
        "category": "Conversations",
        "author": quality.AUTHOR,
        "canonical": f"https://wecare.digital/post/{slug}/",
        "tags": ["Integrity", "Accountability"],
        "seoTitle": f"{distinct_title(n)} | WECARE.DIGITAL",
        "metaDescription": ("Integrity read as structure rather than virtue: what an "
                            "unhonoured word actually moves, and why restoring it is not "
                            "the same as apologising."),
        "articleType": "REFLECTION",
        "imageStatus": "none",
        "centralDistinction": distinct_distinction(n),
        "distinctPurpose": ("Other Integrity articles ask whether breaking one's word is "
                            "wrong. This one asks what it moves, and separates restoration "
                            "from apology."),
        "materiallyDifferentInquiry": "YES",
        "titleOnlyDifference": "NO",
        "uniqueReaderPromise": "YES",
        "uniqueIntellectualMovement": "YES",
        "contentMarkdown": distinct_body(n),
    }
    if gated:
        row["gate"] = {name: "PASS" for name in quality.HUMAN_GATES}
    row.update(overrides)
    return row


def document(count: int = 1, *, gated: bool = True):
    return {"posts": [record(n, gated=gated) for n in range(1, count + 1)]}


def ledger_for(path: Path, records) -> "blog_ledger.Ledger":
    """A ledger holding one row per record, with the record's sourceId filled in."""
    ledger = blog_ledger.Ledger(path)
    for item in records:
        #: A PDF's identity is its bytes, not its filename, so the fixture supplies bytes.
        row, _ = ledger.register("pdf", item["sourceFile"],
                                payload=item["sourceFile"].encode("utf-8"))
        item["sourceId"] = row.sourceId
        ledger.attach_article(row.sourceId, item["slug"], item["title"], "Conversations")
    ledger.save()
    return ledger


class FakeWix:
    """The real module's pure helpers, with the network replaced by a recorder.

    Ricos compilation, the draft body and the SEO tags come from `wix_blog_migrate`
    itself, so a change to the real payload shape shows up here rather than being masked
    by a hand-written stub.
    """

    TARGET_SITE_ID = "site-under-test"
    BULK_LIMIT = real_wix.BULK_LIMIT
    chunks = staticmethod(real_wix.chunks)
    normalize_manifest_post = staticmethod(real_wix.normalize_manifest_post)
    draft_post = staticmethod(real_wix.draft_post)
    markdown_to_rich_content = staticmethod(real_wix.markdown_to_rich_content)

    def __init__(self, live=None, fail_slugs=()):
        self.live = list(live or [])
        self.fail_slugs = set(fail_slugs)
        self.calls = []
        self.next_id = 100

    def query_posts(self, site_id, include_content=False):
        self.calls.append(("query_posts", site_id))
        return [dict(post) for post in self.live]

    def ensure_author(self):
        self.calls.append(("ensure_author", None))
        return "member-1"

    def ensure_category(self):
        self.calls.append(("ensure_category", None))
        return "category-1"

    def ensure_tags(self, labels):
        labels = list(labels)
        self.calls.append(("ensure_tags", labels))
        return {label: f"tag-{index}" for index, label in enumerate(labels)}

    def request(self, site_id, method, path, body=None):
        self.calls.append((method, path, body))
        if "bulk/draft-posts/create" not in path:
            raise AssertionError(f"unexpected Wix call: {method} {path}")
        results = []
        for index, draft in enumerate(body["draftPosts"]):
            slug = draft["seoSlug"]
            if slug in self.fail_slugs:
                results.append({"itemMetadata": {"originalIndex": index,
                                                 "success": False,
                                                 "error": {"description": "rejected"}}})
                continue
            self.next_id += 1
            self.live.append({"id": f"post-{self.next_id}", "slug": slug,
                              "title": draft["title"], "memberId": draft["memberId"]})
            results.append({"itemMetadata": {"originalIndex": index, "success": True}})
        return {"results": results,
                "bulkActionMetadata": {"totalSuccesses": len(results),
                                       "totalFailures": 0}}


@pytest.fixture
def mod(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "build_corpus", lambda path: quality.CorpusIndex())
    return module


def install(monkeypatch, module, fake):
    monkeypatch.setattr(module, "load_wix", lambda: fake)
    return fake


def public_post(mod, item, *, published="2026-09-29T10:00:00Z", **overrides):
    """A live post as `/seo-tools/blog-public/<slug>` would return it."""
    rich = real_wix.markdown_to_rich_content(item["contentMarkdown"])
    post = {
        "id": "post-101",
        "title": item["title"],
        "slug": item["slug"],
        "excerpt": item["metaDescription"],
        "url": f"https://wecare.digital/post/{item['slug']}/",
        "seoTitle": item["seoTitle"],
        "metaDescription": item["metaDescription"],
        "publishedDate": published,
        "modifiedDate": published,
        "coverImage": "",
        "category": "Conversations",
        "tags": list(item["tags"]),
        "authorName": quality.AUTHOR,
        "richContent": rich,
        "content": mod.flatten_text(rich),
    }
    post.update(overrides)
    return post


# ── the entry gate ──────────────────────────────────────────────────────────────

def test_a_fully_gated_record_validates_and_enters_the_queue(mod, tmp_path):
    doc = document(1)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    report = mod.validate_document(doc, manifest_path=None, ledger_path=ledger_path)
    assert report["errors"] == []
    assert report["readyToPublish"] == [doc["posts"][0]["slug"]]


def test_a_record_without_human_gates_is_never_published(mod, monkeypatch, tmp_path):
    """The load-bearing property: automation must not be able to self-certify.

    `blog_quality_v2` holds an ungated record at EDITORIAL_QA. This asserts the runner
    honours that rather than publishing everything a manifest happens to contain.
    """
    doc = document(1, gated=False)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    report = mod.validate_document(doc, manifest_path=None, ledger_path=ledger_path)
    assert report["errors"] == []
    assert report["readyToPublish"] == []
    assert report["byStatus"] == {"EDITORIAL_QA": 1}

    fake = install(monkeypatch, mod, FakeWix())
    result = mod.publish_document(doc, ledger_path=ledger_path)
    assert result["created"] == 0
    assert result["heldByGate"] == [doc["posts"][0]["slug"]]
    assert not any(call[0] == "POST" for call in fake.calls)


def test_one_gate_answer_missing_is_enough_to_hold_the_record(mod, tmp_path):
    doc = document(1)
    del doc["posts"][0]["gate"]["VOICE"]
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    report = mod.validate_document(doc, manifest_path=None, ledger_path=ledger_path)
    assert report["readyToPublish"] == []


@pytest.mark.parametrize("count", [1, 3, 37])
def test_manifest_size_is_arbitrary(mod, tmp_path, count):
    """No editorial batch size. Gastronomy's contiguous 25 is its own rule, not this one."""
    doc = document(count)
    ledger_path = tmp_path / f"ledger-{count}.json"
    ledger_for(ledger_path, doc["posts"])
    report = mod.validate_document(doc, manifest_path=None, ledger_path=ledger_path)
    assert report["errors"] == []
    assert report["total"] == count
    assert len(report["readyToPublish"]) == count


def test_duplicate_slug_inside_one_manifest_is_rejected(mod, tmp_path):
    doc = document(2)
    doc["posts"][1]["slug"] = doc["posts"][0]["slug"]
    ledger_path = tmp_path / "ledger.json"
    report = mod.validate_document(doc, manifest_path=None, ledger_path=ledger_path)
    assert any("appears 2 times" in error for error in report["errors"])


def test_a_record_with_no_ledger_row_cannot_publish(mod, tmp_path):
    """Publishing it would lose the source-to-article link permanently."""
    doc = document(2)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"][:1])
    report = mod.validate_document(doc, manifest_path=None, ledger_path=ledger_path)
    assert any("no ledger row" in error for error in report["errors"])
    assert doc["posts"][1]["slug"] in " ".join(report["errors"])


def test_payload_contract_rejects_what_wix_cannot_accept(mod):
    bad = record(1, slug="Not A Slug", tags=[], seoTitle="", coverImage="x.jpg")
    errors = " ".join(mod.payload_errors(bad))
    assert "slug must be lowercase" in errors
    assert "tags must be a list of 1-3" in errors
    assert "seoTitle is required" in errors
    assert "coverImage is forbidden" in errors


def test_ricos_validity_catches_an_uncompiled_or_media_bearing_body(mod):
    leaked = {"nodes": [{"type": "PARAGRAPH", "nodes": []},
                        {"type": "PARAGRAPH_EMPTY"},
                        {"type": "IMAGE"},
                        {"type": "MENTION"}]}
    errors = " ".join(mod.ricos_errors(leaked, "slug"))
    assert "PARAGRAPH_EMPTY marker reached the payload" in errors
    assert "forbidden media node IMAGE" in errors
    assert "unexpected rich-content node MENTION" in errors


def test_an_empty_ricos_tree_is_an_error_not_a_pass(mod):
    assert mod.ricos_errors({"nodes": []}, "slug") == [
        "slug: rich content compiled to no nodes"]


# ── idempotence ─────────────────────────────────────────────────────────────────

def test_pending_skips_slugs_already_live_and_already_ledgered(mod, tmp_path):
    items = [record(n) for n in (1, 2, 3)]
    ledger = ledger_for(tmp_path / "ledger.json", items)
    ledger.update(items[1]["sourceId"], status="PUBLISHED",
                  publishedAt="2026-09-28T00:00:00+00:00")
    pending = mod.pending_records(items, {items[0]["slug"]}, ledger)
    assert [item["slug"] for item in pending] == [items[2]["slug"]]


def test_publishing_twice_creates_nothing_the_second_time(mod, monkeypatch, tmp_path):
    """The failure this pipeline must never have: the same article published twice."""
    doc = document(3)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    fake = install(monkeypatch, mod, FakeWix())

    first = mod.publish_document(doc, ledger_path=ledger_path)
    assert first["created"] == 3
    assert sorted(first["published"]) == sorted(p["slug"] for p in doc["posts"])

    creates = [call for call in fake.calls if call[0] == "POST"]
    assert len(creates) == 1, "a 3-post manifest should need one bulk call"

    second = mod.publish_document(doc, ledger_path=ledger_path)
    assert second["created"] == 0
    assert second["skipped"] == 3
    assert len([call for call in fake.calls if call[0] == "POST"]) == 1


def test_a_large_manifest_is_chunked_at_the_wix_bulk_limit(mod, monkeypatch, tmp_path):
    doc = document(45)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    fake = install(monkeypatch, mod, FakeWix())
    result = mod.publish_document(doc, ledger_path=ledger_path)
    assert result["created"] == 45
    creates = [call for call in fake.calls if call[0] == "POST"]
    assert [len(call[2]["draftPosts"]) for call in creates] == [20, 20, 5]
    assert all(call[2]["publish"] is True for call in creates)


def test_publish_checkpoints_the_ledger_durably_per_chunk(mod, monkeypatch, tmp_path):
    doc = document(25)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    install(monkeypatch, mod, FakeWix())
    mod.publish_document(doc, ledger_path=ledger_path)

    #: Re-read from disk, not from the in-memory object: the point of the checkpoint is
    #: that an interrupted run leaves the state behind.
    reloaded = blog_ledger.Ledger.load(ledger_path)
    assert len(reloaded.rows) == 25
    for row in reloaded.rows:
        assert row.status == "PUBLISHED"
        assert row.publishedAt
        assert row.wixPostId.startswith("post-")
    assert json.loads(ledger_path.read_text())["version"] == blog_ledger.LEDGER_VERSION


def test_a_failed_wix_item_raises_and_does_not_checkpoint_it(mod, monkeypatch, tmp_path):
    doc = document(2)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    install(monkeypatch, mod, FakeWix(fail_slugs={doc["posts"][1]["slug"]}))
    with pytest.raises(RuntimeError, match="failed"):
        mod.publish_document(doc, ledger_path=ledger_path)
    rows = {row.slug: row for row in blog_ledger.Ledger.load(ledger_path).rows}
    assert rows[doc["posts"][0]["slug"]].publishedAt
    assert not rows[doc["posts"][1]["slug"]].publishedAt


# ── the live read-back ──────────────────────────────────────────────────────────

def test_a_correctly_published_post_audits_clean(mod):
    item = record(1)
    live = {item["slug"]: 1}
    assert mod.audit_post(public_post(mod, item), item,
                          admin={"memberId": "member-1", "slug": item["slug"]},
                          author_member_id="member-1",
                          live_slug_counts=live,
                          live_title_counts={item["title"]: 1}) == []


def test_audit_catches_metadata_and_url_drift(mod):
    item = record(1)
    public = public_post(mod, item, title="Something Else",
                         seoTitle="Wrong | WECARE.DIGITAL",
                         metaDescription="Wrong.",
                         tags=["Integrity"],
                         category="Gastronomy",
                         url="https://wecare.digital/blog/when-a-word-is-load-bearing-1")
    errors = " ".join(mod.audit_post(public, item,
                                    admin={"memberId": "member-1"},
                                    author_member_id="member-1"))
    assert "title is" in errors
    assert "seoTitle is" in errors
    assert "metaDescription is" in errors
    assert "tags are" in errors
    assert "category is" in errors
    assert "public URL is" in errors


def test_audit_catches_formatting_corruption_in_the_published_body(mod):
    """The real body, with each corruption signature appended.

    Built on top of the correct body on purpose: the char floor and the opening-prose check
    then pass, so every error reported is a corruption finding and the assertions below
    cannot be satisfied by unrelated noise.
    """
    item = record(1)
    good = mod.flatten_text(real_wix.markdown_to_rich_content(item["contentMarkdown"]))
    corrupt = {"nodes": [{"type": "PARAGRAPH", "nodes": [{
        "type": "TEXT",
        "textData": {"text": good + r' Tail.\n\n## Heading\t**bold** <p>html</p> '
                                    r'&nbsp; {"type": "PARAGRAPH"} {{placeholder}} '
                                    r'undefined'},
    }]}]}
    errors = mod.audit_post(public_post(mod, item, richContent=corrupt, content=""), item,
                            admin={"memberId": "member-1"},
                            author_member_id="member-1")
    joined = " ".join(errors)
    for expected in ("literal escaped newline", "literal escaped tab",
                     "literal Markdown heading", "literal Markdown bold markers",
                     "raw editor JSON", "raw HTML markup", "unresolved HTML entity",
                     "unresolved template placeholder",
                     "unsubstituted template variable"):
        assert expected in joined, expected
    assert not any("chars, expected at least" in error for error in errors)
    assert not any("does not open with" in error for error in errors)


def test_audit_catches_the_wrong_body_under_the_right_slug(mod):
    """Metadata can match perfectly while the body belongs to another article."""
    item = record(1)
    other = real_wix.markdown_to_rich_content(
        "A completely different opening paragraph about something else entirely, long "
        "enough to clear the minimum published length on its own without repeating any "
        "of the phrasing that belongs to the record under audit here. It continues for "
        "several more clauses so the character floor is comfortably passed and the only "
        "thing wrong with this post is that the prose is not the prose that was "
        "approved for this slug at all, which is the whole point of the check.")
    errors = " ".join(mod.audit_post(public_post(mod, item, richContent=other, content=""),
                                     item, admin={"memberId": "member-1"},
                                     author_member_id="member-1"))
    assert "does not open with this record's body" in errors


def test_audit_requires_a_fresh_publication_timestamp(mod):
    item = record(1)
    stale = mod.audit_post(public_post(mod, item, published="2019-04-02T00:00:00Z"), item,
                           admin={"memberId": "member-1"}, author_member_id="member-1")
    assert any("not newer than the source" in error for error in stale)

    since = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    early = mod.audit_post(public_post(mod, item, published="2026-09-29T10:00:00Z"), item,
                           admin={"memberId": "member-1"}, author_member_id="member-1",
                           published_since=since)
    assert any("predates this run" in error for error in early)

    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    ahead = mod.audit_post(public_post(mod, item, published=future), item,
                           admin={"memberId": "member-1"}, author_member_id="member-1")
    assert any("in the future" in error for error in ahead)


def test_audit_reports_author_as_unverified_without_an_admin_read(mod):
    """The public view serves a constant author name, so it is not evidence.

    `_blog_view` in seo-tools/wix.py sets `authorName` from a module constant. An audit
    that only asserted that field would pass on a post attributed to anyone at all.
    """
    item = record(1)
    errors = mod.audit_post(public_post(mod, item), item, admin=None)
    assert any("author not verified against Wix" in error for error in errors)

    wrong = mod.audit_post(public_post(mod, item), item,
                           admin={"memberId": "someone-else"},
                           author_member_id="member-1")
    assert any("attributed to the wrong author" in error for error in wrong)


def test_audit_catches_a_duplicated_slug_or_title_on_the_live_site(mod):
    item = record(1)
    errors = " ".join(mod.audit_post(public_post(mod, item), item,
                                     admin={"memberId": "member-1"},
                                     author_member_id="member-1",
                                     live_slug_counts={item["slug"]: 2},
                                     live_title_counts={item["title"]: 3}))
    assert "2 live posts share this slug" in errors
    assert "3 live posts share the title" in errors


def test_a_missing_post_is_an_audit_failure_not_a_crash(mod):
    assert mod.audit_post({}, record(1)) == [
        f"{distinct_slug(1)}: not found on the live site"]


def test_audit_marks_verified_in_the_ledger(mod, monkeypatch, tmp_path):
    doc = document(2)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    fake = install(monkeypatch, mod, FakeWix())
    mod.publish_document(doc, ledger_path=ledger_path)
    monkeypatch.setattr(mod, "fetch_public_post",
                        lambda slug: public_post(
                            mod, next(p for p in doc["posts"] if p["slug"] == slug)))

    report = mod.audit_document(doc, ledger_path=ledger_path)
    assert report["errors"] == []
    assert sorted(report["verified"]) == sorted(p["slug"] for p in doc["posts"])
    for row in blog_ledger.Ledger.load(ledger_path).rows:
        assert row.status == "VERIFIED"
        assert row.verifiedAt


def test_audit_reports_an_unpublished_record_rather_than_failing_it(mod, monkeypatch,
                                                                   tmp_path):
    doc = document(1)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    install(monkeypatch, mod, FakeWix())
    report = mod.audit_document(doc, ledger_path=ledger_path)
    assert report["errors"] == []
    assert report["notPublished"] == [doc["posts"][0]["slug"]]


# ── reuse, asserted against the source ──────────────────────────────────────────

def test_the_runner_owns_no_wix_client_of_its_own():
    """Acceptance criterion: one publisher. Reuse is easy to claim and easy to drift from.

    A second HTTP client or a second credential read here would route around
    `wix_blog_migrate.load_api_key`, and with it the WIX_CREDENTIALS_DISABLED kill switch
    that loader checks before touching Secrets Manager.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("import urllib", "import requests", "http.client",
                      "get_secret_value", "secretsmanager", "Authorization"):
        assert forbidden not in source, f"{forbidden} suggests a second Wix client"


def test_the_ricos_and_draft_payload_come_from_the_migrate_module(mod, monkeypatch):
    """Not a hand-rolled equivalent: byte-identical to what `wix_blog_migrate` builds."""
    item = record(1)
    install(monkeypatch, mod, FakeWix())
    payload = mod.to_wix_post(item)
    assert payload["richContent"] == real_wix.markdown_to_rich_content(distinct_body(1))
    draft = real_wix.draft_post(payload, "member-1", "category-1",
                                {"Integrity": "t1", "Accountability": "t2"})
    assert draft["seoSlug"] == item["slug"]
    assert draft["seoData"] == real_wix.seo_data(payload)
    #: Absent on purpose, so Wix stamps a fresh publication date.
    assert "firstPublishedDate" not in draft


def test_publish_sends_only_the_bulk_create_endpoint(mod, monkeypatch, tmp_path):
    doc = document(2)
    ledger_path = tmp_path / "ledger.json"
    ledger_for(ledger_path, doc["posts"])
    fake = install(monkeypatch, mod, FakeWix())
    mod.publish_document(doc, ledger_path=ledger_path)
    paths = {call[1] for call in fake.calls if call[0] == "POST"}
    assert paths == {"/blog/v3/bulk/draft-posts/create"}


def test_build_corpus_excludes_the_manifest_from_itself(tmp_path, monkeypatch):
    """Without this a committed record collides with its own committed copy."""
    module = load_module()
    manifest = tmp_path / "CONV-001.json"
    manifest.write_text(json.dumps(document(1)), encoding="utf-8")
    monkeypatch.setattr(quality, "DEFAULT_CORPUS", (str(manifest),))
    monkeypatch.setattr(quality.CorpusIndex, "load_published_index",
                        lambda self, *a, **k: None)
    corpus = module.build_corpus(manifest)
    assert len(corpus) == 0
