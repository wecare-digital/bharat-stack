#!/usr/bin/env python3
"""Fail if a retired hostname is allowed by any live CORS allow-list, or is
reachable as effective configuration in this repository.

Why this gate exists
--------------------
`stack.wecare.digital` was retired on 2026-09-25 when the `stack` CNAME was
removed from Route 53. It is **NXDOMAIN** — measured, not assumed. Amplify serves
the apex directly and the subdomain had only ever 301'd to it.

The cleanup that accompanied the retirement reached the API Gateway CORS
configuration, the Amplify custom rules, the branch environment, the Cognito
callback and logout lists, and every source allow-list. It missed exactly one
place, found on 2026-09-26: the **S3 bucket `app.wecare.digital`** still carried

    AllowedOrigins: [ "https://stack.wecare.digital", ... ]

That bucket is the live media CDN behind CloudFront `ERCXSFDL0VM8X` — it serves
the logos, the RCS video, and the WhatsApp template media. So the one surface that
kept the dead origin was also the one with the widest reach.

It survived because nothing in this repository configured it. There is no
`put_bucket_cors` call, no CDK construct and no CloudFormation resource for that
bucket's CORS: it was set in the console and then never re-read. A setting with no
generator has no diff, so no review would ever have surfaced it. This script is
the substitute for the missing generator — it does not write the config, but it
refuses to pass while the config is wrong.

Why a dead origin still matters
-------------------------------
It is not merely untidy. An allow-list entry for a hostname nobody owns is a
standing offer: whoever can next resolve that name gets credentialed
cross-origin reads of the media bucket. `stack.wecare.digital` is a subdomain of
a domain we control, so the realistic risk is low — but the same class of entry
is exactly how a dangling-DNS takeover becomes a CORS bypass, and the cost of
removing it is zero. It is also dead weight in every preflight decision.

Comments are stripped before matching
-------------------------------------
Thirteen source files name `stack.wecare.digital` in a comment that explains why
it was retired — `lambda_utils/response.py`, `link-resources.ts`,
`waba-management/handler.py`, `_app.tsx`, `sw.js`, `capacitor.ts`, the Android
manifest, the iOS plist, both native templates, `deploy_site_language.py`,
`google-language-relay.sh` and `.env.local.example`. That is the documentation
working. Reporting it would be reporting the record of the fix as the defect,
which is a mistake this repository's tests have had to correct three times, so
`#`, `//`, `/* */` and `<!-- -->` are blanked before the scan runs.

`tests/test_response.py` goes further and assembles the hostname at runtime
(`'https://' + 'stack.' + 'wecare.digital'`) precisely so a literal scan cannot
trip on a test whose whole purpose is asserting the host is absent. Prose is out
of scope by design: `docs/`, `seo/`, `.kiro/` and every `*.md` are excluded, and
`docs/execution/snapshots/` is excluded absolutely — those files are immutable
rollback evidence and are SUPPOSED to contain the old value.

Usage
-----
    python scripts/check_retired_origins.py          # live + repo
    python scripts/check_retired_origins.py --repo    # repo only, no AWS calls

Exit code 0 means no retired origin is allowed anywhere. Non-zero names every
surface that still carries one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGION = "us-east-1"

# Hostnames that must never appear in a CORS allow-list, with the reason. Keyed on
# the bare host so both the scheme-qualified origin and a stray bare reference are
# caught.
RETIRED_HOSTS = {
    "stack.wecare.digital": (
        "retired 2026-09-25 with the Route 53 CNAME; NXDOMAIN. Amplify serves the "
        "apex and this host only ever 301'd to it, and a redirecting host cannot be "
        "a usable allowed origin because the browser compares Access-Control-Allow-"
        "Origin to the literal request origin and never follows it"
    ),
}

# Extensions that can carry effective configuration. Prose and snapshots are not
# scanned; see the module docstring.
SCANNED_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".json", ".yml", ".yaml", ".sh", ".xml", ".plist", ".template", ".example",
}
EXCLUDED_DIRS = {
    ".git", ".venv", "node_modules", ".next", ".scratch", ".pytest_cache",
    "docs", "seo", ".kiro", "tests", "dist", "build", "coverage",
}
# This file is the registry, so it necessarily contains every value it forbids -
# in RETIRED_HOSTS and in the docstring that explains the retirement. Its first
# run flagged itself five times, which is the same "record of the fix reported as
# the defect" trap the docstring warns about, arriving by the shortest possible
# route. `check_design_drift.py` avoids it by only ever scanning `src/`; this
# script scans the whole tree, so the exclusion has to be explicit.
SELF = Path(__file__).resolve()


def strip_comments(text: str, suffix: str) -> str:
    """Blank comments, preserving line numbers so reported locations stay usable."""
    # Block comments: C-family and XML/HTML.
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)

    out = []
    for line in text.splitlines():
        if suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            # Avoid eating the // in https://
            line = re.sub(r"(?<!:)//.*$", "", line)
        elif suffix in (".py", ".sh", ".yml", ".yaml", ".example", ".template"):
            line = re.sub(r"(?<!\$)#.*$", "", line)
        out.append(line)
    return "\n".join(out)


def scan_repo() -> list[str]:
    """Retired hosts appearing in effective repository configuration."""
    violations = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        if path.resolve() == SELF:
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not any(h in raw for h in RETIRED_HOSTS):
            continue
        cleaned = strip_comments(raw, path.suffix)
        for lineno, line in enumerate(cleaned.splitlines(), 1):
            for host in RETIRED_HOSTS:
                if host in line:
                    violations.append(f"{rel}:{lineno}  {host}  {line.strip()[:120]}")
    return violations


def _client(service):
    import boto3
    return boto3.client(service, region_name=REGION)


def scan_live() -> tuple[list[str], list[str], int]:
    """Retired hosts allowed by a live CORS surface.

    Returns (violations, surfaces_checked, error_count). A non-zero error count
    means the sweep is PARTIAL and its silence must not be read as a pass.
    """
    from botocore.exceptions import ClientError

    violations, checked, errors = [], [], 0

    def flag(where, blob):
        for host in RETIRED_HOSTS:
            if host in str(blob):
                violations.append(f"{where}  allows {host}")

    # S3 bucket CORS. Discovered rather than hardcoded, so a new bucket is covered.
    try:
        s3 = _client("s3")
        for b in s3.list_buckets().get("Buckets", []):
            name = b["Name"]
            try:
                rules = s3.get_bucket_cors(Bucket=name).get("CORSRules", [])
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "NoSuchCORSConfiguration":
                    errors += 1
                    print(f"  ! s3://{name} cors read failed: "
                          f"{exc.response.get('Error', {}).get('Code')}")
                continue
            checked.append(f"s3://{name} cors")
            flag(f"s3://{name} cors", rules)
    except Exception as exc:  # noqa: BLE001
        errors += 1
        print(f"  ! s3 sweep failed: {type(exc)}")

    # API Gateway HTTP API CORS.
    try:
        agw = _client("apigatewayv2")
        for api in agw.get_apis().get("Items", []):
            label = f"apigatewayv2 {api.get('ApiId')} ({api.get('Name')}) cors"
            checked.append(label)
            flag(label, api.get("CorsConfiguration") or {})
    except Exception as exc:  # noqa: BLE001
        errors += 1
        print(f"  ! apigatewayv2 sweep failed: {type(exc)}")

    # Lambda environment variables that carry an origin allow-list.
    try:
        lam = _client("lambda")
        for page in lam.get_paginator("list_functions").paginate():
            for fn in page.get("Functions", []):
                env = (fn.get("Environment") or {}).get("Variables") or {}
                relevant = {k: v for k, v in env.items()
                            if "ORIGIN" in k.upper() or "CORS" in k.upper()}
                if relevant:
                    label = f"lambda {fn['FunctionName']} env"
                    checked.append(label)
                    flag(label, relevant)
    except Exception as exc:  # noqa: BLE001
        errors += 1
        print(f"  ! lambda sweep failed: {type(exc)}")

    # CloudFront response-headers policies can carry their own CORS allow-list.
    try:
        cf = _client("cloudfront")
        for item in (cf.list_response_headers_policies()
                     .get("ResponseHeadersPolicyList", {}).get("Items", [])):
            pol = item.get("ResponseHeadersPolicy", {})
            cfg = pol.get("ResponseHeadersPolicyConfig", {})
            cors = cfg.get("CorsConfig")
            if cors:
                label = f"cloudfront rhp {cfg.get('Name')}"
                checked.append(label)
                flag(label, cors)
    except Exception as exc:  # noqa: BLE001
        errors += 1
        print(f"  ! cloudfront sweep failed: {type(exc)}")

    return violations, checked, errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", action="store_true",
                    help="scan the repository only; make no AWS calls")
    args = ap.parse_args()

    print("retired hosts  : " + ", ".join(sorted(RETIRED_HOSTS)))
    for host, why in sorted(RETIRED_HOSTS.items()):
        print(f"  {host}\n      {why}")
    print()

    repo_v = scan_repo()
    print(f"repository     : {len(repo_v)} violation(s) in effective config "
          f"(comments stripped)")

    live_v, checked, errors = ([], [], 0)
    if not args.repo:
        live_v, checked, errors = scan_live()
        print(f"live surfaces  : {len(checked)} checked, {len(live_v)} violation(s), "
              f"{errors} collector error(s)")

    if repo_v or live_v:
        print()
        for v in repo_v:
            print(f"  REPO  {v}")
        for v in live_v:
            print(f"  LIVE  {v}")
        print("\nRETIRED ORIGIN CHECK FAILED - a hostname that no longer resolves is "
              "still allowed. Remove it; do not allowlist it here.")
        return 1

    if errors:
        print("\nPARTIAL - no violation found, but a collector errored, so this is "
              "NOT a pass. Fix the read and re-run.")
        return 2

    print("\nRETIRED ORIGIN CHECK PASSED - no retired hostname is allowed by any "
          "scanned surface.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
