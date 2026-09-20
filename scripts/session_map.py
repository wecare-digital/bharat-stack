#!/usr/bin/env python3
"""Show every Kiro session on this machine, which project it belongs to, and
whether the machine has room for another one.

Why this exists
---------------
Kiro will happily run many sessions at once, but local sessions are **not
isolated**: every session in a workspace points at the same working tree, the
same git index, the same ``HEAD``. There is no merge step between them. The
first thing you need before running a fleet is an honest answer to "what is
actually running right now, and against which repo".

Nothing in the IDE surfaces that across projects, so this script reconstructs it
from Kiro's own on-disk state:

======================================  ====================================
``~/.kiro/workspace-roots/<hash>/``     which projects Kiro knows about
``~/.kiro/session-index/<hash>.jsonl``  append-only add/remove log per project
``~/.kiro/sessions/<hash>/sess_*/``     per-session transcript directory
``~/.kiro/spec-sessions/<hash>.json``   which session owns which spec
``~/.kiro/sessions/cli/*.json``         CLI + KiroCrew sessions, keyed by cwd
======================================  ====================================

``<hash>`` is ``sha256(absolute_workspace_path)[:16]``; the script verifies that
rather than trusting it, and falls back to the ``root`` field in
``.trust-migration.json`` for roots it cannot recompute.

Privacy
-------
**Metadata only.** This script never opens a transcript body. It reports ids,
timestamps, directory sizes and counts. That is deliberate: transcripts are user
data and may quote credentials, and this output is meant to be safe to paste
into a report or a chat.

Usage
-----
    python scripts/session_map.py              # human-readable map
    python scripts/session_map.py --json       # machine-readable
    python scripts/session_map.py --warm-mins 10
    python scripts/session_map.py --stale-locks   # list dead locks, exit 1 if any

Exit status is 0 normally, and 1 only with ``--stale-locks`` when dead locks were
found, so it can gate a hook or a cron.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

KIRO = Path.home() / ".kiro"
ROOTS_DIR = KIRO / "workspace-roots"
INDEX_DIR = KIRO / "session-index"
SESSIONS_DIR = KIRO / "sessions"
SPEC_SESSIONS_DIR = KIRO / "spec-sessions"
CLI_DIR = SESSIONS_DIR / "cli"

# A session whose directory was written within this window is treated as warm,
# i.e. very likely attached to a live window rather than merely open-but-idle.
DEFAULT_WARM_MINS = 5


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def workspace_hash(path: str) -> str:
    """Kiro's workspace key: first 16 hex chars of sha256 over the abs path."""
    return hashlib.sha256(str(path).encode()).hexdigest()[:16]


def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda _e: None):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except OSError:
                pass
    return total


def human_bytes(n: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}G"


def ago(ts: float | None) -> str:
    if not ts:
        return "-"
    d = max(0, time.time() - ts)
    if d < 90:
        return f"{d:.0f}s ago"
    if d < 5400:
        return f"{d/60:.0f}m ago"
    if d < 172800:
        return f"{d/3600:.1f}h ago"
    return f"{d/86400:.1f}d ago"


def stamp(ts: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "-"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # exists but owned by someone else
    except OSError:
        return False
    return True


def read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #

@dataclass
class Session:
    session_id: str
    warm: bool
    last_write: float | None
    opened: float | None
    size_bytes: int
    spec: str | None = None

    def sort_key(self):
        return (not self.warm, -(self.last_write or 0))


@dataclass
class Workspace:
    hash: str
    root: str | None
    hash_verified: bool
    sessions: list = field(default_factory=list)
    specs: dict = field(default_factory=dict)
    git: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.root or f"<unresolved root {self.hash}>"


@dataclass
class CliSession:
    session_id: str
    cwd: str
    title: str
    updated: float | None
    lock_pid: int | None = None
    lock_alive: bool | None = None


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #

def discover_workspaces(warm_secs: float) -> list[Workspace]:
    """Every workspace root Kiro has registered, with its open sessions."""
    out: list[Workspace] = []
    if not ROOTS_DIR.is_dir():
        return out

    for entry in sorted(ROOTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        h = entry.name

        # Prefer the recorded root, then confirm it really hashes to this dir.
        root = None
        mig = read_json(entry / ".trust-migration.json")
        if isinstance(mig, dict):
            root = mig.get("root")
        verified = bool(root) and workspace_hash(root) == h

        ws = Workspace(hash=h, root=root, hash_verified=verified)
        ws.specs = read_json(SPEC_SESSIONS_DIR / f"{h}.json") or {}
        if not isinstance(ws.specs, dict):
            ws.specs = {}
        spec_by_session = {v: k for k, v in ws.specs.items()}

        # Replay the append-only index: a session is open when its last op is add.
        state: dict[str, tuple[str, float]] = {}
        idx = INDEX_DIR / f"{h}.jsonl"
        if idx.is_file():
            for line in idx.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = str(rec.get("sessionPath", "")).rsplit("/", 1)[-1]
                if not sid:
                    continue
                at = rec.get("at") or 0
                at = at / 1000.0 if at > 1e11 else float(at)
                state[sid] = (rec.get("op", ""), at)

        now = time.time()
        for sid, (op, at) in state.items():
            if op != "add":
                continue
            sdir = SESSIONS_DIR / h / sid
            if not sdir.is_dir():
                continue          # indexed but already reaped from disk
            mtime = sdir.stat().st_mtime
            ws.sessions.append(Session(
                session_id=sid,
                warm=(now - mtime) <= warm_secs,
                last_write=mtime,
                opened=at or None,
                size_bytes=dir_size(sdir),
                spec=spec_by_session.get(sid),
            ))

        ws.sessions.sort(key=lambda s: s.sort_key())
        ws.git = git_snapshot(root) if root else {}
        out.append(ws)

    # Busiest project first.
    out.sort(key=lambda w: (-sum(1 for s in w.sessions if s.warm), -len(w.sessions)))
    return out


def git_snapshot(root: str) -> dict:
    """Branch, head and dirty-file count. The shared state sessions fight over."""
    if not (Path(root) / ".git").exists():
        return {}

    def run(*args: str, strip: bool = True) -> str | None:
        try:
            r = subprocess.run(("git", "-C", root) + args, capture_output=True,
                               text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        if r.returncode != 0:
            return None
        return r.stdout.strip() if strip else r.stdout

    # strip=False is load-bearing. `git status --porcelain` encodes staged state
    # in column X and worktree state in column Y, so an unstaged modification is
    # " M". Stripping the output eats that leading space on the first line only,
    # which made exactly one unstaged file report as staged.
    porcelain = run("status", "--porcelain", strip=False) or ""
    lines = [l for l in porcelain.splitlines() if l.strip()]

    def x(l: str) -> str:
        return l[0] if l else " "

    def y(l: str) -> str:
        return l[1] if len(l) > 1 else " "

    return {
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "head": run("rev-parse", "--short", "HEAD"),
        "dirty_files": len(lines),
        "untracked_files": sum(1 for l in lines if l.startswith("??")),
        "staged_files": sum(1 for l in lines
                            if x(l) not in (" ", "?", "!")),
        "unstaged_files": sum(1 for l in lines
                              if y(l) not in (" ", "?", "!")),
    }


def discover_cli_sessions() -> list[CliSession]:
    """CLI and KiroCrew sessions. Keyed by cwd, so they may be other projects."""
    out: list[CliSession] = []
    if not CLI_DIR.is_dir():
        return out

    for f in CLI_DIR.glob("*.json"):
        d = read_json(f)
        if not isinstance(d, dict):
            continue
        sid = d.get("session_id") or f.stem
        lock = CLI_DIR / f"{f.stem}.lock"
        pid = alive = None
        if lock.is_file():
            ld = read_json(lock)
            if isinstance(ld, dict) and isinstance(ld.get("pid"), int):
                pid = ld["pid"]
                alive = pid_alive(pid)

        updated = d.get("updated_at") or d.get("created_at")
        if isinstance(updated, str):
            try:
                from datetime import datetime
                updated = datetime.fromisoformat(
                    updated.replace("Z", "+00:00")).timestamp()
            except ValueError:
                updated = None
        elif isinstance(updated, (int, float)):
            updated = updated / 1000.0 if updated > 1e11 else float(updated)
        else:
            updated = None

        out.append(CliSession(
            session_id=str(sid),
            cwd=str(d.get("cwd") or ""),
            title=str(d.get("title") or ""),
            updated=updated,
            lock_pid=pid,
            lock_alive=alive,
        ))

    out.sort(key=lambda s: -(s.updated or 0))
    return out


# --------------------------------------------------------------------------- #
# machine capacity
# --------------------------------------------------------------------------- #

def machine_capacity() -> dict:
    """What the Mac can actually carry. RAM is the binding constraint, not CPU."""
    def sysctl(name: str) -> str | None:
        try:
            r = subprocess.run(["sysctl", "-n", name], capture_output=True,
                               text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    cores = int(sysctl("hw.logicalcpu") or 0)
    mem_gb = int(sysctl("hw.memsize") or 0) / 1024 ** 3
    load1 = None
    raw = sysctl("vm.loadavg") or ""
    m = re.search(r"([\d.]+)", raw)
    if m:
        load1 = float(m.group(1))

    # Sum RSS of the Kiro process tree. Renderer + plugin hosts dominate.
    kiro_rss_mb = 0.0
    procs = 0
    try:
        r = subprocess.run(["ps", "-eo", "rss=,comm="], capture_output=True,
                           text=True, timeout=20)
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            rss, _, comm = line.partition(" ")
            if "Kiro" in comm or "kiro" in comm:
                try:
                    kiro_rss_mb += int(rss) / 1024.0
                    procs += 1
                except ValueError:
                    pass
    except (OSError, subprocess.SubprocessError):
        pass

    # Measured on this box: a warm IDE session costs roughly 0.4-1.2 GB once its
    # renderer and plugin host are counted. Budget 1.0 GB and keep 4 GB for macOS
    # plus whatever else is open.
    per_session_gb = 1.0
    reserve_gb = 4.0
    by_ram = max(1, int((mem_gb - reserve_gb) / per_session_gb))
    by_cpu = max(1, cores // 3) if cores else by_ram
    budget = min(by_ram, by_cpu)

    return {
        "model": sysctl("hw.model"),
        "logical_cores": cores,
        "ram_gb": round(mem_gb, 1),
        "load_1min": load1,
        "load_per_core": round(load1 / cores, 2) if load1 and cores else None,
        "kiro_processes": procs,
        "kiro_rss_gb": round(kiro_rss_mb / 1024.0, 2),
        "budget_by_ram": by_ram,
        "budget_by_cpu": by_cpu,
        "recommended_concurrent_sessions": budget,
    }


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

BAR = "=" * 78


def render(workspaces: list[Workspace], cli: list[CliSession], cap: dict,
           warm_mins: int) -> None:
    print(BAR)
    print(f"KIRO SESSION MAP   {time.strftime('%Y-%m-%d %H:%M:%S')}"
          f"   (warm = written < {warm_mins}m ago)")
    print(BAR)

    total = sum(len(w.sessions) for w in workspaces)
    warm = sum(1 for w in workspaces for s in w.sessions if s.warm)
    print(f"\nIDE sessions: {total} open, {warm} warm, "
          f"across {len(workspaces)} registered project(s)")

    for w in workspaces:
        print(f"\n--- {w.label}")
        flag = "" if w.hash_verified else "   [hash unverified]"
        print(f"    key {w.hash}{flag}")
        if w.git:
            g = w.git
            print(f"    git  branch={g.get('branch')}  head={g.get('head')}  "
                  f"dirty={g.get('dirty_files')} "
                  f"(staged={g.get('staged_files')}, "
                  f"unstaged={g.get('unstaged_files')}, "
                  f"untracked={g.get('untracked_files')})")
        if not w.sessions:
            print("    no open sessions")
            continue

        print(f"    {'session':<42} {'state':<6} {'last write':<14} "
              f"{'size':>7}  spec")
        for s in w.sessions:
            print(f"    {s.session_id:<42} {'WARM' if s.warm else 'idle':<6} "
                  f"{ago(s.last_write):<14} {human_bytes(s.size_bytes):>7}  "
                  f"{s.spec or '-'}")

        if w.specs:
            print("    spec ownership (one session per spec):")
            for spec, sid in sorted(w.specs.items()):
                live = any(x.session_id == sid for x in w.sessions)
                print(f"      {spec} -> {sid}"
                      f"{'' if live else '   [owning session not open]'}")

        if len([s for s in w.sessions if s.warm]) > 1 and w.git:
            print(f"    NOTE {len([s for s in w.sessions if s.warm])} warm "
                  f"sessions share this one working tree and git index.")

    # CLI / crew
    print(f"\n{BAR}\nCLI + KiroCrew sessions: {len(cli)}\n{BAR}")
    by_bucket: dict[str, list[CliSession]] = {}
    for s in cli:
        parts = s.cwd.split("/")
        bucket = "/".join(parts[:5]) if len(parts) > 5 else (s.cwd or "(no cwd)")
        by_bucket.setdefault(bucket, []).append(s)

    for bucket, items in sorted(by_bucket.items(), key=lambda kv: -len(kv[1])):
        held = [s for s in items if s.lock_alive is True]
        stale = [s for s in items if s.lock_alive is False]
        print(f"\n  {len(items):>4}  {bucket}")
        if held:
            print(f"        {len(held)} holding a live lock:")
            for s in held[:6]:
                print(f"          {s.session_id}  pid={s.lock_pid}  "
                      f"{ago(s.updated)}")
        if stale:
            print(f"        {len(stale)} STALE lock(s) from dead pids "
                  f"- safe to delete:")
            for s in stale[:6]:
                print(f"          {CLI_DIR / (s.session_id + '.lock')}")

    # capacity
    print(f"\n{BAR}\nMACHINE CAPACITY\n{BAR}")
    print(f"  {cap.get('model')}  {cap.get('logical_cores')} logical cores  "
          f"{cap.get('ram_gb')} GB RAM")
    print(f"  load 1min {cap.get('load_1min')}  "
          f"({cap.get('load_per_core')} per core)")
    print(f"  Kiro process tree: {cap.get('kiro_processes')} processes, "
          f"{cap.get('kiro_rss_gb')} GB resident")
    print(f"  budget: {cap.get('budget_by_ram')} by RAM, "
          f"{cap.get('budget_by_cpu')} by CPU")
    print(f"  -> recommended concurrent sessions: "
          f"{cap.get('recommended_concurrent_sessions')}")
    if warm > (cap.get("recommended_concurrent_sessions") or 99):
        print(f"  WARNING {warm} warm sessions exceeds the recommended "
              f"{cap['recommended_concurrent_sessions']}. Expect swapping.")
    lpc = cap.get("load_per_core")
    if lpc and lpc > 0.7:
        print(f"  WARNING load per core is {lpc}; the machine is already busy.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--warm-mins", type=int, default=DEFAULT_WARM_MINS,
                    help=f"minutes of write recency counted as warm "
                         f"(default {DEFAULT_WARM_MINS})")
    ap.add_argument("--stale-locks", action="store_true",
                    help="list stale CLI locks only; exit 1 if any exist")
    args = ap.parse_args()

    warm_secs = args.warm_mins * 60
    workspaces = discover_workspaces(warm_secs)
    cli = discover_cli_sessions()

    if args.stale_locks:
        stale = [s for s in cli if s.lock_alive is False]
        for s in stale:
            print(CLI_DIR / f"{s.session_id}.lock")
        if not stale:
            print("no stale locks")
        return 1 if stale else 0

    cap = machine_capacity()

    if args.json:
        print(json.dumps({
            "generated_at": time.time(),
            "warm_mins": args.warm_mins,
            "machine": cap,
            "workspaces": [
                {**{k: v for k, v in asdict(w).items() if k != "sessions"},
                 "sessions": [asdict(s) for s in w.sessions]}
                for w in workspaces
            ],
            "cli_sessions": [asdict(s) for s in cli],
        }, indent=2, default=str))
        return 0

    render(workspaces, cli, cap, args.warm_mins)
    return 0


if __name__ == "__main__":
    sys.exit(main())
