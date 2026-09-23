"""Validate and batch-create WECARE.DIGITAL Wix Blog migration manifests.

Wix Blog is the content source of truth. This script never generates editorial
copy: it accepts only already-approved post manifests. The default mode is
validation-only. Draft creation or publication must be explicitly requested.

Examples:
  python scripts/wix_blog_migrate.py export --output /tmp/wix-source.json
  python scripts/wix_blog_migrate.py apply --manifest /tmp/approved.json
  python scripts/wix_blog_migrate.py apply --manifest /tmp/approved.json --mode draft
  python scripts/wix_blog_migrate.py apply --manifest /tmp/approved.json --mode publish
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List

import boto3

WIX_API = "https://www.wixapis.com"
WIX_ACCOUNT_ID = os.environ.get(
    "WIX_ACCOUNT_ID", "15f02319-40ff-4288-b8e6-69c791adae5e"
)
SOURCE_SITE_ID = os.environ.get(
    "WIX_BLOG_SOURCE_SITE_ID", "c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5"
)
TARGET_SITE_ID = os.environ.get(
    "WIX_SITE_ID", "fcd82f0c-9572-49c7-acfb-88fb05042ece"
)
SECRET_NAME = os.environ.get(
    "WIX_API_KEY_SECRET", "wecare/wix/headless-api-key"
)
AUTHOR_NAME = "Anew by WECARE.DIGITAL"
AUTHOR_EMAIL = "one@wecare.digital"
CATEGORY_LABEL = "Conversations"
FORBIDDEN_MEDIA_NODES = {"IMAGE", "GALLERY", "GIF", "VIDEO", "AUDIO"}
BULK_LIMIT = 20

_api_key: str | None = None


def load_api_key() -> str:
    global _api_key
    if _api_key:
        return _api_key
    raw = boto3.client(
        "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1")
    ).get_secret_value(SecretId=SECRET_NAME).get("SecretString", "")
    try:
        parsed = json.loads(raw)
        value = (
            parsed.get("api_key")
            or parsed.get("apiKey")
            or parsed.get("key")
            or parsed.get("value")
            or ""
        )
    except (TypeError, ValueError):
        value = raw
    _api_key = str(value).strip()
    if not _api_key:
        raise RuntimeError(f"Wix API key secret {SECRET_NAME!r} is empty")
    return _api_key


def request(
    site_id: str, method: str, path: str, body: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    headers = {
        "Authorization": load_api_key(),
        "wix-account-id": WIX_ACCOUNT_ID,
        "wix-site-id": site_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        WIX_API + path, data=payload, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Wix API {method} {path} failed: HTTP {error.code}: {detail[:800]}"
        ) from error


def query_posts(site_id: str, include_content: bool = False) -> List[Dict[str, Any]]:
    fieldsets = ["URL", "SEO"]
    if include_content:
        fieldsets += ["CONTENT_TEXT", "RICH_CONTENT"]
    posts: List[Dict[str, Any]] = []
    cursor = ""
    while True:
        paging: Dict[str, Any] = {"limit": 100}
        if cursor:
            paging["cursor"] = cursor
        data = request(
            site_id,
            "POST",
            "/v3/posts/query",
            {
                "fieldsets": fieldsets,
                "query": {"cursorPaging": paging},
                "skipCount": True,
            },
        )
        posts.extend(data.get("posts", []) or [])
        cursor = str(
            (((data.get("pagingMetadata") or {}).get("cursors") or {}).get("next"))
            or ""
        )
        if not cursor:
            return posts


def export_source(output: Path) -> None:
    posts = query_posts(SOURCE_SITE_ID, include_content=True)
    payload = {
        "sourceSiteId": SOURCE_SITE_ID,
        "count": len(posts),
        "posts": posts,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(posts)} source posts to {output}")


def walk_nodes(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from walk_nodes(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_nodes(nested)


def validate_manifest_post(post: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required = [
        "title",
        "slug",
        "firstPublishedDate",
        "richContent",
        "seoTitle",
        "metaDescription",
        "tags",
    ]
    for key in required:
        if not post.get(key):
            errors.append(f"missing {key}")

    tags = post.get("tags") or []
    if not isinstance(tags, list) or not 1 <= len(tags) <= 3:
        errors.append("tags must contain 1-3 labels")

    for forbidden in ("heroImage", "media", "coverImage"):
        if post.get(forbidden):
            errors.append(f"{forbidden} is forbidden: blog is image-free")

    for node in walk_nodes(post.get("richContent") or {}):
        node_type = str(node.get("type") or "").upper()
        if node_type in FORBIDDEN_MEDIA_NODES:
            errors.append(f"forbidden rich-content media node: {node_type}")

    if str(post.get("authorName") or AUTHOR_NAME) != AUTHOR_NAME:
        errors.append(f"authorName must be {AUTHOR_NAME!r}")
    if str(post.get("category") or CATEGORY_LABEL) != CATEGORY_LABEL:
        errors.append(f"category must be {CATEGORY_LABEL!r}")

    return errors


def load_manifest(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    posts = raw.get("posts") if isinstance(raw, dict) else raw
    if not isinstance(posts, list):
        raise ValueError("Manifest must be a JSON array or an object with a posts array")
    return posts


def validate_manifest(posts: List[Dict[str, Any]]) -> None:
    seen = set()
    failures = []
    for index, post in enumerate(posts):
        slug = str(post.get("slug") or "").strip()
        errors = validate_manifest_post(post)
        if slug in seen:
            errors.append("duplicate slug inside manifest")
        seen.add(slug)
        if errors:
            failures.append((index, slug or "<missing>", errors))
    if failures:
        for index, slug, errors in failures:
            print(f"[{index}] {slug}: " + "; ".join(errors), file=sys.stderr)
        raise ValueError(f"Manifest validation failed for {len(failures)} post(s)")


def ensure_author() -> str:
    data = request(
        TARGET_SITE_ID,
        "GET",
        "/members/v1/members?fieldsets=FULL&paging.limit=100",
    )
    members = data.get("members", []) or []
    for member in members:
        if str((member.get("profile") or {}).get("nickname") or "") == AUTHOR_NAME:
            return str(member["id"])
    for member in members:
        if str(member.get("loginEmail") or "").lower() == AUTHOR_EMAIL.lower():
            updated = request(
                TARGET_SITE_ID,
                "PATCH",
                f"/members/v1/members/{member['id']}",
                {"member": {"profile": {"nickname": AUTHOR_NAME}}},
            )
            return str(updated["member"]["id"])
    created = request(
        TARGET_SITE_ID,
        "POST",
        "/members/v1/members",
        {
            "member": {
                "loginEmail": AUTHOR_EMAIL,
                "contact": {"firstName": "Anew", "lastName": "by WECARE.DIGITAL"},
                "profile": {"nickname": AUTHOR_NAME},
            }
        },
    )
    return str(created["member"]["id"])


def ensure_category() -> str:
    data = request(
        TARGET_SITE_ID, "GET", "/blog/v3/categories?paging.limit=100"
    )
    for category in data.get("categories", []) or []:
        if str(category.get("label") or "").lower() == CATEGORY_LABEL.lower():
            return str(category["id"])
    created = request(
        TARGET_SITE_ID,
        "POST",
        "/blog/v3/categories",
        {
            "category": {
                "label": CATEGORY_LABEL,
                "title": CATEGORY_LABEL,
                "slug": "conversations",
                "language": "en",
            }
        },
    )
    return str(created["category"]["id"])


def ensure_tags(labels: Iterable[str]) -> Dict[str, str]:
    data = request(
        TARGET_SITE_ID,
        "POST",
        "/v3/tags/query",
        {"query": {"cursorPaging": {"limit": 100}}},
    )
    existing = {
        str(tag.get("label") or "").lower(): str(tag.get("id") or "")
        for tag in data.get("tags", []) or []
    }
    resolved: Dict[str, str] = {}
    for label in labels:
        key = label.lower()
        if existing.get(key):
            resolved[label] = existing[key]
            continue
        created = request(
            TARGET_SITE_ID,
            "POST",
            "/v3/tags",
            {"label": label, "language": "en"},
        )
        resolved[label] = str(created["tag"]["id"])
        existing[key] = resolved[label]
    return resolved


def seo_data(post: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tags": [
            {"type": "title", "children": str(post["seoTitle"])},
            {
                "type": "meta",
                "props": {
                    "name": "description",
                    "content": str(post["metaDescription"]),
                },
            },
        ]
    }


def draft_post(
    post: Dict[str, Any],
    member_id: str,
    category_id: str,
    tag_ids: Dict[str, str],
) -> Dict[str, Any]:
    return {
        "title": str(post["title"]).strip(),
        "excerpt": str(post.get("excerpt") or post["metaDescription"]).strip(),
        "featured": False,
        "categoryIds": [category_id],
        "memberId": member_id,
        "tagIds": [tag_ids[label] for label in post.get("tags", [])],
        "hashtags": post.get("hashtags", []) or [],
        "language": "en",
        "richContent": post["richContent"],
        "firstPublishedDate": post["firstPublishedDate"],
        "seoSlug": str(post["slug"]).strip(),
        "seoData": seo_data(post),
    }


def chunks(items: List[Any], size: int) -> Iterable[List[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def apply_manifest(posts: List[Dict[str, Any]], mode: str) -> None:
    validate_manifest(posts)
    existing = {str(post.get("slug") or "") for post in query_posts(TARGET_SITE_ID)}
    pending = [post for post in posts if str(post.get("slug") or "") not in existing]
    skipped = len(posts) - len(pending)
    print(
        f"Validated {len(posts)} posts; {len(pending)} new; {skipped} already exists on target"
    )
    if mode == "validate":
        print("Validation-only mode: no Wix mutation performed.")
        return

    member_id = ensure_author()
    category_id = ensure_category()
    all_labels = sorted({label for post in pending for label in post.get("tags", [])})
    tag_ids = ensure_tags(all_labels)
    prepared = [
        draft_post(post, member_id, category_id, tag_ids) for post in pending
    ]

    publish = mode == "publish"
    successes = 0
    failures = []
    for batch_number, batch in enumerate(chunks(prepared, BULK_LIMIT), start=1):
        data = request(
            TARGET_SITE_ID,
            "POST",
            "/blog/v3/bulk/draft-posts/create",
            {
                "draftPosts": batch,
                "publish": publish,
                "returnFullEntity": False,
            },
        )
        for result in data.get("results", []) or []:
            metadata = result.get("itemMetadata") or {}
            if metadata.get("success"):
                successes += 1
            else:
                failures.append(
                    {
                        "batch": batch_number,
                        "index": metadata.get("originalIndex"),
                        "error": metadata.get("error"),
                    }
                )
        print(
            f"Batch {batch_number}: "
            f"{(data.get('bulkActionMetadata') or {}).get('totalSuccesses', 0)} success, "
            f"{(data.get('bulkActionMetadata') or {}).get('totalFailures', 0)} failure"
        )

    print(f"Completed: {successes} created; {len(failures)} failed; mode={mode}")
    if failures:
        print(json.dumps(failures, indent=2), file=sys.stderr)
        raise RuntimeError("One or more Wix bulk items failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    export_parser = commands.add_parser("export")
    export_parser.add_argument("--output", type=Path, required=True)

    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--manifest", type=Path, required=True)
    apply_parser.add_argument(
        "--mode",
        choices=("validate", "draft", "publish"),
        default="validate",
        help="Default is validate: no Wix mutation. Publish must be explicit.",
    )

    args = parser.parse_args()
    if args.command == "export":
        export_source(args.output)
        return
    posts = load_manifest(args.manifest)
    apply_manifest(posts, args.mode)


if __name__ == "__main__":
    main()
