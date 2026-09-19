#!/usr/bin/env python3
"""Verify Secrets Manager entries contain the expected FIELDS, without exposing values.

Reports, per secret: the JSON key names, each value's length and a short
fingerprint (first 4 / last 2 characters). That is enough to confirm a field is
populated and looks like the right credential shape, while never putting the
value into agent context, a log, a command line or a file.

    python scripts/audit_secrets_structure.py

Exit 0 always; this is a report.
"""
from __future__ import annotations

import json

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"

# Secrets relevant to the 2026-09-19 leak plus their production consumers.
TARGETS = [
    ("wecare/razorpay/api",      "Razorpay API credentials (migrated 2026-09-18)"),
    ("wecare/razorpay-webhook",  "Razorpay webhook + API pair read by wecare-partner-onboarding"),
    ("wecare/google-api-key",    "Google API key (migrated 2026-09-18)"),
    ("wecare/google-maps",       "Google Maps key read by wecare-whatsapp-templates"),
    ("wecare/openai/api",        "OpenAI key (migrated 2026-09-18)"),
    ("wecare/plivo/api",         "Plivo API credentials (migrated 2026-09-18)"),
    ("wecare/aws/iam-access-keys", "AWS IAM access keys (developer auth - see note)"),
]


def fingerprint(v: object) -> str:
    if not isinstance(v, str):
        return f"<{type(v).__name__}>"
    if len(v) <= 8:
        return f"len={len(v)} <short>"
    return f"len={len(v):<4} {v[:4]}…{v[-2:]}"


def main() -> int:
    sm = boto3.client("secretsmanager", region_name=REGION)
    print(f"region={REGION}\n")
    for name, note in TARGETS:
        print(f"=== {name}")
        print(f"    {note}")
        try:
            meta = sm.describe_secret(SecretId=name)
        except ClientError as exc:
            print(f"    MISSING or inaccessible: {exc.response['Error']['Code']}\n")
            continue
        kms = meta.get("KmsKeyId") or "aws/secretsmanager (AWS-managed)"
        print(f"    KMS:      {kms}")
        print(f"    Changed:  {meta.get('LastChangedDate')}")
        print(f"    Rotation: {meta.get('RotationEnabled', False)}")
        tags = {t['Key']: t['Value'] for t in meta.get("TagList", [])}
        print(f"    Tags:     {tags or 'none'}")
        try:
            raw = sm.get_secret_value(SecretId=name)["SecretString"]
        except ClientError as exc:
            print(f"    cannot read: {exc.response['Error']['Code']}\n")
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            print(f"    format:   plain string, {fingerprint(raw)}\n")
            continue
        if isinstance(obj, dict):
            print(f"    format:   JSON object, {len(obj)} field(s)")
            for k in sorted(obj):
                print(f"      - {k:24s} {fingerprint(obj[k])}")
        else:
            print(f"    format:   JSON {type(obj).__name__}")
        print()
    print("No secret value was printed: only field names, lengths and 4/2-char "
          "fingerprints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
