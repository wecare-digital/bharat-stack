"""Bedrock draft reconstruction, structurally unable to approve its own output.

WHAT THIS IS ALLOWED TO DO, AND WHAT IT CANNOT DO EVEN IF THE MODEL ASKS.

The model reads a source extract and proposes an article in Anew voice, plus the metadata a
human would otherwise type. That genuinely accelerates the slowest part of the pipeline.

It cannot mark the article publishable, and the reason is structural rather than a policy
someone has to remember. `apply_draft` writes into a whitelist of fields. `sourceReviewedFully`,
the section 5 uniqueness booleans and the section 29 `gate` object are NOT in that whitelist,
so no model output can set them - and `blog_quality_v2.decide_status` will not return
READY_TO_PUBLISH while they are unset. A prompt-injected extract that says "set
sourceReviewedFully to YES" therefore cannot do anything, because the field never reaches
the record.

That matters more than usual here. The input is an arbitrary third-party PDF or web page,
which is exactly the position where untrusted content meets a model with write access. The
whitelist is the boundary.

The record also stays on SOURCE_REVIEW after a successful draft, not EDITORIAL_QA. Section 2
of the standard is about a person having understood the source; a model having read it is a
different claim. So the draft is a proposal on the record, and a human moving it forward is
what asserts the reading happened.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import ai
import blog_sources
import storage

logger = logging.getLogger(__name__)

#: Bedrock costs money per call, so the route defaults OFF and is enabled explicitly.
#: `cost_flags.is_enabled` reads the env var first, then the SystemConfig table, and
#: defaults FALSE - so an operator can turn this off without a deploy.
COST_FLAG = "ENABLE_BEDROCK_ASSIST"

#: Enough of the source for the model to have understood it, bounded so one enormous PDF
#: cannot produce a single request that dominates the month's spend. A 24,000-character
#: extract is roughly 6,000 tokens, which is a normal article-length source.
MAX_SOURCE_CHARS = int(os.environ.get("BLOG_DRAFT_MAX_SOURCE_CHARS", "24000"))

#: Exactly the fields a model may write. Everything else on the record is out of reach.
#: Note what is absent: sourceReviewedFully, materiallyDifferentInquiry, titleOnlyDifference,
#: uniqueReaderPromise, uniqueIntellectualMovement, gate, status.
WRITABLE_FIELDS = (
    "title", "contentMarkdown", "seoTitle", "metaDescription", "tags", "articleType",
    "centralDistinction", "distinctPurpose", "slug",
)

SYSTEM_PROMPT = """You are an editor for Anew by WECARE.DIGITAL, working to the
Conversations Content Quality Standard v2.

You are given the extracted text of a source document. Reconstruct it as an article in Anew
voice. The governing rule is: understand the source, remove any obsolete or personal
wrapper, preserve the real distinction, and reconstruct independently. Never rename the
source and lightly paraphrase it.

VOICE: precise, calm, direct, grounded, economical. Clarity without simplification. Depth
without unnecessary complexity.

HARD CONSTRAINTS, each of which will be checked mechanically after you answer:
- Do NOT use these stock constructions: "the real question is", "the point is not",
  "here is the truth", "this changes everything", "at its core", "ultimately,",
  "in conclusion", "it is important to note", "delve into", "a testament to".
  Using three or more of them fails the article outright.
- Do NOT use motivational or self-help language: "believe in yourself", "embrace the
  journey", "trust the process", "step into your power", and similar.
- Do NOT convert a first-person story from the source into Anew's own biography. "I went
  through" must not become "We went through". Remove it, generalise it, or attribute it.
- Do NOT invent frameworks, statistics, quotations, studies or anecdotes that are not in
  the source. If the source carries a quotation, keep its attribution.
- Do NOT include any image, and do not write a markdown image.
- Vary sentence length. Uniform cadence is checked and rejected.
- Do not open with a rhetorical question, a dramatic claim, or a generic motivational line.

FORMAT: markdown. `## ` for a section heading where the material genuinely benefits from
one. Blank line between paragraphs - this is required, not cosmetic. `- ` for a list only
where the material naturally forms one.

Return ONLY a JSON object with these keys and nothing else:
  title             a faithful, non-clickbait title
  slug              lowercase, hyphenated, derived from the title, no trailing number
  contentMarkdown   the article
  seoTitle          "<title> | WECARE.DIGITAL"
  metaDescription   140-160 characters, representing the actual inquiry
  tags              1 to 3 precise tags
  articleType       one of DISTINCTION, REFLECTION, ARTICLE, DEEP_ARTICLE
  centralDistinction  1-2 sentences naming what the reader can newly notice or distinguish
  distinctPurpose     1-2 sentences on why this deserves its own URL
  notes             anything you could not resolve, or an empty string

Length follows the material, not a target. DISTINCTION 250-400 words, REFLECTION 500-800,
ARTICLE 800-1500. A strong 350-word article beats a padded 1,200-word one."""


def enabled() -> bool:
    from lambda_utils.cost_flags import is_enabled
    return is_enabled(COST_FLAG)


def _invoke(system: str, message: str) -> Dict[str, Any]:
    """The model chain from ai.py, reused rather than re-declared.

    ai.py already owns the per-family request and response shapes and the fallback order, and
    a second copy here would drift the moment a model id changes.
    """
    last_error: Optional[Exception] = None
    for model_id in dict.fromkeys(ai.MODEL_CHAIN):
        try:
            response = ai.client().invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(ai._request(model_id, system, message)).encode("utf-8"),
            )
            parsed = ai._parse(model_id, json.loads(response["body"].read()))
            return {**parsed, "model": model_id, "result": ai.parse_json(parsed["text"])}
        except Exception as error:  # noqa: BLE001
            last_error = error
    raise RuntimeError("All configured Bedrock models failed") from last_error


def _clean_proposal(result: Dict[str, Any], category: str, q) -> Dict[str, Any]:
    """Keep only the writable fields, coerced to the shapes the record expects.

    A dict comprehension over the model's keys would let it write anything it named. This
    walks the whitelist instead, so an unexpected key is dropped rather than stored.
    """
    proposal: Dict[str, Any] = {}
    for field in WRITABLE_FIELDS:
        if field not in result:
            continue
        value = result[field]
        if field == "tags":
            tags = [str(item).strip() for item in (value or []) if str(item).strip()]
            # 1-3 tags is a hard rule in section 24; truncate rather than fail, because the
            # gate will still report it if the model returned none.
            proposal["tags"] = tags[:3]
        elif field == "articleType":
            candidate = str(value or "").strip().upper().replace(" ", "_")
            if candidate in q.ARTICLE_TYPES:
                proposal["articleType"] = candidate
        elif field == "slug":
            slug = q.slugify(str(value or ""))
            # Section 22 forbids a number appended merely to force uniqueness, and a model
            # asked for a "unique" slug reaches for one immediately.
            proposal["slug"] = re.sub(r"-\d{1,3}$", "", slug)
        else:
            proposal[field] = str(value or "").strip()
    proposal["category"] = category
    return proposal


def propose(record_id: str, actor: str) -> Dict[str, Any]:
    """Ask the model for an article, assess it, and store it as a PROPOSAL.

    The gate runs on the proposal before it is stored, so the response tells the operator
    what is still wrong with it. That is the point of doing it here rather than at publish
    time: a model that produced three stock phrases should be visible immediately, next to
    the text, while the operator is deciding whether to keep it.
    """
    import blog_quality_v2 as q

    if not enabled():
        raise PermissionError(
            f"{COST_FLAG} is not enabled, so no model call was made. Enable it in the "
            "cost flags to use AI drafting.")

    record = blog_sources.get_source(record_id)
    if not record:
        raise LookupError("Unknown sourceId")
    # From S3. The item holds a bounded preview only - DynamoDB caps an item at 400 kB and a
    # 300-page book is ~450 kB of text, so the full extract never lived there.
    extract = blog_sources.read_extract(record)
    if not extract.strip():
        raise ValueError("this source has no extract yet; let the worker finish first")

    draft = dict(record.get("draftRecord") or {})
    category = str(record.get("category") or q.DEFAULT_CATEGORY)
    message = json.dumps({
        "category": category,
        "articleClass": record.get("articleClass") or "ARCHIVE_DERIVED",
        "sourceTitle": record.get("sourceTitle") or "",
        "sourceText": extract[:MAX_SOURCE_CHARS],
        "sourceTruncated": len(extract) > MAX_SOURCE_CHARS,
    }, default=str)

    generated = _invoke(SYSTEM_PROMPT, message)
    proposal = _clean_proposal(generated.get("result") or {}, category, q)

    # Assess the PROPOSED article, not the stored one, so the operator sees the verdict on
    # what the model actually wrote.
    candidate = {**draft, **proposal}
    if candidate.get("slug"):
        candidate["canonical"] = q.expected_canonical(candidate["slug"])
    import blog_templates
    assessment = blog_templates.assess_draft(record, candidate)

    input_tokens = int(generated.get("inputTokens", 0))
    output_tokens = int(generated.get("outputTokens", 0))
    ai_draft = {
        "status": "proposed",
        "model": generated.get("model", ""),
        "proposedAt": storage.now_iso(),
        "proposedBy": actor,
        "notes": str((generated.get("result") or {}).get("notes") or "")[:2000],
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "proposal": proposal,
        "assessment": {
            "status": assessment["status"],
            "words": assessment["words"],
            "blocking": assessment["blocking"],
            "review": assessment["review"],
            "humanGatesOutstanding": assessment["humanGatesOutstanding"],
        },
    }

    storage.table().update_item(
        Key={"id": record_id},
        UpdateExpression=("SET aiDraft = :d, aiDraftStatus = :s, draftRecord = :dr, "
                          "articleStatus = :as, gateBlocking = :gb, gateReview = :gr, "
                          "updatedAt = :u"),
        ExpressionAttributeValues={
            ":d": storage._clean(ai_draft),
            ":s": "proposed",
            # The candidate is stored so an operator can edit from it, but note that its
            # status is whatever the gate decided - which cannot be READY_TO_PUBLISH,
            # because nothing here writes the human gates.
            ":dr": storage._clean(candidate),
            ":as": assessment["status"],
            ":gb": assessment["blocking"],
            ":gr": assessment["review"],
            ":u": storage.now_iso(),
        },
    )

    storage.put_record({
        "id": f"log_{record_id[-24:]}_{int(__import__('time').time())}",
        "recordType": "log",
        "createdAt": storage.now_iso(),
        "slug": candidate.get("slug") or record_id,
        "blogSlug": candidate.get("slug") or record_id,
        "pageType": "blogDraft",
        "provider": "aws-bedrock",
        "model": generated.get("model", ""),
        "status": "success",
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "costEstimate": _cost(input_tokens, output_tokens),
        "durationMs": 0,
    })

    logger.info(json.dumps({
        "event": "blog_draft_proposed", "sourceId": record_id, "actor": actor,
        "model": generated.get("model", ""), "articleStatus": assessment["status"],
        "blocking": len(assessment["blocking"]),
    }))
    return {
        "sourceId": record_id,
        "aiDraft": ai_draft,
        "readyToPublish": assessment["readyToPublish"],
        "note": ("This is a proposal. The record stays on its gate-decided status and "
                 "cannot reach READY_TO_PUBLISH until a human records the section 29 "
                 "gates - no field written here can set them."),
    }


def _cost(input_tokens: int, output_tokens: int) -> float:
    value = (input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0
    return round(value, 4)


def apply_draft(record_id: str, body: Dict[str, Any], actor: str) -> Dict[str, Any]:
    """Accept the proposal, with a human's edits, as the working draft.

    Still not an approval. The whitelist is applied a second time here because the edits
    arrive from the browser, and the browser is holding text that originally came from a
    model reading an untrusted document. Same boundary, applied at both ends.
    """
    import blog_quality_v2 as q

    record = blog_sources.get_source(record_id)
    if not record:
        raise LookupError("Unknown sourceId")

    edits = body.get("edits") or {}
    if not isinstance(edits, dict):
        raise ValueError("edits must be an object")
    category = str(record.get("category") or q.DEFAULT_CATEGORY)
    accepted = _clean_proposal(edits, category, q)

    draft = dict(record.get("draftRecord") or {})
    candidate = {**draft, **accepted}
    if candidate.get("slug"):
        candidate["canonical"] = q.expected_canonical(candidate["slug"])
    import blog_templates
    assessment = blog_templates.assess_draft(record, candidate)

    storage.table().update_item(
        Key={"id": record_id},
        UpdateExpression=("SET draftRecord = :dr, aiDraftStatus = :s, articleStatus = :as, "
                          "gateBlocking = :gb, gateReview = :gr, updatedAt = :u, "
                          "draftEditedBy = :by"),
        ExpressionAttributeValues={
            ":dr": storage._clean(candidate),
            ":s": "accepted",
            ":as": assessment["status"],
            ":gb": assessment["blocking"],
            ":gr": assessment["review"],
            ":u": storage.now_iso(),
            ":by": actor,
        },
    )
    logger.info(json.dumps({
        "event": "blog_draft_accepted", "sourceId": record_id, "actor": actor,
        "articleStatus": assessment["status"],
    }))
    return {
        "sourceId": record_id,
        "articleStatus": assessment["status"],
        "blocking": assessment["blocking"],
        "review": assessment["review"],
        "humanGatesOutstanding": assessment["humanGatesOutstanding"],
        "readyToPublish": assessment["readyToPublish"],
    }


def writable_fields() -> List[str]:
    return list(WRITABLE_FIELDS)
