#!/usr/bin/env python3
"""Give Lambda environment variables a source of truth, and detect drift from it.

326 environment variables across 58 functions existed only in the live AWS
configuration. Nothing in the repository described them: the `environment:` blocks
in `amplify/functions/*/resource.ts` were never deployed, because those functions
are not passed to `defineBackend`, so they synthesized nothing and were deleted on
2026-09-20. `deploy_all_lambdas.py` uploads code and never touches configuration.

That is how the live `VERIFY_TOKEN` holding a real credential stayed invisible for
months: there was nowhere in the repo it could have shown up, and no check that
could have compared intent against reality.

This does not deploy anything. It records what is live, so that a change becomes
visible in a diff, and fails when reality and the record disagree.

    python scripts/env_manifest.py --export     # write the manifest from live AWS
    python scripts/env_manifest.py              # check live against the manifest
    python scripts/env_manifest.py --json

Secret safety: every value is compared against the real values in Secrets Manager
and against issuer-anchored shapes. A credential-classed match is a hard failure -
the manifest is not written, because it is committed to a public repository. Any
other Secrets Manager match, or an issuer-shaped string, is stored as a sha256
prefix instead of the value, which still detects drift without disclosing anything.

Exit status: 0 in sync, 1 on drift or refusal.
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
MANIFEST = ROOT / "config" / "lambda-env-manifest.json"
REGION = "us-east-1"

SECRET_FIELD = re.compile(
    r"(secret|token|password|passphrase|api_key|apikey|private_key|"
    r"auth_token|access_key|client_secret|webhook|credential)", re.I)
CONFIG_FIELD = re.compile(r"(_name|_url|_uri|_arn|_id$|_lambda|_region|_at$|"
                          r"last_updated|_status|_type|_path)", re.I)

SHAPES = [
    "rzp" + r"_live_[A-Za-z0-9]{8,}",
    "sk-" + r"(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{30,}",
    "AIz" + r"a[A-Za-z0-9_\-]{30,}",
    r"(?:AKI" + r"A|ASI" + r"A)[0-9A-Z]{16}",
    "gh" + r"[pousr]_[A-Za-z0-9]{30,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
]

# Variables Lambda injects itself; they are not configuration anyone chose.
INJECTED = {"AWS_REGION", "AWS_EXECUTION_ENV", "AWS_LAMBDA_FUNCTION_NAME",
            "AWS_LAMBDA_FUNCTION_VERSION", "AWS_LAMBDA_LOG_GROUP_NAME",
            "AWS_LAMBDA_LOG_STREAM_NAME", "AWS_LAMBDA_INITIALIZATION_TYPE",
            "_HANDLER", "LAMBDA_TASK_ROOT", "LAMBDA_RUNTIME_DIR", "TZ"}

# Written by the maintenance tooling, so they change on every refresh and would
# otherwise report drift forever.
VOLATILE = {"SECRETS_REFRESHED_AT", "SECRETS_ROTATED_AT"}


def fp(v: str) -> str:
    return "sha256:" + hashlib.sha256(v.encode()).hexdigest()[:12]


def load_secret_values(sm) -> tuple[dict[str, str], set[str]]:
    """({value: label} for credential fields, {all values}) from Secrets Manager."""
    creds: dict[str, str] = {}
    every: set[str] = set()
    ids = []
    for page in sm.get_paginator("list_secrets").paginate():
        ids += [s["Name"] for s in page["SecretList"] if s["Name"].startswith("wecare/")]
    for sid in sorted(ids):
        try:
            doc = json.loads(sm.get_secret_value(SecretId=sid)["SecretString"])
        except (ClientError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        for field, value in doc.items():
            if not isinstance(value, str) or len(value) < 12:
                continue
            every.add(value)
            if SECRET_FIELD.search(field) and not CONFIG_FIELD.search(field):
                creds[value] = f"{sid}:{field}"
    return creds, every


def live_env(lam) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for page in lam.get_paginator("list_functions").paginate():
        for f in page["Functions"]:
            env = (f.get("Environment") or {}).get("Variables") or {}
            out[f["FunctionName"]] = {
                k: v for k, v in sorted(env.items())
                if k not in INJECTED and k not in VOLATILE
            }
    return dict(sorted(out.items()))


def classify(value: str, creds: dict[str, str], every: set[str]) -> tuple[str, str | None]:
    """Return (stored_form, refusal_reason).

    Credential matching is by substring, not equality. A credential rarely sits
    alone in a variable - it arrives embedded, as
    `https://host/path?token=<secret>`, and an equality check walks straight past
    that. Non-credential Secrets Manager values are matched by equality only,
    because some of them are short generic strings (a trunk name, a domain) that
    are substrings of half the table names in the account, and refusing on those
    would make the guard useless.
    """
    for secret, label in creds.items():
        if secret in value:
            where = "holds" if secret == value else "contains"
            return value, f"{where} {label}"
    if value in every:
        return fp(value), None
    for pat in SHAPES:
        if re.search(pat, value):
            return fp(value), None
    return value, None


def build(lam, sm) -> tuple[dict, list[str]]:
    creds, every = load_secret_values(sm)
    refusals, fingerprinted = [], 0
    manifest: dict[str, dict[str, str]] = {}
    for fn, env in live_env(lam).items():
        row = {}
        for k, v in env.items():
            stored, refuse = classify(v, creds, every)
            if refuse:
                refusals.append(f"{fn} -> {k}: {refuse}")
            if stored != v:
                fingerprinted += 1
            row[k] = stored
        manifest[fn] = row
    doc = {
        "_comment": (
            "Recorded state of live Lambda environment variables. Not deployed by "
            "anything - this is the source of truth to diff against. Regenerate "
            "with scripts/env_manifest.py --export; verify with no arguments."
        ),
        "_region": REGION,
        "_functions": len(manifest),
        "_variables": sum(len(v) for v in manifest.values()),
        "_fingerprinted": fingerprinted,
        "functions": manifest,
    }
    return doc, refusals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true", help="write the manifest")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    lam = boto3.client("lambda", region_name=REGION)
    sm = boto3.client("secretsmanager", region_name=REGION)

    doc, refusals = build(lam, sm)

    if refusals:
        print("REFUSING: a live environment variable holds a real credential value.")
        print("Move it to Secrets Manager and pass the secret NAME instead.")
        for r in refusals:
            print(f"  {r}")
        print("\nNothing was written. scripts/refresh_secret_consumers.py applies the")
        print("change once the code reads it by reference.")
        return 1

    if args.export:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
        print(f"wrote {MANIFEST.relative_to(ROOT)}")
        print(f"  {doc['_functions']} functions, {doc['_variables']} variables, "
              f"{doc['_fingerprinted']} stored as a fingerprint")
        return 0

    if not MANIFEST.exists():
        print(f"no manifest at {MANIFEST.relative_to(ROOT)} - run --export first")
        return 1

    recorded = json.loads(MANIFEST.read_text())["functions"]
    current = doc["functions"]

    added_fns = sorted(set(current) - set(recorded))
    removed_fns = sorted(set(recorded) - set(current))
    drift: list[tuple[str, str, str]] = []
    for fn in sorted(set(current) & set(recorded)):
        cur, rec = current[fn], recorded[fn]
        for k in sorted(set(cur) - set(rec)):
            drift.append((fn, k, "added live, absent from the manifest"))
        for k in sorted(set(rec) - set(cur)):
            drift.append((fn, k, "in the manifest, missing live"))
        for k in sorted(set(cur) & set(rec)):
            if cur[k] != rec[k]:
                shown = "value changed" if not rec[k].startswith("sha256:") \
                    else "fingerprint changed"
                drift.append((fn, k, shown))

    print("=" * 74)
    print("LAMBDA ENVIRONMENT DRIFT")
    print("=" * 74)
    print(f"manifest: {len(recorded)} function(s)   live: {len(current)} function(s)")
    for fn in added_fns:
        print(f"  NEW FUNCTION live, not in the manifest: {fn}")
    for fn in removed_fns:
        print(f"  GONE from live, still in the manifest:  {fn}")
    for fn, k, what in drift:
        print(f"  {fn:38s} {k:26s} {what}")
    total = len(added_fns) + len(removed_fns) + len(drift)
    print("\n" + "=" * 74)
    print(f"differences: {total}")
    print(f"RESULT: {'IN SYNC' if total == 0 else 'DRIFT'}")
    print("=" * 74)
    if args.json:
        print(json.dumps({"added_functions": added_fns, "removed_functions": removed_fns,
                          "drift": [{"function": f, "var": k, "what": w}
                                    for f, k, w in drift]}, indent=2))
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
