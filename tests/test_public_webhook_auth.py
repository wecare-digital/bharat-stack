"""Both public webhook ingresses must authenticate their caller.

Provenance
----------
Phase 0 discovery on 2026-09-21 measured 332 HTTP API routes across two APIs with
**zero** API Gateway authorizers. Two of those routes reached handlers that
performed no caller verification of any kind:

  GET/POST /webhook/sinch-rcs  -> wecare-rcs-dlr
      No HMAC, no signature, no shared secret, no require_auth. The handler wrote
      into the canonical MessagesTable and could invoke wecare-rcs-send with a
      phone number taken from the unauthenticated request body.

  POST /whatsapp/inbound       -> wecare-inbound-whatsapp
      No X-Hub-Signature-256 check. Its only intended caller is an internal
      lambda_client.invoke from wecare-whatsapp-calling, which verifies the
      signature on the canonical /whatsapp ingress - but the public route bypassed
      that entirely, including the `action=create_invoice` branch.

These tests encode the boundary at the entry point, so a future refactor that
moves verification cannot quietly drop it. They run offline: no AWS call, no
provider call, no real secret.
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import meta_signature, sinch_signature  # noqa: E402

# Test-only values. Assembled rather than written as literals so the file carries
# no credential-shaped string for the secret scanners to flag.
SINCH_SECRET = "sinch-" + "webhook-" + "test-secret"
META_SECRET = "meta-" + "app-" + "test-secret"
META_SECRET_WABA2 = "meta-" + "app2-" + "test-secret"


class _Ctx:
    aws_request_id = "test-request-id"

    def get_remaining_time_in_millis(self):
        return 120000


# ── helpers ─────────────────────────────────────────────────────────────────

def _sinch_event(body: str, *, secret=SINCH_SECRET, nonce="01FJA8B4A7BM43YGWSG9GBV067",
                 timestamp=None, algorithm="HmacSHA256", sign=True,
                 tamper=False, method="POST"):
    """Build an API Gateway v2 event carrying a Sinch-signed callback."""
    ts = str(int(time.time())) if timestamp is None else str(timestamp)
    headers = {"content-type": "application/json"}
    if sign:
        signed = f"{body}.{nonce}.{ts}"
        digest = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).digest()
        headers["x-sinch-webhook-signature"] = base64.b64encode(digest).decode()
        headers["x-sinch-webhook-signature-nonce"] = nonce
        headers["x-sinch-webhook-signature-timestamp"] = ts
        if algorithm:
            headers["x-sinch-webhook-signature-algorithm"] = algorithm
    return {
        "routeKey": f"{method} /webhook/sinch-rcs",
        "rawPath": "/webhook/sinch-rcs",
        "requestContext": {"http": {"method": method}, "apiId": "zllr9lrg7j"},
        "headers": headers,
        "body": (body + " ") if tamper else body,
    }


def _meta_event(body: str, *, secret=META_SECRET, sign=True, tamper=False):
    """Build an API Gateway v2 event carrying a Meta-signed webhook."""
    headers = {"content-type": "application/json"}
    if sign:
        headers["x-hub-signature-256"] = "sha256=" + hmac.new(
            secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
    return {
        "routeKey": "POST /whatsapp/inbound",
        "rawPath": "/whatsapp/inbound",
        "requestContext": {"http": {"method": "POST"}, "apiId": "zllr9lrg7j"},
        "headers": headers,
        "body": (body + " ") if tamper else body,
    }


# ── the shared verifiers ────────────────────────────────────────────────────

class TestSinchSignatureHelper:
    """Contract from developers.sinch.com/docs/conversation/callbacks."""

    def test_official_documented_vector(self):
        """The example published by Sinch must produce the published signature."""
        secret = "foo_secret1234"
        body = (
            '{"app_id":"","accepted_time":"2021-10-18T17:49:13.813615Z","project_id":'
            '"e2df3a34-a71b-4448-9db5-a8d2baad28e4","contact_create_notification":'
            '{"contact":{"id":"01FJA8B466Y0R2GNXD78MD9SM1","channel_identities":'
            '[{"channel":"SMS","identity":"48123456789","app_id":""}],"display_name":'
            '"New Test Contact","email":"new.contact@email.com","external_id":"",'
            '"metadata":"","language":"EN_US"}},"message_metadata":""}'
        )
        nonce = "01FJA8B4A7BM43YGWSG9GBV067"
        timestamp = "1634579353"
        assert sinch_signature.expected_signature(secret, body, nonce, timestamp) == (
            "6bpJoRmFoXVjfJIVglMoJzYXxnoxRujzR4k2GOXewOE="
        )

    def test_valid_signature_accepted(self):
        ok, reason = sinch_signature.verify(_sinch_event('{"a":1}'), SINCH_SECRET)
        assert ok, reason

    def test_missing_signature_rejected(self):
        ok, reason = sinch_signature.verify(
            _sinch_event('{"a":1}', sign=False), SINCH_SECRET)
        assert not ok and reason == "missing_signature"

    def test_tampered_body_rejected(self):
        ok, reason = sinch_signature.verify(
            _sinch_event('{"a":1}', tamper=True), SINCH_SECRET)
        assert not ok and reason == "signature_mismatch"

    def test_wrong_secret_rejected(self):
        ok, reason = sinch_signature.verify(_sinch_event('{"a":1}'), "other-secret")
        assert not ok and reason == "signature_mismatch"

    def test_unsupported_algorithm_rejected(self):
        ok, reason = sinch_signature.verify(
            _sinch_event('{"a":1}', algorithm="HmacMD5"), SINCH_SECRET)
        assert not ok and reason == "unsupported_algorithm"

    def test_stale_timestamp_rejected(self):
        ok, reason = sinch_signature.verify(
            _sinch_event('{"a":1}', timestamp=int(time.time()) - 7200), SINCH_SECRET)
        assert not ok and reason == "timestamp_outside_window"

    def test_retry_within_window_accepted(self):
        """Sinch retries with backoff; a few minutes old is legitimate."""
        ok, reason = sinch_signature.verify(
            _sinch_event('{"a":1}', timestamp=int(time.time()) - 300), SINCH_SECRET)
        assert ok, reason

    def test_absent_secret_never_fails_open(self):
        ok, reason = sinch_signature.verify(_sinch_event('{"a":1}'), "")
        assert not ok and reason == "no_secret_configured"

    def test_base64_encoded_body_verified_against_decoded_bytes(self):
        body = '{"a":1}'
        ev = _sinch_event(body)
        ev["body"] = base64.b64encode(body.encode()).decode()
        ev["isBase64Encoded"] = True
        ok, reason = sinch_signature.verify(ev, SINCH_SECRET)
        assert ok, reason

    def test_already_parsed_body_cannot_be_verified(self):
        ev = _sinch_event('{"a":1}')
        ev["body"] = {"a": 1}
        ok, reason = sinch_signature.verify(ev, SINCH_SECRET)
        assert not ok and reason == "body_not_raw"

    def test_internal_invoke_is_not_an_http_request(self):
        assert sinch_signature.is_http_request({"Records": []}) is False
        assert sinch_signature.is_http_request(_sinch_event("{}")) is True


class TestMetaSignatureHelper:
    def test_valid_signature_accepted(self):
        ok, reason = meta_signature.verify(_meta_event('{"a":1}'), [META_SECRET])
        assert ok, reason

    def test_second_waba_secret_accepted(self):
        ev = _meta_event('{"a":1}', secret=META_SECRET_WABA2)
        ok, reason = meta_signature.verify(ev, [META_SECRET, META_SECRET_WABA2])
        assert ok, reason

    def test_missing_signature_rejected(self):
        ok, reason = meta_signature.verify(
            _meta_event('{"a":1}', sign=False), [META_SECRET])
        assert not ok and reason == "missing_signature"

    def test_tampered_body_rejected(self):
        ok, reason = meta_signature.verify(
            _meta_event('{"a":1}', tamper=True), [META_SECRET])
        assert not ok and reason == "signature_mismatch"

    def test_no_configured_secret_never_fails_open(self):
        ok, reason = meta_signature.verify(_meta_event('{"a":1}'), [])
        assert not ok and reason == "no_app_secret_configured"
        ok, reason = meta_signature.verify(_meta_event('{"a":1}'), ["", ""])
        assert not ok and reason == "no_app_secret_configured"


# ── rcs-dlr entry point ─────────────────────────────────────────────────────

@pytest.fixture
def rcs_handler(monkeypatch):
    """Import rcs-dlr with AWS clients stubbed, and a known webhook secret."""
    path = str(ROOT / "amplify" / "functions" / "messaging" / "rcs-dlr")
    if path not in sys.path:
        sys.path.insert(0, path)
    for mod in list(sys.modules):
        if mod == "handler":
            del sys.modules[mod]

    with patch("boto3.resource") as res, patch("boto3.client") as cli:
        res.return_value = MagicMock()
        secrets = MagicMock()
        secrets.get_secret_value.return_value = {
            "SecretString": json.dumps({"webhook_secret": SINCH_SECRET})
        }
        cli.return_value = secrets
        import handler as mod  # noqa: PLC0415
        mod._webhook_secret_cache.update({"loaded": True, "value": SINCH_SECRET})
        yield mod

    sys.path.remove(path)


class TestRcsDlrIngress:
    def test_unsigned_post_is_rejected_401(self, rcs_handler):
        body = json.dumps({"message_delivery_report": {"message_id": "m1",
                                                       "status": "DELIVERED"}})
        with patch.object(rcs_handler, "_process_delivery") as proc:
            resp = rcs_handler.handler(_sinch_event(body, sign=False), _Ctx())
        assert resp["statusCode"] == 401
        proc.assert_not_called()

    def test_tampered_post_is_rejected_401(self, rcs_handler):
        body = json.dumps({"message_delivery_report": {"message_id": "m1"}})
        with patch.object(rcs_handler, "_process_delivery") as proc:
            resp = rcs_handler.handler(_sinch_event(body, tamper=True), _Ctx())
        assert resp["statusCode"] == 401
        proc.assert_not_called()

    def test_forged_inbound_cannot_reach_the_message_store(self, rcs_handler):
        """The exploit path: forged MESSAGE_INBOUND -> MessagesTable -> rcs-send."""
        body = json.dumps({
            "message": {
                "contact_message": {"text_message": {"text": "forged"}},
                "channel_identity": {"channel": "RCS", "identity": "+919000000000"},
            }
        })
        with patch.object(rcs_handler, "_process_inbound") as proc:
            resp = rcs_handler.handler(_sinch_event(body, sign=False), _Ctx())
        assert resp["statusCode"] == 401
        proc.assert_not_called()

    def test_valid_signature_is_processed(self, rcs_handler):
        body = json.dumps({"message_delivery_report": {"message_id": "m1",
                                                       "status": "DELIVERED"}})
        with patch.object(rcs_handler, "_process_delivery") as proc:
            resp = rcs_handler.handler(_sinch_event(body), _Ctx())
        assert resp["statusCode"] == 200
        proc.assert_called_once()

    def test_missing_secret_returns_retryable_503_and_does_nothing(self, rcs_handler):
        """No secret means unverifiable. 5xx so Sinch retries and receipts survive."""
        rcs_handler._webhook_secret_cache.update({"loaded": True, "value": ""})
        body = json.dumps({"message_delivery_report": {"message_id": "m1"}})
        with patch.object(rcs_handler, "_process_delivery") as proc:
            resp = rcs_handler.handler(_sinch_event(body), _Ctx())
        assert resp["statusCode"] == 503
        proc.assert_not_called()

    def test_health_get_still_answers(self, rcs_handler):
        resp = rcs_handler.handler(_sinch_event("", sign=False, method="GET"), _Ctx())
        assert resp["statusCode"] == 200

    def test_secret_is_not_read_at_import_time(self, rcs_handler):
        """A module-scope read would freeze the value into every warm sandbox.

        Checked structurally: every `get_secret_value` call must live inside a
        function body, never at module level where import executes it.
        """
        import ast  # noqa: PLC0415

        src = (ROOT / "amplify" / "functions" / "messaging" / "rcs-dlr"
               / "handler.py").read_text()
        tree = ast.parse(src)

        inside_function = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    inside_function.add(id(child))

        module_level_reads = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get_secret_value"
            and id(node) not in inside_function
        ]
        assert not module_level_reads, "secret is read at import time"


# ── inbound-whatsapp entry point ────────────────────────────────────────────

class TestInboundWhatsappIngress:
    """The guard is asserted on the source and the helper contract.

    The handler itself is a ~7k-line module whose import pulls in sub-modules and
    AWS clients; these assertions target the boundary without standing that up.
    """

    SRC = (ROOT / "amplify" / "functions" / "messaging"
           / "inbound-whatsapp-handler" / "handler.py")

    def test_handler_verifies_http_events(self):
        src = self.SRC.read_text()
        assert "meta_signature.is_http_request(event)" in src
        assert "meta_signature.verify(event, _meta_app_secrets())" in src

    def test_verification_precedes_the_create_invoice_branch(self):
        """Order matters: the branch must not run before the caller is trusted."""
        src = self.SRC.read_text()
        guard = src.index("meta_signature.verify(event, _meta_app_secrets())")
        invoice = src.index("if event.get('action') == 'create_invoice':")
        assert guard < invoice

    def test_create_invoice_is_internal_invocation_only(self):
        src = self.SRC.read_text()
        branch = src.split("if event.get('action') == 'create_invoice':", 1)[1][:600]
        assert "_via_http" in branch
        assert "internal_invocation_only" in branch

    def test_both_waba_app_secrets_are_candidates(self):
        src = self.SRC.read_text()
        assert "app_secret_waba2" in src
        assert "def _meta_app_secrets()" in src

    def test_internal_sns_shaped_invoke_needs_no_signature(self):
        """The verified production path must keep working untouched."""
        internal = {"Records": [{"Sns": {"Message": "{}", "MessageId": "x"}}]}
        assert meta_signature.is_http_request(internal) is False

    def test_rejection_is_401_not_a_silent_200(self):
        src = self.SRC.read_text()
        assert "'statusCode': 401" in src
        assert "invalid_signature" in src
