#!/usr/bin/env python3
"""Assert the provider policy against the LIVE AWS account, not just the tree.

Why this exists
---------------
``scripts/check-provider-policy.sh`` scans source. It reported 0 violations
across 8 rules while Airtel SMS was still running in production: the retirement
commits (12ee8317, baf1dabe, dda52a68) removed the code but nothing removed the
deployed Lambda, its API routes, its tables or its secrets. A clean tree was
read as a clean estate, and those are different claims.

On 2026-09-20 this script's first run found, in account 775261844268:

  * wecare-sms-in-airtel   - 528 invocations/30d, routes wired, receiving real
                             Airtel DLRs (``airtel_dlr_received``) as of 09-13
  * wecare-sinch-dlr       - 7 invocations/30d
  * 11 API Gateway routes  - 9x /sms-in/airtel*, 2x /webhook/sinch-dlr
  * 4 DynamoDB tables      - Airtel x3 + PayUWebhookLog, all empty
  * 5 Secrets Manager entries still resolvable for Airtel and Sinch SMS
  * 9 orphaned Lambdas     - live, but no source in this repo and absent from
                             deploy_all_lambdas.py, so unpatchable

What it checks
--------------
1. RETIRED PROVIDERS    no live Lambda, route, table or secret belongs to a
                        retired provider (PayU, Airtel, Sinch SMS).
2. UNPATCHABLE FUNCTIONS
                        every live Lambda is either in the portable deploy map
                        or on the short list of externally-deployed functions.
                        The question is whether a fix can REACH production, not
                        whether source exists somewhere in the tree.

Approved exceptions are Sinch RCS for India only - the RCS send path, its DLR
handler, its routes and its secret. See .kiro/steering/ for the provider matrix.

Known residue
-------------
KNOWN_RESIDUE below records what was already present when this gate was written.
Anything in it is reported as TRACKED and does not fail the build; anything NOT
in it fails immediately, which is the regression protection. Delete entries as
the residue is actually removed - the list only ever shrinks.

Usage
-----
    python scripts/check_provider_policy_live.py           # gate
    python scripts/check_provider_policy_live.py --report  # never fail, list all

Exit codes
----------
    0  no untracked violations
    1  untracked violation found
    2  could not query AWS
"""

from __future__ import annotations

import argparse
import sys

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    print("boto3 required: .venv/bin/python -m pip install boto3", file=sys.stderr)
    raise SystemExit(2)

REGION = "us-east-1"
HTTP_API_ID = "zllr9lrg7j"

# Retired providers. Matched case-insensitively against resource names.
RETIRED = ("payu", "airtel", "elevenlabs")
# Sinch is retired for SMS but APPROVED for India RCS, so it needs a narrower
# rule than a bare substring: flag 'sinch' only when it is not an RCS resource.
SINCH_APPROVED_RCS = ("rcs",)

# Live Lambdas that this repo deliberately does not deploy through
# scripts/deploy_all_lambdas.py. Both are documented in
# .kiro/steering/lambda-snapstart-deploy.md.
EXTERNALLY_DEPLOYED = {
    "wecare-seo-tools",      # scripts/deploy_seo_tools.py owns it
    "wecare-docs-scraper",   # PackageType=Image, GitHub Actions
    # Lambda@Edge, source at amplify/functions/edge/get-miss-redirect. It cannot
    # go in the deploy map: CloudFront associates Lambda@Edge by published
    # VERSION, and the deploy map's contract is publish-then-move-the-`live`-alias.
    # An alias is not a valid Lambda@Edge association target, so deploying it that
    # way would publish a version CloudFront never picks up and then report
    # success. It has no `live` alias for the same reason. Owned by its own
    # deployer; see docs/SECURE-FILE-SHARING.md.
    "wecare-get-miss-redirect",
}

# Residue still present. This list only ever shrinks; anything NOT in it fails.
#
# 2026-09-20 teardown removed all PayU, Airtel and Sinch SMS resources:
#   11 API routes (9x /sms-in/airtel*, 2x /webhook/sinch-dlr)  -> deleted,
#      recorded in docs/deleted-routes-20260920-0715.json
#   wecare-sms-in-airtel, wecare-sinch-dlr, wecare-outbound-voice -> deleted
#   4 tables (Airtel x3 + PayUWebhookLog) -> deleted, each re-checked
#      ItemCount==0 immediately before the call
#   5 secrets -> scheduled for deletion with a 30-day recovery window,
#      NOT force-deleted, recoverable until 2026-10-20
# Deployed code for every orphan was archived first
# (~/.local/share/wecare-orphan-lambda-archive/), so those deletions are
# reversible despite the source having been removed from this repo.
#
# What remains is NOT a retired provider. These are orphans: live Lambdas with
# no source here, so they cannot be patched, reviewed or redeployed. Five of
# them are actively serving traffic (postcall-sms 64, mcp 25, enable-mcp 5
# invocations per 30d), so the fix is to restore their source, not delete them.
# wecare-temp-code-inspector is a temporary function still in production at 2
# invocations/30d and wants a decision rather than a default.
# EMPTY, and it should stay that way. Reaching zero means any retired-provider
# resource or any unpatchable function that appears from here on FAILS the gate
# instead of being tolerated as a known exception.
#
# wecare-temp-code-inspector was deleted rather than tracked: it accepted an
# arbitrary `url` from its event, fetched it, unzipped it and grepped the
# contents - an SSRF primitive in production with no source and no owner.
KNOWN_RESIDUE = {
    "lambda": set(),
    "route": set(),
    "table": set(),
    "secret": set(),
}


def is_retired(name: str) -> str | None:
    """Return the retired provider this resource belongs to, or None."""
    low = name.lower()
    for p in RETIRED:
        if p in low:
            return p
    if "sinch" in low and not any(ok in low for ok in SINCH_APPROVED_RCS):
        return "sinch-sms"
    return None


def collect(report_only: bool) -> tuple[list, list]:
    """Return (untracked, tracked) findings as (kind, name, provider) tuples."""
    untracked: list[tuple[str, str, str]] = []
    tracked: list[tuple[str, str, str]] = []

    def record(kind: str, name: str, provider: str):
        bucket = tracked if name in KNOWN_RESIDUE.get(kind, ()) else untracked
        bucket.append((kind, name, provider))

    lam = boto3.client("lambda", region_name=REGION)
    live_fns: set[str] = set()
    for page in lam.get_paginator("list_functions").paginate():
        live_fns |= {f["FunctionName"] for f in page["Functions"]}

    for fn in sorted(live_fns):
        p = is_retired(fn)
        if p:
            record("lambda", fn, p)

    # Orphan check: live but not deployable from this repo.
    try:
        from deploy_all_lambdas import FUNCTION_MAP  # type: ignore
        mapped = set(FUNCTION_MAP)
    except Exception:
        import re
        import subprocess
        out = subprocess.run(
            [sys.executable, "scripts/deploy_all_lambdas.py", "--list"],
            capture_output=True, text=True).stdout
        mapped = set(re.findall(r"\b(?:stack-)?wecare[a-z0-9-]*", out))
    # The label says "not in the deploy map", not "no source", because those are
    # different findings and the distinction is the whole value of the check.
    # wecare-pstn-softphone and wecare-get-miss-redirect were both reported as
    # `orphan-no-source` while their source sat in amplify/functions - so the
    # message sent a reader hunting for code that was already there, and the real
    # defect (five live routes that no supported deploy path could reach) read as
    # a bookkeeping miss. What makes a function unpatchable here is the absence of
    # a deploy route, whether or not the source exists.
    for fn in sorted(live_fns - mapped - EXTERNALLY_DEPLOYED):
        record("lambda", fn, "orphan-not-in-deploy-map")

    api = boto3.client("apigatewayv2", region_name=REGION)
    try:
        # get_routes has no boto3 paginator and returns only 25 items per page.
        # This API carries ~345 routes, so reading page 1 undercounts badly - the
        # first version of this script reported 4 of 11 Airtel routes and still
        # printed a reassuring summary. Always drain NextToken.
        routes, token, pages = [], None, 0
        while True:
            kwargs = {"ApiId": HTTP_API_ID, "MaxResults": "100"}
            if token:
                kwargs["NextToken"] = token
            resp = api.get_routes(**kwargs)
            routes += resp["Items"]
            pages += 1
            token = resp.get("NextToken")
            if not token:
                break
        print(f"routes scanned : {len(routes)} across {pages} page(s)")
        for r in sorted(routes, key=lambda x: x["RouteKey"]):
            p = is_retired(r["RouteKey"])
            if p:
                record("route", r["RouteKey"], p)
    except (ClientError, BotoCoreError) as exc:
        print(f"warning: could not read HTTP API {HTTP_API_ID}: {type(exc).__name__}",
              file=sys.stderr)

    ddb = boto3.client("dynamodb", region_name=REGION)
    for page in ddb.get_paginator("list_tables").paginate():
        for t in page["TableNames"]:
            p = is_retired(t)
            if p:
                record("table", t, p)

    sm = boto3.client("secretsmanager", region_name=REGION)
    for page in sm.get_paginator("list_secrets").paginate():
        for s in page["SecretList"]:
            p = is_retired(s["Name"])
            if p:
                record("secret", s["Name"], p)

    return untracked, tracked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true",
                    help="list everything and always exit 0")
    args = ap.parse_args()

    print(f"account region : {REGION}")
    print("rule set       : retired providers = "
          + ", ".join(p.title() for p in RETIRED)
          + ", Sinch SMS (Sinch RCS India is approved)")
    try:
        untracked, tracked = collect(args.report)
    except (ClientError, BotoCoreError) as exc:
        print(f"could not query AWS: {type(exc).__name__}", file=sys.stderr)
        return 2

    if tracked:
        print(f"\nTRACKED residue ({len(tracked)}) - known, awaiting approved teardown:")
        for kind, name, prov in sorted(tracked):
            print(f"  {kind:7} {name:46} [{prov}]")

    if untracked:
        print(f"\nUNTRACKED VIOLATIONS ({len(untracked)}):")
        for kind, name, prov in sorted(untracked):
            print(f"  {kind:7} {name:46} [{prov}]")
        print("\nLIVE PROVIDER POLICY FAILED - a retired provider or an "
              "unpatchable function appeared in the account.")
        print("If this is intentional, add it to KNOWN_RESIDUE with a reason.")
        return 0 if args.report else 1

    print("\nLIVE PROVIDER POLICY OK - no untracked violations.")
    if tracked:
        print(f"NOTE: {len(tracked)} tracked item(s) still to remove. "
              "This gate does not consider the estate clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
