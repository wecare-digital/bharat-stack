"""Tests for scripts/npm_ci_gate.py.

The gate's whole value is the line it draws between two failures that arrive in the same
`npm ci` output: four known-upstream bundled-dependency edges that no change to this repo
can fix, and genuine lockfile drift that must stop a commit. If that line moves, the gate
either bricks `deps-upgrade.yml` again or silently re-permits the rot that broke the
lockfile last time. Both regressions are invisible without these tests, because the
workflow is `workflow_dispatch`-only and nobody runs it per-push.

`npm` is never invoked here. `decide()` and `classify_output()` are pure, and the fixture
below is the real captured output from `npm ci --legacy-peer-deps --dry-run` on `stack`
at 2026-09-29 (npm 11.19.0 / Node 24.21.0), trimmed of the usage banner.
"""
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "npm_ci_gate.py"

# Registered in sys.modules before exec_module, matching test_deploy_map_provisioning.py.
# Not optional here: the script combines `from __future__ import annotations` with
# @dataclass, and dataclasses resolves its field types via sys.modules[cls.__module__],
# which is None for a module loaded from a path and never registered.
_spec = importlib.util.spec_from_file_location("npm_ci_gate_under_test", SCRIPT)
gate = importlib.util.module_from_spec(_spec)
sys.modules["npm_ci_gate_under_test"] = gate
_spec.loader.exec_module(gate)


REAL_FAILURE = """\
npm error code EUSAGE
npm error
npm error `npm ci` can only install packages when your package.json and package-lock.json or npm-shrinkwrap.json are in sync. Please update your lock file with `npm install` before continuing.
npm error
npm error Missing: @opentelemetry/core@2.0.0 from lock file
npm error Missing: @opentelemetry/core@2.0.0 from lock file
npm error Missing: @opentelemetry/core@2.0.0 from lock file
npm error Missing: @opentelemetry/core@2.0.0 from lock file
npm error
npm error Clean install a project
npm error Run "npm help ci" for more info
"""

#: The five entries the lockfile was actually missing when it rotted. This is the class
#: the gate exists to keep failing.
HISTORICAL_ROT = """\
npm error code EUSAGE
npm error Missing: @aws-cdk/cli-plugin-contract@1.0.0 from lock file
npm error Missing: webpack@5.94.0 from lock file
npm error Missing: @webassemblyjs/ast@1.12.1 from lock file
npm error Missing: @webassemblyjs/wasm-edit@1.12.1 from lock file
npm error Missing: json-schema-traverse@1.0.0 from lock file
"""


class TestClassify:
    def test_finds_every_sync_finding_including_duplicates(self):
        findings = gate.classify_output(REAL_FAILURE)
        assert findings == ["Missing: @opentelemetry/core@2.0.0 from lock file"] * 4

    def test_strips_the_npm_error_prefix(self):
        assert gate.classify_output("npm error Missing: foo@1.0.0 from lock file") == [
            "Missing: foo@1.0.0 from lock file"
        ]

    def test_reads_unprefixed_and_legacy_err_lines(self):
        """A TTY run omits the prefix and old npm used `npm ERR!`; both must still parse."""
        assert gate.classify_output("Missing: foo@1.0.0 from lock file")
        assert gate.classify_output("npm ERR! Invalid: bar@2.0.0")

    def test_ignores_prose_that_merely_mentions_the_package(self):
        noise = (
            "npm error `npm ci` can only install packages when your package.json and\n"
            "npm error package-lock.json are in sync. Please update your lock file.\n"
            "npm error Run \"npm help ci\" for more info\n"
        )
        assert gate.classify_output(noise) == []

    def test_recognises_the_other_sync_kinds(self):
        findings = gate.classify_output(
            "npm error Invalid: lock file's a@1.0.0 does not satisfy a@2.0.0\n"
            "npm error Extraneous: b@1.0.0 from lock file\n"
        )
        assert findings == [
            "Invalid: lock file's a@1.0.0 does not satisfy a@2.0.0",
            "Extraneous: b@1.0.0 from lock file",
        ]


class TestDecide:
    def test_the_former_upstream_finding_is_no_longer_tolerated(self):
        """This used to assert the four OTel findings PASSED. They now fail, by design.

        The allowlist is empty because the packages that produced them left the root lockfile
        (docs/npm-ci-backend-isolation.md). If `npm ci` at the root ever emits them again,
        something has put @aws-amplify/backend back into the web app's dependency tree, and that
        is drift worth failing on rather than tolerating.
        """
        verdict = gate.decide(1, REAL_FAILURE)
        assert not verdict.ok
        assert len(verdict.unexpected) == 4
        assert verdict.tolerated == []

    def test_historical_rot_still_fails(self):
        verdict = gate.decide(1, HISTORICAL_ROT)
        assert not verdict.ok
        assert len(verdict.unexpected) == 5
        assert "webpack@5.94.0" in " ".join(verdict.unexpected)

    def test_real_drift_alongside_the_former_finding_still_fails(self):
        """The mixed case is the one a coarse allowlist gets wrong. With an empty allowlist every
        finding is unexpected, so all five are reported rather than one - still a failure, and now
        a fuller account of why."""
        verdict = gate.decide(1, REAL_FAILURE + "npm error Missing: webpack@5.94.0 from lock file\n")
        assert not verdict.ok
        assert "Missing: webpack@5.94.0 from lock file" in verdict.unexpected
        assert len(verdict.unexpected) == 5
        assert verdict.tolerated == []

    def test_a_different_version_is_still_drift(self):
        """Kept from when the allowlist matched by whole string rather than substring: a different
        version of the same package was never covered, and with an empty allowlist nothing is."""
        verdict = gate.decide(1, "npm error Missing: @opentelemetry/core@2.9.0 from lock file")
        assert not verdict.ok
        assert verdict.unexpected == ["Missing: @opentelemetry/core@2.9.0 from lock file"]

    def test_a_different_opentelemetry_package_is_not_covered(self):
        verdict = gate.decide(1, "npm error Missing: @opentelemetry/resources@2.0.0 from lock file")
        assert not verdict.ok

    def test_failure_with_no_findings_is_not_treated_as_drift(self):
        verdict = gate.decide(1, "npm error network ETIMEDOUT registry.npmjs.org")
        assert not verdict.ok
        assert "not drift" in verdict.reason

    def test_missing_npm_fails(self):
        verdict = gate.decide(127, "npm error npm executable not found on PATH")
        assert not verdict.ok

    def test_success_passes_with_nothing_to_flag(self):
        """allowlist_unused exists to nag when the allowlist tolerates nothing. The allowlist is
        empty now, so there is nothing to nag about and the flag must stay down - otherwise every
        green run would print a notice telling someone to empty an already-empty list."""
        verdict = gate.decide(0, "added 1234 packages in 30s")
        assert verdict.ok
        assert verdict.allowlist_unused is False

    def test_strict_mode_refuses_to_tolerate_anything(self):
        """Probe mode answers "does npm ci work yet", so it must not pass on the allowlist. With an
        empty allowlist strict and default agree; the distinction is kept because it is what makes
        re-adding an entry safe to review."""
        verdict = gate.decide(1, REAL_FAILURE, strict=True)
        assert not verdict.ok
        assert len(verdict.unexpected) == 4
        assert verdict.tolerated == []

    def test_strict_mode_still_passes_a_real_success(self):
        assert gate.decide(0, "added 1234 packages", strict=True).ok


class TestAllowlist:
    def test_is_empty_so_the_gate_is_strict(self):
        """Growing this list is how the gate stops being a gate, so its size is pinned - and the
        correct size is now zero. It held the four-fold @opentelemetry/core@2.0.0 finding until the
        packages causing it moved to amplify/package.json; see
        docs/npm-ci-backend-isolation.md. Re-adding an entry needs captured `npm ci` output and a
        reason no change to this repo can resolve it."""
        assert gate.KNOWN_UPSTREAM == ()

    def test_every_entry_is_a_finding_the_parser_produces(self):
        """An entry the parser can never emit is dead and would tolerate nothing."""
        for entry in gate.KNOWN_UPSTREAM:
            assert gate.classify_output(f"npm error {entry}") == [entry]


class TestWorkflowWiring:
    """The gate only protects anything if the workflow actually routes through it.

    Parsed as YAML rather than grepped, because the prose in these files legitimately
    discusses `npm ci` at length and a text search cannot tell a comment from a step.
    """

    WORKFLOWS = ROOT / ".github" / "workflows"

    @pytest.fixture(scope="class")
    def deps_upgrade(self):
        return yaml.safe_load((self.WORKFLOWS / "deps-upgrade.yml").read_text())

    @pytest.fixture(scope="class")
    def gate_step(self, deps_upgrade):
        steps = [
            step
            for step in deps_upgrade["jobs"]["upgrade"]["steps"]
            if "npm_ci_gate.py" in (step.get("run") or "")
        ]
        assert len(steps) == 1, "expected exactly one step to invoke scripts/npm_ci_gate.py"
        return steps[0]

    def test_deps_upgrade_gates_through_the_script(self, gate_step):
        assert "scripts/npm_ci_gate.py" in gate_step["run"]

    def test_the_gate_runs_from_an_empty_node_modules(self, gate_step):
        """A gate that inspects a tree npm install just populated proves nothing."""
        assert "rm -rf node_modules" in gate_step["run"]

    def test_deps_upgrade_gate_is_blocking(self, gate_step):
        """Tolerating the known finding is the concession; skipping the step is not."""
        assert gate_step.get("continue-on-error") in (None, False)

    def test_deps_upgrade_installs_python_for_the_gate(self, deps_upgrade):
        """No setup-python step and `python` may not resolve, silently or otherwise."""
        uses = [step.get("uses", "") for step in deps_upgrade["jobs"]["upgrade"]["steps"]]
        assert any(u.startswith("actions/setup-python@") for u in uses)

    def test_no_step_calls_npm_ci_directly(self, deps_upgrade):
        """A bare `npm ci` step fails every run on the four upstream findings."""
        for step in deps_upgrade["jobs"]["upgrade"]["steps"]:
            for line in (step.get("run") or "").splitlines():
                assert not line.strip().startswith("npm ci"), (
                    f"step {step.get('name')!r} calls npm ci directly; route it through "
                    "scripts/npm_ci_gate.py"
                )

    def test_deps_upgrade_no_longer_claims_npm_ci_exits_zero(self):
        """The old comment asserted a verified exit 0 that is measurably false on `stack`."""
        raw = (self.WORKFLOWS / "deps-upgrade.yml").read_text()
        assert "complete with exit 0" not in raw

    def test_build_test_installs_with_npm_ci(self):
        """The per-push install is reproducible now. It was `npm install` for as long as the
        bundled-OpenTelemetry findings were in the root lockfile; the packages carrying them are
        backend-only and now live in amplify/package.json, so `npm ci` resolves the web app's
        lockfile cleanly. See docs/npm-ci-backend-isolation.md."""
        build_test = yaml.safe_load((self.WORKFLOWS / "build-test.yml").read_text())
        installs = [
            step["run"]
            for step in build_test["jobs"]["build-test"]["steps"]
            if step.get("name") == "Install dependencies"
        ]
        assert installs == ["npm ci --no-audit --no-fund"]
