"""Guard the CodeQL language matrix against re-creating a permanently errored configuration.

WHY THIS EXISTS. On 2026-09-29 the repository's Code scanning tool status page showed
three errors — "CodeQL exited with errors", "Detected build command failed", "No code
scanning results" — all belonging to a `language:swift` configuration whose last scan was
2026-08-23. Nothing was failing at the time. Swift had been removed from the matrix in
`.github/workflows/codeql.yml` weeks earlier, and that is precisely the problem:

    the tool status page reports each configuration's LAST analysis, forever,
    so deleting a matrix entry freezes its final state instead of retiring it.

Both Swift analyses had run under `{"build-mode":"autobuild","language":"swift"}` and
recorded `unsuccessful execution, exit code: 0` with `results_count: 0`, because autobuild
cannot build Capacitor's generated Xcode project without the npm / `npx cap sync ios` /
CocoaPods chain. Since no new Swift analysis could ever be produced, no green run could
supersede them. Clearing the errors required deleting the analyses by hand through
`DELETE /repos/{owner}/{repo}/code-scanning/analyses/{id}`.

So the failure mode this file blocks is not "CodeQL is red". It is a language being added
here, failing once, and then being dropped — which leaves an error on the repository's
security surface that outlives the change that caused it and cannot be fixed by any
subsequent commit.

WHAT IT ALLOWS. Adding a compiled language back is fine, and is expected if real native
iOS/Android logic ever lands. It must arrive with `build-mode: manual` and a real build,
not with autobuild and not with the CodeQL starter template's `exit 1` placeholder still
in place. Nothing here asserts that native code stays absent; it asserts that whatever is
declared can actually be analysed.
"""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "codeql.yml"

#: The languages carrying maintained application logic. All three support build-mode
#: 'none', which is why they cannot fail the way Swift did.
EXPECTED_LANGUAGES = {"actions", "javascript-typescript", "python"}

#: CodeQL rejects build-mode 'none' for these, so they fall back to a build. Under
#: autobuild that build is a guess, and a guess that fails writes an error onto the tool
#: status page that survives the language being dropped again.
COMPILED_LANGUAGES = {
    "c-cpp",
    "csharp",
    "go",
    "java-kotlin",
    "rust",
    "swift",
}

#: Verbatim fragment of the starter template's unedited manual build step. Its body ends
#: in `exit 1`, so a 'manual' entry that ships alongside it fails every run by design.
TEMPLATE_PLACEHOLDER = "replace this with the commands to build"


@pytest.fixture(scope="module")
def workflow() -> dict:
    assert WORKFLOW.is_file(), f"missing {WORKFLOW.relative_to(ROOT)}"
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def matrix(workflow) -> list[dict]:
    include = workflow["jobs"]["analyze"]["strategy"]["matrix"]["include"]
    assert include, "the analyze job declares no languages, so nothing is scanned at all"
    return include


class TestMatrixShape:
    def test_every_entry_names_a_language_and_a_build_mode(self, matrix):
        # An entry without an explicit build-mode inherits CodeQL's default, which for a
        # compiled language is autobuild. Being explicit is what makes the next two
        # assertions meaningful rather than approximate.
        for entry in matrix:
            assert "language" in entry, f"matrix entry with no language: {entry}"
            assert "build-mode" in entry, (
                f"{entry['language']} declares no build-mode; CodeQL would choose one, "
                "and for a compiled language that choice is autobuild"
            )

    def test_language_set_is_the_documented_one(self, matrix):
        languages = {entry["language"] for entry in matrix}
        assert languages == EXPECTED_LANGUAGES, (
            "the analysed language set changed. Adding a language is allowed, but update "
            "EXPECTED_LANGUAGES here and read the header of this file first: a language "
            "that fails once and is then removed leaves a permanent error on the Code "
            "scanning tool status page.\n"
            f"  expected: {sorted(EXPECTED_LANGUAGES)}\n"
            f"  found:    {sorted(languages)}"
        )

    def test_no_duplicate_languages(self, matrix):
        languages = [entry["language"] for entry in matrix]
        assert len(languages) == len(set(languages)), (
            f"a language is declared twice, which produces two configurations for one "
            f"category: {languages}"
        )


class TestBuildModeSafety:
    def test_no_entry_uses_autobuild(self, matrix):
        # This is the exact configuration the two deleted Swift analyses ran under.
        offenders = [e["language"] for e in matrix if e.get("build-mode") == "autobuild"]
        assert not offenders, (
            f"{offenders} would run under autobuild. That is how the Swift configuration "
            "produced 'Detected build command failed' and then outlived its own matrix "
            "entry. Use build-mode 'manual' with a real build instead."
        )

    def test_compiled_languages_declare_a_manual_build(self, matrix):
        for entry in matrix:
            if entry["language"] in COMPILED_LANGUAGES:
                assert entry.get("build-mode") == "manual", (
                    f"{entry['language']} cannot use build-mode "
                    f"{entry.get('build-mode')!r}; CodeQL only supports 'none' for "
                    "interpreted languages. Declare 'manual' and supply the build."
                )

    def test_a_manual_entry_is_not_paired_with_the_template_placeholder(
        self, matrix, workflow
    ):
        manual = [e["language"] for e in matrix if e.get("build-mode") == "manual"]
        if not manual:
            pytest.skip("no manual build-mode entries; the placeholder step never runs")

        steps = workflow["jobs"]["analyze"]["steps"]
        build_steps = [
            s
            for s in steps
            if "manual" in str(s.get("if", "")) and isinstance(s.get("run"), str)
        ]
        assert build_steps, (
            f"{manual} declares build-mode 'manual' but the job has no step gated on "
            "manual mode, so no build runs and the extractor produces no database"
        )
        for step in build_steps:
            assert TEMPLATE_PLACEHOLDER not in step["run"], (
                f"{manual} declares build-mode 'manual' while the starter template's "
                "placeholder build step is still in place. That step ends in `exit 1`, so "
                "every run fails and writes an error onto the tool status page."
            )


class TestScanCoverageIsNotSilentlyLost:
    def test_python_and_javascript_are_always_analysed(self, matrix):
        # The two languages that hold this repo's own logic. Losing either is a silent
        # reduction in security coverage rather than a visible failure, which is why it is
        # asserted separately from the exact-set check above.
        languages = {entry["language"] for entry in matrix}
        for required in ("python", "javascript-typescript"):
            assert required in languages, (
                f"{required} is no longer analysed. The application's own code lives "
                "there; dropping it removes coverage without turning anything red."
            )

    def test_analysis_categories_are_per_language(self, workflow):
        # Two configurations sharing one category overwrite each other's results, and the
        # survivor's state is what the tool status page reports.
        steps = workflow["jobs"]["analyze"]["steps"]
        analyze = [s for s in steps if "codeql-action/analyze" in str(s.get("uses", ""))]
        assert len(analyze) == 1, f"expected exactly one analyze step, found {len(analyze)}"
        category = analyze[0].get("with", {}).get("category", "")
        assert "matrix.language" in category, (
            "the analyze step's category must vary per language, or every matrix leg "
            f"reports into the same configuration. Found: {category!r}"
        )
