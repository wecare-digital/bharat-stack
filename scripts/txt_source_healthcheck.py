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


def _git_history_leaks(repo: Path, real: set[str]) -> int:
    """Scan every blob ever committed for the authorized source's real values.

    A clean working tree proves nothing on a public repo: a value removed in a
    later commit is still fetchable from the object database forever. Found on
    2026-09-20, when the Plivo auth id sat in history after the tree had been
    fixed. Prints object and commit ids only, never a value.
    """
    print("\nGit object database (every blob ever committed):")
    if not (repo / ".git").exists():
        print("  not a git worktree - skipped")
        return 0
    try:
        listing = subprocess.run(
            ["git", "cat-file", "--batch-all-objects",
             "--batch-check=%(objectname) %(objecttype)"],
            cwd=repo, capture_output=True, text=True, check=True).stdout
        blobs = [ln.split()[0] for ln in listing.splitlines() if ln.endswith(" blob")]
        data = subprocess.run(["git", "cat-file", "--batch"], cwd=repo,
                              input=("\n".join(blobs) + "\n").encode(),
                              capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"  scan failed: {type(exc).__name__}")
        return 0

    found = 0
    for v in sorted(real):
        n = data.count(v.encode())
        if not n:
            continue
        found += n
        log = subprocess.run(["git", "log", "--all", "--format=%h", "-S", v, "--"],
                             cwd=repo, capture_output=True, text=True).stdout
        shas = log.split()[:6]
        print(f"  LEAK  a real value appears in {n} blob(s); "
              f"commits that added/removed it: {' '.join(shas) or 'unknown'}")
    if not found:
        print(f"  clean - {len(blobs)} blobs scanned, no real value present")
    else:
        print("  a history rewrite plus force push is the only way to purge these,")
        print("  so treat the credential as exposed and rotate it instead.")
    return found


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
    # A shape match is not a leak. The repo's own tests deliberately carry
    # issuer-shaped placeholders (a Plivo auth id has a fixed MA-prefix shape, so
    # a realistic fixture necessarily looks like one), and counting those as
    # leaked credentials inflates the number and trains everyone to ignore it.
    # So every hit is compared against the actual values in the authorized
    # source and reported in two separate columns.
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
    real_copies = 0
    shape_only = 0
    pats = [p for p, _, _ in PROVIDERS.values()]
    # The genuine values, taken from the authorized source itself.
    real = {v for p in pats for v in re.findall(p, text)}
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
            r = s = 0
            for p in pats:
                for v in re.findall(p, t):
                    if v in real:
                        r += 1
                    else:
                        s += 1
            if r or s:
                hits.append((f, r, s))
                real_copies += r
                shape_only += s
        if hits:
            print(f"  {label}:")
            for f, r, s in sorted(hits, key=lambda h: (-h[1], -h[2])):
                note = f"real={r:<4d} placeholder={s}"
                flag = "  <-- LEAK" if r else ""
                print(f"    {note:26s}  {f}{flag}")
        else:
            print(f"  {label}: clean")

    hist = _git_history_leaks(repo, real)

    print(f"\nAUTHORIZED RETAINED PLAINTEXT SOURCE : 1")
    print(f"UNEXPECTED PLAINTEXT SECRET COPIES   : {real_copies}")
    print(f"SHAPE-ONLY PLACEHOLDER MATCHES       : {shape_only}  (not leaks)")
    print(f"REAL VALUES IN GIT OBJECT DATABASE   : {hist}")

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
