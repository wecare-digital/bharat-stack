#!/usr/bin/env python3
"""Give every Lambda log group a retention period.

The gap
-------
13 of 67 `wecare-*` Lambda log groups had `retentionInDays` unset, which in
CloudWatch means **never expires**. Two costs, and the second is the one that matters:

* Storage is billed indefinitely for data nobody will read.
* Execution logs hold masked phone numbers, message ids and request ids. Keeping them
  forever is a data-retention decision nobody actually made - it is the default
  winning by absence, which is the same shape as the audit sink that failed open.

Why 30 days, and why that is not an arbitrary pick
--------------------------------------------------
It is the value this codebase already codifies. `provision_cognito_custom_message.py`
and `provision_customer_whatsapp_auth.py` both call
`put_retention_policy(retentionInDays=30)`, and 42 of the 67 groups are already at 30.
Twelve sit at 90 with no discernible category logic - a mix of `automation-rules`,
`docs-scraper`, `payu-webhook` and `url-shortener` - so 90 reads as incidental rather
than as a considered policy for a class of function. Those are left alone: changing a
longer retention to a shorter one would be the one genuinely destructive move
available here.

Nothing is lost by applying this now. Every affected group holds at most 363 KB and
the largest is days old, so no existing log event is old enough for a 30-day policy
to reach. **That is deliberate timing, not luck** - the same change applied to a group
holding a year of data would delete eleven months of it, so check `storedBytes` and
the oldest event before widening this script's scope.

Lambda@Edge, and why one prefix in one region was not enough
-----------------------------------------------------------
This script originally scanned `/aws/lambda/wecare-` in `us-east-1` only, and
reported "every log group has a retention period" while **four** groups never
expired. Lambda@Edge breaks both assumptions at once:

* Its log group is named `/aws/lambda/us-east-1.<function>`, not
  `/aws/lambda/<function>` - the region is part of the name, so the old prefix could
  never match it.
* CloudFront writes those logs **in the region nearest the viewer**, not in the
  function's home region. So the groups exist in several regions and no single-region
  scan can see them all.

Measured across all 34 enabled regions on 2026-09-25: `wecare-get-miss-redirect` and
`/aws/cloudfront/LambdaEdge/E2GP22R4BIFGQ3` each had a never-expiring group in
**`us-east-1` and `ap-south-1`** - ap-south-1 being where the India traffic lands.
All four held 0 bytes and were hours old, so applying 30 days removed nothing.

A gate that silently skips a region it could not reach is the same defect as the
prefix that could not match, so unreachable regions are always named.

`me-south-1` is unreachable from this development host, and it is worth being precise
about why, because the first version of this note guessed wrong. It is **not** a
disabled region: `DescribeRegions` reports all 34 as `opted-in`, me-south-1 included.
The CloudWatch Logs endpoint there simply does not answer from this network - 40s to
a `ConnectTimeoutError` even at a 10s connect timeout. So coverage of that region is
*unproven*, not clean, and not empty.

`--verify` therefore fails on what it can actually establish - a group with no
retention - and reports unreachable regions as unproven coverage without failing on
them. `--strict` additionally fails on unproven regions, for a runner with full
network egress. The alternative, failing always, would produce a gate that can never
pass from a developer machine, and a gate that can never pass gets ignored exactly
like one that always passes.

The audit trail is NOT here. `lambda_utils.audit` writes to `AuditLogsTable`, which
has its own TTL, so a retention policy on an execution log does not shorten the record
of who did what.

Usage:
    python scripts/provision_log_retention.py            # report
    python scripts/provision_log_retention.py --apply
    python scripts/provision_log_retention.py --verify
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

# Full coverage across every enabled region is the point, but a serial scan with
# default timeouts takes minutes because an opt-in region this account has not
# enabled hangs until the default connect timeout expires. Short timeouts plus a
# thread pool keep the honest scope without making the gate unusable - and a region
# that times out is reported as unreachable, never as clean.
_SCAN_CONFIG = Config(connect_timeout=3, read_timeout=5,
                      retries={"max_attempts": 2, "mode": "standard"})
_SCAN_WORKERS = 12

REGION = "us-east-1"
PREFIX = "/aws/lambda/wecare-"
RETENTION_DAYS = 30

# Lambda@Edge. `/aws/lambda/us-east-1.wecare-*` is the replica's own log group and
# `/aws/cloudfront/LambdaEdge/*` carries the execution errors CloudFront reports.
# Neither can match PREFIX above, and both appear in whichever region served the
# viewer - see the module docstring.
EDGE_PREFIXES = ("/aws/lambda/us-east-1.wecare", "/aws/cloudfront/LambdaEdge/")

# A group already carrying a LONGER retention is left alone. Shortening one is the
# only destructive action available in this script, so it is not available.
LEAVE_ALONE_IF_AT_LEAST = RETENTION_DAYS


def logs(region: str = REGION, *, scan: bool = False):
    if scan:
        return boto3.client("logs", region_name=region, config=_SCAN_CONFIG)
    return boto3.client("logs", region_name=region)


def _paged(client, prefix):
    groups, token = [], None
    while True:
        kw = {"logGroupNamePrefix": prefix}
        if token:
            kw["nextToken"] = token
        page = client.describe_log_groups(**kw)
        groups += page.get("logGroups", [])
        token = page.get("nextToken")
        if not token:
            return groups


def all_groups(client):
    return _paged(client, PREFIX)


def enabled_regions() -> list[str]:
    ec2 = boto3.client("ec2", region_name=REGION)
    return sorted(r["RegionName"] for r in ec2.describe_regions()["Regions"])


def edge_groups(regions=None):
    """Lambda@Edge groups across regions.

    Returns (found, unreachable). `found` carries the region with each group,
    because the same group NAME exists in several regions and the retention call
    has to go to the right one. `unreachable` is returned rather than swallowed:
    a region this script could not read is not a region that is clean.
    """
    if regions is None:
        try:
            regions = enabled_regions()
        except (ClientError, BotoCoreError):
            regions = [REGION]
    def scan_region(region):
        client = logs(region, scan=True)
        hits, misses = [], []
        for prefix in EDGE_PREFIXES:
            try:
                for group in _paged(client, prefix):
                    hits.append((region, group))
            except (ClientError, BotoCoreError) as exc:
                misses.append((region, prefix, type(exc).__name__))
        return hits, misses

    found, unreachable = [], []
    with ThreadPoolExecutor(max_workers=_SCAN_WORKERS) as pool:
        for hits, misses in pool.map(scan_region, regions):
            found += hits
            unreachable += misses
    return found, unreachable


def classify(groups):
    unset, shorter, ok = [], [], []
    for group in groups:
        days = group.get("retentionInDays")
        if days is None:
            unset.append(group)
        elif days < LEAVE_ALONE_IF_AT_LEAST:
            shorter.append(group)
        else:
            ok.append(group)
    return unset, shorter, ok


def report(client):
    """Report both families. Returns (regional_unset, edge_unset, unreachable)."""
    groups = all_groups(client)
    unset, shorter, ok = classify(groups)
    print(f"{len(groups)} log groups under {PREFIX} ({REGION})")
    print(f"  already {RETENTION_DAYS}+ days: {len(ok)}")
    print(f"  shorter than {RETENTION_DAYS} (left alone): {len(shorter)}")
    print(f"  never expires: {len(unset)}")
    for group in sorted(unset, key=lambda g: g["logGroupName"]):
        print(f"    {group['logGroupName']:58} "
              f"{group.get('storedBytes', 0):>10,} bytes")

    found, unreachable = edge_groups()
    edge_unset = [(r, g) for r, g in found if g.get("retentionInDays") is None]
    print(f"\n{len(found)} Lambda@Edge log group(s) across all enabled regions")
    print(f"  never expires: {len(edge_unset)}")
    for region, group in sorted(edge_unset, key=lambda p: (p[1]["logGroupName"], p[0])):
        print(f"    {region:15} {group['logGroupName']:50} "
              f"{group.get('storedBytes', 0):>10,} bytes")
    if unreachable:
        # Named, not hidden. An unread region is not a clean region.
        print(f"  unreachable regions (not treated as clean): "
              f"{sorted({r for r, _, _ in unreachable})}")
    return unset, edge_unset, unreachable


def apply(client, unset, edge_unset=()) -> int:
    failed = 0
    for group in unset:
        name = group["logGroupName"]
        try:
            client.put_retention_policy(logGroupName=name,
                                        retentionInDays=RETENTION_DAYS)
            print(f"  {name} -> {RETENTION_DAYS} days")
        except (ClientError, BotoCoreError) as exc:
            print(f"  {name} FAILED: {type(exc).__name__}", file=sys.stderr)
            failed += 1
    for region, group in edge_unset:
        name = group["logGroupName"]
        try:
            # Must go to the region holding the group, not the function's home.
            logs(region).put_retention_policy(logGroupName=name,
                                              retentionInDays=RETENTION_DAYS)
            print(f"  {region} {name} -> {RETENTION_DAYS} days")
        except (ClientError, BotoCoreError) as exc:
            print(f"  {region} {name} FAILED: {type(exc).__name__}", file=sys.stderr)
            failed += 1
    return failed


def verify(strict: bool = False) -> int:
    client = logs()
    unset, edge_unset, unreachable = report(client)
    total = len(unset) + len(edge_unset)
    if total:
        print(f"\nFAIL: {total} log group(s) still never expire "
              f"({len(unset)} regional, {len(edge_unset)} Lambda@Edge)")
        return 1
    print(f"\nevery reachable {PREFIX}* and Lambda@Edge log group has a "
          f"retention period")
    if unreachable:
        regions = sorted({r for r, _, _ in unreachable})
        # Stated every time, pass or fail. The invariant holds where it could be
        # read; it is not established for these regions.
        print(f"UNPROVEN: {len(unreachable)} read(s) failed in {regions} - "
              f"coverage there is unproven, not clean")
        if strict:
            print("FAIL: --strict treats unproven coverage as failure")
            return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="also fail when a region could not be read, so Edge "
                             "coverage is unproven. For runners with full egress.")
    args = parser.parse_args(argv)

    if args.verify:
        return verify(strict=args.strict)

    client = logs()
    try:
        unset, edge_unset, _ = report(client)
    except (ClientError, BotoCoreError) as exc:
        print(f"could not read CloudWatch Logs: {type(exc).__name__}",
              file=sys.stderr)
        return 2

    if not unset and not edge_unset:
        print("\nnothing to do")
        return 0
    if not args.apply:
        print("\nre-run with --apply to converge")
        return 1

    print()
    failed = apply(client, unset, edge_unset)
    print("\nread-back verification:")
    rc = verify(strict=args.strict)
    return rc or (1 if failed else 0)


if __name__ == "__main__":
    raise SystemExit(main())
