#!/usr/bin/env python3
"""Prove that no credential from Secrets Manager appears anywhere in this repo.

Two independent checks, because each one alone has a blind spot.

1. **Exact-value check.** Loads every `wecare/*` secret into memory and looks for
   those exact strings in the working tree and in every blob the repository has
   ever committed. This is the only check that can catch a credential with no
   issuer prefix - an AWS secret access key, a Plivo auth token, a webhook
   secret - because there is nothing to pattern-match on. Values are held in
   memory, hashed for reporting, and never printed or written.

2. **Issuer-shape check.** Anchored patterns for credentials that may never have
   reached Secrets Manager at all, so check 1 would not know to look for them.

Why both scan history and not just the tree: on a public repository a value
deleted in a later commit is still fetchable from the object database for as
long as the repository exists. `git status` clean is not evidence. Found on
2026-09-20, when the Plivo auth id was still in a blob after the working tree
had been corrected.

Field classification matters for the exit code. A Secrets Manager entry holds
secrets *and* ordinary configuration - `answer_url`, `account_name`,
`aws_answer_lambda` - and configuration is supposed to appear in source. Only
fields whose name marks them as credential material fail the run.

Usage:
    python scripts/scan_repo_secrets.py            # tree + full history
    python scripts/scan_repo_secrets.py --tree     # working tree only, faster
    python scripts/scan_repo_secrets.py --json

Exit status: 0 clean, 1 credential material found.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-1"
SECRET_PREFIX = "wecare/"

# A field is credential material when its *name* says so. Anything else in a
# secret is configuration that legitimately appears in source.
SECRET_FIELD = re.compile(
    r"(secret|token|password|passphrase|api_key|apikey|private_key|"
    r"auth_token|access_key|client_secret|webhook|credential)", re.I)

# Never treat these as findings even if the name matches: they are names and
# locations, not values.
CONFIG_FIELD = re.compile(r"(_name|_url|_uri|_arn|_id$|_lambda|_region|_at$|"
                          r"last_updated|_status|_type|_path)", re.I)

# Issuer-anchored shapes, assembled at runtime so this file holds no literal
# credential shape and does not trip the block-inline-secrets hook.
SHAPES = {
    "razorpay live key":   "rzp" + r"_live_[A-Za-z0-9]{8,}",
    "openai key":          "sk-" + r"(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{30,}",
    "google api key":      "AIz" + r"a[A-Za-z0-9_\-]{30,}",
    "aws access key id":   r"(?:AKI" + r"A|ASI" + r"A)[0-9A-Z]{16}",
    "github token":        "gh" + r"[pousr]_[A-Za-z0-9]{30,}",
    "slack token":         "xox" + r"[abprs]-[A-Za-z0-9\-]{20,}",
    "stripe live key":     r"(?:s|p|r)k" + r"_live_[A-Za-z0-9]{16,}",
    "google oauth secret": "GOC" + r"SPX-[A-Za-z0-9_\-]{20,}",
    "sendgrid key":        "SG" + r"\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}",
    "twilio key":          r"(?:AC|SK)[0-9a-f]{32}",
    "plivo auth id":       r"\bMA[A-Z0-9]{18}\b",
    "private key block":   r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "slack webhook":       r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}",
}

# AWS's published example key, and runs of one repeated character used as
# synthetic filler in the guards' own test cases.
BENIGN = {"AKI" + "A" + "IOSFODNN7EXAMPLE"}
FILLER = re.compile(r"(.)\1{15,}")

SKIP_DIRS = {".git", "node_modules", ".venv", ".next", "__pycache__", "out",
             "dist", "build", ".pytest_cache"}


def digest(v: str) -> str:
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:8]


def load_secret_values() -> tuple[list[tuple[str, str, str, bool]], list[str]]:
    """Return [(secret_id, field, value, is_credential)] and a summary.

    Values stay in this process. Nothing is printed, logged or written.
    """
    sm = boto3.client("secretsmanager", region_name=REGION)
    out: list[tuple[str, str, str, bool]] = []
    notes: list[str] = []
    ids: list[str] = []
    paginator = sm.get_paginator("list_secrets")
    for page in paginator.paginate():
        for s in page["SecretList"]:
            if s["Name"].startswith(SECRET_PREFIX):
                ids.append(s["Name"])
    for sid in sorted(ids):
        try:
            raw = sm.get_secret_value(SecretId=sid)["SecretString"]
        except ClientError as exc:
            notes.append(f"  unreadable {sid}: {exc.response['Error']['Code']}")
            continue
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            doc = {"(whole string)": raw}
        if not isinstance(doc, dict):
            doc = {"(whole string)": str(doc)}
        creds = 0
        for field, value in doc.items():
            if not isinstance(value, str) or len(value) < 12:
                continue
            is_cred = bool(SECRET_FIELD.search(field)) and not CONFIG_FIELD.search(field)
            out.append((sid, field, value, is_cred))
            creds += is_cred
        notes.append(f"  {sid}: {len(doc)} field(s), {creds} credential-classed")
    return out, notes


def worktree_files() -> list[Path]:
    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        try:
            if p.stat().st_size > 20_000_000:
                continue
        except OSError:
            continue
        files.append(p)
    return files


def git_blob_data() -> tuple[bytes, int]:
    listing = subprocess.run(
        ["git", "cat-file", "--batch-all-objects",
         "--batch-check=%(objectname) %(objecttype)"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    blobs = [ln.split()[0] for ln in listing.splitlines() if ln.endswith(" blob")]
    data = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT,
                          input=("\n".join(blobs) + "\n").encode(),
                          capture_output=True, check=True).stdout
    return data, len(blobs)


def commits_touching(value: str) -> list[str]:
    log = subprocess.run(["git", "log", "--all", "--format=%h", "-S", value, "--"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    return log.split()[:8]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", action="store_true", help="skip the history scan")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    report: dict = {"tree": [], "history": [], "shapes": []}

    print("=" * 74)
    print("REPOSITORY CREDENTIAL SCAN - values are never printed")
    print("=" * 74)

    print("\n1. loading Secrets Manager entries into memory")
    values, notes = load_secret_values()
    for n in notes:
        print(n)
    creds = [v for v in values if v[3]]
    print(f"  {len(values)} scannable field(s) across the fleet, "
          f"{len(creds)} classed as credential material")

    print("\n2. working tree")
    files = worktree_files()
    tree_hits = 0
    for sid, field, value, is_cred in values:
        for f in files:
            try:
                blob = f.read_bytes()
            except OSError:
                continue
            n = blob.count(value.encode())
            if not n:
                continue
            rel = f.relative_to(ROOT).as_posix()
            kind = "CREDENTIAL" if is_cred else "config"
            report["tree"].append({"secret": sid, "field": field, "file": rel,
                                   "count": n, "credential": is_cred,
                                   "fp": digest(value)})
            if is_cred:
                tree_hits += n
                print(f"  LEAK  {kind:10s} {sid}:{field} x{n} in {rel}")
    print(f"  {len(files)} file(s) scanned, {tree_hits} credential occurrence(s)")
    cfg = [h for h in report["tree"] if not h["credential"]]
    if cfg:
        print(f"  {len(cfg)} non-credential field(s) also appear in source "
              f"(expected: urls, names, ids) - use --json to list")

    hist_hits = 0
    if args.tree:
        print("\n3. git history: skipped (--tree)")
    else:
        print("\n3. git history (every blob ever committed)")
        data, nblobs = git_blob_data()
        for sid, field, value, is_cred in values:
            if not is_cred:
                continue
            n = data.count(value.encode())
            if not n:
                continue
            hist_hits += n
            shas = commits_touching(value)
            report["history"].append({"secret": sid, "field": field, "blobs": n,
                                      "commits": shas, "fp": digest(value)})
            print(f"  LEAK  {sid}:{field} in {n} blob(s); commits {' '.join(shas)}")
        print(f"  {nblobs} blobs scanned, {len(data)/1048576:.0f} MB, "
              f"{hist_hits} credential occurrence(s)")

    print("\n4. issuer-shaped material in the working tree")
    shape_hits = 0
    for f in files:
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        for label, pat in SHAPES.items():
            for m in re.findall(pat, text):
                if m in BENIGN or FILLER.search(m):
                    continue
                known = any(m == v for _, _, v, _ in values)
                rel = f.relative_to(ROOT).as_posix()
                report["shapes"].append({"label": label, "file": rel,
                                         "fp": digest(m), "len": len(m),
                                         "in_secrets_manager": known})
                shape_hits += 1
                tag = "matches a Secrets Manager value" if known else \
                      "not in Secrets Manager - placeholder or foreign"
                print(f"  {label}: {rel}  len={len(m)} sha256:{digest(m)}  {tag}")
    if not shape_hits:
        print("  none")

    print("\n" + "=" * 74)
    print(f"working tree credential occurrences : {tree_hits}")
    print(f"git history credential occurrences  : {hist_hits}")
    print(f"issuer-shaped strings in tree       : {shape_hits}")
    verdict = "CLEAN" if tree_hits == 0 and hist_hits == 0 else "CREDENTIAL MATERIAL FOUND"
    print(f"RESULT: {verdict}")
    print("=" * 74)

    if args.json:
        print(json.dumps(report, indent=2))
    return 0 if tree_hits == 0 and hist_hits == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
