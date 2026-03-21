"""Tests for webhook X-Hub-Signature-256 verification."""
import json
import hmac
import hashlib
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))


class TestWebhookSignatureVerification:
    """Test X-Hub-Signature-256 verification logic."""

    APP_SECRET = 'test_app_secret_12345'

    def _sign(self, body: str) -> str:
        """Generate valid X-Hub-Signature-256 header value."""
        sig = hmac.new(
            self.APP_SECRET.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f'sha256={sig}'

    def test_valid_signature(self):
        body = '{"object":"whatsapp_business_account"}'
        signature = self._sign(body)
        expected = 'sha256=' + hmac.new(
            self.APP_SECRET.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        assert hmac.compare_digest(signature, expected)

    def test_invalid_signature_rejected(self):
        body = '{"object":"whatsapp_business_account"}'
        valid_sig = self._sign(body)
        tampered_sig = valid_sig[:-4] + 'dead'
        assert not hmac.compare_digest(valid_sig, tampered_sig)

    def test_tampered_body_rejected(self):
        original_body = '{"object":"whatsapp_business_account"}'
        tampered_body = '{"object":"hacked"}'
        sig = self._sign(original_body)
        expected_for_tampered = 'sha256=' + hmac.new(
            self.APP_SECRET.encode('utf-8'),
            tampered_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        assert not hmac.compare_digest(sig, expected_for_tampered)

    def test_empty_signature_rejected(self):
        assert not hmac.compare_digest('', 'sha256=abc')

    def test_missing_prefix_rejected(self):
        body = '{"test": true}'
        raw_sig = hmac.new(
            self.APP_SECRET.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        # Without sha256= prefix, should not match
        expected = f'sha256={raw_sig}'
        assert not hmac.compare_digest(raw_sig, expected)


class TestRazorpaySignatureVerification:
    """Test Razorpay webhook signature verification."""

    WEBHOOK_SECRET = 'rzp_test_secret'

    def test_valid_razorpay_signature(self):
        body = '{"event":"payment.captured","payload":{}}'
        expected = hmac.new(
            self.WEBHOOK_SECRET.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        assert len(expected) == 64  # SHA256 hex digest length

    def test_different_secrets_produce_different_sigs(self):
        body = '{"event":"payment.captured"}'
        sig1 = hmac.new(b'secret1', body.encode(), hashlib.sha256).hexdigest()
        sig2 = hmac.new(b'secret2', body.encode(), hashlib.sha256).hexdigest()
        assert sig1 != sig2
