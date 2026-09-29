#!/usr/bin/env python3
"""`npm ci` as a lockfile-drift gate that tolerates exactly one known upstream defect.

WHY THIS EXISTS
---------------
Two true statements were in conflict, and the conflict was resolved in the wrong
direction twice.

1. `npm ci` cannot install this repo at all. It fails with four
   `Missing: @opentelemetry/core@2.0.0 from lock file` errors. The cause is inside
   published tarballs, not this repo: `@aws-amplify/data-construct` and
   `@aws-amplify/graphql-api-construct` each bundle (`inBundle: true`) their own
   OpenTelemetry copies, and their bundled `@opentelemetry/resources@2.0.0` and
   `sdk-trace-base@2.0.0` both declare an *exact* dependency on
   `@opentelemetry/core@2.0.0` while the `@opentelemetry/core` bundled beside them is
   2.8.0. Two packages x two dependents = four errors. `npm install` succeeds because it
   trusts bundled deps rather than resolving them; `npm ci` validates those edges and
   refuses. Regenerating the lockfile from scratch reproduces the identical four errors,
   and an `overrides` entry crashes npm with exit 134. Neither is fixable from here.

2. A non-blocking `npm ci` step is how the lockfile rotted last time. When nothing
   failed, the committed lock drifted until it was missing five entries the tree
   genuinely needs (`@aws-cdk/cli-plugin-contract`, `webpack`, `@webassemblyjs/ast`,
   `@webassemblyjs/wasm-edit`, `json-schema-traverse`).

`deps-upgrade.yml` previously asserted (1) was false and gated hard on `npm ci`, which
makes that workflow unable to commit anything it regenerates - it is a brick, not a
tripwire. Flipping the step back to `continue-on-error` re-creates (2).

Both framings assume one verdict for the whole command. There are two distinct failure
classes in that output, so this gate separates them: the four known upstream edges are
tolerated by exact string, and *any other* sync finding still fails the job. That keeps
real drift detection for the class we caused while not blocking on the class we cannot
fix. The day upstream fixes the bundles, `npm ci` exits 0, the allowlist matches nothing,
and the gate says so - so the workaround cannot silently outlive its cause.

DELIBERATELY NOT A SUBSTRING MATCH. The allowlist holds whole normalised findings, so a
*different* missing package, or a different version of the same package, is unexpected
and fails. An allowlist that matched `@opentelemetry` loosely would hide the next real
drift in the same dependency.

Usage:
    python scripts/npm_ci_gate.py                       # gate (allowlist active)
    python scripts/npm_ci_gate.py --strict              # no allowlist; probe mode
    python scripts/npm_ci_gate.py -- --legacy-peer-deps # extra args passed to npm ci
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Findings that are known-upstream and cannot be fixed from this repo. Whole normalised
#: findings, not substrings. Remove an entry the moment `npm ci` stops producing it.
KNOWN_UPSTREAM: tuple[str, ...] = (
    "Missing: @opentelemetry/core@2.0.0 from lock file",
)

#: npm prefixes each error line with "npm error " when it is not a TTY. The kinds here are
#: the ones npm emits for a package.json/lock mismatch under EUSAGE.
_SYNC_FINDING = re.compile(
    r"^(?:npm\s+(?:error|ERR!)\s+)?"
    r"(?P<kind>Missing|Invalid|Extraneous|Conflicting peer dependency):\s*"
    r"(?P<detail>\S.*?)\s*$"
)


def classify_output(output: str) -> list[str]:
    """Every lockfile-sync finding in `output`, normalised, in order, with duplicates.

    Duplicates are kept because the count is evidence: four identical
    `@opentelemetry/core` lines is the documented signature, and one or seven would mean
    the upstream shape moved and the allowlist needs re-deriving rather than reusing.
    """
    findings: list[str] = []
    for line in output.splitlines():
        match = _SYNC_FINDING.match(line.strip())
        if match:
            findings.append(f"{match.group('kind')}: {match.group('detail')}")
    return findings


@dataclass
class Verdict:
    ok: bool
    reason: str
    tolerated: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    allowlist_unused: bool = False


def decide(exit_code: int, output: str, *, strict: bool = False) -> Verdict:
    """Turn an `npm ci` result into a pass/fail verdict.

    `strict=True` removes the allowlist entirely, which is what an informational probe
    wants: it answers "does npm ci work yet", not "is the lockfile fit to commit".
    """
    findings = classify_output(output)
    allowed = () if strict else KNOWN_UPSTREAM

    if exit_code == 0:
        # Nothing to tolerate. If the allowlist is non-empty it is now dead weight, and
        # saying so is the whole reason this gate can be trusted not to become permanent.
        return Verdict(
            ok=True,
            reason="npm ci completed with exit 0",
            allowlist_unused=bool(allowed),
        )

    if not findings:
        return Verdict(
            ok=False,
            reason=(
                f"npm ci failed (exit {exit_code}) with no lockfile-sync findings, so this is "
                "not drift - look for a network, registry, disk or engine failure in the log"
            ),
        )

    unexpected = [f for f in findings if f not in allowed]
    if unexpected:
        return Verdict(
            ok=False,
            reason=(
                f"npm ci reported {len(unexpected)} lockfile-sync finding(s) that are not "
                "known-upstream; the lockfile is not fit to commit"
            ),
            tolerated=[f for f in findings if f in allowed],
            unexpected=unexpected,
        )

    return Verdict(
        ok=True,
        reason=(
            f"npm ci failed (exit {exit_code}) with only the {len(findings)} known-upstream "
            "bundled-dependency finding(s); tolerated"
        ),
        tolerated=findings,
    )


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_npm_ci(extra_args: list[str]) -> tuple[int, str]:
    cmd = ["npm", "ci", *extra_args]
    print(f"+ {' '.join(cmd)}", flush=True)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        return 127, "npm error npm executable not found on PATH"
    output = (proc.stdout or "") + (proc.stderr or "")
    print(output, end="" if output.endswith("\n") else "\n", flush=True)
    return proc.returncode, output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--lockfile",
        default="package-lock.json",
        help="lockfile whose hash must not change across the run (default: package-lock.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="disable the known-upstream allowlist; any npm ci failure fails the gate",
    )
    parser.add_argument(
        "npm_args",
        nargs="*",
        help="extra arguments forwarded to npm ci (put them after --)",
    )
    args = parser.parse_args(argv)

    lockfile = Path(args.lockfile)
    before = _sha256(lockfile)
    if before is None:
        print(f"::error::{lockfile} does not exist, so there is nothing to gate")
        return 1

    exit_code, output = _run_npm_ci(list(args.npm_args))
    verdict = decide(exit_code, output, strict=args.strict)

    after = _sha256(lockfile)
    if after != before:
        # Checked by hash rather than `git diff` on purpose: callers regenerate the
        # lockfile earlier in the job, so it is expected to differ from HEAD. What must
        # not happen is npm ci itself rewriting it.
        print(f"::error::npm ci rewrote {lockfile} - the lockfile is not self-consistent")
        return 1

    for finding in dict.fromkeys(verdict.tolerated):
        count = verdict.tolerated.count(finding)
        print(f"  tolerated (known upstream, x{count}): {finding}")
    for finding in dict.fromkeys(verdict.unexpected):
        print(f"::error::unexpected lockfile finding: {finding}")

    if verdict.allowlist_unused:
        print(
            "::notice::npm ci now exits 0 - the upstream bundled-dependency defect is fixed. "
            "Empty KNOWN_UPSTREAM in scripts/npm_ci_gate.py, switch build-test.yml's install "
            "step to `npm ci`, and drop the workaround note in docs/grahak-os-handoff.md."
        )

    if verdict.ok:
        print(f"PASS: {verdict.reason}")
        return 0
    print(f"::error::{verdict.reason}")
    print(f"FAIL: {verdict.reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
