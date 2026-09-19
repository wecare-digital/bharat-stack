#!/usr/bin/env python3
"""Prove the _razorpay_creds() fix resolves, and that the old path could not.

Mirrors the exact logic now shipped in
amplify/functions/messaging/partner-onboarding/handler.py. Reports only whether
each field is populated and its length - never a value.
"""
import json

import boto3

sm = boto3.client("secretsmanager", region_name="us-east-1")

NEW_ORDER = ("wecare/razorpay/api", "wecare/razorpay-webhook")
OLD_ONLY = "wecare/razorpay-webhook"


def creds(secret_ids):
    for sid in secret_ids:
        try:
            raw = sm.get_secret_value(SecretId=sid).get("SecretString", "") or "{}"
            d = json.loads(raw)
            k = (d.get("key_id") or "").strip()
            s = (d.get("key_secret") or "").strip()
            if k and s:
                return sid, k, s
        except Exception:  # noqa: BLE001
            continue
    return None, "", ""


def main() -> int:
    src, k, s = creds(NEW_ORDER)
    print("NEW code path")
    print(f"  resolved from      : {src}")
    print(f"  key_id populated   : {bool(k)}  len={len(k)}  prefix={k[:4] if k else '-'}")
    print(f"  key_secret populated: {bool(s)}  len={len(s)}")
    print(f"  would return 501   : {not (k and s)}")

    osrc, ok, os_ = creds((OLD_ONLY,))
    raw = sm.get_secret_value(SecretId=OLD_ONLY)["SecretString"]
    fields = sorted(json.loads(raw))
    print("\nOLD code path (read only wecare/razorpay-webhook)")
    print(f"  fields present     : {fields}")
    print(f"  key_id populated   : {bool(ok)}")
    print(f"  would return 501   : {not (ok and os_)}")

    ok_fix = bool(k and s) and not bool(ok and os_)
    print("\nRESULT:", "FIX CONFIRMED - new path resolves, old path could not"
          if ok_fix else "INCONCLUSIVE")
    return 0 if ok_fix else 1


if __name__ == "__main__":
    raise SystemExit(main())
