#!/usr/bin/env python3
"""Change one Cognito user-pool field without silently resetting the other twenty.

THE HAZARD THIS EXISTS FOR, measured rather than theorised. On 2026-09-28 a single

    aws cognito-idp update-user-pool --user-pool-id us-east-1_46ULYuukt \
        --deletion-protection ACTIVE

did exactly what was asked and two things that were not. `UpdateUserPool` is a
**full replace**, not a patch: every field omitted from the request reverts to its
service default. Recovered from CloudTrail, the pool lost

    lambdaConfig.DefineAuthChallenge            -> {}   (all three CUSTOM_AUTH triggers)
    lambdaConfig.CreateAuthChallenge            -> {}
    lambdaConfig.VerifyAuthChallengeResponse    -> {}
    adminCreateUserConfig.AllowAdminCreateUserOnly  true -> false

The first silently breaks customer WhatsApp OTP sign-in -- the pool is phone-keyed
`CUSTOM_AUTH` and with no triggers there is no challenge to issue. The second is
worse: it **opened self-signup** on an internet-facing pool that WAF fronted at the time
(the web ACL was deleted on 2026-09-28, so that pool now has no edge filtering at all,
which makes an accidental self-signup reopening worse rather than better)
precisely because it is public. Neither raises an error, and `update-user-pool`
returns 200.

So: never call `update_user_pool` with a partial argument set. This reads the live
pool, applies only the named change, and writes the whole configuration back --
and it prints a diff of every field that would move, so an unintended reset is
visible before it happens rather than in a later audit.

    python scripts/cognito_pool_safe_update.py --pool-id us-east-1_46ULYuukt --show
    python scripts/cognito_pool_safe_update.py --pool-id us-east-1_46ULYuukt \
        --set DeletionProtection=ACTIVE --apply
"""

from __future__ import annotations

import argparse
import json
import sys

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"

#: `UpdateUserPool` accepts these; anything present on the pool and absent from the
#: request is reset. Read-only fields returned by `DescribeUserPool` (Id, Arn,
#: CreationDate, EstimatedNumberOfUsers, SchemaAttributes, Domain, Status, ...) must
#: NOT be echoed back or the call is rejected.
WRITABLE = (
    "Policies",
    "DeletionProtection",
    "LambdaConfig",
    "AutoVerifiedAttributes",
    "SmsVerificationMessage",
    "EmailVerificationMessage",
    "EmailVerificationSubject",
    "VerificationMessageTemplate",
    "SmsAuthenticationMessage",
    "UserAttributeUpdateSettings",
    "MfaConfiguration",
    "DeviceConfiguration",
    "EmailConfiguration",
    "SmsConfiguration",
    "UserPoolTags",
    "AdminCreateUserConfig",
    "UserPoolAddOns",
    "AccountRecoverySetting",
    "PoolName",
)


def _client():
    return boto3.client("cognito-idp", region_name=REGION)


def _describe(client, pool_id: str) -> dict:
    return client.describe_user_pool(UserPoolId=pool_id)["UserPool"]


def _request_from(pool: dict, pool_id: str) -> dict:
    request: dict = {"UserPoolId": pool_id}
    for field in WRITABLE:
        if field == "PoolName":
            continue
        value = pool.get(field)
        if value in (None, [], {}):
            continue
        request[field] = value
    # `UnusedAccountValidityDays` is deprecated and Cognito derives it from
    # Policies.PasswordPolicy.TemporaryPasswordValidityDays. Echoing both back makes
    # the API complain about a conflicting pair, so drop the deprecated one.
    admin = request.get("AdminCreateUserConfig")
    if isinstance(admin, dict):
        admin = dict(admin)
        admin.pop("UnusedAccountValidityDays", None)
        request["AdminCreateUserConfig"] = admin
    return request


def _coerce(raw: str):
    text = raw.strip()
    if text.startswith(("{", "[")):
        return json.loads(text)
    if text in ("true", "false"):
        return text == "true"
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool-id", required=True)
    parser.add_argument("--set", action="append", default=[], metavar="Field=Value",
                        help="a writable DescribeUserPool field; JSON allowed")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    client = _client()
    try:
        before = _describe(client, args.pool_id)
    except ClientError as exc:
        print(f"DescribeUserPool failed: {exc.response['Error']['Code']}", file=sys.stderr)
        return 2

    if args.show or not args.set:
        for field in WRITABLE:
            if field == "PoolName":
                continue
            print(f"{field}: {json.dumps(before.get(field), default=str)}")
        return 0

    changes: dict = {}
    for item in args.set:
        if "=" not in item:
            print(f"--set expects Field=Value, got {item!r}", file=sys.stderr)
            return 2
        field, raw = item.split("=", 1)
        field = field.strip()
        if field not in WRITABLE:
            print(f"{field} is not writable by UpdateUserPool. Writable: "
                  f"{', '.join(WRITABLE)}", file=sys.stderr)
            return 2
        changes[field] = _coerce(raw)

    request = _request_from(before, args.pool_id)
    preserved = [f for f in request if f not in ("UserPoolId",) and f not in changes]
    request.update(changes)

    print("changing:")
    for field, value in changes.items():
        print(f"  {field}: {json.dumps(before.get(field), default=str)}"
              f"  ->  {json.dumps(value, default=str)}")
    print(f"preserving {len(preserved)} other field(s): {', '.join(sorted(preserved))}")

    if not args.apply:
        print("\n(dry run; pass --apply)")
        return 0

    try:
        client.update_user_pool(**request)
    except ClientError as exc:
        print(f"UpdateUserPool failed: {exc.response['Error']['Code']}: "
              f"{exc.response['Error']['Message']}", file=sys.stderr)
        return 1

    after = _describe(client, args.pool_id)
    drifted = []
    for field in WRITABLE:
        if field in ("PoolName", "UserPoolId"):
            continue
        if field in changes:
            continue
        if json.dumps(before.get(field), default=str, sort_keys=True) != \
           json.dumps(after.get(field), default=str, sort_keys=True):
            drifted.append(field)

    for field, value in changes.items():
        actual = after.get(field)
        ok = json.dumps(actual, default=str, sort_keys=True) == \
            json.dumps(value, default=str, sort_keys=True)
        print(f"  {'OK  ' if ok else 'FAIL'}  {field} = {json.dumps(actual, default=str)}")

    if drifted:
        print(f"\nUNINTENDED DRIFT on {len(drifted)} field(s): {drifted}", file=sys.stderr)
        return 1
    print("\nno unintended drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
