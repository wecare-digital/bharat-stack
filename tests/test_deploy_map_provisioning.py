"""A deploy report whose failure count is never zero is not a signal.

Every `deploy_all_lambdas.py` run ended `failed=1`, always for the same reason:
`wecare-customer-whatsapp-auth` is in the deploy map but has never been created in
the account - its first creation is owned by
`scripts/provision_customer_whatsapp_auth.py`, which has not been run.

That is a correctness problem in the report rather than in the deploy. A genuinely
broken deploy would have landed in a summary that already said `failed=1`, next to
an entry everyone had learned to skip. "Awaiting provisioning" and "failed" are
different states and now count separately.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "deploy_all_lambdas.py"


@pytest.fixture(scope="module")
def deploy_module():
    spec = importlib.util.spec_from_file_location("deploy_all_lambdas", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["deploy_all_lambdas"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("deploy_all_lambdas", None)


def test_spec_carries_who_provisions_it(deploy_module):
    spec = deploy_module.Spec("x", "core/contacts", provisioned_by="python scripts/x.py")
    assert spec.provisioned_by == "python scripts/x.py"


def test_an_ordinary_function_claims_no_provisioner(deploy_module):
    """The default must stay empty.

    A function with no `provisioned_by` that goes missing IS a failure - it means
    something deleted it. Defaulting to "awaiting provisioning" would hide that.
    """
    spec = deploy_module.Spec("x", "core/contacts")
    assert spec.provisioned_by == ""


def test_the_one_known_unprovisioned_function_declares_its_script(deploy_module):
    specs = {s.name: s for s in deploy_module.SPECS}
    auth = specs["wecare-customer-whatsapp-auth"]
    assert auth.provisioned_by
    # The named script has to exist, or the message sends someone nowhere.
    referenced = auth.provisioned_by.split()[-1]
    assert (ROOT / referenced).exists(), f"{referenced} does not exist"


def test_exactly_one_spec_is_awaiting_provisioning(deploy_module):
    """Pinned as a count so a second one has to be a deliberate decision.

    Marking a function `provisioned_by` is how a real failure could be made to
    look expected, so the set is small and explicit on purpose.
    """
    waiting = [s.name for s in deploy_module.SPECS if s.provisioned_by]
    assert waiting == ["wecare-customer-whatsapp-auth"]


def test_the_summary_line_reports_the_new_state(deploy_module):
    """It has to appear in the output, or the count exists and nobody sees it."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "awaiting_provisioning={tally['awaiting_provisioning']}" in source
    assert "awaiting provisioning" in source
    # And it must not be quietly folded into `failed`.
    assert 'tally["awaiting_provisioning"] += 1' in source


def test_qrcode_is_no_longer_imported_at_runtime():
    """The other source of permanent noise in the same report.

    `import qrcode` was in no requirements file and in no attached layer, so it
    failed on every invoice render and logged a WARNING each time - for a condition
    that was permanent and not actionable. The encoded value is a constant URL, so
    the pre-rendered S3 image is the right artifact and adding the dependency would
    have been the wrong repair.
    """
    handler = (ROOT / "amplify" / "functions" / "payments" / "invoice-engine"
               / "handler.py").read_text(encoding="utf-8")
    assert "import qrcode" not in handler
    assert "qrcode.QRCode" not in handler
    # The S3 asset and the text fallback both stay - the image degrades, the
    # information does not.
    assert "stream/media/m/qr-selfservice.png" in handler
    assert "wecare.digital/selfservice" in handler
