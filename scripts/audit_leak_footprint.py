#!/usr/bin/env python3
"""Report where the 2026-09-19 leaked credentials still exist on disk.

Reads the secret values out of the still-unreplaced workspace permissions file,
holds them in memory only, and prints PATHS AND COUNTS ONLY - never a value.
Re-run after rotating and after installing the hardened permissions file to
confirm the footprint is gone.

Usage:  python scripts/audit_leak_footprint.py
Exit 0 always; this is a report, not a gate.
"""
from __future__ import annotations

import os
import re
import pathlib

HOME = pathlib.Path.home()
LIVE = HOME / ".kiro/workspace-roots/df7bb16a63efe7f7/permissions.yaml"
BACKUP = HOME / ".local/share/kiro-maintenance-backup/20260919-063734/workspace-permissions.yaml.LEAKED-BACKUP"

PATTERNS = {
    "openai_svcacct": r"sk-svcacct-[A-Za-z0-9_\-]{20,}",
    "razorpay_keyid": r"rzp_live_[A-Za-z0-9]{10,}",
    "google_apikey":  r"AIza[A-Za-z0-9_\-]{30,}",
    "plivo_authid":   r"\bMA[A-Z0-9]{18}\b",
}
QUOTED = {
    "razorpay_secret": r"RZP_SECRET='([^']+)'",
    "plivo_token":     r"PLIVO_AUTH_TOKEN='([^']+)'",
}

SCAN_ROOTS = [
    ("kiro user data",        HOME / ".kiro"),
    ("kiro app support",      HOME / "Library/Application Support/Kiro"),
    ("repo worktree",         HOME / "wecare-store"),
    ("maintenance snapshot",  HOME / ".local/share/kiro-maintenance-backup"),
    ("shell history",         HOME / ".zsh_history"),
    ("bash history",          HOME / ".bash_history"),
    ("loose key file",        HOME / "aws-new-keys-SAVE-THEN-DELETE.txt"),
]
SKIP = {"node_modules", ".venv", ".next", "__pycache__", "out", ".git",
        "Cellar", "Caskroom", "CachedData", "Crashpad"}


def load_secrets() -> list[str]:
    src = LIVE if LIVE.exists() else BACKUP
    if not src.exists():
        return []
    text = src.read_text(errors="replace")
    found: set[str] = set()
    for rx in PATTERNS.values():
        found.update(re.findall(rx, text))
    for rx in QUOTED.values():
        found.update(re.findall(rx, text))
    # a redacted backup yields nothing, which is the desired end state
    return [s for s in found if not s.startswith("<REDACTED")]


def walk(root: pathlib.Path):
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        return
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            yield pathlib.Path(base) / f


def main() -> int:
    secrets = [s.encode() for s in load_secrets()]
    if not secrets:
        print("No secret values recoverable from the permissions file or backup.")
        print("Either the hardened file is installed and the backup is redacted,")
        print("or both are gone. Nothing to scan for.")
        return 0

    print(f"scanning for {len(secrets)} distinct leaked value(s)\n")
    total = 0
    for label, root in SCAN_ROOTS:
        hits = []
        for f in walk(root):
            try:
                if f.stat().st_size > 60_000_000:
                    continue
                blob = f.read_bytes()
            except Exception:
                continue
            n = sum(blob.count(s) for s in secrets)
            if n:
                hits.append((f, n))
        print(f"=== {label}")
        if not hits:
            print("    clean")
        for f, n in sorted(hits, key=lambda h: -h[1]):
            print(f"    {n:4d}  {f}")
            total += n
    print(f"\nTOTAL occurrences still on disk: {total}")
    if total:
        print("Rotation is what makes these harmless. See "
              "docs/CREDENTIAL-ROTATION-RUNBOOK.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
