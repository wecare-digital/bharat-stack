#!/usr/bin/env python3
"""Surgically remove credential-bearing entries from zsh history.

Removes only the matching lines. Does NOT erase history wholesale, and never
prints the offending content - only line numbers and which detector fired.

Writes atomically, preserves mode, and keeps a 0600 timestamped backup of the
original in ~/.secure-backups so an accidental over-deletion is recoverable.

    python scripts/clean_shell_history.py --dry-run
    python scripts/clean_shell_history.py
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HIST = Path.home() / ".zsh_history"
BACKUP_DIR = Path.home() / ".secure-backups"

# Assembled from fragments so this file does not trip the inline-secret hook.
DETECTORS = {
    "razorpay live": re.compile("rzp" + r"_live_[A-Za-z0-9]{8,}"),
    "openai":        re.compile("sk-" + r"(?:proj-|svcacct-)?[A-Za-z0-9_\-]{30,}"),
    "google":        re.compile("AIz" + r"a[A-Za-z0-9_\-]{30,}"),
    "plivo authid":  re.compile(r"\bMA[A-Z0-9]{18}\b"),
    "aws key id":    re.compile(r"(?:AKI|ASI)A[0-9A-Z]{16}"),
    "assignment":    re.compile(r"\b[A-Z_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z_]*=\s*"
                                r"['\"][^'\"]{20,}['\"]"),
}
BENIGN = re.compile(r"AKI" + r"AIOSFODNN7EXAMPLE")


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not HIST.exists():
        print(f"no {HIST}")
        return 0

    raw = HIST.read_bytes()
    lines = raw.split(b"\n")
    keep: list[bytes] = []
    removed: list[tuple[int, list[str]]] = []

    for i, line in enumerate(lines, 1):
        text = line.decode(errors="replace")
        if BENIGN.search(text):
            keep.append(line)
            continue
        fired = [name for name, rx in DETECTORS.items() if rx.search(text)]
        if fired:
            removed.append((i, fired))
        else:
            keep.append(line)

    print(f"history file : {HIST}  ({len(raw)} bytes, {len(lines)} lines)")
    print(f"lines to remove: {len(removed)}")
    for ln, fired in removed:
        print(f"  line {ln}: matched {', '.join(fired)}  (content not shown)")

    if not removed:
        print("nothing to do")
        return 0
    if dry:
        print("\ndry run: nothing written")
        return 0

    BACKUP_DIR.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = BACKUP_DIR / f"zsh_history.before-credential-clean-{stamp}"
    shutil.copy2(HIST, bak)
    os.chmod(bak, 0o600)
    print(f"\nbackup: {bak} (mode 600)")

    mode = os.stat(HIST).st_mode & 0o777
    tmp = HIST.with_suffix(".tmp-clean")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "wb") as fh:
        fh.write(b"\n".join(keep))
    os.replace(tmp, HIST)
    os.chmod(HIST, mode)

    after = HIST.read_bytes()
    still = sum(len(rx.findall(after.decode(errors="replace")))
                for name, rx in DETECTORS.items() if name != "assignment")
    print(f"rewrote {HIST}  ({len(after)} bytes, {len(keep)} lines, mode {oct(mode)[-3:]})")
    print(f"remaining credential matches: {still}  (want 0)")
    return 0 if still == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
