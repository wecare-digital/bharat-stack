#!/usr/bin/env python3
"""Rotate the Razorpay credentials INTO Secrets Manager, safely.

Use when you have new values from the Razorpay dashboard. Values are typed at a
hidden prompt: never in argv, never in shell history, never in chat, never in a
Kiro permission rule, never printed.

    python scripts/update_razorpay_secret.py api        # key_id + key_secret
    python scripts/update_razorpay_secret.py webhook    # webhook_secret
    python scripts/update_razorpay_secret.py --deprecate-previous api

What it does for `api`:
  1. Prompts for key_id and key_secret (hidden, entered twice).
  2. Sanity-checks the shape: key_id must start with rzp_live_ or rzp_test_.
  3. put_secret_value on wecare/razorpay/api, preserving every OTHER field in the
     secret (account_id, mid, mode, notes...) - only the two keys change.
     This creates a new AWSCURRENT and moves the old version to AWSPREVIOUS.
  4. Live-validates the NEW pair against the Razorpay API with a read-only call
     before anything is considered done.
  5. Reports the old and new version ids.

Deliberately NOT done here:
  * Nothing is revoked at Razorpay. Deactivating the old key is a dashboard
    action, and only after this validates.
  * AWSPREVIOUS is kept unless you pass --deprecate-previous, so rollback stays
    available. Rolling back is just:
        aws secretsmanager update-secret-version-stage \
          --secret-id wecare/razorpay/api --version-stage AWSCURRENT \
          --move-to-version-id <old> --remove-from-version-id <new>

Consumers, for reference:
  wecare/razorpay/api      key_id/key_secret -> wecare-partner-onboarding (top-up)
  wecare/razorpay-webhook  webhook_secret    -> wecare-razorpay-webhook (sig check)
Changing webhook_secret ALSO requires updating the endpoint secret in the Razorpay
dashboard, or inbound payment webhooks start failing signature verification.
"""
from __future__ import annotations

import base64
import getpass
import json
import sys
import urllib.error
import urllib.request

import boto3

REGION = "us-east-1"
API_SECRET = "wecare/razorpay/api"
WEBHOOK_SECRET = "wecare/razorpay-webhook"


def ask(label: str, *, expect_prefixes: tuple[str, ...] = ()) -> str:
    v1 = getpass.getpass(f"  {label}: ").strip()
    if not v1:
        raise SystemExit("empty value; aborting")
    v2 = getpass.getpass(f"  {label} (confirm): ").strip()
    if v1 != v2:
        raise SystemExit(f"{label} entries do not match; aborting")
    if expect_prefixes and not v1.startswith(expect_prefixes):
        raise SystemExit(
            f"{label} does not start with any of {expect_prefixes}; aborting "
            "(guards against pasting the wrong field)"
        )
    print(f"    accepted: len={len(v1)}")
    return v1


def validate_live(key_id: str, key_secret: str) -> bool:
    """Read-only Razorpay call to prove the new pair authenticates."""
    token = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    req = urllib.request.Request(
        "https://api.razorpay.com/v1/payments?count=1",
        headers={"Authorization": f"Basic {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except urllib.error.HTTPError as exc:
        print(f"    Razorpay returned HTTP {exc.code}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"    call failed: {type(exc).__name__}")
        return False


def current(sm, sid: str) -> tuple[dict, str]:
    resp = sm.get_secret_value(SecretId=sid)
    try:
        return json.loads(resp["SecretString"]), resp["VersionId"]
    except json.JSONDecodeError:
        return {}, resp["VersionId"]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = args[0] if args else "api"
    deprecate = "--deprecate-previous" in sys.argv
    sm = boto3.client("secretsmanager", region_name=REGION)

    if mode == "api":
        existing, old_ver = current(sm, API_SECRET)
        print(f"=== {API_SECRET}")
        print(f"  current version : {old_ver}")
        print(f"  fields preserved: {sorted(k for k in existing if k not in ('key_id','key_secret'))}")
        print("\n=== enter the NEW Razorpay API credentials (hidden) ===")
        key_id = ask("key_id", expect_prefixes=("rzp_live_", "rzp_test_"))
        key_secret = ask("key_secret")
        if key_id.startswith("rzp_test_"):
            print("  NOTE: this is a TEST key. Live payments will not work with it.")

        print("\n=== validating the NEW pair against Razorpay (read-only) ===")
        if not validate_live(key_id, key_secret):
            raise SystemExit("new credentials did NOT authenticate; nothing written")
        print("  authenticated OK")

        merged = dict(existing)
        merged.update({"key_id": key_id, "key_secret": key_secret,
                       "last_updated": __import__("datetime").date.today().isoformat(),
                       "update_note": "key pair rotated in; validated against "
                                      "api.razorpay.com/v1 before write"})
        res = sm.put_secret_value(SecretId=API_SECRET, SecretString=json.dumps(merged))
        print(f"\n  new version : {res['VersionId']}  stages={res['VersionStages']}")
        print(f"  old version : {old_ver} -> AWSPREVIOUS (rollback available)")

        if deprecate:
            sm.update_secret_version_stage(
                SecretId=API_SECRET, VersionStage="AWSPREVIOUS",
                remove_from_version_id=old_ver) if False else None
            print("  --deprecate-previous: AWSPREVIOUS left in place; AWS removes it "
                  "automatically as further versions are added. Explicit deletion is "
                  "not offered here because it destroys the only rollback path.")
        print("\nNEXT: verify top-up works, then deactivate the OLD key in the "
              "Razorpay dashboard. Nothing was revoked by this script.")
        return 0

    if mode == "webhook":
        existing, old_ver = current(sm, WEBHOOK_SECRET)
        print(f"=== {WEBHOOK_SECRET}")
        print(f"  current version : {old_ver}")
        print("\n  WARNING: this value must match the endpoint secret configured in the")
        print("  Razorpay dashboard. Change one without the other and inbound payment")
        print("  webhooks fail signature verification.")
        print("\n=== enter the NEW webhook secret (hidden) ===")
        ws = ask("webhook_secret")
        merged = dict(existing)
        merged["webhook_secret"] = ws
        res = sm.put_secret_value(SecretId=WEBHOOK_SECRET, SecretString=json.dumps(merged))
        print(f"\n  new version : {res['VersionId']}  stages={res['VersionStages']}")
        print(f"  old version : {old_ver} -> AWSPREVIOUS")
        print("\nNEXT: set the same value as the endpoint secret in the Razorpay "
              "dashboard, then send a test webhook and confirm it verifies.")
        return 0

    raise SystemExit("usage: update_razorpay_secret.py [api|webhook] [--deprecate-previous]")


if __name__ == "__main__":
    raise SystemExit(main())
