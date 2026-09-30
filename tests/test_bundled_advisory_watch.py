"""A dismissed alert cannot tell you it became fixable. This is what does.

Three Dependabot alerts (55, 56, 57 - two HIGH) cover `brace-expansion@5.0.9` bundled inside
the `aws-cdk-lib` tarball. They are not fixable here: `inBundle: True` means the code ships
inside the archive, so an npm `overrides` entry - which describes what npm should *fetch* -
cannot reach it. That was attempted and reverted; it left the version unchanged while churning
the lockfile by 1537 lines.

The original plan was to leave them OPEN so the upstream fix would be noticed. They were then
dismissed as `tolerable_risk`, which is defensible - they reach no deployed artifact - but it
removes the only thing that was going to notice. `scripts/check_bundled_advisories.py` replaces
that mechanism, and these tests keep it honest.

The distinction the gate has to preserve
---------------------------------------
"The bundled version changed" is NOT a security failure. It means the triage text cites a
version that is no longer there and must be re-read before it is quoted again. Conflating that
with "something vulnerable is reachable" produces a gate that fires on routine upgrades, and a
gate that cries wolf gets switched off. So the script separates PROBLEMS (the reasoning no
longer holds) from NOTICES (a fact moved; go look), and these tests assert that separation
rather than just "exit 0".
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_bundled_advisories.py"
AMPLIFY_LOCK = ROOT / "amplify" / "package-lock.json"
TRIAGE_DOC = ROOT / "docs" / "security-dependabot-triage.md"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=ROOT)


@pytest.fixture(scope="module")
def report() -> dict:
    """The offline report. No network, so this is CI-safe."""
    proc = run("--json")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_the_watch_runs_offline():
    """CI has no npm registry access guaranteed and no AWS credentials. The gate must work
    from the committed lockfile alone, or it will be disabled the first time it flakes."""
    proc = run("--gate")
    assert proc.returncode == 0, f"gate failed:\n{proc.stdout}\n{proc.stderr}"
    assert "GATE PASSED" in proc.stdout


def test_the_bundled_copy_is_still_the_one_that_was_triaged(report):
    """If this fails, `docs/security-dependabot-triage.md` cites a version that is not there."""
    assert report["lock"]["bundledVersion"] == report["triaged"]["bundledVersion"]


def test_it_is_still_bundled_because_that_is_the_whole_argument(report):
    """`inBundle` is the load-bearing fact. If the copy ever becomes a normal transitive
    dependency, an npm `overrides` entry WOULD work and 'unfixable' stops being true - which
    means the dismissal should be undone, not inherited."""
    assert report["lock"]["inBundle"] is True, (
        "the copy is no longer bundled, so it is now fixable with an overrides entry")


def test_the_gate_reports_a_problem_when_the_copy_stops_being_bundled(tmp_path):
    """Proves the assertion above is actually enforced rather than merely stated.

    Runs the script against a doctored lockfile with `inBundle` removed. Uses a real temporary
    copy of the tree's lockfile so the shape is genuine rather than a hand-built fixture.
    """
    lock = json.loads(AMPLIFY_LOCK.read_text(encoding="utf-8"))
    path = "node_modules/aws-cdk-lib/node_modules/brace-expansion"
    assert path in lock["packages"], "the triaged path has moved; update this test with it"
    lock["packages"][path].pop("inBundle", None)

    # Mirror the layout the script expects: <root>/amplify/package-lock.json
    fake_root = tmp_path / "repo"
    (fake_root / "amplify").mkdir(parents=True)
    (fake_root / "scripts").mkdir()
    (fake_root / "amplify" / "package-lock.json").write_text(json.dumps(lock))
    (fake_root / "amplify" / "package.json").write_text(
        json.dumps({"dependencies": {"aws-cdk-lib": "2.270.0"}}))
    copied = fake_root / "scripts" / SCRIPT.name
    copied.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    proc = subprocess.run([sys.executable, str(copied), "--gate"],
                          capture_output=True, text=True, cwd=fake_root)
    assert proc.returncode == 1, (
        f"the gate passed on a lockfile where the copy is NOT bundled, so the 'unfixable' "
        f"claim is unguarded:\n{proc.stdout}\n{proc.stderr}")
    assert "no longer inBundle" in (proc.stdout + proc.stderr)


def test_a_version_move_that_stays_vulnerable_is_a_problem_not_a_notice(tmp_path):
    """A bump to 5.0.10 clears one of the three advisories and not the others. That must be a
    PROBLEM - the triage text would be stale in a way that overstates how covered we are -
    rather than a quiet notice."""
    lock = json.loads(AMPLIFY_LOCK.read_text(encoding="utf-8"))
    path = "node_modules/aws-cdk-lib/node_modules/brace-expansion"
    lock["packages"][path]["version"] = "5.0.10"

    fake_root = tmp_path / "repo2"
    (fake_root / "amplify").mkdir(parents=True)
    (fake_root / "scripts").mkdir()
    (fake_root / "amplify" / "package-lock.json").write_text(json.dumps(lock))
    (fake_root / "amplify" / "package.json").write_text(json.dumps({"dependencies": {}}))
    copied = fake_root / "scripts" / SCRIPT.name
    copied.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    proc = subprocess.run([sys.executable, str(copied), "--json"],
                          capture_output=True, text=True, cwd=fake_root)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert any("5.0.10" in p for p in payload["problems"]), (
        f"a still-vulnerable bump was not reported as a problem: {payload}")


def test_a_safe_version_is_reported_as_the_fix_rather_than_a_failure(tmp_path):
    """The success case has to be recognisable, or nobody will act on it. A bump to a safe
    version must produce a NOTICE telling the reader to undo the dismissal - not a problem,
    and not silence."""
    lock = json.loads(AMPLIFY_LOCK.read_text(encoding="utf-8"))
    path = "node_modules/aws-cdk-lib/node_modules/brace-expansion"
    lock["packages"][path]["version"] = "5.0.12"

    fake_root = tmp_path / "repo3"
    (fake_root / "amplify").mkdir(parents=True)
    (fake_root / "scripts").mkdir()
    (fake_root / "amplify" / "package-lock.json").write_text(json.dumps(lock))
    (fake_root / "amplify" / "package.json").write_text(json.dumps({"dependencies": {}}))
    copied = fake_root / "scripts" / SCRIPT.name
    copied.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    proc = subprocess.run([sys.executable, str(copied), "--json"],
                          capture_output=True, text=True, cwd=fake_root)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["problems"] == [], f"a safe version should not be a problem: {payload}"
    assert any("CLEARS" in n for n in payload["notices"]), (
        f"a safe version must announce itself as the fix: {payload}")


def test_a_vulnerable_copy_elsewhere_is_not_absorbed_by_this_dismissal(report):
    """The dismissal covers ONE copy. Another vulnerable copy arriving under a different
    parent is a separate problem and must not inherit the 'tolerable risk' verdict."""
    triaged_path = report["triaged"]["bundledPath"]
    others = {p: v for p, v in report["lock"]["vulnerableCopies"].items() if p != triaged_path}
    assert not others, f"vulnerable copies outside the dismissal: {others}"


def test_the_triage_doc_records_that_the_alerts_are_dismissed_not_open():
    """The doc said they were deliberately left OPEN so the fix would be noticed. They are
    now dismissed, so that sentence is false and the doc must name this watch instead -
    otherwise the recorded plan points at a mechanism that no longer exists."""
    text = TRIAGE_DOC.read_text(encoding="utf-8")
    assert "check_bundled_advisories" in text, (
        "the triage doc must name the script that replaced 'leave them open'")
    assert "tolerable_risk" in text, (
        "the doc must record the dismissal reason actually applied")
