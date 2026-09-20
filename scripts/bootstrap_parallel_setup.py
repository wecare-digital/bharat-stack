#!/usr/bin/env python3
"""Install the unattended parallel-agent setup into a project, and keep it healthy.

Makes the configuration **permanent** in the two senses that were missing:

*Across projects.* Kiro stores permissions per workspace root, and hooks and
agents live inside each repository's ``.kiro/``. A new project therefore starts
with none of it and stalls on approval prompts again. ``--install <path>`` copies
the guards, the agents and the steering note into that repo and writes the wide
permission policy for its workspace key.

*Across restarts.* Things drift. Measured on this machine while the setup was
being built:

* ``.kiro/hooks/block-inline-secrets.json`` was deleted from disk mid-session
  while three sessions were live, which silently removed the justification for
  the wide permission policy
* 27 KiroCrew paths pointed at an ejected disk image, leaving a dangling
  ``~/.local/bin/kirocrew``
* stale session locks accumulated from processes that had already exited

``--heal`` detects and repairs all of that, and is safe to run on every session
start. It only ever restores things to their intended state; it never deletes
project files.

Usage
-----
    python scripts/bootstrap_parallel_setup.py --check
    python scripts/bootstrap_parallel_setup.py --heal
    python scripts/bootstrap_parallel_setup.py --install /path/to/other/project
    python scripts/bootstrap_parallel_setup.py --install /path/to/repo --dry-run

Exit status: 0 when healthy or repaired, 1 when something needs a human.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_REPO = HERE.parent
KIRO = Path.home() / ".kiro"

# Everything a project needs for the wide-permissions trade to hold.
GUARD_SCRIPTS = [
    "guard_shell_parse.py",
    "block_inline_secrets.py",
    "block_broad_git_staging.py",
    "block_catastrophic.py",
    "session_map.py",
    "apply_unattended_permissions.py",
    "bootstrap_parallel_setup.py",
    "unattended_mode.py",
]
HOOK_FILES = [
    "block-inline-secrets.json",
    "block-broad-git-staging.json",
    "block-catastrophic.json",
    "heal-parallel-setup.json",
]

# MCP servers whose autoApprove must be populated, or a long run stops on the
# first tool call. Empty arrays were the last remaining prompt source.
MCP_EXPECTED_TOOLS = {
    "aws-mcp": 8,
    "google-cloud": 1,
    # devtools_signout is deliberately withheld - an agent signing the session out
    # mid-run is exactly the failure an unattended setup must not have. Two more
    # are in disabledTools, so 9 of 12 is the correct full state.
    "devtools": 9,
}
AGENT_FILES = ["fleet-lead.json", "fleet-worker.json"]
STEERING_FILES = ["multi-session-parallel-agents.md"]


def workspace_key(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)
    return r.returncode, (r.stdout + r.stderr)


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #

def check(repo: Path) -> list[tuple[str, bool, str]]:
    """[(label, ok, detail)] for one project."""
    results: list[tuple[str, bool, str]] = []

    for h in HOOK_FILES:
        p = repo / ".kiro/hooks" / h
        ok = p.is_file()
        detail = "present" if ok else "MISSING - wide permissions are unjustified"
        if ok:
            try:
                json.loads(p.read_text())
            except json.JSONDecodeError as e:
                ok, detail = False, f"invalid JSON: {e}"
        results.append((f"hook {h}", ok, detail))

    for s in GUARD_SCRIPTS:
        p = repo / "scripts" / s
        results.append((f"script {s}", p.is_file(),
                        "present" if p.is_file() else "MISSING"))

    for a in AGENT_FILES:
        p = repo / ".kiro/agents" / a
        results.append((f"agent {a}", p.is_file(),
                        "present" if p.is_file() else "MISSING"))

    key = workspace_key(repo)
    pol = KIRO / "workspace-roots" / key / "permissions.yaml"
    if pol.is_file():
        text = pol.read_text(errors="replace")
        caps = [l.split("capability:", 1)[1].strip()
                for l in text.splitlines() if "capability:" in l]
        wide = "- '*'" in text or '- "*"' in text
        n_entries = sum(1 for l in text.splitlines() if l.strip().startswith("- "))
        ok = wide and "fs_write" in caps
        detail = (f"{len(caps)} capabilities, {n_entries} entries"
                  + ("" if ok else " - NOT the wide policy; runs will prompt"))
        results.append(("permissions policy", ok, detail))
    else:
        results.append(("permissions policy", False,
                        f"no file at {pol} - every action will prompt"))

    # KiroCrew symlink
    link = Path.home() / ".local/bin/kirocrew"
    if link.is_symlink():
        tgt = os.readlink(link)
        ok = Path(tgt).exists()
        results.append(("kirocrew symlink", ok,
                        "resolves" if ok else f"DANGLING -> {tgt}"))
    else:
        results.append(("kirocrew symlink", True, "not a symlink, skipped"))

    # Stale CLI locks
    cli = KIRO / "sessions/cli"
    stale = []
    if cli.is_dir():
        for lock in cli.glob("*.lock"):
            try:
                pid = json.loads(lock.read_text()).get("pid")
            except Exception:
                continue
            if isinstance(pid, int):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    stale.append(lock)
                except OSError:
                    pass
    results.append(("stale session locks", not stale,
                    "none" if not stale else f"{len(stale)} from dead pids"))

    # MCP autoApprove - empty arrays prompt on every tool call.
    for cfg_path in (KIRO / "settings/mcp.json", repo / ".kiro/settings/mcp.json"):
        if not cfg_path.is_file():
            continue
        try:
            servers = (json.loads(cfg_path.read_text()) or {}).get("mcpServers", {})
        except (OSError, json.JSONDecodeError) as e:
            results.append((f"mcp {cfg_path.parent.parent.name}", False, f"unreadable: {e}"))
            continue
        for name, scfg in servers.items():
            if scfg.get("disabled"):
                continue
            n = len(scfg.get("autoApprove") or [])
            want = MCP_EXPECTED_TOOLS.get(name)
            if want is None:
                results.append((f"mcp {name} autoApprove", n > 0,
                                f"{n} tools" if n else
                                "EMPTY - will prompt; tool names unknown, set by hand"))
            else:
                results.append((f"mcp {name} autoApprove", n >= want,
                                f"{n}/{want} tools"))

    # Unattended mode - reported, never auto-enabled. Enabling is a human decision.
    sys.path.insert(0, str(repo / "scripts"))
    try:
        import unattended_mode
        import importlib
        importlib.reload(unattended_mode)
        st = unattended_mode.read_state()
        on = bool(st.get("enabled"))
        detail = st.get("reason", "")
        if on and st.get("expires_in_hours") is not None:
            detail = f"active, expires in {st['expires_in_hours']}h"
        results.append(("unattended mode", True,
                        f"{'ON' if on else 'OFF'} - {detail}"))
    except Exception as e:  # never fail the whole check on this
        results.append(("unattended mode", True, f"not determinable: {str(e)[:60]}"))

    return results


def report(repo: Path, results: list[tuple[str, bool, str]]) -> bool:
    print(f"\n=== {repo}")
    print(f"    workspace key {workspace_key(repo)}\n")
    width = max(len(l) for l, _, _ in results)
    all_ok = True
    for label, ok, detail in results:
        all_ok &= ok
        print(f"    {'ok  ' if ok else 'FAIL'}  {label:<{width}}  {detail}")
    return all_ok


# --------------------------------------------------------------------------- #
# heal
# --------------------------------------------------------------------------- #

def heal(repo: Path, *, dry_run: bool = False) -> int:
    """Restore intended state. Never deletes project files."""
    fixed = unfixable = 0

    print("=== hooks and scripts ===")
    for rel in ([f".kiro/hooks/{h}" for h in HOOK_FILES]
                + [f"scripts/{s}" for s in GUARD_SCRIPTS]
                + [f".kiro/agents/{a}" for a in AGENT_FILES]):
        dst = repo / rel
        if dst.is_file():
            continue
        src = SOURCE_REPO / rel
        # Prefer git, so a file deleted from the worktree comes back byte-exact.
        code, _ = run(["git", "-C", str(repo), "cat-file", "-e", f"HEAD:{rel}"])
        if code == 0:
            if dry_run:
                print(f"  would restore from git: {rel}")
            else:
                c, out = run(["git", "-C", str(repo), "checkout", "HEAD", "--", rel])
                if c == 0:
                    print(f"  restored from git: {rel}")
                    fixed += 1
                else:
                    print(f"  FAILED git restore {rel}: {out.strip()[:120]}")
                    unfixable += 1
            continue
        if src.is_file() and src != dst:
            if dry_run:
                print(f"  would copy from source repo: {rel}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  copied from source repo: {rel}")
                fixed += 1
            continue
        print(f"  CANNOT RESTORE {rel} - not in git and not in {SOURCE_REPO}")
        unfixable += 1
    if not fixed and not unfixable:
        print("  all present")

    print("\n=== permissions policy ===")
    applier = repo / "scripts/apply_unattended_permissions.py"
    key = workspace_key(repo)
    pol = KIRO / "workspace-roots" / key / "permissions.yaml"
    needs = True
    if pol.is_file():
        t = pol.read_text(errors="replace")
        needs = not ("- '*'" in t and "fs_write" in t)
    if not needs:
        print("  already the wide policy")
    elif not applier.is_file():
        print("  CANNOT APPLY - apply_unattended_permissions.py missing")
        unfixable += 1
    elif dry_run:
        print("  would write the wide policy")
    else:
        code, out = run([sys.executable, str(applier), "--root", str(repo)])
        tail = [l for l in out.splitlines() if l.strip()][-1:] or [""]
        print(f"  {'applied' if code == 0 else 'FAILED'}: {tail[0].strip()}")
        fixed += code == 0
        unfixable += code != 0

    print("\n=== kirocrew paths ===")
    repair = repo / "scripts/repair_kirocrew_paths.py"
    link = Path.home() / ".local/bin/kirocrew"
    dangling = link.is_symlink() and not Path(os.readlink(link)).exists()
    if not dangling:
        print("  nothing dangling")
    elif not repair.is_file():
        print("  dangling, but repair_kirocrew_paths.py is not in this repo")
        unfixable += 1
    elif dry_run:
        print("  would repair dead /Volumes references")
    else:
        code, _ = run([sys.executable, str(repair)])
        print(f"  {'repaired' if code == 0 else 'FAILED'}")
        fixed += code == 0
        unfixable += code != 0

    print("\n=== stale session locks ===")
    cli = KIRO / "sessions/cli"
    removed = 0
    if cli.is_dir():
        for lock in cli.glob("*.lock"):
            try:
                pid = json.loads(lock.read_text()).get("pid")
            except Exception:
                continue
            if not isinstance(pid, int):
                continue
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                if dry_run:
                    print(f"  would remove {lock.name} (pid {pid} dead)")
                else:
                    lock.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                pass
    print(f"  removed {removed}" if removed else "  none stale")
    fixed += removed

    print(f"\n{fixed} repaired, {unfixable} need a human"
          + (" (dry run)" if dry_run else ""))
    return 1 if unfixable else 0


# --------------------------------------------------------------------------- #
# install
# --------------------------------------------------------------------------- #

def install(target: Path, *, dry_run: bool) -> int:
    target = target.resolve()
    if target == SOURCE_REPO:
        print(f"{target} is the source repo; use --heal instead")
        return 1
    if not target.is_dir():
        print(f"{target} is not a directory")
        return 1

    print(f"Installing parallel-agent setup into {target}")
    copied = 0
    for rel in ([f"scripts/{s}" for s in GUARD_SCRIPTS]
                + [f".kiro/hooks/{h}" for h in HOOK_FILES]
                + [f".kiro/agents/{a}" for a in AGENT_FILES]
                + [f".kiro/steering/{s}" for s in STEERING_FILES]):
        src = SOURCE_REPO / rel
        dst = target / rel
        if not src.is_file():
            print(f"  skip (absent in source): {rel}")
            continue
        if dst.is_file():
            print(f"  exists, left alone: {rel}")
            continue
        if dry_run:
            print(f"  would copy: {rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if rel.startswith("scripts/"):
            os.chmod(dst, 0o755)
        print(f"  copied: {rel}")
        copied += 1

    # Hook commands embed an absolute repo path; rewrite it for the new project.
    if not dry_run:
        for h in HOOK_FILES:
            p = target / ".kiro/hooks" / h
            if not p.is_file():
                continue
            t = p.read_text()
            if str(SOURCE_REPO) in t:
                p.write_text(t.replace(str(SOURCE_REPO), str(target)))
                print(f"  repointed hook path: {h}")

    print("\n=== permissions ===")
    applier = target / "scripts/apply_unattended_permissions.py"
    if dry_run:
        print("  would write the wide policy for this workspace key")
    elif applier.is_file():
        code, out = run([sys.executable, str(applier), "--root", str(target)])
        for line in out.splitlines():
            if line.strip():
                print("  " + line)
    else:
        print("  applier not present; run it manually")

    print(f"\n{copied} file(s) copied"
          + (" (dry run)" if dry_run else "")
          + f"\nVerify with: python scripts/bootstrap_parallel_setup.py --check")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--heal", action="store_true")
    ap.add_argument("--install", metavar="PATH")
    ap.add_argument("--repo", default=str(SOURCE_REPO),
                    help="project to check or heal (default: this repo)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true",
                    help="with --heal, print only when something changed")
    args = ap.parse_args()

    if args.install:
        return install(Path(args.install), dry_run=args.dry_run)

    repo = Path(args.repo).resolve()

    if args.heal:
        results = check(repo)
        if all(ok for _, ok, _ in results):
            if not args.quiet:
                print(f"{repo}: healthy, nothing to heal")
            return 0
        if args.quiet:
            print(f"kiro setup drift detected in {repo}, repairing:")
        return heal(repo, dry_run=args.dry_run)

    # default: --check
    ok = report(repo, check(repo))
    print(f"\n{'HEALTHY' if ok else 'NEEDS ATTENTION - run with --heal'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
