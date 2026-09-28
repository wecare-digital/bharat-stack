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

IMPORT_RE = re.compile(r"\s*from lambda_utils import .*\bmedia_paths\b")
# A quoted S3 key prefix: starts with a known top-level folder name.
KEYISH_RE = re.compile(
    r"""['"]((?:stack|stream|public|whatsapp-media|obd-audio|media)/[^'"]*)['"]""")


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
    for p in handler_files():
        for i, line in enumerate(p.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("*"):
                continue  # prose explaining the history is expected
            for dead in DEAD_BUCKETS:
                if f"'{dead}'" in line or f'"{dead}"' in line:
                    offenders.append(f"{p.relative_to(FUNCTIONS)}:{i} {dead}")
    r.add("no dead bucket literal is used as a value", not offenders,
          "; ".join(offenders[:4]) if offenders else f"{len(handler_files())} files scanned")


def logical_lines(text: str):
    """Yield (start_line, source) for each logical statement.

    Line-at-a-time scanning produced three false positives: a key split across a
    continuation line has its `media_paths.public(` on the PREVIOUS physical line, so the
    rooting is invisible to a per-line check. Statements are the correct unit. Comments are
    stripped first, because a trailing `# e.g. "stack/..."` is documentation, not a key.
    """
    depth = 0
    buf: list[str] = []
    start = 1
    for i, raw in enumerate(text.splitlines(), 1):
        code = re.sub(r"(?<!['\"])#.*$", "", raw)  # crude, but keys here are never after #
        if not buf:
            start = i
        buf.append(code)
        depth += code.count("(") + code.count("[") + code.count("{")
        depth -= code.count(")") + code.count("]") + code.count("}")
        if depth <= 0 and not code.rstrip().endswith("\\"):
            yield start, " ".join(buf)
            buf, depth = [], 0
    if buf:
        yield start, " ".join(buf)


def check_keys_rooted(r: Result) -> None:
    print("\n2. every S3 key prefix is rooted in o/ or secure/")
    offenders: list[str] = []
    for p in handler_files():
        for lineno, stmt in logical_lines(p.read_text()):
            for m in KEYISH_RE.finditer(stmt):
                key = m.group(1)
                if key.startswith((PUBLIC_ROOT, SECURE_ROOT)):
                    continue
                # Rooted at runtime by a media_paths call in the same statement, or used
                # only to CLASSIFY a legacy string rather than to address an object.
                if "media_paths." in stmt or ".startswith(" in stmt:
                    continue
                offenders.append(f"{p.relative_to(FUNCTIONS)}:{lineno} {key}")
    r.add("no un-rooted key addresses an object", not offenders,
          "; ".join(offenders[:4]) if offenders else "all rooted")


def check_import_before_use(r: Result) -> None:
    print("\n3. media_paths is imported above its first use")
    offenders: list[str] = []
    for p in handler_files():
        lines = p.read_text().splitlines()
        imp = use = None
        for i, line in enumerate(lines, 1):
            if imp is None and IMPORT_RE.match(line):
                imp = i
                continue
            if use is None and "media_paths." in line and not line.lstrip().startswith("#"):
                use = i
        if use is not None and (imp is None or imp > use):
            where = f"import@{imp}" if imp else "NO IMPORT"
            offenders.append(f"{p.relative_to(FUNCTIONS)} {where} use@{use}")
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
