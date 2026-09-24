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

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-east-1"
PREFIX = "/aws/lambda/wecare-"
RETENTION_DAYS = 30

# A group already carrying a LONGER retention is left alone. Shortening one is the
# only destructive action available in this script, so it is not available.
LEAVE_ALONE_IF_AT_LEAST = RETENTION_DAYS


def logs():
    return boto3.client("logs", region_name=REGION)


def all_groups(client):
    groups, token = [], None
    while True:
        kw = {"logGroupNamePrefix": PREFIX}
        if token:
            kw["nextToken"] = token
        page = client.describe_log_groups(**kw)
        groups += page.get("logGroups", [])
        token = page.get("nextToken")
        if not token:
            return groups


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
    groups = all_groups(client)
    unset, shorter, ok = classify(groups)
    print(f"{len(groups)} log groups under {PREFIX}")
    print(f"  already {RETENTION_DAYS}+ days: {len(ok)}")
    print(f"  shorter than {RETENTION_DAYS} (left alone): {len(shorter)}")
    print(f"  never expires: {len(unset)}")
    for group in sorted(unset, key=lambda g: g["logGroupName"]):
        print(f"    {group['logGroupName']:58} "
              f"{group.get('storedBytes', 0):>10,} bytes")
    return unset


def apply(client, unset) -> int:
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
    return failed


def verify() -> int:
    client = logs()
    unset = report(client)
    if unset:
        print(f"\nFAIL: {len(unset)} log group(s) still never expire")
        return 1
    print(f"\nevery {PREFIX}* log group has a retention period")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    client = logs()
    try:
        unset = report(client)
    except (ClientError, BotoCoreError) as exc:
        print(f"could not read CloudWatch Logs: {type(exc).__name__}",
              file=sys.stderr)
        return 2

    if not unset:
        print("\nnothing to do")
        return 0
    if not args.apply:
        print("\nre-run with --apply to converge")
        return 1

    print()
    failed = apply(client, unset)
    print("\nread-back verification:")
    rc = verify()
    return rc or (1 if failed else 0)


if __name__ == "__main__":
    raise SystemExit(main())
