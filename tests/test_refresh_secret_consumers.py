"""Secret rotations must refresh indirect shared-module consumers too."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/refresh_secret_consumers.py"


def load_module():
    spec = importlib.util.spec_from_file_location("refresh_secret_consumers_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_razorpay_rotation_discovers_checkout_through_shared_import_closure():
    module = load_module()
    try:
        found = dict(module.consumers("wecare/razorpay/api"))
    finally:
        sys.modules.pop("refresh_secret_consumers_under_test", None)

    assert "wecare-checkout" in found
    evidence = found["wecare-checkout"]
    assert "handler.py" in evidence
    # The handler need not spell the secret id: website checkout imports the provider client.
    assert "lambda_utils." in evidence


def test_webhook_secret_does_not_become_a_checkout_api_credential_dependency():
    module = load_module()
    try:
        found = dict(module.consumers("wecare/razorpay-webhook"))
    finally:
        sys.modules.pop("refresh_secret_consumers_under_test", None)

    assert "wecare-checkout" not in found
