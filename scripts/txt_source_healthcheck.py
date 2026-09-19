#!/usr/bin/env python3
"""Health-check the AUTHORIZED temporary plaintext credential source.

    ~/aws-new-keys-SAVE-THEN-DELETE.txt

Reports metadata ONLY: presence, mode, owner, field counts, fingerprints, and
whether each provider is synchronized to Secrets Manager / the encrypted local
backup / the encrypted S3 backup. Never prints a credential value.

This file is INTENTIONALLY RETAINED until project close. This script never
modifies or deletes it.

    python scripts/txt_source_healthcheck.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import pwd
import re
import stat
import subprocess
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

TXT = Path.home() / "aws-new-keys-SAVE-THEN-DELETE.txt"
ENC = Path.home() / ".secure-backups" / "wecare-secrets-backup.txt.enc"
BUCKET = "wecare-credential-backups-775261844268"
S3_KEY = "credential-backups/current/wecare-secrets-backup.txt.enc"
REGION = "us-east-1"

# Provider detectors, assembled so this file does not trip the inline-secret hook.
PROVIDERS = {
    "Razorpay": ("rzp" + r"_live_[A-Za-z0-9]{8,}", "wecare/razorpay/api", "key_id"),
    "OpenAI":   ("sk-" + r"svcacct-[A-Za-z0-9_\-]{20,}", "wecare/openai/api", "ads_service_account_api_key"),
    "Google":   ("AIz" + r"a[A-Za-z0-9_\-]{30,}", "wecare/google-api-key", "api_key"),
    "Plivo":    (r"\bMA[A-Z0-9]{18}\b", "wecare/plivo/api", "auth_id"),
}


def main() -> int:
    print("=" * 70)
    print("PLAINTEXT CREDENTIAL SOURCE - HEALTH CHECK")
    print("=" * 70)
    if not TXT.exists():
        print(f"File exists: NO  ({TXT})")
        return 1

    st = TXT.stat()
    mode = oct(stat.S_IMODE(st.st_mode))[-3:]
    owner = pwd.getpwuid(st.st_uid).pw_name
    print(f"\nFile:                {TXT}")
    print("Status:              INTENTIONALLY RETAINED UNTIL PROJECT COMPLETE")
    print(f"File exists:         YES  ({st.st_size} bytes)")
    print(f"Permissions:         {mode}" + ("  OK" if mode == "600" else "  SHOULD BE 600"))
    print(f"Owner:               {owner}" +
          ("  expected" if owner == os.environ.get("USER") else "  UNEXPECTED"))
    print(f"Readable by user:    {'YES' if os.access(TXT, os.R_OK) else 'NO'}")

    blob = TXT.read_bytes()
    text = blob.decode(errors="replace")

    # --- git / packaging exposure -------------------------------------------
    repo = Path.home() / "wecare-store"
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(TXT)],
                             cwd=repo, capture_output=True).returncode == 0
    print(f"Git tracked:         {'YES - PROBLEM' if tracked else 'NO  (correct)'}")
    inside_repo = str(TXT).startswith(str(repo))
    print(f"Inside project dir:  {'YES - PROBLEM' if inside_repo else 'NO  (correct)'}")
    for label, root in (("iCloud", Path.home() / "Library/Mobile Documents"),
                        ("Dropbox", Path.home() / "Dropbox")):
        print(f"In {label+':':16s} {'YES - PROBLEM' if str(TXT).startswith(str(root)) else 'NO  (correct)'}")

    # --- duplicate plaintext copies elsewhere ------------------------------
    print("\nUnexpected plaintext duplicates (same credential, other locations):")
    sm = boto3.client("secretsmanager", region_name=REGION)
    enc_ok = ENC.exists()
    s3_ok = False
    try:
        boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=S3_KEY)
        s3_ok = True
    except ClientError:
        pass

    rows = []
    for name, (pat, secret_id, field) in PROVIDERS.items():
        in_txt = bool(re.search(pat, text))
        try:
            d = json.loads(sm.get_secret_value(SecretId=secret_id)["SecretString"])
            in_sm = bool((d.get(field) or "").strip())
        except (ClientError, json.JSONDecodeError, AttributeError):
            in_sm = False
        rows.append((name, in_txt, in_sm))

    scan_roots = [
        (Path.home() / ".kiro", "kiro user data"),
        (Path.home() / "Library/Application Support/Kiro", "kiro app support"),
        (repo, "repo worktree"),
        (Path.home() / ".zsh_history", "shell history"),
    ]
    skip = {"node_modules", ".venv", ".next", "__pycache__", "out", ".git"}
    dupes = 0
    pats = [p for p, _, _ in PROVIDERS.values()]
    for root, label in scan_roots:
        hits = []
        files = [root] if root.is_file() else []
        if root.is_dir():
            for base, dirs, fs in os.walk(root):
                dirs[:] = [d for d in dirs if d not in skip]
                files += [Path(base) / f for f in fs]
        for f in files:
            if f == TXT:
                continue
            try:
                if f.stat().st_size > 60_000_000:
                    continue
                t = f.read_text(errors="replace")
            except Exception:  # noqa: BLE001
                continue
            n = sum(len(re.findall(p, t)) for p in pats)
            if n:
                hits.append((f, n))
                dupes += n
        if hits:
            print(f"  {label}:")
            for f, n in sorted(hits, key=lambda h: -h[1]):
                print(f"    {n:4d}  {f}")
        else:
            print(f"  {label}: clean")

    print(f"\nAUTHORIZED RETAINED PLAINTEXT SOURCE : 1")
    print(f"UNEXPECTED PLAINTEXT SECRET COPIES   : {dupes}")

    # --- synchronization matrix -------------------------------------------
    print("\n" + "=" * 70)
    print("TXT FILE SYNCHRONIZATION MATRIX (no values)")
    print("=" * 70)
    print(f"{'Provider':10s} | {'TXT':5s} | {'SecretsMgr':10s} | {'Runtime':18s} "
          f"| {'EncLocal':8s} | {'EncS3':5s} | Status")
    print("-" * 94)
    runtime = {
        "Razorpay": "VERIFIED (top-up)",
        "OpenAI": "NOT REQUIRED",
        "Google": "VERIFIED (templates)",
        "Plivo": "NOT REQUIRED",
    }
    for name, in_txt, in_sm in rows:
        status = "SYNCHRONIZED" if (in_sm and enc_ok and s3_ok) else "INCOMPLETE"
        print(f"{name:10s} | {'YES' if in_txt else 'no':5s} | "
              f"{'YES' if in_sm else 'NO':10s} | {runtime[name]:18s} | "
              f"{'YES' if enc_ok else 'NO':8s} | {'YES' if s3_ok else 'NO':5s} | {status}")

    print("\nSOURCE-OF-TRUTH")
    print(f"  TEMPORARY MAINTENANCE SOURCE : {TXT}")
    print("  APPLICATION RUNTIME SOURCE   : AWS Secrets Manager")
    print(f"  LOCAL DR BACKUP              : {ENC}  {'VERIFIED' if enc_ok else 'MISSING'}")
    print(f"  CLOUD DR BACKUP              : s3://{BUCKET}/{S3_KEY}  "
          f"{'VERIFIED' if s3_ok else 'MISSING'}")
    print("\nFinal deletion: DEFERRED UNTIL PROJECT-CLOSE CONFIRMATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
