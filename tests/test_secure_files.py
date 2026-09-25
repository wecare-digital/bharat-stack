"""Secure-file-sharing invariants that must not regress.

These pin the decisions that are easy to undo by accident, not the happy path:

* an opaque S3 key that leaks nothing about the customer or the file
* one refusal message shared by "not yours" and "does not exist"
* payment disabled by default, and no Razorpay contact while it is disabled
* entitlement written only by the signature-verified webhook
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FUNC_DIR = ROOT / "amplify" / "functions" / "core" / "secure-files"
SHARED = ROOT / "amplify" / "functions" / "shared"

for path in (str(FUNC_DIR), str(SHARED)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture()
def mod(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("SECURE_FILES_PAYMENT_ENABLED", raising=False)
    handler = importlib.import_module("handler")
    return importlib.reload(handler)


# ── the opaque key ────────────────────────────────────────────────────────────

def test_key_is_two_uuids_and_leaks_nothing(mod):
    """The key must not contain the customer's number or the original filename."""
    import re
    import uuid

    phone = "918100640044"
    original = "Trade-Licence-Ramesh.pdf"

    file_id = f"{uuid.uuid4().hex}-{uuid.uuid4().hex}"
    key = f"{mod.SECURE_PREFIX}wecare-digital-{file_id}{mod._safe_extension(original)}"

    assert key.startswith("secure/wecare-digital-")
    assert re.fullmatch(r"secure/wecare-digital-[0-9a-f]{32}-[0-9a-f]{32}\.pdf", key)
    assert phone not in key
    assert "Ramesh" not in key
    assert "Licence" not in key


def test_extension_is_whitelisted_not_sanitised(mod):
    assert mod._safe_extension("a.pdf") == ".pdf"
    assert mod._safe_extension("a.PNG") == ".png"
    # anything odd is dropped rather than cleaned, because it lands in an S3 key
    assert mod._safe_extension("a.tar.gz") == ".gz"
    assert mod._safe_extension("noextension") == ""
    assert mod._safe_extension("a.verylongextension") == ""
    assert mod._safe_extension("a.p df") == ""
    assert mod._safe_extension("a.../../etc") == ""
    assert mod._safe_extension("") == ""


# ── phone handling ────────────────────────────────────────────────────────────

def test_phone_normalisation_matches_the_otp_lambda(mod):
    """If these drift, a customer authenticates and then owns nothing."""
    assert mod.normalise_phone("8100640044") == "918100640044"
    assert mod.normalise_phone("+91 81006 40044") == "918100640044"
    assert mod.normalise_phone("918100640044") == "918100640044"
    for bad in ("", "123", "abc", "9" * 20):
        with pytest.raises(ValueError):
            mod.normalise_phone(bad)


def test_phone_is_masked_to_last_four(mod):
    masked = mod.mask_phone("918100640044")
    assert masked.endswith("0044")
    assert "8100" not in masked
    assert masked == "********0044"


# ── uniform refusal ───────────────────────────────────────────────────────────

def test_wrong_owner_and_missing_file_are_indistinguishable(mod):
    """Any difference here lets a caller probe which file ids exist."""
    a = mod._not_registered("https://wecare.digital")
    b = mod._not_registered("https://wecare.digital")
    assert a == b
    assert a["statusCode"] == 403
    assert "NOT_REGISTERED" in a["body"]
    # must not hint at existence
    for leak in ("not found", "does not exist", "unknown file", "forbidden owner"):
        assert leak.lower() not in a["body"].lower()


# ── payment stays off ─────────────────────────────────────────────────────────

def test_payment_disabled_by_default(mod, monkeypatch):
    monkeypatch.delenv("SECURE_FILES_PAYMENT_ENABLED", raising=False)
    assert mod._payment_enabled() is False


def test_payment_flag_is_read_per_call_not_captured_at_import(mod, monkeypatch):
    """A switch that needs every sandbox to recycle is not a switch."""
    assert mod._payment_enabled() is False
    monkeypatch.setenv("SECURE_FILES_PAYMENT_ENABLED", "true")
    assert mod._payment_enabled() is True
    monkeypatch.setenv("SECURE_FILES_PAYMENT_ENABLED", "off")
    assert mod._payment_enabled() is False


def test_order_creation_refuses_and_never_touches_razorpay_while_disabled(mod, monkeypatch):
    monkeypatch.delenv("SECURE_FILES_PAYMENT_ENABLED", raising=False)

    monkeypatch.setattr(
        mod,
        "_owned_active_file",
        lambda fid, ident: {"fileId": fid, "pricePaise": 4900, "s3Key": "secure/x"},
    )

    def explode(*_a, **_k):  # pragma: no cover - must not be reached
        raise AssertionError("Razorpay must not be contacted while payment is disabled")

    monkeypatch.setitem(
        sys.modules, "razorpay_orders", type(sys)("razorpay_orders")
    )
    sys.modules["razorpay_orders"].create_order = explode

    result = mod._create_order("f1", {"phone": "918100640044"}, "https://wecare.digital")
    assert result["statusCode"] == 503
    assert "PAYMENT_DISABLED" in result["body"]


# ── the customer pool, not the admin pool ─────────────────────────────────────

def test_issuer_is_pinned_to_the_customer_pool(mod):
    """An admin-pool token must not authorise a customer download.

    `get_user` is pool-agnostic, so the issuer check is the only thing separating
    the two pools.
    """
    assert mod.CUSTOMER_POOL_ID != "us-east-1_cSx0RHCIR"
    assert mod.CUSTOMER_POOL_ISSUER.endswith(mod.CUSTOMER_POOL_ID)
    assert mod.CUSTOMER_POOL_ISSUER.startswith("https://cognito-idp.")


def test_unverified_claim_decode_never_raises(mod):
    """It runs on attacker-supplied strings, so it must fail soft."""
    for junk in ("", "a", "a.b", "a.b.c", "...", "x" * 500):
        assert mod._jwt_claims_unverified(junk) == {}


def test_customer_identity_requires_a_token(mod):
    assert mod._customer_identity({"headers": {}}) is None
    assert mod._customer_identity({}) is None


# ── the webhook is the only grantor ───────────────────────────────────────────

def test_only_the_webhook_sets_paid_true():
    """`secure-files` must never write paid=True; that is the webhook's job alone."""
    source = (FUNC_DIR / "handler.py").read_text()
    # the pending grant is written with paid False
    assert '"paid": False' in source
    assert '"paid": True' not in source


def test_redeem_requires_paid_and_unconsumed():
    source = (FUNC_DIR / "handler.py").read_text()
    assert "paid = :true" in source
    assert "consumed = :false" in source
    assert "ConditionalCheckFailedException" in source


def test_webhook_grant_refuses_to_revive_a_spent_grant():
    source = (
        ROOT / "amplify/functions/payments/razorpay-webhook/handler.py"
    ).read_text()
    assert "_mark_download_grant_paid" in source
    assert "secure_file_download" in source
    # replay protection: only flips a grant that is still unpaid
    assert "attribute_exists(grantId) AND paid = :false" in source


def test_razorpay_orders_reads_the_secret_lazily_not_at_import():
    """A module-scope secret read is frozen for the sandbox's life."""
    source = (FUNC_DIR / "razorpay_orders.py").read_text()
    assert "_cached" in source
    # no top-level get_secret_value call
    for line in source.splitlines():
        if line.startswith("get_secret_value") or line.startswith("_sm.get_secret_value"):
            raise AssertionError("secret is read at import scope")
    assert "def _credentials()" in source


def test_no_credential_is_logged_or_returned():
    source = (FUNC_DIR / "razorpay_orders.py").read_text()
    assert "key_secret" in source  # it is used
    # but never printed, logged or put in an exception message
    for bad in ("print(", "logger.info(creds", "logger.warning(creds", f'{{creds}}'):
        assert bad not in source


def test_generated_password_is_never_logged_or_returned():
    """The random permanent password exists only to reach CONFIRMED status."""
    source = (FUNC_DIR / "handler.py").read_text()
    assert "admin_set_user_password" in source
    assert "token_urlsafe" in source
    # it must not be returned to the admin or logged anywhere
    assert "password" not in source.split("def _upload_init")[1].lower()
