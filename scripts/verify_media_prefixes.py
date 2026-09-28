#!/usr/bin/env python3
"""Verify the Lambda fleet's S3 usage against the one media bucket and its two roots.

Why this exists
---------------
The merge into `wecare-digital-get` mapped `app.wecare.digital/<X>` to `o/<X>`, but the
handler prefixes kept the pre-merge shape, so the fleet read and wrote one level above its
own data. Nothing failed loudly: the apex host serves the whole bucket, so a key written to
the root returned HTTP 200. The breakage only showed up as a missing invoice logo, an
empty cleanup sweep, and a document download pointing at a bucket that does not exist.

Four things are checked, and each one corresponds to a defect that actually shipped:

1. **No dead bucket names.** `app.wecare.digital` (deleted), `wecare-digital-media` and
   `wecare-digital-documents` (never existed) must not appear in handler source or in live
   Lambda configuration.
2. **Keys are rooted.** Every S3 key prefix must sit under `o/` or `secure/`.
3. **Import precedes use.** `media_paths` imported BELOW its first use is a module-scope
   NameError that byte-compiles cleanly and only fails at runtime. Three handlers shipped
   that way for one deploy cycle; this is the check that catches it statically.
4. **The hosts still map as documented.** `o/` is only load-bearing because
   app.wecare.digital serves this bucket through origin path `/o`. If that ever changes,
   the convention needs rewriting, not enforcing.

    python scripts/verify_media_prefixes.py            # source checks only
    python scripts/verify_media_prefixes.py --live     # also check AWS

Exit status: 0 all checks pass, 1 otherwise.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FUNCTIONS = ROOT / "amplify" / "functions"
MEDIA_PATHS = FUNCTIONS / "shared" / "lambda_utils" / "media_paths.py"

BUCKET = "wecare-digital-get"
DEAD_BUCKETS = ["app.wecare.digital", "wecare-digital-media", "wecare-digital-documents"]
PUBLIC_ROOT = "o/"
SECURE_ROOT = "secure/"

# The distribution that makes `o/` load-bearing, and the origin path it must keep.
LEGACY_HOST_DISTRIBUTION = "E1DP37QIS4G0T4"
LEGACY_HOST_ORIGIN_PATH = "/o"

# An S3 key: a string constant beginning with a known top-level folder name.
KEYISH_RE = re.compile(r"(?:stack|stream|public|whatsapp-media|obd-audio|media)/")


class Result:
    def __init__(self) -> None:
        self.failed = 0
        self.passed = 0

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
            print(f"  ok    {name}" + (f"  [{detail}]" if detail else ""))
        else:
            self.failed += 1
            print(f"  FAIL  {name}" + (f"  [{detail}]" if detail else ""))


def handler_files() -> list[pathlib.Path]:
    return [p for p in sorted(FUNCTIONS.rglob("*.py"))
            if p != MEDIA_PATHS and "__pycache__" not in p.parts
            and "/tests/" not in p.as_posix()]


def check_no_dead_buckets(r: Result) -> None:
    print("\n1. no dead bucket names in handler source")
    offenders: list[str] = []
    files = handler_files()
    for p in files:
        parsed = parse(p)
        if parsed is None:
            continue
        tree, _src, docstrings = parsed
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in docstrings:
                continue  # prose explaining the history is expected, and necessary
            if node.value in DEAD_BUCKETS:
                offenders.append(f"{p.relative_to(FUNCTIONS)}:{node.lineno} {node.value}")
    r.add("no dead bucket literal is used as a value", not offenders,
          "; ".join(offenders[:4]) if offenders else f"{len(files)} files scanned")


def parse(p: pathlib.Path):
    """(tree, source, docstring_node_ids) or None when the file will not parse.

    Text scanning was wrong twice here, in opposite directions, which is why this is an
    AST now:

    * Per-LINE scanning missed rooting that sits on a continuation line, because
      `media_paths.public(` ends up on the previous physical line. Three false positives.
    * Per-STATEMENT scanning then flagged PROSE, because a docstring explaining the `o/`
      convention legitimately contains the text `media_paths.` and `stack/`. One false
      positive, in the very file being documented.

    An AST distinguishes code from the text that describes it, which is exactly the
    distinction both mistakes turned on.
    """
    src = p.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    return tree, src, docstrings


def enclosing_statements(tree):
    """Map id(node) -> nearest enclosing statement, so a whole statement can be re-read."""
    owner = {}
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.stmt):
            for child in ast.walk(stmt):
                owner.setdefault(id(child), stmt)
    return owner


def check_keys_rooted(r: Result) -> None:
    print("\n2. every S3 key prefix is rooted in o/ or secure/")
    offenders: list[str] = []
    for p in handler_files():
        parsed = parse(p)
        if parsed is None:
            offenders.append(f"{p.relative_to(FUNCTIONS)} does not parse")
            continue
        tree, src, docstrings = parsed
        owner = enclosing_statements(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in docstrings:
                continue  # prose, not a key
            key = node.value
            if not KEYISH_RE.match(key) or key.startswith((PUBLIC_ROOT, SECURE_ROOT)):
                continue
            stmt = owner.get(id(node))
            stmt_src = ast.get_source_segment(src, stmt) or "" if stmt else ""
            # Rooted at runtime by a media_paths call in the same statement, or used only
            # to CLASSIFY a legacy string rather than to address an object.
            if "media_paths." in stmt_src or ".startswith(" in stmt_src:
                continue
            offenders.append(f"{p.relative_to(FUNCTIONS)}:{node.lineno} {key}")
    r.add("no un-rooted key addresses an object", not offenders,
          "; ".join(offenders[:4]) if offenders else "all rooted")


def check_import_before_use(r: Result) -> None:
    print("\n3. media_paths is imported above its first MODULE-SCOPE use")
    offenders: list[str] = []
    for p in handler_files():
        parsed = parse(p)
        if parsed is None:
            continue
        tree, _src, _docstrings = parsed

        imp = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "lambda_utils" \
                    and any(a.name == "media_paths" for a in node.names):
                imp = node.lineno if imp is None else min(imp, node.lineno)

        # Only MODULE-SCOPE uses can raise at import time. A reference inside a function
        # body is resolved when that function is called, by which point the import has run
        # regardless of where it sits - so flagging those would be noise.
        module_scope_uses = []
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for node in ast.walk(stmt):
                if isinstance(node, ast.Name) and node.id == "media_paths":
                    module_scope_uses.append(node.lineno)
        if not module_scope_uses:
            continue
        first = min(module_scope_uses)
        if imp is None or imp > first:
            where = f"import@{imp}" if imp else "NO IMPORT"
            offenders.append(f"{p.relative_to(FUNCTIONS)} {where} use@{first}")
    r.add("no module-scope NameError from import ordering", not offenders,
          "; ".join(offenders[:4]) if offenders else "ordering correct")


def check_live(r: Result) -> None:
    print("\n4. live AWS configuration")
    try:
        import boto3
    except ImportError:
        r.add("boto3 available", False, "pip install boto3")
        return

    lam = boto3.client("lambda", region_name="us-east-1")
    bad: list[str] = []
    checked = 0
    for page in lam.get_paginator("list_functions").paginate():
        for f in page["Functions"]:
            env = (f.get("Environment") or {}).get("Variables") or {}
            checked += 1
            for k, v in env.items():
                if isinstance(v, str) and v in DEAD_BUCKETS:
                    bad.append(f"{f['FunctionName']}.{k}={v}")
    r.add("no live env var names a dead bucket", not bad,
          "; ".join(bad[:4]) if bad else f"{checked} functions checked")

    s3 = boto3.client("s3", region_name="us-east-1")
    roots = {c["Prefix"] for c in s3.list_objects_v2(
        Bucket=BUCKET, Delimiter="/").get("CommonPrefixes", [])}
    r.add("bucket has exactly the two documented roots",
          roots == {PUBLIC_ROOT, SECURE_ROOT}, f"found {sorted(roots)}")

    cf = boto3.client("cloudfront")
    try:
        cfg = cf.get_distribution_config(Id=LEGACY_HOST_DISTRIBUTION)["DistributionConfig"]
        origin = cfg["Origins"]["Items"][0]
        r.add("legacy host still serves this bucket via origin path /o",
              origin["OriginPath"] == LEGACY_HOST_ORIGIN_PATH and BUCKET in origin["DomainName"],
              f"path={origin['OriginPath']!r} origin={origin['DomainName']}")
    except Exception as exc:  # noqa: BLE001
        r.add("legacy host distribution readable", False, type(exc).__name__)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also check AWS configuration")
    args = ap.parse_args()

    if not MEDIA_PATHS.is_file():
        sys.exit(f"missing {MEDIA_PATHS}")

    print(f"media prefix verification - bucket {BUCKET}")
    r = Result()
    check_no_dead_buckets(r)
    check_keys_rooted(r)
    check_import_before_use(r)
    if args.live:
        check_live(r)
    else:
        print("\n4. live AWS configuration  (skipped, pass --live)")

    print(f"\n{r.passed} passed, {r.failed} failed")
    return 1 if r.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
