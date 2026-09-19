#!/usr/bin/env python3
"""Sync the webhook registry into the TXT ledger and Secrets Manager, and verify AWS keys.

    python scripts/sync_webhook_registry.py --dry-run
    python scripts/sync_webhook_registry.py

What it does:
  1. Verifies the AWS IAM access key is consistent across ~/.aws/credentials,
     the TXT ledger and Secrets Manager - by FINGERPRINT only, no value printed.
     Verifies rather than replaces: no rotation is authorized.
  2. Writes/refreshes a WEBHOOK REGISTRY block in the TXT ledger, between stable
     markers so re-running replaces the block instead of appending a second copy.
  3. Stores the same registry in Secrets Manager at wecare/config/webhook-registry.
     URLs are NOT secrets; this is a config record, and webhook SECRETS are not
     copied into it.

TXT ledger safety, per .kiro/steering/plaintext-source-policy.md: parsed in
memory, written atomically via a 0600 temp in the same directory then os.replace,
mode preserved, no .bak/.swp/.tmp remnant, nothing printed.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
ACCOUNT = "775261844268"
TXT = Path.home() / "aws-new-keys-SAVE-THEN-DELETE.txt"
BEGIN = "# >>> BEGIN WEBHOOK REGISTRY (managed by scripts/sync_webhook_registry.py) >>>"
END = "# <<< END WEBHOOK REGISTRY <<<"
CONFIG_SECRET = "wecare/config/webhook-registry"
BASE = "https://api.wecare.digital"

WEBHOOKS = [
    ("Razorpay", "POST", "/razorpay-webhook", "wecare-razorpay-webhook",
     "HMAC SHA256 X-Razorpay-Signature vs wecare/razorpay-webhook:webhook_secret",
     "CONFIGURED at provider (id TTtfLAe18fnqax, 57 events, all 31 handled events subscribed)"),
    ("Meta / WhatsApp Cloud", "POST", "/whatsapp/inbound", "wecare-inbound-whatsapp",
     "X-Hub-Signature-256 vs app_secret; GET verify_token challenge", "CONFIGURED at provider"),
    ("Meta / WhatsApp business", "POST", "/wa-business/webhooks", "wecare-whatsapp-business-api",
     "X-Hub-Signature-256", "CONFIGURED at provider"),
    ("Plivo voice IVR", "POST", "/plivo/answer", "wecare-plivo-answer",
     "optional ?token= (PLIVO_ANSWER_TOKEN); Plivo does not sign answer_url", "CONFIGURED at provider"),
    ("Sinch SMS DLR", "POST", "/webhook/sinch-dlr", "wecare-sinch-dlr", "unsigned callback", "route live"),
    ("Sinch RCS", "POST", "/webhook/sinch-rcs", "wecare-rcs-dlr", "unsigned callback", "route live"),
    ("Airtel IQ SMS inbound", "POST", "/sms-in/airtel", "wecare-sms-in-airtel", "unsigned callback", "route live"),
    ("Airtel IQ voice C2C", "POST", "/voice-in/c2c", "wecare-voice-in-c2c", "unsigned callback", "route live"),
    ("Airtel IQ voice CDR", "POST", "/voice-in/cdr", "wecare-voice-in-cdr", "unsigned callback", "route live"),
    ("Airtel IQ voice OBD", "POST", "/voice-in/obd", "wecare-voice-in-obd", "unsigned callback", "route live"),
    ("Voice CDR", "POST", "/voice-cdr-webhook", "wecare-voice-cdr-read", "unsigned callback", "route live"),
]


def fp(v: str) -> str:
    return f"len={len(v)} {v[:4]}…{v[-2:]}" if len(v) > 8 else f"len={len(v)}"


def verify_aws_keys() -> list[str]:
    """Compare the AWS key id across all three stores. Fingerprints only."""
    out = []
    # ~/.aws/credentials - read the id only, never the secret
    cred = Path.home() / ".aws/credentials"
    ids: dict[str, str] = {}
    if cred.exists():
        prof = None
        for ln in cred.read_text(errors="replace").splitlines():
            ln = ln.strip()
            if ln.startswith("[") and ln.endswith("]"):
                prof = ln[1:-1]
            elif prof and ln.lower().startswith("aws_access_key_id"):
                ids[prof] = ln.split("=", 1)[1].strip()
    for prof, kid in sorted(ids.items()):
        out.append(f"  ~/.aws/credentials [{prof}]  access_key_id {fp(kid)}")

    sm = boto3.client("secretsmanager", region_name=REGION)
    try:
        d = json.loads(sm.get_secret_value(SecretId="wecare/aws/iam-access-keys")["SecretString"])
        accts = d.get("accounts", {})
        found = []
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, str) and re.fullmatch(r"(?:AKI|ASI)A[0-9A-Z]{16}", v):
                        found.append(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for i in o:
                    walk(i)
        walk(accts)
        for kid in sorted(set(found)):
            out.append(f"  Secrets Manager wecare/aws/iam-access-keys  {fp(kid)}")
        matched = set(found) & set(ids.values())
        out.append(f"  MATCH between credentials file and Secrets Manager: "
                   f"{len(matched)} key id(s)")
    except ClientError as exc:
        out.append(f"  Secrets Manager read failed: {exc.response['Error']['Code']}")

    # the TXT ledger
    if TXT.exists():
        t = TXT.read_text(errors="replace")
        n = len(set(re.findall(r"(?:AKI|ASI)A[0-9A-Z]{16}", t)))
        out.append(f"  TXT ledger contains {n} distinct AWS key id(s)")
        present = [k for k in ids.values() if k in t]
        out.append(f"  TXT ledger carries the ACTIVE key id: "
                   f"{'YES' if present else 'NO'}")
    return out


def registry_block() -> str:
    now = datetime.now(timezone.utc).isoformat()
    L = [BEGIN, "",
         "##########################################################################",
         "WEBHOOK REGISTRY - inbound endpoints (record only; NOT secrets)",
         "##########################################################################",
         f"last_synced          = {now}",
         f"api_gateway          = zllr9lrg7j  ({ACCOUNT} / {REGION})",
         f"base_url             = {BASE}",
         f"also_in_secrets_mgr  = {CONFIG_SECRET}",
         f"also_in_repo         = docs/WEBHOOK-INVENTORY.md",
         "",
         "NOTE: webhook SECRETS are not recorded here. Razorpay's signing secret",
         "lives only in Secrets Manager wecare/razorpay-webhook:webhook_secret, and",
         "it must match the value configured in the Razorpay dashboard - change one",
         "without the other and every payment webhook fails signature verification.",
         ""]
    for i, (prov, method, path, fn, auth, status) in enumerate(WEBHOOKS, 1):
        L += [f"[{i}] {prov}",
              f"    url      = {BASE}{path}",
              f"    method   = {method}",
              f"    lambda   = {fn}",
              f"    auth     = {auth}",
              f"    status   = {status}",
              ""]
    L += ["Razorpay events: 31 handled and all subscribed. Two names appearing in",
          "the handler are NOT valid Razorpay events and cannot be subscribed:",
          "  fund_account.validation  - a dict key, not an event (handler.py:1386)",
          "  payment.pending          - unreachable branch (handler.py:120)",
          "Razorpay rejects both with BAD_REQUEST_ERROR 'Invalid event name/names'.",
          "Webhook editing is dashboard-only on this account: no API update verb is",
          "accepted (PUT 400, PATCH 404, account-scoped variants 404).",
          "", END]
    return "\n".join(L)


def write_txt(block: str, dry: bool) -> str:
    original = TXT.read_text(errors="replace")
    if BEGIN in original and END in original:
        updated = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block,
                         original, flags=re.S)
        action = "REPLACED existing block"
    else:
        sep = "" if original.endswith("\n") else "\n"
        updated = original + sep + "\n" + block + "\n"
        action = "APPENDED new block"
    if dry:
        return f"{action} (dry run, not written). size {len(original)} -> {len(updated)}"

    mode = os.stat(TXT).st_mode & 0o777
    tmp = TXT.with_name(TXT.name + ".tmp-sync")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(updated)
    os.replace(tmp, TXT)
    os.chmod(TXT, mode)
    assert not tmp.exists()
    return f"{action}. size {len(original)} -> {len(updated)}, mode {oct(mode)[-3:]}"


def write_secret(dry: bool) -> str:
    payload = {
        "_note": "Inbound webhook registry. URLs are not secrets. Signing secrets "
                 "are NOT stored here.",
        "last_synced": datetime.now(timezone.utc).isoformat(),
        "api_gateway": "zllr9lrg7j",
        "base_url": BASE,
        "webhooks": [
            {"provider": p, "method": m, "url": BASE + path, "lambda": fn,
             "auth": a, "status": s}
            for p, m, path, fn, a, s in WEBHOOKS
        ],
        "razorpay": {
            "webhook_id": "TTtfLAe18fnqax",
            "url": f"{BASE}/razorpay-webhook",
            "handled_events": 31,
            "all_handled_subscribed": True,
            "invalid_names_in_handler": ["fund_account.validation", "payment.pending"],
            "api_editing_supported": False,
            "secret_location": "wecare/razorpay-webhook:webhook_secret",
        },
    }
    if dry:
        return f"would write {CONFIG_SECRET} ({len(json.dumps(payload))} bytes)"
    sm = boto3.client("secretsmanager", region_name=REGION)
    body = json.dumps(payload, indent=2)
    try:
        r = sm.put_secret_value(SecretId=CONFIG_SECRET, SecretString=body)
        return f"updated {CONFIG_SECRET} -> version {r['VersionId'][:8]}…"
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        r = sm.create_secret(Name=CONFIG_SECRET, SecretString=body,
                             Description="Inbound webhook registry (config, not secrets)")
        return f"created {CONFIG_SECRET} -> version {r['VersionId'][:8]}…"


def main() -> int:
    dry = "--dry-run" in sys.argv
    print("=== AWS access key consistency (verify, not rotate) ===")
    for line in verify_aws_keys():
        print(line)
    print("\n=== Secrets Manager webhook registry ===")
    print("  " + write_secret(dry))
    print("\n=== TXT ledger webhook block ===")
    print("  " + write_txt(registry_block(), dry))
    if dry:
        print("\ndry run: nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
