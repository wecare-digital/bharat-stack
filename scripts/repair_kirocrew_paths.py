#!/usr/bin/env python3
"""Repoint KiroCrew references from the ejected DMG to the installed app.

The problem
-----------
KiroCrew was first run straight from its disk image, so every path it recorded
points at the mount point rather than the install:

    /Volumes/KiroCrew/KiroCrew.app/Contents/Resources/backend-dist/...

``/Volumes`` now holds only ``Macintosh HD`` and ``Recovery``. The image is gone,
so all of it is dead:

* ``~/.local/bin/kirocrew`` is a dangling symlink
* 13 agent configs in ``~/.kiro/agents`` carry 27 dead references between them,
  in ``prompt`` (a ``file://`` URI) and in ``mcpServers[*].command``
* 4 rendered agents under ``~/.kiro/rendered-agents/pptx-maker`` carry more

The visible symptom is ``kiro-cli agent list`` emitting ``File URI not found`` and
every ``kirocrew-*`` agent failing to load its system prompt.

The backend itself was never missing. It is installed at
``/Applications/KiroCrew.app/Contents/Resources/backend-dist/kirocrew-backend-arm64``.
Only the recorded paths are wrong.

Why a script instead of sed
---------------------------
A blind substitution across JSON would happily write a path that does not exist
and turn a loud failure into a quiet one. This checks that each rewritten target
is really present on disk before committing the change, backs up every file it
edits, and re-parses the JSON afterwards so a corrupted write cannot survive.

Known unfixable by this script
------------------------------
``~/.kiro/crew/apps/pptx-maker/data/vendor/sdpm/...`` prompt files are missing
too, but that is not a path problem: the vendor directory was never unpacked.
Reinstalling or re-enabling the pptx-maker app is the fix, and this script
reports them rather than pretending otherwise.

Usage
-----
    python scripts/repair_kirocrew_paths.py --dry-run
    python scripts/repair_kirocrew_paths.py
    python scripts/repair_kirocrew_paths.py --verify
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

HOME = Path.home()
OLD_PREFIX = "/Volumes/KiroCrew/KiroCrew.app"
NEW_PREFIX = "/Applications/KiroCrew.app"

SYMLINK = HOME / ".local/bin/kirocrew"
SEARCH_DIRS = [HOME / ".kiro/agents", HOME / ".kiro/rendered-agents"]

PATH_RX = re.compile(re.escape(OLD_PREFIX) + r"[^\"'\s]*")


def targets_in(text: str) -> list[str]:
    return sorted(set(PATH_RX.findall(text)))


def rewrite(path_str: str) -> str:
    return path_str.replace(OLD_PREFIX, NEW_PREFIX, 1)


def check_all_targets_exist(paths: list[str]) -> tuple[list[str], list[str]]:
    ok, missing = [], []
    for p in paths:
        (ok if Path(rewrite(p)).exists() else missing).append(p)
    return ok, missing


def collect_files() -> list[Path]:
    out: list[Path] = []
    for d in SEARCH_DIRS:
        if not d.is_dir():
            continue
        for f in d.rglob("*.json"):
            try:
                if OLD_PREFIX in f.read_text(errors="replace"):
                    out.append(f)
            except OSError:
                pass
    return sorted(out)


def verify() -> int:
    print("=== symlink ===")
    if SYMLINK.is_symlink():
        tgt = os.readlink(SYMLINK)
        state = "OK" if Path(tgt).exists() else "DANGLING"
        print(f"  {state}  {SYMLINK} -> {tgt}")
    else:
        print(f"  absent  {SYMLINK}")

    print("\n=== remaining dead references ===")
    files = collect_files()
    if not files:
        print("  none")
    total = 0
    for f in files:
        n = len(PATH_RX.findall(f.read_text(errors="replace")))
        total += n
        print(f"  {n:>2}  {f}")
    print(f"\n  {total} reference(s) across {len(files)} file(s)")

    print("\n=== backend present at install location? ===")
    for rel in ("bin/kirocrew", "bin/python3.12", "bin/uv",
                "lib/python3.12/site-packages/kiro_crew/config/prompt.md"):
        p = Path(NEW_PREFIX) / "Contents/Resources/backend-dist/kirocrew-backend-arm64" / rel
        print(f"  {'EXISTS ' if p.exists() else 'MISSING'}  {rel}")

    return 1 if total or (SYMLINK.is_symlink() and not Path(os.readlink(SYMLINK)).exists()) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    if args.verify:
        return verify()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    changed = skipped = 0

    # 1. the symlink
    print("=== symlink ===")
    new_target = (Path(NEW_PREFIX) /
                  "Contents/Resources/backend-dist/kirocrew-backend-arm64/bin/kirocrew")
    if not new_target.exists():
        print(f"  ABORT: {new_target} does not exist; nothing to point at")
        return 1
    if SYMLINK.is_symlink():
        current = os.readlink(SYMLINK)
        if current == str(new_target):
            print("  already correct")
        elif args.dry_run:
            print(f"  would repoint {SYMLINK}\n    from {current}\n    to   {new_target}")
        else:
            SYMLINK.unlink()
            SYMLINK.symlink_to(new_target)
            print(f"  repointed {SYMLINK} -> {new_target}")
            changed += 1
    else:
        print(f"  {SYMLINK} is not a symlink; leaving alone")

    # 2. the JSON files
    print("\n=== json references ===")
    for f in collect_files():
        text = f.read_text(errors="replace")
        found = targets_in(text)
        ok, missing = check_all_targets_exist(found)

        print(f"\n  {f}")
        for p in ok:
            print(f"    -> {rewrite(p)}")
        for p in missing:
            print(f"    SKIP (target absent): {rewrite(p)}")

        if missing:
            print("    file left unchanged: refusing to write a path that "
                  "does not exist")
            skipped += 1
            continue
        if args.dry_run:
            print(f"    dry-run: would rewrite {len(found)} reference(s)")
            continue

        new_text = text.replace(OLD_PREFIX, NEW_PREFIX)
        try:
            json.loads(new_text)
        except json.JSONDecodeError as e:
            print(f"    SKIP: rewrite would produce invalid JSON ({e})")
            skipped += 1
            continue

        shutil.copy2(f, f.with_name(f.name + f".bak-{stamp}"))
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(new_text)
        os.replace(tmp, f)
        print(f"    rewrote {len(found)} reference(s), backup .bak-{stamp}")
        changed += 1

    print(f"\n{changed} file(s) changed, {skipped} skipped"
          + (" (dry run)" if args.dry_run else ""))

    # 3. report what this cannot fix
    vendor = HOME / ".kiro/crew/apps/pptx-maker/data/vendor"
    if not vendor.exists():
        print("\nNOT a path problem, so not fixed here: "
              f"{vendor} was never unpacked, so the pptx-maker agent prompts "
              "stay missing. Re-enable or reinstall that app to restore them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
