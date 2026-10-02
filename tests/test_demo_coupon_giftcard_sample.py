"""`scripts/demo_coupon_giftcard_sample.py`'s anti-rot enforcer.

Design reference: `.agents/tasks/wix-coupon-giftcard-sample-20261002/design.md` revision 8, §7.

A TEST rather than a new CI step, for three reasons: the existing `python -m pytest -q` already
collects it, it inherits the harness's containment, and a failure is a named assertion instead
of a scrollback. No workflow file is modified.

The demo is run IN-PROCESS through `main(["--json", "--no-colour"])`, which is why `main`
returns its exit code rather than calling `sys.exit` itself.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from lambda_utils import wix_ecom  # noqa: E402
from lambda_utils.ecommerce import wix_gift_cards as wg  # noqa: E402

DEMO = ROOT / "scripts/demo_coupon_giftcard_sample.py"
PLACEHOLDER_API_KEY = "wix-admin-key-PLACEHOLDER-not-a-credential"
REFERENCE = "wd-gc-sample-2026-10-02"


class _UnexpectedAwsUse(BaseException):
    pass


class _ExplodesOnAttributeAccess:
    def __getattr__(self, name):
        raise _UnexpectedAwsUse(f"this test touched boto3.{name}")


@pytest.fixture
def demo(monkeypatch):
    """Load the script by path - this repository's existing pattern for a script under test."""
    monkeypatch.setitem(wix_ecom._key_cache, "key", PLACEHOLDER_API_KEY)
    monkeypatch.setitem(sys.modules, "boto3", _ExplodesOnAttributeAccess())
    spec = importlib.util.spec_from_file_location("demo_under_test", DEMO)
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_the_demo_runs_offline_and_reports_three_legs_and_no_mismatches(demo, capsys):
    code = demo.main(["--json", "--no-colour"])
    captured = capsys.readouterr()
    assert code == 0, captured.out

    # `--json`'s contract is MACHINE-READABLE STDOUT AND NOTHING ELSE, so the whole of stdout
    # has to parse. A stray print would make the transcript unusable to a consumer.
    transcript = json.loads(captured.out)
    assert captured.err == ""

    assert len(transcript["legs"]) == 3
    assert [leg["leg"] for leg in transcript["legs"]] == [
        "coupon", "wix-giftcard", "our-giftcard"]
    assert transcript["mismatchCount"] == 0
    assert transcript["awsCallsAttempted"] == 0
    assert transcript["secretsManagerClientBuilt"] is False

    # Corroborated from OUTSIDE the demo, rather than by the demo agreeing with itself.
    assert wix_ecom._secrets is None


def test_the_transcript_carries_no_clear_bearer_code_and_no_credential(demo, capsys):
    """The clear gift-card code and the credential are both absent from the whole transcript.

    The masking is a HABIT for the day the adapter is wired; what makes the demo safe offline is
    that the transport is stubbed unconditionally, so every code is a fixture placeholder. Both
    facts are asserted so neither is assumed.
    """
    assert demo.main(["--json", "--no-colour"]) == 0
    rendered = capsys.readouterr().out
    assert wg.demo_code(reference_id=REFERENCE) not in rendered
    assert wg.card_code(reference_id=REFERENCE, pepper="any-pepper") not in rendered
    assert PLACEHOLDER_API_KEY not in rendered
    for issuer in ("rzp_live_", "sk-", "AIza", "ghp_", "xoxb-", "AKIA", "ASIA", "sk_live_",
                   "ksk_", "PRIVATE KEY"):
        assert issuer not in rendered

    # The secret is referenced by NAME in the rendered form, which is the correct disclosure.
    assert demo.main(["--no-colour", "--leg", "wix-giftcard"]) == 0
    plain = capsys.readouterr().out
    assert "wecare/wix/headless-api-key" in plain
    assert "<redacted" in plain
    assert wg.demo_code(reference_id=REFERENCE) not in plain


@pytest.mark.parametrize("leg", ["coupon", "wix-giftcard", "our-giftcard"])
def test_each_leg_runs_on_its_own(demo, capsys, leg):
    assert demo.main(["--json", "--no-colour", "--leg", leg]) == 0
    transcript = json.loads(capsys.readouterr().out)
    assert [entry["leg"] for entry in transcript["legs"]] == [leg]
    assert transcript["mismatchCount"] == 0


@pytest.mark.parametrize("argv,reason", [
    (["--value-paise", "100", "--redeem-paise", "200"], "redeem above value"),
    (["--value-paise", "0"], "a card worth nothing"),
    (["--redeem-paise", "0"], "a redemption of nothing"),
    (["--value-paise", "250050", "--redeem-paise", "250000"], "residual below the minimum leg"),
    (["--coupon-money-off-paise", "12345"], "not a whole number of rupees"),
    (["--coupon-money-off-paise", "0"], "a discount of nothing"),
    (["--reference-id", ""], "an empty reference"),
    (["--coupon-code", "not a code!"], "the store's own code rule"),
    (["--leg", "nonexistent"], "argparse choices"),
])
def test_a_usage_error_exits_two(demo, argv, reason):
    """`2` for every usage error, so a misuse is never mistaken for a contract failure (`1`)."""
    with pytest.raises(SystemExit) as exit_info:
        demo.main(["--json", "--no-colour"] + argv)
    assert exit_info.value.code == 2, reason


def test_the_demo_imports_the_shared_stubs_rather_than_private_copies():
    """ONE stub, TWO callers. A private copy inside `scripts/` is the drift this prevents.

    Nothing in `tests/` ships in a Lambda package, so importing from there costs nothing at
    deploy time - `scripts/deploy_all_lambdas.py` packages per-function sources under
    `amplify/`.
    """
    tree = ast.parse(DEMO.read_text(encoding="utf-8"), filename=str(DEMO))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert "coupon_fake_dynamo" in imported
    assert "wix_transport_stub" in imported
    # And it reimplements neither.
    assert not (ROOT / "scripts/coupon_fake_dynamo.py").exists()
    assert not (ROOT / "scripts/wix_transport_stub.py").exists()


def test_the_demo_makes_no_payment_state_decision():
    """It imports no payment vocabulary and asserts nothing about a payment status.

    A demonstration that decided a payment state would be a second decision site for the one
    vocabulary that must have exactly one.
    """
    tree = ast.parse(DEMO.read_text(encoding="utf-8"), filename=str(DEMO))
    modules = {(node.module or "") for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom)}
    modules |= {alias.name for node in ast.walk(tree)
                if isinstance(node, ast.Import) for alias in node.names}
    assert not [name for name in modules if "payment_status" in name]
    assert not [name for name in modules if "payment_attempt" in name]
