"""Content templates: versioned, immutable once published against, and only ever restrictive.

THE TEST THAT CARRIES THE MODULE.

`test_a_published_version_forks_instead_of_mutating`. A template is the structural contract an
article was certified against. If it could be edited in place, every QA record and every
sign-off referring to it would silently start meaning something else, and the records would
look identical before and after. That is not hypothetical - it is what happens the first time
somebody tightens a word band.

The second one worth naming is `test_a_template_can_only_hold_an_article_back`. A template that
could release an article would be a way to reach READY_TO_PUBLISH without the section 29 human
gates, which is the boundary the whole pipeline is built on.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify" / "functions" / "operations" / "seo-tools"))
sys.path.insert(0, str(ROOT / "amplify" / "functions" / "shared"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import blog_quality_v2 as q  # noqa: E402
from blog_pdf_fixture import make_pdf, wrap  # noqa: E402
from test_blog_sources import (  # noqa: E402
    FakeLambda, FakeS3, FakeTable, _pdf_entry,
)


@pytest.fixture()
def env(monkeypatch):
    import blog_batches as bb
    import blog_sources as bs
    import blog_templates as bt
    import storage

    table = FakeTable()
    s3 = FakeS3()
    lam = FakeLambda()
    monkeypatch.setattr(storage, "table", lambda: table)
    monkeypatch.setattr(bs, "s3_client", lambda: s3)
    monkeypatch.setattr(bs, "lambda_client", lambda: lam)
    monkeypatch.setattr(bs, "BUCKET", "wecare-digital-get")
    return {"table": table, "s3": s3, "bb": bb, "bs": bs, "bt": bt, "storage": storage}


TEMPLATE = {
    "name": "Conversations reflection",
    "description": "The shape a reflection takes when it comes from an archive source.",
    "category": "Conversations",
    "minWords": 500,
    "maxWords": 800,
    "sections": [
        {"key": "situation", "heading": "The situation", "required": True,
         "headingRequired": True, "minWords": 120},
        {"key": "distinction", "heading": "What becomes visible", "required": True,
         "headingRequired": True, "minWords": 150},
        {"key": "consequence", "heading": "What follows", "required": False,
         "headingRequired": True},
    ],
    "forbiddenPhrases": ["the journey of a lifetime"],
}


def _save(env, **overrides) -> Dict[str, Any]:
    body = {**TEMPLATE, **overrides}
    return env["bt"].save(body, "admin", q.CATEGORIES, q.ARTICLE_CLASSES)


PROSE = [
    "A person gives their word and then does not honour it. The ordinary response reaches "
    "for morality, and that reading arrives instantly while explaining nothing about what "
    "actually broke in the situation itself.",
    "Something was counting on the word. A schedule, a decision someone else made on the "
    "strength of it, a resource committed. The word was load-bearing and the structure "
    "moved when it came out of the arrangement.",
    "Workability asks a different question from whether the person is good. It asks what "
    "became possible and what stopped being possible for everybody who had planned around "
    "the commitment in the first place.",
]


def sample_pdf(header: str = "THE GIVEN WORD") -> bytes:
    lines = [header, ""]
    for paragraph in PROSE:
        lines += wrap(paragraph) + [""]
    return make_pdf([lines, lines])


def _source(env, batch_id: str = "", category: str = "Conversations",
            header: str = "THE GIVEN WORD") -> str:
    payload = sample_pdf(header)
    body: Dict[str, Any] = {"category": category, "sources": [_pdf_entry(payload)]}
    if batch_id:
        body["batchId"] = batch_id
    result = env["bs"].register(body, "admin", q.CATEGORIES)
    source_id = result["sources"][0]["sourceId"]
    env["s3"].objects[env["table"].items[source_id]["s3Key"]] = payload
    env["bs"].confirm({"sourceIds": [source_id]}, "admin")
    env["bs"].run_worker({})
    return source_id


# ── Identity and versioning ─────────────────────────────────────────────────────

def test_a_template_is_created_at_version_one(env):
    saved = _save(env)
    assert saved["version"] == 1
    assert saved["created"] is True
    assert saved["templateId"] == "blogtpl_conversations-reflection"
    assert saved["recordId"] == "blogtpl_conversations-reflection_v1"


def test_the_family_id_is_idempotent(env):
    bt = env["bt"]
    assert bt.family_id("Conversations reflection") == "blogtpl_conversations-reflection"
    assert bt.family_id("blogtpl_conversations-reflection") == \
        "blogtpl_conversations-reflection"
    assert bt.family_id("blogtpl_conversations-reflection_v7") == \
        "blogtpl_conversations-reflection"


def test_an_unlocked_version_is_edited_in_place(env):
    """Drafting a template is iterative; a new version per typo makes the number meaningless."""
    first = _save(env)
    second = _save(env, maxWords=900)
    assert second["version"] == 1
    assert second["created"] is False
    assert second["maxWords"] == 900
    assert len(env["bt"].history(first["templateId"])) == 1


def test_a_published_version_forks_instead_of_mutating(env):
    """THE test. A certification must keep pointing at what was actually certified."""
    first = _save(env)
    source_id = _source(env)
    env["bt"].assign(source_id, first["templateId"], first["version"], "admin")
    env["bs"].update_pipeline(source_id, publishStatus="PUBLISHED")
    assert env["bt"].locked(first["templateId"], first["version"]) is True

    second = _save(env, maxWords=1200)
    assert second["version"] == 2
    assert second["created"] is True
    assert "certified against" in second["reason"]
    # v1 is exactly as the published article was written to.
    held = env["bt"].resolve(first["templateId"], 1)
    assert held["maxWords"] == 800


def test_a_draft_article_does_not_lock_a_version(env):
    """Only PUBLISHED counts. An assigned-but-unpublished article has certified nothing."""
    first = _save(env)
    source_id = _source(env)
    env["bt"].assign(source_id, first["templateId"], first["version"], "admin")
    assert env["bt"].locked(first["templateId"], first["version"]) is False
    assert _save(env, minWords=400)["version"] == 1


def test_locking_is_derived_from_records_not_a_flag(env):
    first = _save(env)
    source_id = _source(env)
    env["bt"].assign(source_id, first["templateId"], first["version"], "admin")
    env["bs"].update_pipeline(source_id, publishStatus="VERIFIED")
    assert env["bt"].published_against(first["templateId"], 1) == [source_id]
    stored = env["table"].items[first["recordId"]]
    for forbidden in ("useCount", "publishedCount", "locked", "inUse"):
        assert forbidden not in stored, forbidden


def test_history_is_newest_first(env):
    first = _save(env)
    source_id = _source(env)
    env["bt"].assign(source_id, first["templateId"], 1, "admin")
    env["bs"].update_pipeline(source_id, publishStatus="PUBLISHED")
    _save(env, maxWords=900)
    assert [row["version"] for row in env["bt"].history(first["templateId"])] == [2, 1]


def test_an_explicit_version_can_be_targeted(env):
    first = _save(env)
    source_id = _source(env)
    env["bt"].assign(source_id, first["templateId"], 1, "admin")
    env["bs"].update_pipeline(source_id, publishStatus="PUBLISHED")
    _save(env, maxWords=900)  # -> v2
    with pytest.raises(LookupError, match="no version 5"):
        _save(env, version=5)


def test_a_version_is_deprecated_never_deleted(env):
    """A published article points at it; removing it breaks the certification from the
    other direction."""
    first = _save(env)
    result = env["bt"].deprecate(first["recordId"], "admin")
    assert result["deprecatedAt"]
    assert env["bt"].get(first["recordId"]) is not None
    assert env["bt"].list_templates() == []
    assert len(env["bt"].list_templates(include_deprecated=True)) == 1


def test_listing_returns_the_newest_version_of_each_family(env):
    first = _save(env)
    source_id = _source(env)
    env["bt"].assign(source_id, first["templateId"], 1, "admin")
    env["bs"].update_pipeline(source_id, publishStatus="PUBLISHED")
    _save(env, maxWords=900)
    _save(env, name="Gastronomy note", category="Gastronomy")
    listed = env["bt"].list_templates()
    assert {row["name"]: row["version"] for row in listed} == {
        "Conversations reflection": 2, "Gastronomy note": 1}


def test_every_view_field_is_present(env):
    saved = _save(env)
    assert set(env["bt"].template_fields()) <= set(saved)


# ── Validation ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("overrides,message", [
    ({"name": ""}, "name is required"),
    ({"name": "x" * 200}, "at most"),
    ({"category": "Insights"}, "category must be"),
    ({"articleClass": "NEW"}, "articleClass"),
    ({"minWords": 900, "maxWords": 500}, "minWords exceeds"),
    ({"minWords": -1}, "negative"),
    ({"sections": []}, "non-empty"),
    ({"sections": [{"key": "A B", "heading": "x"}]}, "lowercase identifier"),
    ({"sections": [{"key": "a", "heading": "x"}, {"key": "a", "heading": "y"}]}, "twice"),
    ({"sections": [{"key": "a", "heading": "x", "minWords": 9, "maxWords": 2}]},
     "exceeds maxWords"),
])
def test_creation_validates(env, overrides, message):
    with pytest.raises(ValueError, match=message):
        _save(env, **overrides)


def test_sections_that_cannot_fit_the_band_are_refused(env):
    """Otherwise every article following the template fails, and reads as an article defect.

    `minWords=0` so the template's own band is internally consistent and the ONLY conflict is
    between the sections' 270-word floor and the 200-word ceiling.
    """
    with pytest.raises(ValueError, match="exceeds the template's own maximum"):
        _save(env, minWords=0, maxWords=200)


def test_section_order_comes_from_the_list_not_a_field(env):
    """Two sections claiming order 3 is a conflict with no correct resolution."""
    saved = _save(env)
    assert [section["order"] for section in saved["sections"]] == [0, 1, 2]
    assert [section["key"] for section in saved["sections"]] == [
        "situation", "distinction", "consequence"]


def test_a_template_may_apply_to_any_category(env):
    saved = _save(env, name="House rules", category=env["bt"].ANY_CATEGORY)
    assert saved["category"] == "ANY"


# ── Assignment ──────────────────────────────────────────────────────────────────

def test_assigning_records_the_resolved_version_not_the_family(env):
    """An article recording only a family id would be re-checked against whatever the
    template later became - the exact substitution this module prevents."""
    first = _save(env)
    source_id = _source(env)
    result = env["bt"].assign(source_id, first["templateId"], 0, "admin")
    assert result["templateVersion"] == 1
    pipeline = env["bs"].get_source(source_id)["pipeline"]
    assert pipeline["templateId"] == first["templateId"]
    assert pipeline["templateVersion"] == 1


def test_a_category_mismatch_is_refused(env):
    _save(env)
    source_id = _source(env, category="Gastronomy")
    with pytest.raises(ValueError, match="is for Conversations"):
        env["bt"].assign(source_id, "blogtpl_conversations-reflection", 0, "admin")


def test_an_any_category_template_fits_both(env):
    saved = _save(env, name="House rules", category=env["bt"].ANY_CATEGORY)
    for category in q.CATEGORIES:
        source_id = _source(env, category=category)
        env["table"].items[source_id]["sourceSha256"] = category  # distinct rows
        assert env["bt"].assign(source_id, saved["templateId"], 0, "admin")[
            "templateVersion"] == 1


def test_a_deprecated_latest_must_be_named_explicitly(env):
    saved = _save(env)
    env["bt"].deprecate(saved["recordId"], "admin")
    source_id = _source(env)
    with pytest.raises(ValueError, match="deprecated"):
        env["bt"].assign(source_id, saved["templateId"], 0, "admin")
    assert env["bt"].assign(source_id, saved["templateId"], 1, "admin")["templateVersion"] == 1


def test_an_unknown_template_or_source_is_refused(env):
    _save(env)
    with pytest.raises(LookupError, match="Unknown sourceId"):
        env["bt"].assign("blogsrc_nope", "blogtpl_conversations-reflection", 0, "admin")
    source_id = _source(env)
    with pytest.raises(LookupError, match="Unknown template"):
        env["bt"].assign(source_id, "blogtpl_nope", 0, "admin")


def test_a_source_with_no_template_resolves_to_none(env):
    """Assessed against NO template rather than against a guess: falling back to "the newest
    Conversations template" would certify an article against a document nobody saw."""
    _save(env)
    source_id = _source(env)
    assert env["bt"].for_source(env["bs"].get_source(source_id)) is None


def test_a_batch_default_flows_onto_its_sources(env):
    saved = _save(env)
    batch_id = env["bb"].create({
        "name": "Wave 1", "defaultCategory": "Conversations",
        "defaultTemplateId": saved["templateId"], "defaultTemplateVersion": "1",
    }, "admin", q.CATEGORIES, q.ARTICLE_CLASSES)["batchId"]
    source_id = _source(env, batch_id)
    resolved = env["bt"].for_source(env["bs"].get_source(source_id))
    assert resolved["templateId"] == saved["templateId"]
    assert resolved["version"] == 1


def test_an_explicit_assignment_beats_the_batch_default(env):
    first = _save(env)
    source_id_holder = _source(env)
    env["bt"].assign(source_id_holder, first["templateId"], 1, "admin")
    env["bs"].update_pipeline(source_id_holder, publishStatus="PUBLISHED")
    second = _save(env, maxWords=1100)
    assert second["version"] == 2

    batch_id = env["bb"].create({
        "name": "Wave 2", "defaultCategory": "Conversations",
        "defaultTemplateId": first["templateId"], "defaultTemplateVersion": "1",
    }, "admin", q.CATEGORIES, q.ARTICLE_CLASSES)["batchId"]
    source_id = _source(env, batch_id)
    env["table"].items[source_id]["sourceSha256"] = "other"
    env["bt"].assign(source_id, first["templateId"], 2, "admin")
    assert env["bt"].for_source(env["bs"].get_source(source_id))["version"] == 2


# ── Compliance ──────────────────────────────────────────────────────────────────

def _article(body: str) -> Dict[str, Any]:
    return {"title": "The given word", "slug": "the-given-word",
            "category": "Conversations", "contentMarkdown": body}


def test_a_compliant_article_reports_no_findings(env):
    template = _save(env, minWords=10, maxWords=4000,
                     sections=[{"key": "a", "heading": "The situation", "required": True,
                                "headingRequired": True},
                               {"key": "b", "heading": "What follows", "required": True,
                                "headingRequired": True}])
    body = ("## The situation\n\n" + "word " * 30 + "\n\n"
            "## What follows\n\n" + "word " * 30)
    result = env["bt"].compliance(_article(body), template)
    assert result["compliant"] is True
    assert result["findings"] == []
    assert result["templateVersion"] == 1


def test_a_missing_required_section_is_reported(env):
    template = _save(env, minWords=0, maxWords=4000)
    result = env["bt"].compliance(
        _article("## The situation\n\nWords here."), template)
    assert any("What becomes visible" in item for item in result["findings"])
    assert result["compliant"] is False


def test_sections_out_of_order_are_reported(env):
    template = _save(env, minWords=0, maxWords=4000)
    body = ("## What becomes visible\n\nWords.\n\n## The situation\n\nWords.\n\n"
            "## What follows\n\nWords.")
    findings = env["bt"].compliance(_article(body), template)["findings"]
    assert any("TEMPLATE_SECTION_ORDER" in item for item in findings)


def test_a_missing_optional_section_does_not_break_the_order_check(env):
    """Comparing index positions would make every section after an absent optional one read
    as out of order, which is a false report on a correct article."""
    template = _save(env, minWords=0, maxWords=4000)
    body = "## The situation\n\nWords.\n\n## What becomes visible\n\nWords."
    findings = env["bt"].compliance(_article(body), template)["findings"]
    assert not any("TEMPLATE_SECTION_ORDER" in item for item in findings)


def test_the_word_band_is_reported_both_ways(env):
    template = _save(env, minWords=500, maxWords=800,
                     sections=[{"key": "a", "heading": "The situation", "required": True}])
    thin = env["bt"].compliance(_article("word " * 50), template)["findings"]
    assert any("below" in item for item in thin)
    fat = env["bt"].compliance(_article("word " * 1000), template)["findings"]
    assert any("exceeds" in item for item in fat)


def test_a_template_forbidden_phrase_is_reported(env):
    template = _save(env, minWords=0, maxWords=4000)
    findings = env["bt"].compliance(
        _article("It was the journey of a lifetime, and more."), template)["findings"]
    assert any("journey of a lifetime" in item for item in findings)


def test_a_required_list_is_reported_when_absent(env):
    template = _save(env, minWords=0, maxWords=4000, requireList=True)
    findings = env["bt"].compliance(_article("Just prose here."), template)["findings"]
    assert any("requires at least one list" in item for item in findings)


def test_no_template_means_no_template_findings(env):
    result = env["bt"].compliance(_article("Anything at all."), {})
    assert result["checked"] is False
    assert result["compliant"] is False
    assert result["findings"] == []


# ── The boundary ────────────────────────────────────────────────────────────────

def test_a_template_can_only_hold_an_article_back(env):
    """A template that could RELEASE an article would be a route to READY_TO_PUBLISH that
    bypasses the section 29 human gates."""
    template = _save(env, minWords=0, maxWords=99999,
                     sections=[{"key": "a", "heading": "The situation", "required": False}])
    article = _article("## The situation\n\n" + "word " * 600)
    without = q.assess(article)
    with_template = q.assess(
        article, extra_findings=env["bt"].check_article(article, template, q))
    assert without["readyToPublish"] is False
    assert with_template["readyToPublish"] is False
    # Adding a template never shortens the list of reasons it cannot publish.
    assert len(with_template["blocking"]) >= len(without["blocking"])
    assert set(without["humanGatesOutstanding"]) == set(with_template["humanGatesOutstanding"])


def test_template_findings_are_review_not_block(env):
    """House style is a rewrite instruction, not a declaration that the article is invalid."""
    template = _save(env, minWords=0, maxWords=4000)
    findings = env["bt"].check_article(
        _article("It was the journey of a lifetime."), template, q)
    assert findings
    assert all(finding.severity == "REVIEW" for finding in findings)
    assert all(finding.routes_to == "EDITORIAL_REWRITE" for finding in findings)


def test_the_template_is_not_a_model_writable_field(env):
    import blog_draft as bd
    for forbidden in ("templateId", "templateVersion", "template"):
        assert forbidden not in bd.WRITABLE_FIELDS, forbidden


def test_every_assessment_site_folds_the_template_in(env):
    """A rule added to a template must apply everywhere or nowhere, not on whichever call
    site somebody remembered to change. `blog_gate.assess_draft` is that one place."""
    source = ROOT / "amplify" / "functions" / "operations" / "seo-tools"
    for name in ("blog_sources.py", "blog_draft.py", "blog_analysis.py", "blog_qa.py"):
        text = (source / name).read_text(encoding="utf-8")
        assert "q.assess(" not in text, (
            f"{name} assesses a draft directly; route it through blog_gate.assess_draft "
            f"so the template and the gate sign-off both apply")


def test_assess_draft_reports_the_template_it_used(env):
    import blog_gate
    saved = _save(env, minWords=0, maxWords=4000)
    source_id = _source(env)
    env["bt"].assign(source_id, saved["templateId"], 1, "admin")
    record = env["bs"].get_source(source_id)
    result = blog_gate.assess_draft(record, record["draftRecord"])
    assert result["template"]["templateVersion"] == 1
    assert result["template"]["checked"] is True


def test_assess_draft_with_no_template_still_assesses(env):
    import blog_gate
    source_id = _source(env)
    record = env["bs"].get_source(source_id)
    result = blog_gate.assess_draft(record, record["draftRecord"])
    assert result["status"] == "SOURCE_REVIEW"
    assert result["template"]["checked"] is False
