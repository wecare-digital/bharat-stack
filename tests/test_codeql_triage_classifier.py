"""The triage classifier decides what gets dismissed, so its FAIL-CLOSED rules are the test.

`scripts/triage_codeql_logging.py --apply` dismisses a CodeQL alert when every element of a
logged expression classifies as safe. A wrong "safe" therefore hides a disclosure
permanently, which is the one outcome `docs/security-codeql-triage.md` exists to prevent.

So these tests are weighted towards the negative: most of them assert that something is
**not** proven. Each case is a shape that was actually present in this tree, or a shape that
a plausible next rule would wrongly accept. Two were real mistakes caught while writing the
classifier and are pinned here so they cannot come back:

  * `mask_text` was added to the sanitiser list on the strength of its name. It substitutes
    `Bearer <token>` and masks no phone number at all, so it would have proven a Meta error
    body safe.
  * The exception check first rejected any expression *mentioning* `exc`, which wrongly
    condemned `exc.response['Error']['Code']` and `type(exc).__name__` — the two forms the
    steering actually asks for.
"""
import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "triage_codeql_logging.py"

_spec = importlib.util.spec_from_file_location("triage_under_test", SCRIPT)
triage = importlib.util.module_from_spec(_spec)
sys.modules["triage_under_test"] = triage
_spec.loader.exec_module(triage)


def classify_in(source: str, expr_src: str) -> str:
    """Classify `expr_src` as it appears inside `source`, with resolution enabled."""
    tree = ast.parse(source)
    resolver = triage.Resolver(tree)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and ast.unparse(node.value) == expr_src:
            target = node.value
            break
    assert target is not None, f"{expr_src!r} not found as an interpolation in the fixture"
    key = triage._expr_key(target) or expr_src
    return triage.classify_expr(target, key, resolver, target)


def proven(source: str, expr_src: str) -> bool:
    return classify_in(source, expr_src) != "UNPROVEN"


class TestExceptionTextIsNeverProven:
    """Steering: log `type(exc).__name__`; log an exception's text only when we built it."""

    @pytest.mark.parametrize("expr", [
        "e", "exc", "err", "str(e)", "repr(exc)", "exc.args", "e.message",
        "e.response['Error']['Message']", "exc.detail", "e or 'none'",
    ])
    def test_exception_text_stays_unproven(self, expr):
        src = f"def h():\n    try:\n        pass\n    except Exception as e:\n" \
              f"        exc = e\n        logger.info(f\"x {{{expr}}}\")\n"
        assert not proven(src, expr), f"{expr} was proven safe"

    @pytest.mark.parametrize("expr", [
        "type(exc).__name__",
        "exc.response['Error']['Code']",
    ])
    def test_narrowings_of_an_exception_are_judged_on_their_merits(self, expr):
        # The regression: a blanket "mentions exc" rule rejected both of these, which are
        # the forms the steering prescribes.
        src = f"def h():\n    try:\n        pass\n    except Exception as exc:\n" \
              f"        logger.info(f\"x {{{expr}}}\")\n"
        assert proven(src, expr), f"{expr} should be provable, it is the prescribed form"


class TestSanitisersAreVerifiedNotTrusted:
    def test_mask_text_does_not_launder_a_phone_number(self):
        # It substitutes `Bearer <token>` only. Named here because it WAS added to the
        # sanitiser list and had to be removed after reading the implementation.
        assert "mask_text" not in triage.SANITISERS
        src = 'def h():\n    logger.info(f"x {mask_text(json.dumps(payload))}")\n'
        assert not proven(src, "mask_text(json.dumps(payload))")

    def test_bool_returning_str_predicates_are_sanitisers(self):
        src = 'def h():\n    logger.info(f"x {(formatted_phone or \'\').isdigit()}")\n'
        assert proven(src, "(formatted_phone or '').isdigit()")

    def test_string_returning_str_methods_are_not(self):
        # `strip`/`format`/`join` return the STRING and would carry a number through.
        for expr in ("phone.strip()", "phone.upper()"):
            src = f'def h():\n    logger.info(f"x {{{expr}}}")\n'
            assert not proven(src, expr), f"{expr} must not be treated as a sanitiser"


class TestNameResolutionFailsClosed:
    def test_a_parameter_is_never_resolvable(self):
        # Its value comes from a caller this pass cannot see.
        src = 'def h(sid):\n    logger.info(f"x {sid}")\n'
        assert not proven(src, "sid")

    def test_a_for_target_is_not_resolvable(self):
        src = 'def h():\n    for p in problems:\n        logger.info(f"x {p}")\n'
        assert not proven(src, "p")

    def test_a_walrus_and_a_with_target_are_not_resolvable(self):
        src = 'def h():\n    if (v := compute()):\n        logger.info(f"x {v}")\n'
        assert not proven(src, "v")
        src2 = 'def h():\n    with open(f) as fh:\n        logger.info(f"x {fh}")\n'
        assert not proven(src2, "fh")

    def test_a_tuple_unpack_is_not_resolvable(self):
        src = 'def h():\n    a, b = split()\n    logger.info(f"x {a}")\n'
        assert not proven(src, "a")

    def test_a_module_constant_bound_twice_proves_nothing(self):
        # Either binding could be live, so neither proves the other.
        once = 'NAME = "wecare/x"\ndef h():\n    logger.info(f"x {NAME}")\n'
        twice = ('NAME = "wecare/x"\nNAME = fetch()\n'
                 'def h():\n    logger.info(f"x {NAME}")\n')
        assert proven(once, "NAME")
        assert not proven(twice, "NAME")

    def test_a_local_assigned_from_an_unresolvable_call_stays_unproven(self):
        src = 'def h():\n    v = fetch_secret()\n    logger.info(f"x {v}")\n'
        assert not proven(src, "v")

    def test_resolution_terminates_on_a_cycle(self):
        # `x = y; y = x` must hit the depth limit rather than the stack.
        src = 'def h():\n    x = y\n    y = x\n    logger.info(f"x {x}")\n'
        assert not proven(src, "x")

    def test_a_constant_chain_resolves(self):
        src = ('REGION = "us-east-1"\nACCOUNT = "775261844268"\n'
               'ARN = f"arn:aws:iam::{ACCOUNT}:role/r"\n'
               'def h():\n    logger.info(f"x {ARN}")\n')
        assert proven(src, "ARN")


class TestTheFstringReaderSeesLoggedFstringsOnly:
    def test_it_finds_a_logged_fstring(self, tmp_path):
        p = tmp_path / "m.py"
        p.write_text('import logging\nlogger = logging.getLogger()\n'
                     'def h(x):\n    logger.info(f"a {phone_number_id} b {bool(x)}")\n')
        out = triage.fstring_interpolations(p, 4, 4)
        assert out is not None
        assert [v for _, v, _ in out] == ["OPAQUE_ID", "SANITISED:bool"]

    def test_a_non_logger_fstring_is_not_treated_as_a_log(self, tmp_path):
        # Returning None here is what keeps the reader from proving an unrelated f-string
        # and dismissing an alert that points at something else entirely.
        p = tmp_path / "m.py"
        p.write_text('def h(to):\n    body = f"send to {to}"\n    return body\n')
        assert triage.fstring_interpolations(p, 2, 2) is None

    def test_one_unproven_interpolation_taints_the_whole_site(self, tmp_path):
        p = tmp_path / "m.py"
        p.write_text('import logging\nlogger = logging.getLogger()\n'
                     'def h(raw):\n    logger.info(f"{phone_number_id} {raw}")\n')
        out = triage.fstring_interpolations(p, 4, 4)
        assert "UNPROVEN" in [v for _, v, _ in out]


class TestStalenessGuard:
    def test_an_uncommitted_file_is_stale_regardless_of_commit(self):
        # The guard used to check the working tree only when the analysed commit differed
        # from HEAD, so editing a file and re-running at the same commit classified the
        # alert against lines that had already moved.
        assert triage.working_tree_dirty("definitely/not/a/path/in/this/repo.py") is False
        assert triage.working_tree_dirty("scripts/triage_codeql_logging.py") in (True, False)

    def test_an_unknown_commit_is_treated_as_changed(self):
        assert triage.file_changed("0" * 40, "HEAD", "README.md") is True
