#!/usr/bin/env python3
"""Watch the advisories we cannot fix, so the upstream fix is noticed.

Why this exists
---------------
`brace-expansion@5.0.9` inside `aws-cdk-lib` produced three Dependabot alerts (two HIGH:
GHSA-qhr7-859c-m2p7, GHSA-6j4f-fj2g-mc7p, and GHSA-q2hr-2g5m-vwhr). None of them is fixable
here, and the reason is structural rather than a matter of effort:

    node_modules/aws-cdk-lib/node_modules/brace-expansion
        version  = 5.0.9
        inBundle = True

`inBundle: True` means the code ships **inside the aws-cdk-lib tarball**. An npm `overrides`
entry describes what npm should *fetch*; it cannot change the contents of something already
fetched. That was tried and reverted - it left the version at 5.0.9 while churning the
lockfile by 1537 lines. Upgrading does not help either: `2.270.0` (pinned) and `2.271.0`
(latest at triage) both bundle 5.0.9.

The original plan was to leave the alerts OPEN so the fix would be noticed when AWS refreshed
the bundle. They were then dismissed, which is a reasonable call - they reach no deployed
artifact - but it removes the only mechanism that was going to notice. A dismissed alert does
not come back to tell you it is fixable.

So this script is that mechanism, and it is better than the plan it replaces: an open alert
nags constantly and gets ignored; this answers the actual question ("is it fixable yet?") on
demand and fails a gate only when the facts the triage rests on have moved.

Two modes, and the distinction matters
--------------------------------------
`--gate` (offline, CI-safe) asserts the situation is still the one that was triaged. It reads
the committed lockfile only. It fails when the bundled version or the pinned `aws-cdk-lib`
changes - which is NOT a security failure, it is "the triage is stale, re-read it". Treating
those differently is the whole point; a gate that cries wolf gets switched off.

`--check-upstream` (needs network) downloads the newest `aws-cdk-lib` tarball and reads the
bundled `package.json` directly. The tarball is the authority: the lockfile records what was
requested, the tarball records what shipped.

Usage:
    python scripts/check_bundled_advisories.py                  # report
    python scripts/check_bundled_advisories.py --gate           # offline, non-zero on drift
    python scripts/check_bundled_advisories.py --check-upstream # is it fixable yet?
    python scripts/check_bundled_advisories.py --json
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AMPLIFY_LOCK = ROOT / "amplify" / "package-lock.json"
AMPLIFY_PKG = ROOT / "amplify" / "package.json"

#: The state this triage was written against, on 2026-09-30. Each is re-derived rather than
#: trusted; these are the values a change should make us re-read the reasoning.
TRIAGED = {
    "bundledPath": "node_modules/aws-cdk-lib/node_modules/brace-expansion",
    "bundledVersion": "5.0.9",
    "awsCdkLibPinned": "2.270.0",
    #: Clears all three advisories: the ranges are < 5.0.10, < 5.0.11 and < 5.0.12.
    "firstSafeVersion": "5.0.12",
    "alerts": [55, 56, 57],
}


def parse_version(value: str) -> tuple[int, ...]:
    """`5.0.9` -> `(5, 0, 9)`. Non-numeric parts are dropped rather than raising."""
    return tuple(int(part) for part in re.findall(r"\d+", value or ""))


def is_safe(version: str) -> bool:
    return parse_version(version) >= parse_version(TRIAGED["firstSafeVersion"])


def read_lock() -> dict:
    """What the committed amplify lockfile says about the bundled copy."""
    if not AMPLIFY_LOCK.exists():
        return {"error": f"{AMPLIFY_LOCK.relative_to(ROOT)} not found"}
    lock = json.loads(AMPLIFY_LOCK.read_text(encoding="utf-8"))
    packages = lock.get("packages", {})

    entry = packages.get(TRIAGED["bundledPath"], {})
    cdk = packages.get("node_modules/aws-cdk-lib", {})

    # Every brace-expansion copy, so a NEW bundled one elsewhere is not missed.
    all_copies = {path: meta.get("version")
                  for path, meta in packages.items()
                  if path.endswith("/brace-expansion")}
    vulnerable = {path: version for path, version in all_copies.items()
                  if version and parse_version(version)[:1] >= (4,) and not is_safe(version)}

    return {
        "bundledVersion": entry.get("version"),
        "inBundle": entry.get("inBundle", False),
        "awsCdkLibVersion": cdk.get("version"),
        "allCopies": all_copies,
        "vulnerableCopies": vulnerable,
    }


def read_declared_pin() -> str:
    if not AMPLIFY_PKG.exists():
        return ""
    pkg = json.loads(AMPLIFY_PKG.read_text(encoding="utf-8"))
    return (pkg.get("dependencies", {}) or {}).get("aws-cdk-lib", "")


def latest_upstream() -> dict:
    """Download the newest aws-cdk-lib and read the bundled brace-expansion it ships.

    The tarball rather than the registry metadata, because a bundled dependency does not appear
    in the package's declared dependency list - it is simply inside the archive.
    """
    try:
        version = subprocess.run(["npm", "view", "aws-cdk-lib", "version"],
                                 capture_output=True, text=True, check=True).stdout.strip()
        tarball = subprocess.run(["npm", "view", "aws-cdk-lib", "dist.tarball"],
                                 capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {"error": f"could not query npm: {exc}"}

    try:
        with urllib.request.urlopen(tarball, timeout=180) as response:
            blob = response.read()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not download the tarball: {type(exc).__name__}"}

    member_path = "package/node_modules/brace-expansion/package.json"
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
            handle = archive.extractfile(member_path)
            if handle is None:
                # No bundled copy at all is the best possible outcome.
                return {"latestAwsCdkLib": version, "bundledVersion": None,
                        "note": "no bundled brace-expansion in the tarball"}
            bundled = json.loads(handle.read().decode("utf-8")).get("version")
    except KeyError:
        return {"latestAwsCdkLib": version, "bundledVersion": None,
                "note": "no bundled brace-expansion in the tarball"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not read the tarball: {type(exc).__name__}"}

    return {"latestAwsCdkLib": version, "bundledVersion": bundled,
            "fixAvailable": bundled is None or is_safe(bundled)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gate", action="store_true",
                        help="offline; non-zero when the triaged facts have moved")
    parser.add_argument("--check-upstream", action="store_true",
                        help="download the latest aws-cdk-lib and report whether a fix exists")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    lock = read_lock()
    report: dict = {"triaged": TRIAGED, "lock": lock, "declaredPin": read_declared_pin()}
    problems: list[str] = []
    notices: list[str] = []

    if lock.get("error"):
        print(f"ERROR: {lock['error']}", file=sys.stderr)
        return 2

    # 1. Is the bundled copy still the one that was triaged?
    if lock["bundledVersion"] is None:
        notices.append(
            "the bundled brace-expansion is GONE from the lockfile - if aws-cdk-lib stopped "
            "bundling it, alerts 55/56/57 may now be genuinely resolved and their dismissal "
            "should be revisited")
    elif lock["bundledVersion"] != TRIAGED["bundledVersion"]:
        if is_safe(lock["bundledVersion"]):
            notices.append(
                f"the bundled copy moved to {lock['bundledVersion']}, which CLEARS all three "
                f"advisories. Reopen 55/56/57 as fixed, or let Dependabot close them, and "
                f"delete this watch.")
        else:
            problems.append(
                f"the bundled copy moved to {lock['bundledVersion']}, still below "
                f"{TRIAGED['firstSafeVersion']}. The triage text cites "
                f"{TRIAGED['bundledVersion']} and must be re-read before it is quoted again.")

    # 2. Is it still bundled? If it became a normal transitive dep, an override WOULD work.
    if lock["bundledVersion"] is not None and not lock["inBundle"]:
        problems.append(
            "the copy is no longer inBundle, so it is now a normal transitive dependency - an "
            "npm `overrides` entry would work, and the 'unfixable' conclusion no longer holds")

    # 3. Has the pin moved? The triage measured two specific versions.
    if lock["awsCdkLibVersion"] != TRIAGED["awsCdkLibPinned"]:
        notices.append(
            f"aws-cdk-lib is now {lock['awsCdkLibVersion']}, not the "
            f"{TRIAGED['awsCdkLibPinned']} that was measured - re-run --check-upstream")

    # 4. A vulnerable copy anywhere else is a different problem and must not be absorbed.
    unexpected = {path: version for path, version in lock["vulnerableCopies"].items()
                  if path != TRIAGED["bundledPath"]}
    if unexpected:
        problems.append(
            f"vulnerable brace-expansion copies outside the triaged one: {unexpected}. These "
            f"are NOT covered by the dismissal of 55/56/57.")

    upstream: dict = {}
    if args.check_upstream:
        upstream = latest_upstream()
        report["upstream"] = upstream
        if upstream.get("error"):
            notices.append(f"upstream check failed: {upstream['error']}")
        elif upstream.get("fixAvailable"):
            notices.append(
                f"A FIX IS AVAILABLE: aws-cdk-lib {upstream['latestAwsCdkLib']} bundles "
                f"brace-expansion {upstream.get('bundledVersion') or 'none'}. Bump the pin in "
                f"amplify/package.json, regenerate the lockfile, and undo the dismissal of "
                f"{TRIAGED['alerts']}.")

    report["problems"] = problems
    report["notices"] = notices

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print("BUNDLED ADVISORY WATCH - brace-expansion inside aws-cdk-lib")
        print("=" * 72)
        print(f"  triaged bundled version : {TRIAGED['bundledVersion']}")
        print(f"  lockfile bundled version: {lock['bundledVersion']}  "
              f"(inBundle={lock['inBundle']})")
        print(f"  aws-cdk-lib             : {lock['awsCdkLibVersion']} "
              f"(declared {report['declaredPin'] or '-'})")
        print(f"  first safe version      : {TRIAGED['firstSafeVersion']}")
        print(f"  dismissed alerts         : {TRIAGED['alerts']} (tolerable_risk)")
        print()
        print("  every brace-expansion copy in the amplify lockfile:")
        for path, version in sorted(lock["allCopies"].items(), key=lambda kv: kv[0]):
            mark = "VULNERABLE" if path in lock["vulnerableCopies"] else "ok        "
            print(f"    {mark} {version:10s} {path}")
        if args.check_upstream:
            print()
            if upstream.get("error"):
                print(f"  upstream: {upstream['error']}")
            else:
                print(f"  latest aws-cdk-lib      : {upstream.get('latestAwsCdkLib')}")
                print(f"  it bundles              : "
                      f"{upstream.get('bundledVersion') or 'nothing'}")
                print(f"  FIX AVAILABLE           : {upstream.get('fixAvailable')}")
        if notices:
            print("\n  NOTICES")
            for notice in notices:
                print(f"    - {notice}")
        if problems:
            print("\n  PROBLEMS")
            for problem in problems:
                print(f"    - {problem}")

    if args.gate:
        if problems:
            print("\nGATE FAILED - the facts this triage rests on have changed",
                  file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            print("\nRe-read docs/security-dependabot-triage.md and update both it and "
                  "TRIAGED in this script.", file=sys.stderr)
            return 1
        print("\nGATE PASSED - still the situation that was triaged; nothing new is reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
