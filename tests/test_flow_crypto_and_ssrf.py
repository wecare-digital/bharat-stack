"""Flow data-exchange encrypt/decrypt round-trip (test RSA key) + link-preview SSRF guard."""
import os
import sys
import json
import base64
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


@pytest.fixture()
def handler_mod():
    # Multiple lambdas share the module name `handler`; force-resolve the
    # business-api one (conftest clears the cached module between tests).
    biz = os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api')
    sys.path.insert(0, biz)
    sys.modules.pop('handler', None)
    with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
        with patch('boto3.resource'), patch('boto3.client'):
            import handler as h
            return h


def _meta_encrypt(payload: dict, public_key):
    """Simulate how Meta encrypts a Flow data-exchange request to us."""
    aes_key = os.urandom(16)            # AES-128
    iv = os.urandom(16)
    encryptor = Cipher(algorithms.AES(aes_key), modes.GCM(iv)).encryptor()
    ct = encryptor.update(json.dumps(payload).encode()) + encryptor.finalize()
    flow_data = ct + encryptor.tag      # handler splits last 16 bytes as tag
    enc_aes = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return (
        base64.b64encode(flow_data).decode(),
        base64.b64encode(enc_aes).decode(),
        base64.b64encode(iv).decode(),
        aes_key, iv,
    )


class TestFlowCrypto:
    def test_decrypt_roundtrip(self, handler_mod):
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        payload = {'action': 'data_exchange', 'screen': 'WELCOME', 'data': {'x': 1}}
        fd, ek, iv_b64, aes_key, iv = _meta_encrypt(payload, priv.public_key())
        with patch.object(handler_mod, '_get_flow_private_key', return_value=priv):
            decrypted, got_key, got_iv = handler_mod._decrypt_flow_request(fd, ek, iv_b64)
        assert decrypted == payload
        assert got_key == aes_key
        assert got_iv == iv

    def test_encrypt_response_is_decryptable(self, handler_mod):
        aes_key = os.urandom(16)
        iv = os.urandom(16)
        resp = {'screen': 'SUCCESS', 'data': {'ok': True}}
        b64 = handler_mod._encrypt_flow_response(resp, aes_key, iv)
        blob = base64.b64decode(b64)
        ct, tag = blob[:-16], blob[-16:]
        flipped = bytes(b ^ 0xFF for b in iv)  # handler flips IV for the response
        dec = Cipher(algorithms.AES(aes_key), modes.GCM(flipped, tag)).decryptor()
        out = dec.update(ct) + dec.finalize()
        assert json.loads(out.decode()) == resp

    def test_decrypt_without_key_raises(self, handler_mod):
        with patch.object(handler_mod, '_get_flow_private_key', return_value=None):
            with pytest.raises(ValueError):
                handler_mod._decrypt_flow_request('AA==', 'AA==', 'AA==')


class TestLinkPreviewSSRF:
    def test_blocks_localhost(self, handler_mod):
        assert handler_mod._is_ssrf_safe_url('http://localhost/x') is False

    def test_blocks_loopback_ip(self, handler_mod):
        assert handler_mod._is_ssrf_safe_url('http://127.0.0.1/x') is False

    def test_blocks_metadata_ip(self, handler_mod):
        assert handler_mod._is_ssrf_safe_url('http://169.254.169.254/latest/meta-data/') is False

    def test_blocks_private_ip(self, handler_mod):
        assert handler_mod._is_ssrf_safe_url('http://10.0.0.5/x') is False
        assert handler_mod._is_ssrf_safe_url('http://192.168.1.1/x') is False

    def test_blocks_non_http_scheme(self, handler_mod):
        assert handler_mod._is_ssrf_safe_url('ftp://example.com/x') is False
        assert handler_mod._is_ssrf_safe_url('file:///etc/passwd') is False

    def test_allows_public_host(self, handler_mod):
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 0))]):
            assert handler_mod._is_ssrf_safe_url('https://example.com/page') is True

    def test_check_link_preview_rejects_internal(self, handler_mod):
        res = handler_mod._check_link_preview('http://169.254.169.254/latest/meta-data/')
        assert res['statusCode'] == 400

    def test_check_link_preview_rejects_non_http(self, handler_mod):
        res = handler_mod._check_link_preview('file:///etc/passwd')
        assert res['statusCode'] == 400
