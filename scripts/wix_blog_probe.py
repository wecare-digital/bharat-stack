#!/usr/bin/env python3
"""Read one published Wix Headless blog post through our own Lambda. Read-only.

WHY THIS EXISTS. docs/blog-migration-standard.md quotes the approved Integrity
article as the editorial reference, and on 2026-09-28 those quotes were stale:
the post had been edited in Wix, and the stale copy had been pinned verbatim in
`.github/workflows/seo-tools-deploy.yml`, so a copy edit turned a perfectly good
Lambda deploy red. The standard names Wix Blog the content source of truth, so
the fix is to re-read live before quoting - which needs a command that exists.

WHY IT GOES THROUGH THE LAMBDA. `wecare-seo-tools` already holds the Wix Headless
client credential and already implements the anonymous-visitor OAuth exchange.
Invoking it is read-only and adds no new credential surface; no Wix secret enters
this process, this shell, or the output. Same reasoning as
scripts/rcs_template_sync.py.

    python scripts/wix_blog_probe.py                                  # Integrity
    python scripts/wix_blog_probe.py --slug some-other-slug
    python scripts/wix_blog_probe.py --json
    python scripts/wix_blog_probe.py --check                          # gate, exit 1

`--check` applies the same structural assertions the deploy workflow uses, so the
gate can be reproduced locally without pushing.
"""
from __future__ import annotations

import argparse
import json
import sys

FUNCTION = "wecare-seo-tools"
REGION = "us-east-1"
DEFAULT_SLUG = "integrity-honoring-our-word"

MEDIA_NODES = {"IMAGE", "GALLERY", "GIF", "VIDEO", "AUDIO"}

#: Publication rules from docs/blog-migration-standard.md that are fixed as rules
#: rather than as cadence, so they are safe to assert and prose is not.
EXPECTED_AUTHOR = "Anew by WECARE.DIGITAL"
EXPECTED_CATEGORY = "Conversations"
MIN_PARAGRAPHS = 4
MIN_CHARS = 400


def fetch(slug: str) -> dict:
    import boto3

    path = f"/seo-tools/blog-public/{slug}"
    payload = {
        "requestContext": {"apiId": "probe",
                           "http": {"method": "GET", "path": path, "sourceIp": "127.0.0.1"}},
        "rawPath": path,
    }
    resp = boto3.client("lambda", region_name=REGION).invoke(
        FunctionName=FUNCTION, InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode())
    raw = resp["Payload"].read().decode()
    if resp.get("FunctionError"):
        raise RuntimeError(f"probe failed: {raw[:300]}")
    outer = json.loads(raw)
    status = int(outer.get("statusCode") or 0)
    if status != 200:
        raise RuntimeError(f"HTTP {status}: {(outer.get('body') or '')[:300]}")
    body = json.loads(outer.get("body") or "{}")
    if body.get("ok") is not True:
        raise RuntimeError(f"handler reported not-ok: {str(body)[:300]}")
    return body.get("post") or {}


def flatten(post: dict) -> tuple[list[str], list[str]]:
    """Return (paragraphs, node_types) from the Ricos rich-content tree."""
    node_types: list[str] = []
    paragraphs: list[str] = []

    def walk(value) -> None:
        if isinstance(value, dict):
            kind = str(value.get("type") or "").upper()
            if kind:
                node_types.append(kind)
            text = (value.get("textData") or {}).get("text")
            if text:
                paragraphs.append(text)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk((post.get("richContent") or {}).get("nodes") or [])
    return paragraphs, node_types


def check(post: dict, slug: str, paragraphs: list[str], node_types: list[str]) -> list[str]:
    text = "\n".join(paragraphs)
    problems = []
    if post.get("slug") != slug:
        problems.append(f"slug is {post.get('slug')!r}, expected {slug!r}")
    if post.get("authorName") != EXPECTED_AUTHOR:
        problems.append(f"authorName is {post.get('authorName')!r}, expected {EXPECTED_AUTHOR!r}")
    if post.get("category") != EXPECTED_CATEGORY:
        problems.append(f"category is {post.get('category')!r}, expected {EXPECTED_CATEGORY!r}")
    if post.get("coverImage"):
        problems.append("coverImage is set; the standard forbids a cover image")
    if len(paragraphs) < MIN_PARAGRAPHS:
        problems.append(f"{len(paragraphs)} text nodes, expected >= {MIN_PARAGRAPHS}")
    if len(text) < MIN_CHARS:
        problems.append(f"body is {len(text)} chars, expected >= {MIN_CHARS}")
    media = sorted(MEDIA_NODES & set(node_types))
    if media:
        problems.append(f"migrated media nodes present: {', '.join(media)}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", default=DEFAULT_SLUG)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", action="store_true",
                    help="apply the deploy gate's structural assertions, exit 1 on failure")
    args = ap.parse_args(argv)

    post = fetch(args.slug)
    paragraphs, node_types = flatten(post)
    text = "\n".join(paragraphs)
    problems = check(post, args.slug, paragraphs, node_types)

    if args.json:
        print(json.dumps({
            "slug": post.get("slug"), "title": post.get("title"),
            "authorName": post.get("authorName"), "category": post.get("category"),
            "coverImage": post.get("coverImage") or None,
            "paragraphCount": len(paragraphs), "charCount": len(text),
            "mediaNodeTypes": sorted(MEDIA_NODES & set(node_types)),
            "paragraphs": paragraphs, "problems": problems,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"title      {post.get('title')}")
        print(f"slug       {post.get('slug')}")
        print(f"author     {post.get('authorName')}")
        print(f"category   {post.get('category')}")
        print(f"cover      {post.get('coverImage') or '(none)'}")
        print(f"structure  {len(paragraphs)} paragraphs, {len(text)} chars, "
              f"media nodes: {sorted(MEDIA_NODES & set(node_types)) or 'none'}\n")
        for i, para in enumerate(paragraphs, 1):
            print(f"  [{i}] {para}\n")
        if problems:
            print("PROBLEMS")
            for p in problems:
                print(f"  - {p}")
        else:
            print("No structural problems. Prose is NOT asserted - Wix is the source of truth.")

    return 1 if (args.check and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
