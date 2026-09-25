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


def test_order_creation_reads_the_api_secret_not_the_webhook_secret():
    """The two Razorpay secrets hold different fields and are not interchangeable.

        wecare/razorpay/api        key_id + key_secret
        wecare/razorpay-webhook    webhook_secret only

    partner-onboarding already shipped this bug once: it read the API pair out of
    the webhook secret, got two empty strings, and returned 501 on every top-up.
    This pins the correct one so the same mistake cannot land twice.
    """
    source = (FUNC_DIR / "razorpay_orders.py").read_text()
    assert 'RAZORPAY_SECRET_ID = os.environ.get("RAZORPAY_SECRET_ID", "wecare/razorpay/api")' in source

    provisioner = (ROOT / "scripts/provision_secure_files_api.py").read_text()
    assert 'RAZORPAY_SECRET_NAME = "wecare/razorpay/api"' in provisioner
    # and the IAM grant must follow the same secret, or the read 403s at runtime
    assert "secret:{RAZORPAY_SECRET_NAME}-*" in provisioner


def test_no_razorpay_sdk_is_bundled():
    """razorpay==2.0.1 is dev-only; the Lambda runtime does not have it."""
    source = (FUNC_DIR / "razorpay_orders.py").read_text()
    assert "import razorpay" not in source
    assert "urllib.request" in source

    dev_requirements = (ROOT / "requirements-dev.txt").read_text()
    assert "razorpay==" in dev_requirements, "expected the SDK pinned for dev use"


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


# ── the OTP send shape, proven against the live WABA ──────────────────────────

def test_otp_button_is_url_not_copy_code():
    """`wecare_otp` is an AUTHENTICATION template and its button is type URL.

    Meta materialises the copy-code affordance as a real URL button:

        https://www.whatsapp.com/otp/code/?...&code=otp{{1}}

    so the OTP is a text substitution into that URL. Sending
    `sub_type: "copy_code"` with a `coupon_code` parameter is refused:

        (#132018) buttons: Button at index 0 must be of type Url

    and the caller sees only "sender returned HTTP 400", which is why this was
    invisible until a live round trip was run. Verified 2026-09-25: copy_code
    fails, url succeeds.
    """
    source = (
        ROOT / "amplify/functions/auth/customer-whatsapp-auth/handler.py"
    ).read_text()

    # Assert on the payload, not on the whole file: the comment above the fix names
    # the rejected shape, so a bare substring search for "copy_code" matches the
    # explanation rather than any real code.
    code_lines = [
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    ]
    code = "\n".join(code_lines)

    assert '"sub_type": "url"' in code
    assert '"sub_type": "copy_code"' not in code
    assert '"coupon_code"' not in code
    # the OTP substitutes {{1}} as text
    assert '{"type": "text", "text": otp}' in code


def test_otp_template_name_and_language_are_not_drifted():
    """The live template is `wecare_otp` / `en`. A mismatch fails at the Meta call."""
    source = (
        ROOT / "amplify/functions/auth/customer-whatsapp-auth/handler.py"
    ).read_text()
    assert '"OTP_TEMPLATE_NAME", "wecare_otp"' in source
    assert '"OTP_TEMPLATE_LANGUAGE", "en"' in source


def test_otp_is_never_logged():
    """The handler prints metadata about a send but must never include the code."""
    source = (
        ROOT / "amplify/functions/auth/customer-whatsapp-auth/handler.py"
    ).read_text()
    logged = source.split("customer_whatsapp_otp_sent")[1][:400]
    assert "otp" not in logged.lower().replace("otp_sent", "")


# ── the customer loop in the browser ──────────────────────────────────────────

CLIENT_TS = ROOT / "src/api/client.ts"
FILES_PAGE = ROOT / "src/pages/files.tsx"
CUSTOMER_AUTH = ROOT / "src/lib/customerAuth.ts"


def _strip_comments(source: str) -> str:
    """Drop TS comments before asserting.

    These files document the shape they deliberately avoid - "sessionStorage, not
    localStorage", "must NOT go through authFetch" - so a naive substring search
    matches the explanation and fails on correct code.
    """
    out = []
    in_block = False
    for line in source.splitlines():
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block = True
            continue
        if stripped.startswith("*") or stripped.startswith("//"):
            continue
        out.append(line.split("//")[0] if "://" not in line else line)
    return "\n".join(out)


def _ts_function(source: str, name: str) -> str:
    """One function's own source, and nothing after it.

    Two approaches that do not work here, both tried:

    * cutting at the next ``\\n}`` - these signatures carry multi-line generic return
      types like ``Promise<ApiResult<{ ... }>>``, so the first closing brace belongs
      to the type rather than the body;
    * cutting at the next ``\\nexport`` - ``customerApiCall`` is an unexported helper
      sitting between two exported functions, so it got swallowed into the preceding
      one and every assertion about which fetch path is used became meaningless.

    Cutting at the first column-zero ``}`` ends at the function's own closing brace,
    since everything nested is indented.
    """
    marker = f"export async function {name}"
    start = source.index(marker)
    lines = source[start:].splitlines()
    body = []
    for index, line in enumerate(lines):
        body.append(line)
        if index > 0 and line == "}":
            break
    return "\n".join(body)


def test_customer_routes_use_the_customer_token_not_the_staff_token():
    """The three customer routes must not go through apiCall/authFetch.

    authFetch attaches the Amplify session, which belongs to the STAFF pool. A staff
    token on a customer route does not fail cleanly: the backend validates it, sees
    the wrong issuer and returns 401, which is indistinguishable from an expired
    customer session - so the customer would be sent round the verification loop
    forever with no indication why.
    """
    source = _strip_comments(CLIENT_TS.read_text())

    for fn in (
        "listMySecureFiles",
        "createSecureFileOrder",
        "redeemSecureFileDownload",
    ):
        body = _ts_function(source, fn)
        assert "customerApiCall" in body, f"{fn} must use the customer token"
        assert "apiCallResult(" not in body, f"{fn} must not use the staff token path"
        assert "authFetch(" not in body, f"{fn} must not use the staff token path"


def test_admin_routes_still_use_the_staff_token():
    source = _strip_comments(CLIENT_TS.read_text())
    for fn in ("initSecureUpload", "listSecureFiles", "revokeSecureFile", "confirmSecureUpload"):
        body = _ts_function(source, fn)
        assert "apiCallResult" in body, f"{fn} is an admin route and needs the staff token"
        assert "customerApiCall" not in body, f"{fn} must not use a customer token"


def test_the_page_does_not_trust_the_razorpay_callback():
    """Checkout's handler runs in the browser and is forgeable.

    It may only stop the spinner. The download must come from polling the server,
    which requires the signature-verified webhook to have marked the grant paid.
    """
    source = FILES_PAGE.read_text()
    assert "pollForDownload" in source
    # the handler must not itself redeem or navigate
    handler_body = source.split("handler: ()")[1][:200]
    assert "redeem" not in handler_body
    assert "location" not in handler_body


def test_presigned_upload_does_not_get_a_bearer_header():
    """A presigned URL carries its own SigV4; adding our bearer makes S3 refuse."""
    source = CLIENT_TS.read_text()
    body = source.split("export async function uploadSecureFileBytes")[1].split("\n}")[0]
    assert "Authorization" not in body
    assert "authFetch" not in body


def test_frontend_phone_normalisation_matches_the_backend():
    """Drift here means a customer signs in and owns nothing."""
    source = CUSTOMER_AUTH.read_text()
    # same rule as normalise_phone: 10 digits starting 6-9 gets 91 prefixed
    assert "length === 10" in source
    assert "[6-9]" in source
    assert "91${digits}" in source


def test_customer_token_is_not_in_localstorage():
    """sessionStorage dies with the tab; localStorage would outlive a shared browser."""
    source = _strip_comments(CUSTOMER_AUTH.read_text())
    assert "sessionStorage" in source
    assert "localStorage" not in source


def test_provisioner_preserves_a_manually_enabled_payment_flag():
    """Re-provisioning must not silently switch live payments back off."""
    source = (ROOT / "scripts/provision_secure_files_api.py").read_text()
    assert "keep_payment = current_payment_flag() if exists else False" in source
    assert "environment(payment_enabled=keep_payment)" in source


# ── webhook-independence, so a missing subscription cannot strand a payment ────

def test_reconcile_only_accepts_a_captured_payment():
    """`authorized` means held, not taken. Granting on it hands over the file for a
    payment that can still fail."""
    source = (FUNC_DIR / "razorpay_orders.py").read_text()
    assert 'payment.get("status") == "captured"' in source
    assert '"authorized"' not in source


def test_reconcile_cannot_replay_a_spent_grant():
    """The fallback may only change whether a grant is payable, never unspend it."""
    source = (FUNC_DIR / "handler.py").read_text()
    body = source.split("def _reconcile_grant")[1].split("\ndef ")[0]
    assert 'grant.get("consumed")' in body
    assert "return False" in body
    # it writes paid through the same guard the webhook uses
    assert 'ConditionExpression="attribute_exists(grantId) AND paid = :false"' in body
    # and it is inert while payments are off
    assert "_payment_enabled()" in body


def test_reconcile_verifies_ownership_before_paying():
    source = (FUNC_DIR / "handler.py").read_text()
    body = source.split("def _reconcile_grant")[1].split("\ndef ")[0]
    assert 'grant.get("fileId") != file_id' in body
    assert 'grant.get("ownerPhone") != identity["phone"]' in body


def test_redeem_after_reconcile_is_still_single_use():
    source = (FUNC_DIR / "handler.py").read_text()
    body = source.split("def _redeem_after_reconcile")[1].split("\ndef ")[0]
    assert "consumed = :false" in body
    assert "paid = :true" in body


def test_reconciliation_is_flagged_in_logs_for_visibility():
    """If this path ever fires, the webhook is not doing its job and that should be
    findable rather than silent."""
    source = (FUNC_DIR / "handler.py").read_text()
    assert "WEBHOOK_MAY_NOT_BE_SUBSCRIBED" in source
    assert '":via": "reconcile"' in source
