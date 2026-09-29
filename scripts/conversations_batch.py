#!/usr/bin/env python3
"""Conversations continuous publishing runner: validate, publish, audit.

WHAT THIS REPLACES, AND WHY IT IS NOT A SECOND PUBLISHER.

Conversations publication was orchestrated outside the repository, on a schedule nobody
here could see, resume or audit. This module makes the orchestration durable: the queue is
a committed manifest, the state is `content/conversations/ledger.json`, and a re-run is a
no-op on work already done.

It deliberately owns NO Wix mutation of its own. Every write goes through
`scripts/wix_blog_migrate.py` - its auth, its `WIX_CREDENTIALS_DISABLED` kill switch, its
Markdown-to-Ricos compiler, its `draft_post` body builder, its SEO tag builder, its bulk
`draft-posts/create` endpoint and its chunk size. What lives here is the part that module
does not have: a quality gate on entry, resume-by-slug across runs, a live read-back, and
a ledger checkpoint. `.github/workflows/conversations-content-gate.yml` warns that a
second route to the same Wix mutation is how a review step gets bypassed; that warning is
respected by delegating rather than reimplementing.

THREE HUMAN GATES, ALL OF THEM PRE-EXISTING.

  1. Per record - the eleven `gate` answers the v2 standard requires. Only
     READY_TO_PUBLISH records enter the queue, and `blog_quality_v2.decide_status` will
     not award that status to a record no human has signed. This module never writes a
     `gate` value and never overrides a status.
  2. Per run - `publish` is its own subcommand, and the workflow's `publish` input is a
     boolean defaulting to false. A branch push can only validate.
  3. Per integration - `WIX_CREDENTIALS_DISABLED`, inherited from the migrate module's
     credential loader, which refuses before any secret is read.

No fourth kind of approval is invented here. There is no approver-name field and no
sign-off timestamp, because the standard's contract is answer-per-gate and adding a field
nothing checks would look like a control while being none.

MANIFEST SIZE IS ARBITRARY. There is no editorial batch size, unlike Gastronomy's
contiguous 25. A manifest may hold one record or two thousand; Wix is fed in chunks of
`wix_blog_migrate.BULK_LIMIT` because that is the API's limit, which is an internal
detail rather than an editorial unit.

Usage:
    python scripts/conversations_batch.py validate --manifest content/conversations/batches/CONV-001.json
    python scripts/conversations_batch.py publish  --manifest <file>
    python scripts/conversations_batch.py audit    --manifest <file> [--published-since <iso>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

#: Neither of these imports pulls in boto3, so `validate` can run in a job with no AWS
#: role at all. `wix_blog_migrate` does pull boto3, and is therefore imported lazily by
#: `load_wix()` at the point a Wix call or a Ricos compile is actually needed.
import blog_ledger  # noqa: E402
import blog_quality_v2 as quality  # noqa: E402

CATEGORY = quality.DEFAULT_CATEGORY
AUTHOR = quality.AUTHOR
SITE = quality.SITE
LEDGER_PATH = blog_ledger.DEFAULT_LEDGER

#: The read-back goes through our own Lambda rather than Wix, exactly as
#: `scripts/wix_blog_probe.py` does: `wecare-seo-tools` already holds the Headless client
#: credential and performs the anonymous-visitor exchange, so auditing adds no credential
#: surface and no Wix secret enters this process.
AUDIT_FUNCTION = os.environ.get("CONVERSATIONS_AUDIT_FUNCTION", "wecare-seo-tools")
AUDIT_REGION = os.environ.get("AWS_REGION", "us-east-1")

#: Every node type `wix_blog_migrate.markdown_to_rich_content` can emit, and nothing else.
#: An unexpected type in a published body means something other than that compiler wrote
#: it, which is the corruption this set is here to notice.
ALLOWED_RICOS_NODES = frozenset({
    "PARAGRAPH", "HEADING", "BULLETED_LIST", "ORDERED_LIST", "LIST_ITEM",
    "BLOCKQUOTE", "TEXT",
})
FORBIDDEN_RICOS_NODES = frozenset({"IMAGE", "GALLERY", "GIF", "VIDEO", "AUDIO"})

#: `PARAGRAPH_EMPTY` is an internal marker the compiler uses for a blank line and then
#: converts away. Seeing one in a published post means a raw, half-compiled tree was sent.
RICOS_INTERNAL_MARKER = "PARAGRAPH_EMPTY"

MIN_PUBLISHED_CHARS = 400
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Corruption signatures, as (regex, description). Each one has been seen in a real
#: publishing pipeline: a JSON-encoded body written without decoding, a Markdown body
#: pasted straight into a rich-text field, an HTML body from a different editor, and a
#: template variable that resolved to nothing.
CORRUPTION_PATTERNS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\\n"), "literal escaped newline"),
    (re.compile(r"\\t"), "literal escaped tab"),
    #: Matches at a real line break AND after a literal `\n`, because the two corruptions
    #: travel together: a body that arrived JSON-escaped has its headings mid-line, where
    #: an anchored multiline pattern cannot see them.
    (re.compile(r"(?:^|\n|\\n)#{1,6}\s"), "literal Markdown heading"),
    (re.compile(r"\*\*[^*\n]+\*\*"), "literal Markdown bold markers"),
    (re.compile(r"\{\s*[\"']?(?:type|nodes|richContent|textData)[\"']?\s*:"),
     "raw editor JSON"),
    (re.compile(r"</?(?:p|div|span|br|strong|em|h[1-6])\b[^>]*>", re.IGNORECASE),
     "raw HTML markup"),
    (re.compile(r"&(?:nbsp|amp|lt|gt|quot|#\d+);"), "unresolved HTML entity"),
    (re.compile(r"\b(?:undefined|NaN)\b"), "unresolved template placeholder"),
    (re.compile(r"\{\{[^}]+\}\}|\$\{[^}]+\}"), "unsubstituted template variable"),
)


# ── loading ─────────────────────────────────────────────────────────────────────

def load_wix():
    """The publisher. Imported lazily because it imports boto3."""
    import wix_blog_migrate as wix
    return wix


def load_document(path: Path) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"posts": data}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: manifest must be a JSON object or array")
    return data


def manifest_posts(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    posts = document.get("posts") if isinstance(document, dict) else document
    if not isinstance(posts, list):
        raise ValueError("manifest must carry a posts array")
    return [post for post in posts if isinstance(post, dict)]


def build_corpus(manifest_path: Optional[Path]) -> quality.CorpusIndex:
    """The section 28 corpus, with the manifest under test excluded from itself.

    Without the exclusion every committed record reports an exact slug collision with its
    own committed copy, which is how a duplication gate ends up being switched off.
    """
    target = Path(manifest_path).resolve() if manifest_path else None
    patterns = [p for p in quality.DEFAULT_CORPUS
                if not (manifest_path and str(manifest_path) in p)]
    corpus = quality._build_corpus(patterns, published=True)
    if target is not None:
        corpus.entries = [entry for entry in corpus.entries
                          if Path(entry.origin or ".").resolve() != target]
        corpus._by_slug = {entry.slug: entry
                           for entry in reversed(corpus.entries) if entry.slug}
    return corpus


# ── the payload contract ────────────────────────────────────────────────────────

def to_wix_post(record: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a Conversations record into the shape `wix_blog_migrate` publishes.

    Field aliases are resolved through the quality module so both spellings in the corpus
    work, and the Ricos body is compiled by the migrate module's own compiler - this
    function chooses nothing about markup.
    """
    wix = load_wix()
    post = {
        "title": str(record.get("title") or "").strip(),
        "slug": str(record.get("slug") or "").strip(),
        "seoTitle": quality.text_field(record, "seoTitle"),
        "metaDescription": quality.text_field(record, "metaDescription"),
        "tags": [str(tag).strip() for tag in (quality.field(record, "tags") or [])
                 if str(tag).strip()],
        "excerpt": str(record.get("excerpt")
                       or quality.text_field(record, "metaDescription")).strip(),
        "contentMarkdown": quality.body_of(record),
        "category": CATEGORY,
        "authorName": AUTHOR,
    }
    return wix.normalize_manifest_post(post)


def expected_url(slug: str) -> str:
    return f"{SITE}/post/{slug}/"


def payload_errors(record: Dict[str, Any], rich_content: Optional[Dict[str, Any]] = None
                   ) -> List[str]:
    """Publication prerequisites, as distinct from the editorial standard.

    The v2 gate judges whether a record is fit to publish. This judges whether it can be
    turned into a Wix payload at all, which is a different question with different failure
    text - a missing `seoTitle` is an editorial gap to the standard and a malformed request
    to the API.
    """
    slug = str(record.get("slug") or "").strip()
    prefix = slug or str(record.get("title") or "<untitled>")
    errors: List[str] = []

    if not slug:
        errors.append(f"{prefix}: slug is required")
    elif not SLUG_PATTERN.match(slug):
        errors.append(f"{prefix}: slug must be lowercase words joined by single hyphens")
    if not str(record.get("title") or "").strip():
        errors.append(f"{prefix}: title is required")
    if not quality.text_field(record, "seoTitle"):
        errors.append(f"{prefix}: seoTitle is required")
    if not quality.text_field(record, "metaDescription"):
        errors.append(f"{prefix}: metaDescription is required")

    category = str(record.get("category") or "").strip()
    if category and category != CATEGORY:
        errors.append(f"{prefix}: category must be {CATEGORY!r}, got {category!r}")
    author = quality.text_field(record, "author")
    if author and author != AUTHOR:
        errors.append(f"{prefix}: author must be {AUTHOR!r}, got {author!r}")

    tags = quality.field(record, "tags") or []
    if not isinstance(tags, list) or not 1 <= len(tags) <= 3:
        errors.append(f"{prefix}: tags must be a list of 1-3 labels")

    canonical = str(record.get("canonical") or "").strip()
    if slug and canonical and canonical != expected_url(slug):
        errors.append(f"{prefix}: canonical must be {expected_url(slug)}, got {canonical}")

    for key in ("heroImage", "media", "coverImage", "image"):
        if record.get(key):
            errors.append(f"{prefix}: {key} is forbidden; the blog is image-free")

    body = quality.body_of(record)
    if not body.strip():
        errors.append(f"{prefix}: body is required")
    if rich_content is not None:
        errors.extend(ricos_errors(rich_content, prefix))
    return errors


def ricos_errors(rich_content: Dict[str, Any], prefix: str) -> List[str]:
    """Whether a Ricos tree is one this pipeline could have produced and Wix can render."""
    errors: List[str] = []
    nodes = (rich_content or {}).get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return [f"{prefix}: rich content compiled to no nodes"]

    seen_types: List[str] = []
    for node in walk_ricos(nodes):
        kind = str(node.get("type") or "").upper()
        if not kind:
            errors.append(f"{prefix}: rich content holds a node with no type")
            continue
        seen_types.append(kind)
        if kind == RICOS_INTERNAL_MARKER:
            errors.append(f"{prefix}: {RICOS_INTERNAL_MARKER} marker reached the payload; "
                          "the body was not fully compiled")
        elif kind in FORBIDDEN_RICOS_NODES:
            errors.append(f"{prefix}: forbidden media node {kind}")
        elif kind not in ALLOWED_RICOS_NODES:
            errors.append(f"{prefix}: unexpected rich-content node {kind}")
        if kind == "TEXT":
            text = (node.get("textData") or {}).get("text")
            if not isinstance(text, str):
                errors.append(f"{prefix}: TEXT node carries no textData.text string")

    if "PARAGRAPH" not in seen_types:
        errors.append(f"{prefix}: rich content holds no paragraph")
    #: Deduplicated: a long body repeats the same defect once per node, and forty
    #: identical lines bury the one that differs.
    return list(dict.fromkeys(errors))


def walk_ricos(nodes: Any) -> Iterable[Dict[str, Any]]:
    """Yield Ricos NODES only, descending through `nodes` arrays.

    Deliberately not a walk over every dict in the tree. A node carries sibling dicts that
    are not nodes - `textData`, `paragraphData`, `headingData`, `textStyle` - and a
    decoration is `{"type": "BOLD"}`, which reads as a node type while being nothing of the
    kind. A generic walk therefore reports every paragraph as a typeless node and every
    bold run as an unknown node type, which is what the first version of this function did.
    """
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        yield node
        yield from walk_ricos(node.get("nodes"))


def flatten_text(rich_content: Dict[str, Any]) -> str:
    parts: List[str] = []
    for node in walk_ricos((rich_content or {}).get("nodes")):
        text = (node.get("textData") or {}).get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return "\n".join(parts)


def heading_texts(rich_content: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for node in walk_ricos((rich_content or {}).get("nodes")):
        if str(node.get("type") or "").upper() != "HEADING":
            continue
        value = "".join(str((child.get("textData") or {}).get("text") or "")
                        for child in node.get("nodes") or [])
        if value:
            out.append(value)
    return out


# ── the ledger ──────────────────────────────────────────────────────────────────

def ledger_row(ledger: "blog_ledger.Ledger", record: Dict[str, Any]):
    """The row for a record: by sourceId first, then by slug.

    sourceId is the durable identity - it is the hash of the source bytes - so it is tried
    first. Slug is the fallback for a record predating the ledger.
    """
    source_id = str(record.get("sourceId") or "").strip()
    if source_id:
        row = ledger.resolve(source_id)
        if row is not None:
            return row
    slug = str(record.get("slug") or "").strip()
    return ledger.by_slug(slug) if slug else None


def ledger_errors(ledger: "blog_ledger.Ledger",
                  records: Sequence[Dict[str, Any]]) -> List[str]:
    """Records with no ledger row. Their provenance is unrecorded and PUBLISHED cannot be
    checkpointed against anything, so publishing one would lose the link permanently."""
    problems: List[str] = []
    for record in records:
        if ledger_row(ledger, record) is None:
            slug = str(record.get("slug") or "<no slug>")
            problems.append(f"{slug}: no ledger row; run blog_ingest so its source "
                            "provenance is recorded before publishing")
    return problems


# ── validate ────────────────────────────────────────────────────────────────────

def validate_document(document: Dict[str, Any], *, manifest_path: Optional[Path] = None,
                      ledger_path: Path = LEDGER_PATH,
                      compile_bodies: bool = True) -> Dict[str, Any]:
    """The full entry gate: v2 standard, payload contract, ledger provenance.

    Returns a report rather than raising, so the CLI can print every problem in one pass.
    """
    posts = manifest_posts(document)
    corpus = build_corpus(manifest_path)
    wave = quality.assess_wave(posts, corpus)
    queue = set(quality.publish_queue(wave))

    errors: List[str] = []
    if not posts:
        errors.append("manifest holds no posts")

    slugs: Dict[str, int] = {}
    for post in posts:
        slug = str(post.get("slug") or "").strip()
        if slug:
            slugs[slug] = slugs.get(slug, 0) + 1
    for slug, count in sorted(slugs.items()):
        if count > 1:
            errors.append(f"{slug}: appears {count} times in this manifest")

    for post in posts:
        rich = None
        if compile_bodies:
            try:
                rich = to_wix_post(post).get("richContent")
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                errors.append(f"{post.get('slug') or '<no slug>'}: body failed to "
                              f"compile ({type(exc).__name__}: {exc})")
        errors.extend(payload_errors(post, rich))

    for record in wave["records"]:
        for line in record["blocking"]:
            errors.append(f"{record['slug'] or '<no slug>'}: {line}")

    ledger = blog_ledger.Ledger.load(ledger_path)
    publishable = [post for post in posts
                   if str(post.get("slug") or "").strip() in queue]
    if ledger.rows:
        errors.extend(ledger_errors(ledger, publishable))

    return {
        "manifest": str(manifest_path or ""),
        "total": len(posts),
        "readyToPublish": sorted(queue),
        "byStatus": wave["byStatus"],
        "blocked": wave["blocked"],
        "publishedIndex": quality.published_index_health(),
        "errors": errors,
    }


# ── publish ─────────────────────────────────────────────────────────────────────

def pending_records(records: Sequence[Dict[str, Any]], existing_slugs: Iterable[str],
                    ledger: Optional["blog_ledger.Ledger"] = None
                    ) -> List[Dict[str, Any]]:
    """Records still to publish. Idempotent by slug, from two independent directions.

    Wix is authoritative: a slug already live is never re-created, which is what makes a
    re-run after a partial failure safe. The ledger is the second check, so a post that
    the live query somehow misses - a query page lost, a slug renamed upstream - is still
    not published twice.
    """
    existing = {str(slug) for slug in existing_slugs}
    out: List[Dict[str, Any]] = []
    for record in records:
        slug = str(record.get("slug") or "").strip()
        if not slug or slug in existing:
            continue
        if ledger is not None:
            row = ledger_row(ledger, record)
            if row is not None and row.publishedAt:
                continue
        out.append(record)
    return out


def publish_document(document: Dict[str, Any], *, manifest_path: Optional[Path] = None,
                     ledger_path: Path = LEDGER_PATH) -> Dict[str, Any]:
    """Publish the READY_TO_PUBLISH records this manifest still owes Wix.

    Refuses on any validation error, publishes only the queue, and checkpoints the ledger
    after every chunk rather than once at the end - an interrupted run must leave behind a
    record of what it already did, or the next run cannot tell.
    """
    report = validate_document(document, manifest_path=manifest_path,
                               ledger_path=ledger_path)
    if report["errors"]:
        raise ValueError("validation failed:\n  " + "\n  ".join(report["errors"]))

    posts = manifest_posts(document)
    queue = set(report["readyToPublish"])
    candidates = [post for post in posts if str(post.get("slug") or "").strip() in queue]
    held = [str(post.get("slug") or "<no slug>") for post in posts
            if str(post.get("slug") or "").strip() not in queue]

    wix = load_wix()
    ledger = blog_ledger.Ledger.load(ledger_path)
    live = wix.query_posts(wix.TARGET_SITE_ID)
    existing = {str(post.get("slug") or ""): post for post in live}
    pending = pending_records(candidates, existing.keys(), ledger)

    result: Dict[str, Any] = {
        "queued": len(candidates),
        "heldByGate": held,
        "created": 0,
        "skipped": len(candidates) - len(pending),
        "published": [],
        "failures": [],
    }
    if not pending:
        return result

    member_id = wix.ensure_author()
    category_id = wix.ensure_category()
    labels = sorted({label for record in pending
                     for label in (quality.field(record, "tags") or [])})
    tag_ids = wix.ensure_tags(labels)

    for chunk in wix.chunks(pending, wix.BULK_LIMIT):
        prepared = [wix.draft_post(to_wix_post(record), member_id, category_id, tag_ids)
                    for record in chunk]
        data = wix.request(
            wix.TARGET_SITE_ID,
            "POST",
            "/blog/v3/bulk/draft-posts/create",
            {"draftPosts": prepared, "publish": True, "returnFullEntity": False},
        )
        for offset, outcome in enumerate(data.get("results", []) or []):
            metadata = outcome.get("itemMetadata") or {}
            index = metadata.get("originalIndex")
            record = chunk[index] if isinstance(index, int) and index < len(chunk) \
                else (chunk[offset] if offset < len(chunk) else {})
            slug = str(record.get("slug") or "")
            if metadata.get("success"):
                result["created"] += 1
                result["published"].append(slug)
            else:
                result["failures"].append({"slug": slug, "error": metadata.get("error")})

        #: Resolve ids from Wix rather than from the bulk response: `returnFullEntity` is
        #: false, so the response carries no post id, and inventing one would put a value
        #: in the ledger that matches nothing.
        checkpoint_ledger(ledger, chunk, result["published"], ledger_path, wix)

    if result["failures"]:
        raise RuntimeError(
            f"{len(result['failures'])} Wix item(s) failed: "
            + json.dumps(result["failures"], indent=2))
    return result


def checkpoint_ledger(ledger: "blog_ledger.Ledger", chunk: Sequence[Dict[str, Any]],
                      published: Sequence[str], ledger_path: Path, wix) -> None:
    """Write PUBLISHED for the slugs that landed, then save atomically."""
    landed = {str(slug) for slug in published}
    ids = {str(post.get("slug") or ""): str(post.get("id") or "")
           for post in wix.query_posts(wix.TARGET_SITE_ID)}
    touched = False
    for record in chunk:
        slug = str(record.get("slug") or "").strip()
        if slug not in landed:
            continue
        row = ledger_row(ledger, record)
        if row is None:
            continue
        ledger.update(row.sourceId, status="PUBLISHED",
                      publishedAt=blog_ledger.now_iso(),
                      wixPostId=ids.get(slug) or row.wixPostId)
        touched = True
    if touched:
        ledger.path = Path(ledger_path)
        ledger.save()


# ── audit ───────────────────────────────────────────────────────────────────────

def fetch_public_post(slug: str) -> Dict[str, Any]:
    """One published post, read through `wecare-seo-tools`. No Wix secret is involved."""
    import boto3

    path = f"/seo-tools/blog-public/{slug}"
    payload = {
        "requestContext": {"apiId": "conversations-audit",
                           "http": {"method": "GET", "path": path,
                                    "sourceIp": "127.0.0.1"}},
        "rawPath": path,
    }
    response = boto3.client("lambda", region_name=AUDIT_REGION).invoke(
        FunctionName=AUDIT_FUNCTION, InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode())
    raw = response["Payload"].read().decode()
    if response.get("FunctionError"):
        raise RuntimeError(f"{AUDIT_FUNCTION} failed reading {slug}: {raw[:400]}")
    outer = json.loads(raw)
    status = int(outer.get("statusCode") or 0)
    if status != 200:
        raise RuntimeError(f"public-blog HTTP {status} for {slug}: "
                           f"{str(outer.get('body'))[:300]}")
    body = json.loads(outer.get("body") or "{}")
    if body.get("ok") is not True:
        raise RuntimeError(f"public-blog reported not-ok for {slug}")
    return body.get("post") or {}


def parse_iso(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def normalized_prose(value: str) -> str:
    """Body text reduced to what survives the Markdown-to-Ricos round trip."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", str(value or ""))
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:[-*]\s+|\d+\.\s+|>\s+|#{1,6}\s+)", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def audit_post(public: Dict[str, Any], expected: Dict[str, Any], *,
               admin: Optional[Dict[str, Any]] = None,
               author_member_id: str = "",
               live_slug_counts: Optional[Dict[str, int]] = None,
               live_title_counts: Optional[Dict[str, int]] = None,
               published_since: Optional[datetime] = None,
               now: Optional[datetime] = None) -> List[str]:
    """Compare one live post against the record that produced it.

    Pure: every input is plain data, so the whole audit is testable without touching Wix
    or Lambda. That seam is why the Gastronomy tests need no network stubbing and this one
    does not either.
    """
    slug = str(expected.get("slug") or "").strip()
    errors: List[str] = []
    now = now or datetime.now(timezone.utc)

    def fail(message: str) -> None:
        errors.append(f"{slug or '<no slug>'}: {message}")

    if not public:
        fail("not found on the live site")
        return errors

    if str(public.get("slug") or "") != slug:
        fail(f"slug is {public.get('slug')!r}, expected {slug!r}")
    if str(public.get("title") or "") != str(expected.get("title") or "").strip():
        fail(f"title is {public.get('title')!r}, expected "
             f"{str(expected.get('title') or '').strip()!r}")

    #: AUTHOR IS CHECKED AGAINST WIX, NOT AGAINST THE PUBLIC VIEW. `_blog_view` in
    #: seo-tools/wix.py sets `authorName` to a module constant, so asserting it here can
    #: never fail and proves nothing about what was published. The Wix-side `memberId` is
    #: the real evidence, which is why `audit_document` resolves the expected member.
    if str(public.get("authorName") or "") != AUTHOR:
        fail(f"authorName is {public.get('authorName')!r}, expected {AUTHOR!r}")
    if admin is not None and author_member_id:
        if str(admin.get("memberId") or "") != str(author_member_id):
            fail(f"Wix memberId is {admin.get('memberId')!r}, expected "
                 f"{author_member_id!r}; the post is attributed to the wrong author")
    elif admin is None:
        fail("author not verified against Wix: no admin read available, and the public "
             "view serves a constant author name")

    if str(public.get("category") or "") != CATEGORY:
        fail(f"category is {public.get('category')!r}, expected {CATEGORY!r}")

    want_tags = [str(tag).strip() for tag in (quality.field(expected, "tags") or [])
                 if str(tag).strip()]
    got_tags = [str(tag).strip() for tag in (public.get("tags") or []) if str(tag).strip()]
    if sorted(got_tags) != sorted(want_tags):
        fail(f"tags are {got_tags}, expected {want_tags}")

    want_seo_title = quality.text_field(expected, "seoTitle")
    if str(public.get("seoTitle") or "").strip() != want_seo_title:
        fail(f"seoTitle is {public.get('seoTitle')!r}, expected {want_seo_title!r}")
    want_meta = quality.text_field(expected, "metaDescription")
    if str(public.get("metaDescription") or "").strip() != want_meta:
        fail(f"metaDescription is {public.get('metaDescription')!r}, "
             f"expected {want_meta!r}")

    url = str(public.get("url") or "").strip()
    if url != expected_url(slug):
        fail(f"public URL is {url!r}, expected {expected_url(slug)!r}")
    canonical = str(expected.get("canonical") or "").strip()
    if canonical and canonical != url:
        fail(f"record canonical {canonical!r} does not match the live URL {url!r}")

    published_at = parse_iso(public.get("publishedDate"))
    if published_at is None:
        fail(f"publishedDate {public.get('publishedDate')!r} is missing or unparseable")
    else:
        if published_at > now + timedelta(minutes=5):
            fail(f"publishedDate {published_at.isoformat()} is in the future")
        if published_since and published_at < published_since:
            fail(f"publishedDate {published_at.isoformat()} predates this run "
                 f"({published_since.isoformat()}); the post was not freshly published")
        #: THE DATE THAT MUST NOT BE REUSED. `wix_blog_migrate.draft_post` omits
        #: `firstPublishedDate` precisely so Wix stamps a new one; a live post carrying
        #: the source's original date means that omission was defeated somewhere.
        source_date = parse_iso(quality.field(expected, "originalSourceDate")
                                or quality.field(expected, "originalPublishedDate"))
        if source_date and published_at <= source_date:
            fail(f"publishedDate {published_at.isoformat()} is not newer than the "
                 f"source's own date {source_date.isoformat()}")

    rich = public.get("richContent") or {}
    errors.extend(ricos_errors(rich, slug or "<no slug>"))

    flat = flatten_text(rich) or str(public.get("content") or "")
    if len(flat) < MIN_PUBLISHED_CHARS:
        fail(f"published body is {len(flat)} chars, expected at least "
             f"{MIN_PUBLISHED_CHARS}")
    for pattern, description in CORRUPTION_PATTERNS:
        if pattern.search(flat):
            fail(f"{description} in the published body")
    for heading in heading_texts(rich):
        if heading.strip().startswith("#"):
            fail(f"heading {heading!r} still carries Markdown hashes")

    opening = normalized_prose(quality.body_of(expected))[:80]
    if opening and opening not in normalized_prose(flat):
        fail("the published body does not open with this record's body; the wrong "
             "content is live under this slug")

    if live_slug_counts is not None and live_slug_counts.get(slug, 0) > 1:
        fail(f"{live_slug_counts[slug]} live posts share this slug")
    if live_title_counts is not None:
        title = str(expected.get("title") or "").strip()
        if title and live_title_counts.get(title, 0) > 1:
            fail(f"{live_title_counts[title]} live posts share the title {title!r}")
    return errors


def audit_document(document: Dict[str, Any], *, manifest_path: Optional[Path] = None,
                   ledger_path: Path = LEDGER_PATH,
                   published_since: Optional[datetime] = None,
                   use_admin: bool = True) -> Dict[str, Any]:
    """Read every published record in this manifest back off the live site.

    Only records Wix actually holds are audited; one still sitting behind the human gate
    is reported as not-yet-published rather than as a failure, because that is the system
    working.
    """
    posts = manifest_posts(document)
    admin_by_slug: Dict[str, Dict[str, Any]] = {}
    live_slug_counts: Dict[str, int] = {}
    live_title_counts: Dict[str, int] = {}
    author_member_id = ""

    if use_admin:
        wix = load_wix()
        for post in wix.query_posts(wix.TARGET_SITE_ID):
            slug = str(post.get("slug") or "")
            admin_by_slug.setdefault(slug, post)
            live_slug_counts[slug] = live_slug_counts.get(slug, 0) + 1
            title = str(post.get("title") or "").strip()
            if title:
                live_title_counts[title] = live_title_counts.get(title, 0) + 1
        author_member_id = wix.ensure_author()

    ledger = blog_ledger.Ledger.load(ledger_path)
    errors: List[str] = []
    verified: List[str] = []
    absent: List[str] = []

    for record in posts:
        slug = str(record.get("slug") or "").strip()
        if not slug:
            errors.append("<no slug>: record cannot be audited without a slug")
            continue
        if use_admin and slug not in admin_by_slug:
            absent.append(slug)
            continue
        try:
            public = fetch_public_post(slug)
        except RuntimeError as exc:
            if not use_admin:
                absent.append(slug)
                continue
            errors.append(f"{slug}: read-back failed ({exc})")
            continue
        problems = audit_post(
            public, record,
            admin=admin_by_slug.get(slug) if use_admin else None,
            author_member_id=author_member_id,
            live_slug_counts=live_slug_counts or None,
            live_title_counts=live_title_counts or None,
            published_since=published_since,
        )
        if problems:
            errors.extend(problems)
            continue
        verified.append(slug)
        row = ledger_row(ledger, record)
        if row is not None:
            ledger.update(row.sourceId, status="VERIFIED",
                          verifiedAt=blog_ledger.now_iso(),
                          publishedAt=row.publishedAt or str(public.get("publishedDate")
                                                             or blog_ledger.now_iso()),
                          wixPostId=row.wixPostId or str(public.get("id") or ""))

    if verified and ledger.rows:
        ledger.path = Path(ledger_path)
        ledger.save()

    return {
        "manifest": str(manifest_path or ""),
        "total": len(posts),
        "verified": verified,
        "notPublished": absent,
        "errors": errors,
    }


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _print_report(title: str, report: Dict[str, Any]) -> None:
    print(f"{title}: {report.get('manifest') or '<manifest>'}")
    for key in ("total", "queued", "created", "skipped", "blocked"):
        if key in report:
            print(f"  {key:<16} {report[key]}")
    if "readyToPublish" in report:
        print(f"  {'readyToPublish':<16} {len(report['readyToPublish'])}")
    if report.get("byStatus"):
        print(f"  {'byStatus':<16} {report['byStatus']}")
    if report.get("heldByGate"):
        print(f"  held by the human gate: {len(report['heldByGate'])}")
    if report.get("verified"):
        print(f"  {'verified':<16} {len(report['verified'])}")
    if report.get("notPublished"):
        print(f"  {'notPublished':<16} {len(report['notPublished'])}")
    health = report.get("publishedIndex")
    if health:
        if health.get("present"):
            print(f"  published corpus index: {health['indexed']} posts"
                  + (f"  ⚠ {health['note']}" if health.get("note") else ""))
        else:
            print(f"  ⚠ NO PUBLISHED CORPUS INDEX — {health.get('note')}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Conversations continuous publishing runner")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "publish", "audit"):
        node = sub.add_parser(name)
        node.add_argument("--manifest", required=True, type=Path)
        node.add_argument("--ledger", type=Path, default=LEDGER_PATH)
        node.add_argument("--json", action="store_true")
    sub.choices["audit"].add_argument(
        "--published-since", default="",
        help="ISO timestamp; a post published before it fails the freshness check")
    sub.choices["audit"].add_argument(
        "--no-admin", action="store_true",
        help="skip the Wix admin read (author attribution and duplicates go unverified)")

    args = parser.parse_args(argv)
    document = load_document(args.manifest)

    if args.command == "validate":
        report = validate_document(document, manifest_path=args.manifest,
                                   ledger_path=args.ledger)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            _print_report("validate", report)
            for line in report["errors"]:
                print(f"  ✗ {line}")
        return 1 if report["errors"] else 0

    if args.command == "publish":
        report = publish_document(document, manifest_path=args.manifest,
                                  ledger_path=args.ledger)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            _print_report("publish", report)
            for slug in report["published"]:
                print(f"  + {slug}")
        return 0

    since = parse_iso(args.published_since) if args.published_since else None
    if args.published_since and since is None:
        print(f"--published-since {args.published_since!r} is not an ISO timestamp",
              file=sys.stderr)
        return 2
    report = audit_document(document, manifest_path=args.manifest,
                            ledger_path=args.ledger, published_since=since,
                            use_admin=not args.no_admin)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report("audit", report)
        for slug in report["notPublished"]:
            print(f"  · {slug} not published yet")
        for line in report["errors"]:
            print(f"  ✗ {line}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
