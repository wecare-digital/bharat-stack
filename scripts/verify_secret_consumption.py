#!/usr/bin/env python3
"""Prove the fleet reads credentials from Secrets Manager, not from anywhere else.

A repository can be clean of credentials while production still hands them to
code some other way. The usual other way is a Lambda environment variable, which
is visible to anyone with `lambda:GetFunctionConfiguration`, is printed by the
console, and lands in CloudFormation templates and deploy logs. Removing a key
from git does not fix that, so this checks the deployed configuration too.

Three questions, answered against the live account:

1. Does any deployed function carry a real secret value in its environment?
   Every environment variable is compared against the actual values in Secrets
   Manager, and against issuer-anchored shapes for credentials that may never
   have reached Secrets Manager.
2. Does the source read credentials by reference? Counts the functions calling
   `get_secret_value` and the secret ids they name.
3. Does every secret id named in source actually exist? A typo fails closed at
   runtime, in the request path, which is the worst place to find out.

Passing a *name* in an environment variable is correct and expected - that is
what by-reference means - so `..._SECRET=wecare/plivo/api` is a pass, while a
variable holding the value is a failure.

Values are held in memory, reported as a sha256 prefix, never printed.

Usage:
    python scripts/verify_secret_consumption.py
    python scripts/verify_secret_consumption.py --json

Exit status: 0 when no credential value reaches a function environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-1"
FUNCTIONS = ROOT / "amplify" / "functions"

SECRET_FIELD = re.compile(
    r"(secret|token|password|passphrase|api_key|apikey|private_key|"
    r"auth_token|access_key|client_secret|webhook|credential)", re.I)
CONFIG_FIELD = re.compile(r"(_name|_url|_uri|_arn|_id$|_lambda|_region|_at$|"
                          r"last_updated|_status|_type|_path)", re.I)

SHAPES = {
    "razorpay live key": "rzp" + r"_live_[A-Za-z0-9]{8,}",
    "openai key":        "sk-" + r"(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{30,}",
    "google api key":    "AIz" + r"a[A-Za-z0-9_\-]{30,}",
    "aws access key id": r"(?:AKI" + r"A|ASI" + r"A)[0-9A-Z]{16}",
    "github token":      "gh" + r"[pousr]_[A-Za-z0-9]{30,}",
    "stripe live key":   r"(?:s|p|r)k" + r"_live_[A-Za-z0-9]{16,}",
    "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}

# An environment variable holding a secret *name* is the correct pattern.
BY_REFERENCE = re.compile(r"^(wecare/|arn:aws:secretsmanager:)")


def digest(v: str) -> str:
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:8]


def load_secrets(sm) -> tuple[dict[str, str], set[str]]:
    """Return {value: 'secret_id:field'} for credential fields, and all ids."""
    ids: set[str] = set()
    for page in sm.get_paginator("list_secrets").paginate():
        for s in page["SecretList"]:
            ids.add(s["Name"])
    creds: dict[str, str] = {}
    for sid in sorted(i for i in ids if i.startswith("wecare/")):
        try:
            doc = json.loads(sm.get_secret_value(SecretId=sid)["SecretString"])
        except (ClientError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        for field, value in doc.items():
            if (isinstance(value, str) and len(value) >= 12
                    and SECRET_FIELD.search(field) and not CONFIG_FIELD.search(field)):
                creds[value] = f"{sid}:{field}"
    return creds, ids


def source_consumers() -> dict[str, set[str]]:
    """Map each source file that reads Secrets Manager to the secret ids it names."""
    out: dict[str, set[str]] = {}
    pat_ids = re.compile(r"['\"](wecare/[A-Za-z0-9/_\-]+)['\"]")
    for p in FUNCTIONS.rglob("*.py"):
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        if "get_secret_value" not in text:
            continue
        out[p.relative_to(ROOT).as_posix()] = set(pat_ids.findall(text))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    sm = boto3.client("secretsmanager", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)

    print("=" * 74)
    print("SECRET CONSUMPTION VERIFICATION - values are never printed")
    print("=" * 74)

    creds, all_ids = load_secrets(sm)
    print(f"\nSecrets Manager: {len(all_ids)} secret(s), "
          f"{len(creds)} credential-classed field(s) to look for")

    print("\n1. deployed function environments")
    names: list[str] = []
    for page in lam.get_paginator("list_functions").paginate():
        names += [f["FunctionName"] for f in page["Functions"]]
    leaks, byref, plain = [], 0, 0
    for name in sorted(names):
        try:
            cfg = lam.get_function_configuration(FunctionName=name)
        except ClientError as exc:
            print(f"  unreadable {name}: {exc.response['Error']['Code']}")
            continue
        env = (cfg.get("Environment") or {}).get("Variables") or {}
        for key, value in env.items():
            if not isinstance(value, str):
                continue
            if value in creds:
                leaks.append((name, key, creds[value], digest(value), "exact value"))
                continue
            shape = next((lab for lab, pat in SHAPES.items() if re.search(pat, value)), None)
            if shape:
                leaks.append((name, key, shape, digest(value), "issuer shape"))
                continue
            if BY_REFERENCE.match(value):
                byref += 1
            else:
                plain += 1
    print(f"  {len(names)} function(s) inspected")
    print(f"  {byref} variable(s) hold a secret name or ARN (by reference - correct)")
    print(f"  {plain} variable(s) hold ordinary configuration")
    if leaks:
        for name, key, what, fp, how in leaks:
            print(f"  LEAK  {name}  env {key}  = {what}  sha256:{fp}  ({how})")
    else:
        print("  no environment variable holds a credential value")

    print("\n2. source reads credentials by reference")
    consumers = source_consumers()
    referenced: set[str] = set()
    for f, sids in sorted(consumers.items()):
        referenced |= sids
    print(f"  {len(consumers)} source file(s) call get_secret_value")
    print(f"  {len(referenced)} distinct secret id(s) named in source")

    print("\n3. every secret id named in source exists")
    missing = sorted(s for s in referenced if s not in all_ids)
    dynamic = sorted(s for s in referenced if s.endswith("/"))
    for s in missing:
        if s in dynamic:
            print(f"  prefix  {s}  (built at runtime, per-tenant)")
        else:
            print(f"  MISSING {s}  named in source but absent from Secrets Manager")
    hard_missing = [s for s in missing if s not in dynamic]
    if not hard_missing:
        print("  all resolvable ids exist")

    unused = sorted(i for i in all_ids
                    if i.startswith("wecare/") and i not in referenced)
    print(f"\n  {len(unused)} wecare secret(s) not named by any function "
          f"(console/ops use or stale)")

    print("\n" + "=" * 74)
    print(f"credential values in function environments : {len(leaks)}")
    print(f"source files reading Secrets Manager       : {len(consumers)}")
    print(f"missing secret ids                         : {len(hard_missing)}")
    verdict = "PASS" if not leaks and not hard_missing else "FAIL"
    print(f"RESULT: {verdict}")
    print("=" * 74)

    if args.json:
        print(json.dumps({
            "leaks": [{"function": n, "env": k, "what": w, "fp": f, "how": h}
                      for n, k, w, f, h in leaks],
            "consumers": {k: sorted(v) for k, v in consumers.items()},
            "unused_secrets": unused,
            "missing_ids": hard_missing,
        }, indent=2))
    return 0 if not leaks and not hard_missing else 1


if __name__ == "__main__":
    sys.exit(main())
