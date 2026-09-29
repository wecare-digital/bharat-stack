"""Production batches: a parent record, and rollups derived from the children.

THE ONE RULE THIS MODULE IS BUILT AROUND.

Every count is computed by reading the source records. There is no `extractedCount` attribute
on a batch that something increments.

That is a requirement rather than a preference - the specification says "Derive all totals
from actual records" and "Never maintain unrelated manually incremented counters" - and the
reason is that a counter and the records it claims to count drift apart at exactly the moment
you need them to agree. A worker that crashes after writing the source status but before
incrementing the batch leaves a batch that says 2,499 of 2,500 forever, and no amount of
re-running fixes it because the increment is not idempotent. A derived count cannot be wrong;
it can only be expensive, and `batchId-createdAt-index` is what makes it cheap.

## Why a dedicated GSI rather than filtering the record-type partition

`storage.list_records` clamps at 500 items. A batch is specified to hold thousands. Filtering
the `blogSource` partition in Python would also read every source in the system to report on
one batch.

The index projects only what a rollup and the sources table need - `INCLUDE`, not `ALL`.
The item carries `extractPreview` (1,500 characters) and `draftRecord`, and projecting those
into the index would roughly double the storage for data no listing renders. That is a
deliberate cost decision, not an oversight.

## What a batch does NOT do

It does not publish, and completing does not imply publishing. Section 38 is explicit:
"Processing completion must never automatically mean publishing." A batch reaching
`COMPLETE` means every source has an article in some state, not that anything is live.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import storage

logger = logging.getLogger(__name__)

RECORD_TYPE = "blogBatch"
BATCH_INDEX = "batchId-createdAt-index"

#: A batch's own lifecycle, which is about INTAKE, not about publication.
OPEN = "OPEN"                 # accepting sources
INGESTING = "INGESTING"       # sources registered, extraction in flight
READY = "READY"               # every source extracted or failed
CLOSED = "CLOSED"             # operator closed it; no more sources accepted
BATCH_STATUSES = (OPEN, INGESTING, READY, CLOSED)

#: Batch statuses the worker still has to look at.
ACTIVE_STATUSES = (OPEN, INGESTING)

MAX_NAME = 160
MAX_DESCRIPTION = 2000
MAX_TAGS = 8


def new_batch_id() -> str:
    return f"blogbatch_{uuid.uuid4().hex}"


# ── Create ──────────────────────────────────────────────────────────────────────

def create(body: Dict[str, Any], actor: str, categories: Sequence[str],
           article_classes: Sequence[str]) -> Dict[str, Any]:
    name = str(body.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    if len(name) > MAX_NAME:
        raise ValueError(f"name must be at most {MAX_NAME} characters")

    category = str(body.get("defaultCategory") or "").strip()
    if category not in categories:
        raise ValueError(f"defaultCategory must be one of {list(categories)}")

    article_class = str(body.get("articleClass") or "ARCHIVE_DERIVED").strip().upper()
    if article_class not in article_classes:
        raise ValueError(f"articleClass must be one of {list(article_classes)}")

    tags = [str(tag).strip() for tag in (body.get("tags") or []) if str(tag).strip()]
    if len(tags) > MAX_TAGS:
        raise ValueError(f"at most {MAX_TAGS} batch tags")

    batch_id = new_batch_id()
    now = storage.now_iso()
    record = {
        "id": batch_id,
        "recordType": RECORD_TYPE,
        "createdAt": now,
        "updatedAt": now,
        #: `slug` is required by `storage.put_record` because the slug GSI keys on it. A batch
        #: has no slug, so it carries its own id - the same choice a source record makes.
        "slug": batch_id,
        "name": name,
        "description": str(body.get("description") or "")[:MAX_DESCRIPTION],
        "defaultCategory": category,
        "articleClass": article_class,
        "defaultTemplateId": str(body.get("defaultTemplateId") or "").strip(),
        "defaultTemplateVersion": str(body.get("defaultTemplateVersion") or "").strip(),
        "tags": tags,
        "status": OPEN,
        "createdBy": actor,
        "updatedBy": actor,
    }
    storage.put_record(record)
    logger.info(json.dumps({
        "event": "blog_batch_created", "batchId": batch_id, "actor": actor,
        "category": category, "articleClass": article_class,
    }))
    return {"batchId": batch_id, **_view(record), "rollup": _empty_rollup()}


def get(batch_id: str) -> Optional[Dict[str, Any]]:
    item = storage.table().get_item(Key={"id": str(batch_id)}).get("Item")
    if not item or item.get("recordType") != RECORD_TYPE:
        return None
    return storage._json_safe(item)


def _view(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "batchId": item.get("id", ""),
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "defaultCategory": item.get("defaultCategory", ""),
        "articleClass": item.get("articleClass", ""),
        "defaultTemplateId": item.get("defaultTemplateId", ""),
        "defaultTemplateVersion": item.get("defaultTemplateVersion", ""),
        "tags": item.get("tags", []) or [],
        "status": item.get("status", ""),
        "createdBy": item.get("createdBy", ""),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }


# ── Sources in a batch ──────────────────────────────────────────────────────────

def batch_sources(batch_id: str, limit: int = 0) -> List[Dict[str, Any]]:
    """Every source in a batch, paginated, no ceiling."""
    return storage.query_index(BATCH_INDEX, "batchId", str(batch_id), limit=limit)


def _empty_rollup() -> Dict[str, Any]:
    return {"sources": 0, "bySourceStatus": {}, "byArticleStatus": {},
            "extracted": 0, "failed": 0, "pending": 0, "words": 0,
            "complete": False, "note": "no sources registered yet"}


def rollup(batch_id: str) -> Dict[str, Any]:
    """Counts, derived from the source records. Never from a stored counter.

    Reports BOTH axes because they answer different questions and are routinely confused.
    `bySourceStatus` is about the document - did the bytes arrive, did extraction work.
    `byArticleStatus` is about the editorial pipeline - the section 32 statuses. A source can
    be EXTRACTED while its article is still SOURCE_REVIEW, and a dashboard that showed one
    number would hide which half of the work remains.
    """
    rows = batch_sources(batch_id)
    if not rows:
        return _empty_rollup()

    by_source: Dict[str, int] = {}
    by_article: Dict[str, int] = {}
    words = 0
    for row in rows:
        source_status = str(row.get("status") or "")
        by_source[source_status] = by_source.get(source_status, 0) + 1
        article_status = str(row.get("articleStatus") or "")
        if article_status:
            by_article[article_status] = by_article.get(article_status, 0) + 1
        words += int(row.get("extractedWords") or 0)

    extracted = by_source.get("EXTRACTED", 0)
    failed = by_source.get("EXTRACTION_FAILED", 0)
    pending = len(rows) - extracted - failed
    return {
        "sources": len(rows),
        "bySourceStatus": dict(sorted(by_source.items())),
        "byArticleStatus": dict(sorted(by_article.items())),
        "extracted": extracted,
        "failed": failed,
        "pending": pending,
        "words": words,
        #: Complete means every source has reached a terminal INTAKE state. It does NOT mean
        #: anything is publishable, let alone published - section 38.
        "complete": pending == 0,
        "note": "",
    }


def refresh_status(batch_id: str) -> str:
    """Move the batch's own status to match its children, and return it.

    Derived from the rollup for the same reason the counts are: a status maintained by
    increments drifts, and a batch stuck on INGESTING with every source finished is
    indistinguishable from one that is genuinely still working.

    CLOSED is never overwritten. It is an operator decision, and a late-arriving source
    should not silently reopen a batch somebody deliberately closed.
    """
    record = get(batch_id)
    if not record:
        raise LookupError("Unknown batchId")
    current = str(record.get("status") or OPEN)
    if current == CLOSED:
        return CLOSED

    counts = rollup(batch_id)
    if counts["sources"] == 0:
        wanted = OPEN
    elif counts["complete"]:
        wanted = READY
    else:
        wanted = INGESTING

    if wanted != current:
        storage.table().update_item(
            Key={"id": batch_id},
            UpdateExpression="SET #s = :s, updatedAt = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": wanted, ":u": storage.now_iso()},
        )
    return wanted


def close(batch_id: str, actor: str) -> Dict[str, Any]:
    record = get(batch_id)
    if not record:
        raise LookupError("Unknown batchId")
    if str(record.get("status")) == CLOSED:
        return {"batchId": batch_id, "status": CLOSED, "alreadyClosed": True}
    storage.table().update_item(
        Key={"id": batch_id},
        UpdateExpression="SET #s = :s, updatedAt = :u, updatedBy = :by",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": CLOSED, ":u": storage.now_iso(), ":by": actor},
    )
    logger.info(json.dumps({"event": "blog_batch_closed", "batchId": batch_id,
                            "actor": actor}))
    return {"batchId": batch_id, "status": CLOSED, "alreadyClosed": False}


def assert_accepting(batch_id: str) -> Dict[str, Any]:
    """The batch a source is being added to must exist and still be open."""
    record = get(batch_id)
    if not record:
        raise LookupError(f"Unknown batchId {batch_id!r}")
    if str(record.get("status")) == CLOSED:
        raise ValueError(f"batch {batch_id!r} is closed and accepts no further sources")
    return record


# ── Listing ─────────────────────────────────────────────────────────────────────

def list_batches(with_rollup: bool = True, limit: int = 200) -> List[Dict[str, Any]]:
    """Batches, newest first.

    `with_rollup` is a real cost switch, not a convenience flag: each rollup pages that
    batch's sources, so a page showing 50 batches with rollups performs 50 index queries.
    That is correct for the batches page and wasteful for a dropdown.
    """
    records = storage.list_records(RECORD_TYPE, limit=limit)
    out: List[Dict[str, Any]] = []
    for record in records:
        view = _view(record)
        if with_rollup:
            view["rollup"] = rollup(record["id"])
        out.append(view)
    return out


def detail(batch_id: str, source_limit: int = 0) -> Dict[str, Any]:
    record = get(batch_id)
    if not record:
        raise LookupError("Unknown batchId")
    import blog_sources
    rows = batch_sources(batch_id, limit=source_limit)
    return {
        **_view(record),
        "rollup": rollup(batch_id),
        "sources": [blog_sources.view(row) for row in rows],
    }


def active_batch_ids() -> List[str]:
    """Batches the worker still has to look at.

    Few enough to read with `list_records`: batches are created by hand, one per production
    wave, so the 500 ceiling is a real limit on SOURCES and a non-issue on batches.
    """
    return [str(record["id"]) for record in storage.list_records(RECORD_TYPE, limit=500)
            if str(record.get("status")) in ACTIVE_STATUSES]
