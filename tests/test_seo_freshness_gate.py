"""Unchanged content must never pay for a second Bedrock call — and must never be mutated.

THE LEAK. `_run_audit` called `ai.invoke_seo` unconditionally, so auditing a post and then
auditing it again with nothing changed invoked the model twice and produced the same answer at
the same price. The repository already hashes content for exactly this purpose in
`blog_pipeline.content_hash`, `blog_gate.body_sha256` and `blog_sources`; the SEO audit path was
the one place that skipped it.

    audit #1   hash absent or different  ->  model called, hash stored
    audit #2   hash matches              ->  stored audit returned, ZERO model calls
    audit #3   hash matches              ->  same

THE OTHER HALF IS THE RULE THAT MATTERS MOST HERE: the hash is computed FROM source content and
written ONLY onto the derived audit record. No source field is touched, and no `updatedAt` is
stamped - a freshness check that stamped the thing it checked would corrupt sitemap lastmod and
make every check look like an edit.
"""
from __future__ import annotations

import copy
import importlib.util
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEO_DIR = ROOT / "amplify/functions/operations/seo-tools"

for path in (str(SEO_DIR), str(ROOT / "amplify/functions/shared")):
    if path not in sys.path:
        sys.path.insert(0, path)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SEO_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fresh = _load("seo_freshness")

POST = {
    "slug": "a-post",
    "title": "A Post",
    "content": "The body of the post.",
    "excerpt": "An excerpt.",
    "seoTitle": "A Post | WECARE.DIGITAL",
    "metaDescription": "A meta description.",
    "category": "Gastronomy",
    "updatedAt": "2026-09-30T10:00:00Z",
}


def _audit(source_hash: str, created_at: str = "2026-09-30T10:00:00Z", status: str = "pending_review"):
    return {
        "id": f"audit_{created_at}", "recordType": "audit", "slug": "a-post",
        "createdAt": created_at, "status": status, "sourceHash": source_hash,
        "aiModel": "global.anthropic.claude-sonnet-4-6",
    }


# --------------------------------------------------------------------------- #
# the hash itself
# --------------------------------------------------------------------------- #

def test_the_hash_is_stable_regardless_of_key_order():
    # json.dumps(sort_keys=True), so a dict built in a different order is the same content.
    reordered = {key: POST[key] for key in reversed(list(POST))}
    assert fresh.source_hash(POST, "blog") == fresh.source_hash(reordered, "blog")


def test_the_hash_is_stable_across_repeated_calls():
    assert fresh.source_hash(POST, "blog") == fresh.source_hash(POST, "blog")


@pytest.mark.parametrize("field", ["title", "content", "excerpt", "seoTitle",
                                   "metaDescription", "category"])
def test_changing_any_audited_field_changes_the_hash(field):
    edited = {**POST, field: str(POST[field]) + " changed"}
    assert fresh.source_hash(edited, "blog") != fresh.source_hash(POST, "blog")


def test_updatedAt_alone_does_NOT_change_the_hash():
    """A CMS rewrites updatedAt for a tag change, a republish or a migration, none of which
    change a word the model would read. Trusting the timestamp would pay for a model call every
    time the CMS touched a record."""
    assert fresh.source_hash({**POST, "updatedAt": "2027-01-01T00:00:00Z"}, "blog") \
        == fresh.source_hash(POST, "blog")


def test_page_type_is_part_of_the_hash():
    # A page audit and a blog audit read different things, so the same title must not collide.
    assert fresh.source_hash(POST, "blog") != fresh.source_hash(POST, "page")


def test_a_decimal_from_dynamodb_does_not_raise_and_compares_by_value():
    from decimal import Decimal
    assert fresh.source_hash({**POST, "title": Decimal("1")}, "blog") \
        == fresh.source_hash({**POST, "title": "1"}, "blog")


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #

def test_matching_hash_returns_the_stored_audit_so_no_model_is_called():
    current = fresh.source_hash(POST, "blog")
    _, reusable = fresh.decide(POST, "blog", [_audit(current)])
    assert reusable is not None


def test_edited_content_runs_the_model_again():
    stored = fresh.source_hash(POST, "blog")
    edited = {**POST, "content": "A different body."}
    _, reusable = fresh.decide(edited, "blog", [_audit(stored)])
    assert reusable is None


def test_an_audit_with_NO_stored_hash_never_matches():
    """Records written before this gate existed carry no sourceHash. Treating absent as equal
    would suppress the first audit of every one of them, turning a cost fix into a silent
    feature removal."""
    legacy = _audit("")
    del legacy["sourceHash"]
    _, reusable = fresh.decide(POST, "blog", [legacy, _audit("")])
    assert reusable is None


def test_force_re_runs_even_when_the_hash_matches():
    """The hash covers the CONTENT, not the prompt. When ai.py's system prompt or model chain
    changes, identical content should be re-auditable without editing the post - which is the
    source mutation this architecture forbids."""
    current = fresh.source_hash(POST, "blog")
    _, reusable = fresh.decide(POST, "blog", [_audit(current)], force=True)
    assert reusable is None


def test_the_newest_matching_audit_is_the_one_reused():
    current = fresh.source_hash(POST, "blog")
    older = _audit(current, "2026-01-01T00:00:00Z")
    newer = _audit(current, "2026-09-30T00:00:00Z")
    for order in ([older, newer], [newer, older]):
        _, reusable = fresh.decide(POST, "blog", order)
        assert reusable["createdAt"] == "2026-09-30T00:00:00Z"


def test_a_pending_review_audit_still_satisfies_the_gate():
    """Status is deliberately not filtered here. A pending_review audit for identical content is
    still the answer to "has this been audited"; re-running would add another pending_review
    beside it. Whether that content may be PUBLISHED is faq.py's decision, and it does filter."""
    current = fresh.source_hash(POST, "blog")
    _, reusable = fresh.decide(POST, "blog", [_audit(current, status="pending_review")])
    assert reusable is not None


def test_non_audit_records_are_ignored():
    current = fresh.source_hash(POST, "blog")
    log = {**_audit(current), "recordType": "log"}
    _, reusable = fresh.decide(POST, "blog", [log])
    assert reusable is None


def test_a_skip_reports_zero_tokens_and_zero_cost():
    # Stated explicitly rather than omitted, so a reader comparing two responses can see that
    # one of them did not call a model.
    log = fresh.skip_log(_audit("abc"), "blog")
    assert log["skipped"] is True
    assert log["inputTokens"] == 0 and log["outputTokens"] == 0 and log["costEstimate"] == 0


# --------------------------------------------------------------------------- #
# THE RULE: source content is never modified
# --------------------------------------------------------------------------- #

def test_hashing_does_not_mutate_the_source_record():
    before = copy.deepcopy(POST)
    fresh.source_hash(POST, "blog")
    assert POST == before, "source_hash mutated the record it read"


def test_the_whole_decision_does_not_mutate_the_source_record():
    before = copy.deepcopy(POST)
    records = [_audit(fresh.source_hash(POST, "blog"))]
    fresh.decide(POST, "blog", records)
    fresh.decide(POST, "blog", records, force=True)
    assert POST == before, "decide() mutated the source record"


def test_no_timestamp_field_is_written_by_the_freshness_module():
    """SEO processing must never stamp updatedAt/publishedAt/dateModified on source content: the
    sitemap reads those, so a freshness check that stamped what it checked would make every check
    look like an edit. Asserted against the module source, because the absence is the guarantee.
    """
    source = (SEO_DIR / "seo_freshness.py").read_text(encoding="utf-8")
    # DOCSTRINGS STRIPPED FIRST, and this test failed until they were. The module documents at
    # length that it does NOT stamp updatedAt, so a bare substring search found its own
    # explanation and reported the guarantee as the violation - a search cannot tell a citation
    # from a write. Same distinction test_public_surface_role_permissions.py records for
    # `-f action=apply`, and the same mistake this file's own author made twice in one morning.
    code = re.sub(r'"""[\s\S]*?"""', "", source)
    code = "\n".join(line.split("#", 1)[0] for line in code.splitlines())
    for banned in ("updatedAt", "publishedAt", "dateModified", "now_iso", "put_item", "update_item"):
        assert banned not in code, f"seo_freshness writes or stamps {banned}"


def test_the_handler_gate_is_wired_before_the_model_call():
    """The skip has to come BEFORE ai.invoke_seo or it saves nothing."""
    handler = (SEO_DIR / "handler.py").read_text(encoding="utf-8")
    body = handler[handler.index("def _run_audit("):]
    body = body[:body.index("\ndef _blog_audit")]
    # THE ASSIGNMENT, not the bare name. _run_audit's docstring explains that it "used to call
    # ai.invoke_seo unconditionally", so searching for the bare name found the prose at offset
    # 270 and the real gate at 1789, and reported a correctly wired gate as backwards.
    gate = body.index("seo_freshness.decide")
    call = body.index("generated = ai.invoke_seo(")
    assert gate < call, "the freshness gate runs after the model call, so it saves nothing"
    assert "'sourceHash': content_hash" in body, "the hash is not stored, so it can never match"
    # A history read failure must degrade to "run the audit", not to an error.
    assert "history = []" in body
