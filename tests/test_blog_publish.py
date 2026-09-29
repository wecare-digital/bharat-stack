"""The publish queue, and the one failure this domain cannot recover from.

THE FOUR TESTS THAT CARRY THIS FILE.

`test_releasing_twice_resolves_to_the_same_job`. Publishing the same article twice cannot be
undone: a duplicate post gets indexed, linked and cited, and deleting it afterwards leaves a dead
URL where a real one was. A second job is how that happens.

`test_two_concurrent_publishers_cannot_both_write`. The conditional QUEUED -> PUBLISHING claim.
Two operators pressing Publish at the same moment would otherwise both reach the Wix call.

`test_an_edit_after_release_blocks_the_publish`. Release time and publish time are different
moments, and the queue is exactly where the gap lives.

`test_nothing_in_the_pipeline_can_release`. Section 38: processing completion must never
automatically mean publishing. Enforced by grepping the modules, because that is the kind of
convenience somebody adds later.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify" / "functions" / "operations" / "seo-tools"))
sys.path.insert(0, str(ROOT / "amplify" / "functions" / "shared"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import blog_quality_v2 as q  # noqa: E402
from blog_pdf_fixture import make_pdf, wrap  # noqa: E402
from test_blog_sources import FakeLambda, FakeS3, FakeTable, _pdf_entry  # noqa: E402
from test_blog_qa import GOOD_BODY, PROSE, DISTINCTION, STATEMENT  # noqa: E402


class FakeWix:
    """The Wix surface `blog_publish` touches, plus a switch for the kill switch."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.disabled = False
        self.reject = False
        self.raise_on_write = False

    def request(self, method, path, body=None):
        if self.disabled:
            #: EXACTLY what `wix._load_api_key` raises through `wix_guard.refuse_if_disabled` -
            #: a RuntimeError, not a PermissionError. The first version of this fake invented a
            #: PermissionError, `blog_publish` caught that type, and the whole kill-switch
            #: classification passed here while recording FAILED in production. A fake that
            #: raises a different exception than the real thing tests nothing.
            raise RuntimeError(
                "Wix credentials are disabled by WIX_CREDENTIALS_DISABLED (seo-tools "
                "authenticated Wix client). This is deliberate; clear that variable.")
        self.calls.append({"method": method, "path": path, "body": body})
        if path.endswith("/members/v1/members/query"):
            return {"members": [{"id": "member-1",
                                 "profile": {"nickname": "Anew by WECARE.DIGITAL"}}]}
        if path.endswith("/blog/v3/categories/query"):
            return {"categories": [{"id": "cat-1", "label": "Conversations"},
                                   {"id": "cat-2", "label": "Gastronomy"}]}
        if path.endswith("/blog/v3/bulk/draft-posts/create"):
            if self.raise_on_write:
                raise RuntimeError("wix 503")
            if self.reject:
                return {"results": [{"itemMetadata": {"success": False,
                                                      "error": "slug already exists"}}]}
            posted = (body or {}).get("draftPosts", [{}])[0]
            return {"results": [{
                "itemMetadata": {"success": True, "id": "post-1"},
                "item": {"draftPost": {"id": "post-1",
                                       "seoSlug": posted.get("seoSlug", "")}},
            }]}
        return {}


@pytest.fixture()
def env(monkeypatch):
    import blog_analysis as ba
    import blog_batches as bb
    import blog_gate as bg
    import blog_publish as bp
    import blog_qa as bq
    import blog_sources as bs
    import storage
    import wix

    table = FakeTable()
    s3 = FakeS3()
    lam = FakeLambda()
    fake_wix = FakeWix()
    monkeypatch.setattr(storage, "table", lambda: table)
    monkeypatch.setattr(bs, "s3_client", lambda: s3)
    monkeypatch.setattr(bs, "lambda_client", lambda: lam)
    monkeypatch.setattr(bs, "BUCKET", "wecare-digital-get")
    monkeypatch.setattr(wix, "request", fake_wix.request)
    monkeypatch.setenv("WIX_BLOG_AUTHOR_NAME", "Anew by WECARE.DIGITAL")
    bg.reset_corpus_cache()
    index = q.CorpusIndex()
    index.add({"slug": "an-unrelated-article", "title": "Something else entirely",
               "category": "Conversations",
               "contentMarkdown": "Quite different prose about an unrelated subject at "
                                  "sufficient length to produce a comparable sketch."},
              origin="test-corpus")
    monkeypatch.setattr(bg, "_corpus", index)
    monkeypatch.setattr(bg, "_corpus_state", {"loaded": 1, "present": True, "path": "test",
                                              "packaged": True, "builtAt": "", "note": ""})
    yield {"table": table, "s3": s3, "wix": fake_wix, "ba": ba, "bb": bb, "bg": bg,
           "bp": bp, "bq": bq, "bs": bs, "storage": storage}
    bg.reset_corpus_cache()


def sample_pdf(header: str = "THE GIVEN WORD") -> bytes:
    lines = [header, ""]
    for paragraph in PROSE:
        lines += wrap(paragraph) + [""]
    return make_pdf([lines, lines])


def _signed(env, batch_id: str = "", header: str = "THE GIVEN WORD") -> str:
    """A source all the way through to a valid gate sign-off."""
    payload = sample_pdf(header)
    body: Dict[str, Any] = {"category": "Conversations", "sources": [_pdf_entry(payload)]}
    if batch_id:
        body["batchId"] = batch_id
    result = env["bs"].register(body, "admin", q.CATEGORIES)
    source_id = result["sources"][0]["sourceId"]
    env["s3"].objects[env["table"].items[source_id]["s3Key"]] = payload
    env["bs"].confirm({"sourceIds": [source_id]}, "admin")
    env["bs"].run_worker({})

    analysis_id = env["ba"].analyse(source_id, "admin")["analysisId"]
    env["ba"].record_review({"analysisId": analysis_id, "sourceReviewedFully": "YES",
                             "centralDistinctionCandidate": DISTINCTION,
                             "originalSourceDate": "1987"}, "editor")
    record = env["bs"].get_source(source_id)
    draft = dict(record["draftRecord"])
    slug = q.slugify(f"the given word {header.lower()}")
    draft.update({
        "contentMarkdown": GOOD_BODY,
        "title": f"The given word {header.lower()}",
        "slug": slug,
        "canonical": q.expected_canonical(slug),
        "seoTitle": f"The given word {header.lower()} | WECARE.DIGITAL",
        "metaDescription": ("What breaks when a commitment fails, read as a question about "
                            "workability rather than about character or good intent."),
        "tags": ["integrity"],
        "articleType": "REFLECTION",
        "centralDistinction": DISTINCTION,
        "distinctPurpose": ("It separates repair as work from repair as apology, which no "
                            "other article on the site takes as its subject."),
        "originalSourceDate": "1987",
    })
    env["table"].items[source_id]["draftRecord"] = env["storage"]._clean(draft)

    qa = env["bq"].run(source_id, "qa")
    import blog_qa
    env["bq"].sign_off({
        "qaRunId": qa["qaRunId"],
        "gates": {name: "PASS" for name in q.HUMAN_GATES},
        "declarations": {name: expected for name, expected in blog_qa.DECLARATIONS},
        "statement": STATEMENT}, "editor")
    return source_id


# ── Release records a decision and nothing more ─────────────────────────────────

def test_releasing_queues_without_publishing(env):
    source_id = _signed(env)
    env["wix"].calls.clear()
    job = env["bp"].release(source_id, "operator")
    assert job["status"] == env["bp"].QUEUED
    assert job["created"] is True
    assert job["postId"] == ""
    assert env["wix"].calls == [], "release touched Wix"
    assert env["bs"].get_source(source_id)["pipeline"]["publishStatus"] == "QUEUED"


def test_a_release_records_what_it_rests_on(env):
    """source -> reading -> QA -> signature -> release, complete in the records."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    signoff = env["bq"].current_signoff(source_id)
    assert job["signoffId"] == signoff["id"]
    assert job["qaRunId"] == signoff["qaRunId"]
    assert job["bodySha256"] == signoff["bodySha256"]
    assert job["releasedBy"] == "operator"
    assert job["articleSlug"]


def test_releasing_twice_resolves_to_the_same_job(env):
    """THE test. A second job is how the same article gets posted twice."""
    source_id = _signed(env)
    first = env["bp"].release(source_id, "operator")
    second = env["bp"].release(source_id, "operator")
    assert second["jobId"] == first["jobId"]
    assert second["created"] is False
    assert "already has a QUEUED job" in second["note"]
    assert len(env["bp"].jobs_for(source_id)) == 1


def test_releasing_after_publishing_is_still_a_no_op(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["bp"].publish(job["jobId"], "operator")
    again = env["bp"].release(source_id, "operator")
    assert again["created"] is False
    assert again["status"] == env["bp"].PUBLISHED
    assert len(env["bp"].jobs_for(source_id)) == 1


def test_a_release_is_refused_without_a_signoff(env):
    payload = sample_pdf("UNSIGNED")
    result = env["bs"].register(
        {"category": "Conversations", "sources": [_pdf_entry(payload)]},
        "admin", q.CATEGORIES)
    source_id = result["sources"][0]["sourceId"]
    env["s3"].objects[env["table"].items[source_id]["s3Key"]] = payload
    env["bs"].confirm({"sourceIds": [source_id]}, "admin")
    env["bs"].run_worker({})
    with pytest.raises(ValueError, match="cannot be released"):
        env["bp"].release(source_id, "operator")
    assert env["bp"].jobs_for(source_id) == []


def test_a_release_is_refused_after_the_signoff_is_revoked(env):
    source_id = _signed(env)
    signoff = env["bq"].current_signoff(source_id)
    env["bq"].revoke(signoff["id"], "the second quotation needs re-checking", "editor")
    with pytest.raises(ValueError, match="no gate sign-off"):
        env["bp"].release(source_id, "operator")


def test_an_unknown_source_is_refused(env):
    with pytest.raises(LookupError, match="Unknown sourceId"):
        env["bp"].release("blogsrc_nope", "operator")


# ── Withdrawal ──────────────────────────────────────────────────────────────────

def test_a_queued_job_can_be_withdrawn(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    result = env["bp"].unrelease(job["jobId"], "holding this wave for a second read",
                                "operator")
    assert result["withdrawn"] is True
    assert env["bs"].get_source(source_id)["pipeline"]["publishStatus"] == ""
    # And it can be released again afterwards.
    assert env["bp"].release(source_id, "operator")["created"] is True


def test_a_published_job_cannot_be_withdrawn(env):
    """A live post comes down through Wix, which is outside this module's authority.
    Pretending otherwise would be a lie told to an operator during an incident."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["bp"].publish(job["jobId"], "operator")
    with pytest.raises(ValueError, match="only a QUEUED job"):
        env["bp"].unrelease(job["jobId"], "changed our mind about this one", "operator")


def test_a_withdrawal_needs_a_reason(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    with pytest.raises(ValueError, match="reason"):
        env["bp"].unrelease(job["jobId"], "no", "operator")


# ── Publish ─────────────────────────────────────────────────────────────────────

def test_publishing_writes_once_and_records_the_post(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    result = env["bp"].publish(job["jobId"], "operator")
    assert result["published"] is True
    assert result["postId"] == "post-1"
    assert result["postUrl"].startswith("https://wecare.digital/post/")
    writes = [call for call in env["wix"].calls if "bulk/draft-posts/create" in call["path"]]
    assert len(writes) == 1
    assert writes[0]["body"]["publish"] is True
    assert len(writes[0]["body"]["draftPosts"]) == 1


def test_the_post_body_is_compiled_by_the_corpus_compiler(env):
    """A second Ricos compiler would drift from the one behind the 1,165 live posts, and the
    first symptom would be an article that renders differently from every article beside it."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["bp"].publish(job["jobId"], "operator")
    posted = [c for c in env["wix"].calls if "bulk/draft-posts" in c["path"]][0]
    post = posted["body"]["draftPosts"][0]
    import wix_blog_migrate as migrate
    expected = migrate.markdown_to_rich_content(GOOD_BODY)
    assert post["richContent"] == expected
    assert post["memberId"] == "member-1"
    assert post["categoryIds"] == ["cat-1"]
    assert post["seoSlug"] == job["articleSlug"]


def test_no_image_node_reaches_the_post(env):
    """Section 27, and the compiler is the thing that guarantees it."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["bp"].publish(job["jobId"], "operator")
    posted = [c for c in env["wix"].calls if "bulk/draft-posts" in c["path"]][0]
    rich = json.dumps(posted["body"]["draftPosts"][0]["richContent"])
    for forbidden in ("IMAGE", "GALLERY", "VIDEO", "AUDIO", "EMBED"):
        assert forbidden not in rich, forbidden


def test_publishing_updates_the_pipeline_and_writes_the_record(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["bp"].publish(job["jobId"], "operator")
    pipeline = env["bs"].get_source(source_id)["pipeline"]
    assert pipeline["publishStatus"] == env["bp"].PUBLISHED
    assert pipeline["postId"] == "post-1"
    assert pipeline["publishedAt"]
    key = env["bp"].record_key(source_id)
    assert key in env["s3"].objects
    record = json.loads(env["s3"].objects[key].decode())
    assert record["postId"] == "post-1"
    assert record["signoffId"] == job["signoffId"]
    assert record["templateVersion"] == job["templateVersion"]
    assert record["originalSourceDate"] == "1987"


def test_publishing_twice_is_a_no_op_not_a_second_post(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["bp"].publish(job["jobId"], "operator")
    env["wix"].calls.clear()
    again = env["bp"].publish(job["jobId"], "operator")
    assert again["published"] is False
    assert "already published" in again["note"]
    assert env["wix"].calls == []


def test_two_concurrent_publishers_cannot_both_write(env):
    """The conditional QUEUED -> PUBLISHING claim. Two operators pressing Publish at the same
    moment would otherwise both reach the Wix call."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    assert env["bp"]._claim(job["jobId"]) is True
    assert env["bp"]._claim(job["jobId"]) is False
    env["wix"].calls.clear()
    #: The job is now PUBLISHING, so a publish attempt refuses rather than writing.
    with pytest.raises(ValueError, match="only a QUEUED job"):
        env["bp"].publish(job["jobId"], "operator")
    assert env["wix"].calls == []


def test_an_edit_after_release_blocks_the_publish(env):
    """Release time and publish time are different moments, and the queue is the gap."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    draft = dict(env["bs"].get_source(source_id)["draftRecord"])
    draft["contentMarkdown"] += "\n\nOne more paragraph arrives after the release."
    env["table"].items[source_id]["draftRecord"] = env["storage"]._clean(draft)
    env["wix"].calls.clear()
    with pytest.raises(ValueError, match="no longer be published|changed after it was released"):
        env["bp"].publish(job["jobId"], "operator")
    assert env["wix"].calls == []
    assert env["bp"].get(job["jobId"])["status"] == env["bp"].QUEUED


def test_a_revocation_after_release_blocks_the_publish(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    signoff = env["bq"].current_signoff(source_id)
    env["bq"].revoke(signoff["id"], "withdrawn before it went live", "editor")
    env["wix"].calls.clear()
    with pytest.raises(ValueError, match="no longer be published"):
        env["bp"].publish(job["jobId"], "operator")
    assert env["wix"].calls == []


def test_an_unknown_job_is_refused(env):
    with pytest.raises(LookupError, match="Unknown jobId"):
        env["bp"].publish("blogpub_nope", "operator")


# ── The kill switch is a distinct state ─────────────────────────────────────────

def test_the_kill_switch_records_refused_not_failed(env, monkeypatch):
    """"The operator has writes switched off" and "Wix rejected the post" must not look the
    same on a dashboard.

    Flips the REAL flag rather than a fake's exception type. That distinction is the whole point
    of this test: the first version raised an invented PermissionError from the fake, matched it,
    and passed - while production recorded FAILED, because `wix_guard` raises RuntimeError.
    """
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    monkeypatch.setenv("WIX_CREDENTIALS_DISABLED", "true")
    env["wix"].disabled = True
    result = env["bp"].publish(job["jobId"], "operator")
    assert result["published"] is False
    assert result["refused"] is True
    assert "WIX_CREDENTIALS_DISABLED" in result["error"]
    stored = env["bp"].get(job["jobId"])
    assert stored["status"] == env["bp"].REFUSED
    assert env["bs"].get_source(source_id)["pipeline"]["publishStatus"] == "REFUSED"


def test_a_refusal_writes_no_publish_record(env, monkeypatch):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    monkeypatch.setenv("WIX_CREDENTIALS_DISABLED", "true")
    env["wix"].disabled = True
    env["bp"].publish(job["jobId"], "operator")
    assert env["bp"].record_key(source_id) not in env["s3"].objects


def test_a_refusal_is_not_retried_automatically(env, monkeypatch):
    """Retrying past a deliberate operator state would defeat the switch."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    monkeypatch.setenv("WIX_CREDENTIALS_DISABLED", "true")
    env["wix"].disabled = True
    env["bp"].publish(job["jobId"], "operator")
    monkeypatch.delenv("WIX_CREDENTIALS_DISABLED")
    env["wix"].disabled = False
    env["wix"].calls.clear()
    #: Still REFUSED, and a publish attempt refuses because it is no longer QUEUED. An operator
    #: has to release it again deliberately.
    with pytest.raises(ValueError, match="only a QUEUED job"):
        env["bp"].publish(job["jobId"], "operator")
    assert env["wix"].calls == []


def test_the_refusal_is_not_attempted_at_all(env, monkeypatch):
    """Checked before the claim, so the attempt counter means REAL attempts and the log says
    "not tried" rather than "tried and failed"."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    monkeypatch.setenv("WIX_CREDENTIALS_DISABLED", "true")
    env["wix"].calls.clear()
    result = env["bp"].publish(job["jobId"], "operator")
    assert result["refused"] is True
    assert "NOT attempted" in result["note"]
    assert env["wix"].calls == [], "a refused publish reached Wix"
    assert env["bp"].get(job["jobId"])["attempts"] == 0


def test_a_switch_flipped_mid_flight_is_still_a_refusal(env, monkeypatch):
    """Re-checked in the handler rather than matched on the exception, because the switch can be
    flipped between the check and the call - and a state read answers that where a type match
    cannot."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["wix"].disabled = True  # raises the guard's RuntimeError from inside the call

    def flip(*args, **kwargs):
        monkeypatch.setenv("WIX_CREDENTIALS_DISABLED", "true")
        raise RuntimeError("Wix credentials are disabled by WIX_CREDENTIALS_DISABLED")

    monkeypatch.setattr(env["bp"], "_write_to_wix", flip)
    result = env["bp"].publish(job["jobId"], "operator")
    assert result["refused"] is True
    assert env["bp"].get(job["jobId"])["status"] == env["bp"].REFUSED


def test_a_genuine_wix_failure_is_not_reported_as_the_switch(env):
    """Broadening the catch to RuntimeError would have made a real Wix rejection read as
    "writes are off" - the same mistake in the opposite direction."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["wix"].raise_on_write = True
    result = env["bp"].publish(job["jobId"], "operator")
    assert result.get("refused") is None
    assert env["bp"].get(job["jobId"])["status"] == env["bp"].FAILED
    assert "WIX_CREDENTIALS_DISABLED" not in env["bp"].get(job["jobId"])["error"]


def test_a_wix_rejection_records_failed(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["wix"].reject = True
    result = env["bp"].publish(job["jobId"], "operator")
    assert result["published"] is False
    assert result.get("refused") is None
    stored = env["bp"].get(job["jobId"])
    assert stored["status"] == env["bp"].FAILED
    assert "slug already exists" in stored["error"]


def test_a_transport_failure_records_failed_and_does_not_retry(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["wix"].raise_on_write = True
    result = env["bp"].publish(job["jobId"], "operator")
    assert result["published"] is False
    assert env["bp"].get(job["jobId"])["status"] == env["bp"].FAILED
    assert env["bp"].get(job["jobId"])["attempts"] == 1


def test_a_record_write_failure_does_not_report_a_failed_publish(env, monkeypatch):
    """The post is already live. Reporting failure invites a second attempt, which is the one
    wrong answer in this direction."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")

    def exploding(**kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr(env["s3"], "put_object", exploding)
    result = env["bp"].publish(job["jobId"], "operator")
    assert result["published"] is True
    assert env["bp"].get(job["jobId"])["status"] == env["bp"].PUBLISHED


# ── Nothing else may publish ────────────────────────────────────────────────────

def test_nothing_in_the_pipeline_can_release(env):
    """Section 38. Enforced by grepping, because this is the kind of convenience somebody
    adds later - a batch reaching READY calling release "to save a click"."""
    import ast
    source = ROOT / "amplify" / "functions" / "operations" / "seo-tools"
    for name in ("blog_sources.py", "blog_queue.py", "blog_batches.py", "blog_qa.py",
                 "blog_draft.py", "blog_analysis.py", "blog_repetition.py",
                 "blog_templates.py", "blog_gate.py"):
        #: Parsed rather than grepped. A grep for the module name also matches the PROSE in
        #: `blog_qa`'s docstring, which correctly explains that releasing lives elsewhere - and a
        #: test that fails on an accurate comment gets the comment deleted, not the code fixed.
        tree = ast.parse((source / name).read_text(encoding="utf-8"))
        imported = set()
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                called.add(node.value.id)
        assert "blog_publish" not in imported, (
            f"{name} imports blog_publish; releasing must come from an operator route only")
        assert "blog_publish" not in called, f"{name} calls into blog_publish"


def test_the_publish_route_is_not_idempotency_claimed(env):
    """It was, and the first live run caught the claim doing harm.

    The claim keys on the request body, which is just `{jobId}`, so the first attempt records it
    whatever the outcome and a later legitimate retry answers 409. The live run hit exactly that:
    a publish correctly refused because the article had been edited, then the operator restored
    the body, re-signed, pressed Publish again, and got "This Admin action was already submitted"
    with no way forward.

    The conditional QUEUED -> PUBLISHING claim is the real guard and is strictly better, because
    it is tied to the job's STATE rather than to a request shape.
    """
    import ast
    text = (ROOT / "amplify" / "functions" / "operations" / "seo-tools"
            / "handler.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "_claim":
            continue
        literals = [arg.value for arg in node.args if isinstance(arg, ast.Constant)]
        assert "seo.blogpublish.publish" not in literals, (
            "the publish route is idempotency-claimed again; that blocks a legitimate retry "
            "after a refusal, and the conditional state claim already covers double-submit")


def test_a_retry_after_a_refusal_is_not_blocked(env, monkeypatch):
    """The behaviour the claim broke: refuse, fix, re-sign, release, publish."""
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    monkeypatch.setenv("WIX_CREDENTIALS_DISABLED", "true")
    env["wix"].disabled = True
    assert env["bp"].publish(job["jobId"], "operator")["refused"] is True
    monkeypatch.delenv("WIX_CREDENTIALS_DISABLED")
    env["wix"].disabled = False

    #: A REFUSED job is not QUEUED, so it has to be released again - deliberately, because
    #: retrying past a refusal automatically would defeat the switch. That new release must work.
    fresh = env["bp"].release(source_id, "operator")
    assert fresh["created"] is True, "a refused job blocked a fresh release"
    assert fresh["jobId"] != job["jobId"]
    result = env["bp"].publish(fresh["jobId"], "operator")
    assert result["published"] is True
    assert result["postId"] == "post-1"


def test_the_only_wix_mutation_is_in_the_publish_path(env):
    """R7.4 wants the Wix calls the pipeline can make enumerated, so "it cannot post twice" is
    demonstrated rather than asserted."""
    source = ROOT / "amplify" / "functions" / "operations" / "seo-tools"
    mutating = []
    for path in sorted(source.glob("blog_*.py")):
        text = path.read_text(encoding="utf-8")
        if "bulk/draft-posts" in text or "draft-posts/create" in text:
            mutating.append(path.name)
    assert mutating == ["blog_publish.py"]


def test_publishing_is_not_a_model_writable_field(env):
    import blog_draft as bd
    for forbidden in ("publishStatus", "postId", "postUrl", "publishedAt"):
        assert forbidden not in bd.WRITABLE_FIELDS, forbidden


def test_the_batch_worker_cannot_publish(env):
    """A whole batch extracted and signed off still publishes nothing on its own."""
    batch_id = env["bb"].create({"name": "Wave 1", "defaultCategory": "Conversations"},
                                "admin", q.CATEGORIES, q.ARTICLE_CLASSES)["batchId"]
    source_id = _signed(env, batch_id, "ONE")
    env["bs"].run_worker({})
    assert env["bb"].detail(batch_id)["status"] == env["bb"].READY
    assert env["bs"].get_source(source_id)["pipeline"]["publishStatus"] == ""
    assert env["bp"].queue() == []
    assert env["wix"].calls == []


# ── The queue surface ───────────────────────────────────────────────────────────

def test_the_queue_lists_newest_first_and_filters_by_status(env):
    first = _signed(env, header="ONE")
    second = _signed(env, header="TWO")
    job_one = env["bp"].release(first, "operator")
    job_two = env["bp"].release(second, "operator")
    env["bp"].publish(job_one["jobId"], "operator")

    assert len(env["bp"].queue()) == 2
    queued = env["bp"].queue(status="QUEUED")
    assert [row["jobId"] for row in queued] == [job_two["jobId"]]
    published = env["bp"].queue(status="published")
    assert [row["jobId"] for row in published] == [job_one["jobId"]]


def test_the_detail_carries_the_publish_record(env):
    source_id = _signed(env)
    job = env["bp"].release(source_id, "operator")
    env["bp"].publish(job["jobId"], "operator")
    detail = env["bp"].detail(job["jobId"])
    assert detail["record"]["postId"] == "post-1"
    for key in detail:
        assert "url" not in key.lower() or key == "postUrl"


def test_the_batch_publish_state_is_derived_from_the_sources(env):
    batch_id = env["bb"].create({"name": "Wave 1", "defaultCategory": "Conversations"},
                                "admin", q.CATEGORIES, q.ARTICLE_CLASSES)["batchId"]
    first = _signed(env, batch_id, "ONE")
    _signed(env, batch_id, "TWO")
    state = env["bp"].batch_publish_state(batch_id)
    assert state == {"sources": 2, "byStatus": {"UNRELEASED": 2}, "published": 0,
                     "queued": 0, "refused": 0, "failed": 0, "unreleased": 2, "jobs": 0}

    job = env["bp"].release(first, "operator")
    env["bp"].publish(job["jobId"], "operator")
    state = env["bp"].batch_publish_state(batch_id)
    assert state["published"] == 1
    assert state["unreleased"] == 1
    assert state["jobs"] == 1


def test_the_candidate_list_says_why_each_source_cannot_be_released(env):
    """A release page whose only content is the eligible rows leaves an operator with no idea
    why the other forty are missing."""
    batch_id = env["bb"].create({"name": "Wave 1", "defaultCategory": "Conversations"},
                                "admin", q.CATEGORIES, q.ARTICLE_CLASSES)["batchId"]
    ready = _signed(env, batch_id, "READY")
    payload = sample_pdf("NOTREADY")
    result = env["bs"].register(
        {"batchId": batch_id, "category": "Conversations",
         "sources": [_pdf_entry(payload)]}, "admin", q.CATEGORIES)
    unready = result["sources"][0]["sourceId"]
    env["s3"].objects[env["table"].items[unready]["s3Key"]] = payload
    env["bs"].confirm({"sourceIds": [unready]}, "admin")
    env["bs"].run_worker({})

    candidates = {row["sourceId"]: row for row in env["bp"].releasable_in_batch(batch_id)}
    assert candidates[ready]["releasable"] is True
    assert candidates[unready]["releasable"] is False
    assert candidates[unready]["reason"]

    env["bp"].release(ready, "operator")
    candidates = {row["sourceId"]: row for row in env["bp"].releasable_in_batch(batch_id)}
    assert candidates[ready]["releasable"] is False
    assert "already has a QUEUED job" in candidates[ready]["reason"]
    assert candidates[ready]["jobStatus"] == "QUEUED"


def test_a_publish_job_does_not_count_as_a_source(env):
    batch_id = env["bb"].create({"name": "Wave 1", "defaultCategory": "Conversations"},
                                "admin", q.CATEGORIES, q.ARTICLE_CLASSES)["batchId"]
    source_id = _signed(env, batch_id, "ONE")
    env["bp"].release(source_id, "operator")
    assert env["bb"].rollup(batch_id)["sources"] == 1


def test_the_ricos_compiler_is_packaged_for_the_lambda():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "dep_seo_publish", ROOT / "scripts" / "deploy_seo_tools.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(module.package())) as archive:
        names = set(archive.namelist())
    assert "wix_blog_migrate.py" in names
    assert "operations/seo-tools/blog_publish.py" in names
