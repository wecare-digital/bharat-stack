"""A receipt link must expire, because a receipt carries a name, an address and a GSTIN.

`invoice-engine` currently writes receipts under the public prefix and returns
`https://{CDN_DOMAIN}/{key}`, which is fetchable forever without authentication. The key is
`wecare-digital-{reference_id}.png` and a reference is 70 bits of CSPRNG, so it is unlisted rather
than enumerable — but unlisted is not private once a URL is forwarded.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))

from lambda_utils import receipt_links as rl  # noqa: E402

BUCKET = 'wecare-digital-get'
KEY = 'o/stack/invoices/wecare-digital-WD-PAY-ABCDEFGHJKMNPQ.pdf'

SIGNED = (f'https://{BUCKET}.s3.amazonaws.com/{KEY}'
          '?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA%2F20260930'
          '&X-Amz-Expires=86400&X-Amz-Signature=deadbeef')
PERMANENT = f'https://wecare.digital/get/{KEY}'


class FakeS3:
    def __init__(self, *, fail=False):
        self.calls = []
        self._fail = fail

    def generate_presigned_url(self, operation, Params=None, ExpiresIn=None):
        self.calls.append({'operation': operation, 'Params': Params,
                           'ExpiresIn': ExpiresIn})
        if self._fail:
            raise RuntimeError('EndpointConnectionError')
        return SIGNED


# ── signing ────────────────────────────────────────────────────────────────────

def test_a_signed_url_is_produced_for_the_right_object():
    client = FakeS3()
    url = rl.signed_url(client, bucket=BUCKET, key=KEY)

    assert url == SIGNED
    call = client.calls[0]
    assert call['operation'] == 'get_object'
    assert call['Params']['Bucket'] == BUCKET
    assert call['Params']['Key'] == KEY


def test_the_default_ttl_is_applied():
    client = FakeS3()
    rl.signed_url(client, bucket=BUCKET, key=KEY)
    assert client.calls[0]['ExpiresIn'] == rl.DEFAULT_TTL_SECONDS


def test_an_explicit_ttl_is_honoured():
    client = FakeS3()
    rl.signed_url(client, bucket=BUCKET, key=KEY, ttl_seconds=900)
    assert client.calls[0]['ExpiresIn'] == 900


def test_a_filename_is_signed_into_the_disposition():
    """Part of the signature, so it cannot be tampered with in transit."""
    client = FakeS3()
    rl.signed_url(client, bucket=BUCKET, key=KEY, filename='receipt-7KMP4X9Q2DTR.pdf')
    disposition = client.calls[0]['Params']['ResponseContentDisposition']
    assert 'receipt-7KMP4X9Q2DTR.pdf' in disposition
    assert disposition.startswith('attachment;')


def test_a_ttl_beyond_the_ceiling_is_refused_not_clamped():
    """Clamping hides the caller's intent. They asked for something that defeats signing."""
    client = FakeS3()
    with pytest.raises(ValueError):
        rl.signed_url(client, bucket=BUCKET, key=KEY,
                      ttl_seconds=rl.MAX_TTL_SECONDS + 1)
    assert client.calls == []


@pytest.mark.parametrize('ttl', [0, -1, -86400])
def test_a_non_positive_ttl_is_refused(ttl):
    with pytest.raises(ValueError):
        rl.signed_url(FakeS3(), bucket=BUCKET, key=KEY, ttl_seconds=ttl)


@pytest.mark.parametrize('kwargs', [
    {'bucket': '', 'key': KEY},
    {'bucket': BUCKET, 'key': ''},
])
def test_missing_arguments_are_refused(kwargs):
    with pytest.raises(ValueError):
        rl.signed_url(FakeS3(), **kwargs)


def test_a_signing_failure_raises_rather_than_falling_back_to_a_public_url():
    """A receipt that cannot be delivered securely is a support ticket. One delivered over a
    permanent public URL is a disclosure, and the second is worse."""
    with pytest.raises(rl.ReceiptLinkUnavailable):
        rl.signed_url(FakeS3(fail=True), bucket=BUCKET, key=KEY)


def test_the_url_never_reaches_a_log():
    """The URL itself carries a grant."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(rl))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not ast.unparse(node.func).startswith('logger.'):
            continue
        rendered = ast.unparse(node)
        for forbidden in ('url', 'key', 'params'):
            assert forbidden not in rendered.lower(), \
                f'log call references {forbidden!r}: {rendered}'


# ── detecting the thing we are replacing ───────────────────────────────────────

def test_the_current_invoice_engine_url_shape_is_recognised_as_permanent():
    assert rl.is_permanent_public_url(PERMANENT)


def test_a_signed_url_is_not_flagged():
    assert not rl.is_permanent_public_url(SIGNED)


@pytest.mark.parametrize('url', [
    'https://example.com/a.pdf?Signature=abc&Expires=123',
    'https://example.com/a.pdf?X-Amz-Signature=abc',
    'https://example.com/a.pdf?X-Amz-Credential=abc',
])
def test_other_signed_shapes_are_not_flagged(url):
    """Detects the absence of a signature rather than the presence of a domain, so it stays
    correct if the CDN host changes."""
    assert not rl.is_permanent_public_url(url)


@pytest.mark.parametrize('value', ['', None, 'not-a-url', 's3://bucket/key', 123])
def test_non_urls_are_not_flagged(value):
    assert not rl.is_permanent_public_url(value)


def test_assert_not_permanent_passes_a_signed_url():
    assert rl.assert_not_permanent(SIGNED) == SIGNED


def test_assert_not_permanent_refuses_the_current_public_shape():
    """The boundary check. The failure mode of getting this wrong is silent: a permanent URL
    works perfectly, forever, for everyone."""
    with pytest.raises(rl.ReceiptLinkUnavailable):
        rl.assert_not_permanent(PERMANENT)


def test_the_ceiling_is_a_week_at_most():
    assert rl.MAX_TTL_SECONDS <= 7 * 24 * 60 * 60
    assert rl.DEFAULT_TTL_SECONDS <= rl.MAX_TTL_SECONDS


def test_an_order_number_is_not_usable_as_a_link():
    """The obvious shortcut, and wrong twice: the number is printed on the receipt and read aloud
    to support, and 12 characters over 30 symbols is guessable at scale if it is the only guard."""
    import inspect
    signature = inspect.signature(rl.signed_url)
    assert 'order_number' not in signature.parameters
    assert 'bucket' in signature.parameters and 'key' in signature.parameters
