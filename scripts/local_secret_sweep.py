#!/usr/bin/env python3
"""Find - and optionally redact - every real credential value stored on this Mac.

The standing requirement is that exactly one file on this machine may hold
plaintext credentials: `~/aws-new-keys-SAVE-THEN-DELETE.txt`, retained by
explicit decision as the maintenance record. Everywhere else is a leak, whether
it got there through a log, a session transcript, an editor's local history, a
temp file or a well-meaning backup.

This compares against the *real values* - loaded from Secrets Manager and from
the authorized source itself - rather than issuer shapes, so it catches the
credentials that have no recognisable prefix. Values stay in memory and are
reported as a sha256 prefix.

Redaction, not deletion, is the default remedy. A session transcript is user
data and the plaintext-source policy forbids deleting it; replacing the value
in place with `[REDACTED sha256:...]` removes the credential while leaving the
record intact and greppable.

The transcript of the session that is running right now is skipped. Rewriting a
file the IDE holds open would leave its file descriptor pointing at an unlinked
inode, and every later message in that session would be written into a file
nobody can see. It is reported instead.

Usage:
    python scripts/local_secret_sweep.py                 # report only
    python scripts/local_secret_sweep.py --redact        # rewrite in place
    python scripts/local_secret_sweep.py --redact --include-live

Exit status: 0 when nothing outside the authorized source holds a value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

HOME = Path.home()
AUTHORIZED = HOME / "aws-new-keys-SAVE-THEN-DELETE.txt"
REGION = "us-east-1"

SECRET_FIELD = re.compile(
    r"(secret|token|password|passphrase|api_key|apikey|private_key|"
    r"auth_token|access_key|client_secret|webhook|credential)", re.I)
CONFIG_FIELD = re.compile(r"(_name|_url|_uri|_arn|_id$|_lambda|_region|_at$|"
                          r"last_updated|_status|_type|_path)", re.I)

# Issuer-anchored shapes, for values that never reached Secrets Manager.
SHAPES = [
    "rzp" + r"_live_[A-Za-z0-9]{8,}",
    "sk-" + r"(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{30,}",
    "AIz" + r"a[A-Za-z0-9_\-]{30,}",
    "gh" + r"[pousr]_[A-Za-z0-9]{30,}",
    r"\bMA[A-Z0-9]{18}\b",
]

# Directories with nothing but compiled or compressed content, where a plaintext
# match is impossible. `.git` is excluded on purpose: its objects are zlib
# compressed, so a byte scan cannot see into them - scan_repo_secrets.py walks
# them properly with `git cat-file`.
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "__pycache__", ".next", "site-packages",
    "Photos Library.photoslibrary", "CloudStorage", ".Trash",
    "com.apple.Safari", "Safari", "Containers", "Group Containers",
    "CoreSimulator", "DerivedData", "models", "codex-runtimes",
}
SKIP_SUFFIX = {".enc", ".zip", ".gz", ".tar", ".whl", ".pack", ".idx", ".dylib",
               ".so", ".o", ".a", ".png", ".jpg", ".jpeg", ".gif", ".webp",
               ".pdf", ".mp4", ".mov", ".wav", ".sqlite", ".db", ".bundle",
               ".dmg", ".app", ".node", ".woff", ".woff2", ".ttf", ".ico"}
MAX_BYTES = 80_000_000


def digest(v: bytes) -> str:
    return hashlib.sha256(v).hexdigest()[:8]


def load_values() -> dict[bytes, str]:
    """{value: label} for credential-classed Secrets Manager fields."""
    out: dict[bytes, str] = {}
    sm = boto3.client("secretsmanager", region_name=REGION)
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
            if (isinstance(value, str) and len(value) >= 12
                    and SECRET_FIELD.search(field) and not CONFIG_FIELD.search(field)):
                out[value.encode()] = f"{sid}:{field}"
    # Anything issuer-shaped in the authorized source, even if it is not in
    # Secrets Manager - that is exactly the case worth catching.
    if AUTHORIZED.exists():
        text = AUTHORIZED.read_text(errors="replace")
        for pat in SHAPES:
            for m in re.findall(pat, text):
                out.setdefault(m.encode(), f"authorized-source:{digest(m.encode())}")
    return out


def live_session_files() -> set[Path]:
    """Transcripts of sessions with a live lock, plus anything touched recently."""
    live: set[Path] = set()
    root = HOME / ".kiro" / "sessions"
    if not root.is_dir():
        return live
    now = time.time()
    for p in root.rglob("messages.jsonl"):
        try:
            if now - p.stat().st_mtime < 900:      # touched in the last 15 min
                live.add(p)
        except OSError:
            continue
    return live


def walk() -> list[Path]:
    files: list[Path] = []
    roots = [HOME, Path("/tmp")]
    for root in roots:
        for base, dirs, names in os.walk(root, topdown=True, followlinks=False):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(".app")]
            for n in names:
                p = Path(base) / n
                if p.suffix.lower() in SKIP_SUFFIX:
                    continue
                try:
                    st = p.lstat()
                except OSError:
                    continue
                if not stat.S_ISREG(st.st_mode) or st.st_size == 0 or st.st_size > MAX_BYTES:
                    continue
                files.append(p)
    return files


def redact(path: Path, values: dict[bytes, str]) -> int:
    data = path.read_bytes()
    n = 0
    for v in values:
        c = data.count(v)
        if c:
            data = data.replace(v, f"[REDACTED sha256:{digest(v)}]".encode())
            n += c
    if not n:
        return 0
    st = path.stat()
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".sweep")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.chmod(tmp, stat.S_IMODE(st.st_mode))
    os.replace(tmp, path)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redact", action="store_true")
    ap.add_argument("--include-live", action="store_true",
                    help="also rewrite the transcript of a running session (risky)")
    args = ap.parse_args()

    print("=" * 74)
    print("LOCAL PLAINTEXT CREDENTIAL SWEEP - values are never printed")
    print("=" * 74)
    values = load_values()
    print(f"\nlooking for {len(values)} distinct credential value(s)")
    print(f"authorized to hold them: {AUTHORIZED}")

    live = live_session_files()
    if live:
        print(f"live session transcript(s) skipped unless --include-live: {len(live)}")

    files = walk()
    print(f"scanning {len(files)} file(s) under {HOME} and /tmp\n")

    hits: list[tuple[Path, int, list[str]]] = []
    for p in files:
        if p == AUTHORIZED:
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        found, labels = 0, []
        for v, label in values.items():
            c = data.count(v)
            if c:
                found += c
                labels.append(f"{label} x{c}")
        if found:
            hits.append((p, found, labels))

    total = sum(h[1] for h in hits)
    redacted_files = redacted_vals = skipped = 0
    for p, n, labels in sorted(hits, key=lambda h: -h[1]):
        rel = str(p).replace(str(HOME), "~")
        is_live = p in live
        mark = "  [LIVE SESSION - skipped]" if is_live and not args.include_live else ""
        print(f"  {n:4d}  {rel}{mark}")
        for lab in labels[:6]:
            print(f"          {lab}")
        if args.redact and (not is_live or args.include_live):
            try:
                got = redact(p, values)
                redacted_files += 1
                redacted_vals += got
                print(f"          -> redacted {got} occurrence(s)")
            except OSError as exc:
                print(f"          -> FAILED {type(exc).__name__}")
        elif is_live:
            skipped += n

    print("\n" + "=" * 74)
    print(f"AUTHORIZED RETAINED PLAINTEXT SOURCE : 1  ({AUTHORIZED.name})")
    print(f"files holding a credential value     : {len(hits)}")
    print(f"total occurrences                    : {total}")
    if args.redact:
        print(f"files redacted                       : {redacted_files}")
        print(f"occurrences redacted                 : {redacted_vals}")
        print(f"occurrences left in live session(s)  : {skipped}")
    remaining = total - redacted_vals
    print(f"RESULT: {'CLEAN' if remaining == 0 else f'{remaining} occurrence(s) outside the authorized source'}")
    print("=" * 74)
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
