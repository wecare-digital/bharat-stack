#!/usr/bin/env python3
"""Bring the Lambda role's AWS End User Messaging permissions up to what the
target communications architecture actually needs.

Why this is needed
------------------
`simulate_principal_policy` against the live `wecare-digital-lambda-role` showed
the `PinpointSMSVoice` statement in inline policy `wecare-digital-lambda-permissions`
grants only four actions:

    sms-voice:SendTextMessage
    sms-voice:SendVoiceMessage
    sms-voice:DescribePhoneNumbers
    sms-voice:DescribePools

Sixteen simulated actions came back `implicitDeny`. Two groups matter:

1. **Delivery receipts were unbuildable, not merely unbuilt.**
   `CreateEventDestination`, `UpdateEventDestination`, `CreateConfigurationSet`
   and `DescribeConfigurationSets` were all denied. The missing SMS
   delivery-receipt consumer - the reason every AWS SMS row sits at `SENT`
   forever - could not have been built even if the code existed.

2. **The SMS dashboard (§42) could not tell the truth.** It is specified to show
   India DLT status, origination-identity status, pool status and spend/limit
   warnings, but `DescribeSenderIds`, `DescribeSpendLimits`,
   `DescribeRegistrations` and `DescribeOptOutLists` were all denied.

Scope
-----
Only the `PinpointSMSVoice` statement is touched, and only by ADDING actions.
Nothing is removed, no other statement is read or written, no other policy is
modified, and the resource stays `*` exactly as it already was.

`Resource: "*"` is correct rather than lazy for the Describe* family: they are
account-level list operations with no per-resource ARN to scope to. The Send*
actions could in principle be narrowed to specific phone-number and sender-id
ARNs, but narrowing a live send path is a separate change with its own blast
radius - it would be made in the same commit as the corresponding test, not
smuggled into a permissions top-up.

    python scripts/iam_sync_comms_permissions.py --dry-run
    python scripts/iam_sync_comms_permissions.py --apply

Idempotent: a second --apply reports "already current" and writes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    import boto3
except ImportError:  # pragma: no cover
    sys.exit("boto3 required: use .venv/bin/python")

ROLE = "wecare-digital-lambda-role"
POLICY = "wecare-digital-lambda-permissions"
SID = "PinpointSMSVoice"
ACCOUNT = "775261844268"

# Actions the target architecture needs, with the reason each one is here.
REQUIRED = {
    # sending
    "sms-voice:SendTextMessage": "normal SMS, every country (§23)",
    "sms-voice:SendVoiceMessage": "voice message sends (already granted)",
    "sms-voice:SendMediaMessage": "MMS / RCS media fallback",
    # inventory the dashboard needs to be honest (§42)
    "sms-voice:DescribePhoneNumbers": "origination identity status",
    "sms-voice:DescribePools": "pool status",
    "sms-voice:DescribeSenderIds": "India WDBEEP registration status",
    "sms-voice:DescribeSpendLimits": "spend/limit warnings",
    "sms-voice:DescribeRegistrations": "India DLT + RCS launch registration status",
    "sms-voice:DescribeOptOutLists": "opt-out compliance",
    "sms-voice:DescribeOptedOutNumbers": "opt-out compliance",
    # delivery receipts - without these the consumer cannot be created at all
    "sms-voice:CreateConfigurationSet": "delivery-receipt event destination",
    "sms-voice:DescribeConfigurationSets": "delivery-receipt event destination",
    "sms-voice:CreateEventDestination": "delivery-receipt event destination",
    "sms-voice:UpdateEventDestination": "delivery-receipt event destination",
    "sms-voice:DeleteEventDestination": "delivery-receipt rollback",
}

# Every action is checked in both regions the architecture sends from.
REGIONS = ("us-east-1", "ap-south-1")


def statements(doc: dict) -> list:
    s = doc.get("Statement") or []
    return s if isinstance(s, list) else [s]


def simulate(iam, actions: list) -> dict:
    """action -> decision, simulated against the resource the policy grants.

    Resource MUST be '*' here, matching the statement. An earlier version passed
    `arn:aws:sms-voice:<region>:<account>:*` on the theory that a region-scoped
    ARN was the more honest test. It is not: several of these actions
    (CreateConfigurationSet, DescribeSpendLimits, SendVoiceMessage) are
    account-level or use a resource type that ARN shape does not match, so the
    simulator returned implicitDeny for permissions that were in fact granted.
    That produced three permanent false denials and would have sent someone
    hunting an explicit Deny or a permissions boundary that does not exist.

    Simulate what the policy actually says. Region coverage is established by the
    fact that `*` spans every region, and separately by the live two-region
    DryRun sends in scripts/aws_sms_check.py.
    """
    out: dict = {}
    arn = f"arn:aws:iam::{ACCOUNT}:role/{ROLE}"
    for action in actions:
        try:
            out[action] = iam.simulate_principal_policy(
                PolicySourceArn=arn, ActionNames=[action], ResourceArns=["*"],
            )["EvaluationResults"][0]["EvalDecision"]
        except Exception as exc:  # noqa: BLE001
            out[action] = f"error:{type(exc).__name__}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="show the diff, write nothing")
    g.add_argument("--apply", action="store_true", help="write the policy")
    args = ap.parse_args()

    iam = boto3.client("iam")
    ident = boto3.client("sts").get_caller_identity()
    if ident["Account"] != ACCOUNT:
        sys.exit(f"wrong account {ident['Account']}, expected {ACCOUNT}")

    doc = iam.get_role_policy(RoleName=ROLE, PolicyName=POLICY)["PolicyDocument"]
    target = None
    for st in statements(doc):
        if st.get("Sid") == SID:
            target = st
            break
    if target is None:
        sys.exit(f"statement Sid={SID} not found in inline policy {POLICY}")

    current = target.get("Action") or []
    current = [current] if isinstance(current, str) else list(current)
    current_set = set(current)
    missing = [a for a in REQUIRED if a not in current_set]

    print(f"\nrole   {ROLE}")
    print(f"policy {POLICY} (inline)   statement {SID}")
    print(f"resource stays: {target.get('Resource')!r}\n")

    print(f"currently granted ({len(current)}):")
    for a in sorted(current_set):
        print(f"  have     {a}")
    if missing:
        print(f"\nto ADD ({len(missing)}):")
        for a in missing:
            print(f"  ADD      {a:42s} {REQUIRED[a]}")
    else:
        print("\nnothing to add - already current")

    print("\nlive simulation BEFORE:")
    before = simulate(iam, sorted(REQUIRED))
    denied_before = [a for a, d in before.items() if d != "allowed"]
    print(f"  allowed {len(before) - len(denied_before)} / {len(before)}")
    for a in denied_before:
        print(f"  DENIED   {a}")

    if not missing:
        return 0

    if args.dry_run:
        print("\nDRY RUN - no policy written. Re-run with --apply.\n")
        return 0

    target["Action"] = sorted(current_set | set(REQUIRED))
    iam.put_role_policy(RoleName=ROLE, PolicyName=POLICY,
                        PolicyDocument=json.dumps(doc))
    print(f"\npolicy written: {len(target['Action'])} action(s) on {SID}")

    # IAM is eventually consistent; simulation can lag a moment.
    import time
    time.sleep(5)
    print("\nlive simulation AFTER:")
    after = simulate(iam, sorted(REQUIRED))
    denied_after = [a for a, d in after.items() if d != "allowed"]
    print(f"  allowed {len(after) - len(denied_after)} / {len(after)}")
    for a in denied_after:
        print(f"  STILL DENIED  {a}  ({after[a]})")
    if denied_after:
        print("\nSome actions are still denied. If this is not eventual consistency,")
        print("check for an explicit Deny or a permissions boundary.\n")
        return 1
    print("\nall required End User Messaging actions are permitted in "
          f"{' and '.join(REGIONS)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
