"""The verification email: right sender, right configuration set, tokens that match the site.

The drift test is the one that earns its keep. Email cannot reference CSS custom properties, so
the page's colours have to be resolved to literals and inlined - which is exactly how
`design-tokens.ts` once ended up saying `#111827` while `tokens.css` said `#1a1a1a`, leaving
primary text a retired blue-tinted grey in 14 files. `scripts/check_design_drift.py` exists
because of that. This file stops this module becoming the next disagreeing copy.
"""

import os
import re
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'amplify', 'functions', 'shared'))

from lambda_utils.comms import verification_email as ve  # noqa: E402

CODE = '481502'
TOKENS_CSS = os.path.join(REPO, 'src', 'styles', 'tokens.css')


class FakeSes:
    """Records the one call, and can be told to fail."""

    def __init__(self, *, fail: Exception = None, message_id: str = 'ses-msg-1') -> None:
        self.calls = []
        self._fail = fail
        self._message_id = message_id

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail:
            raise self._fail
        return {'MessageId': self._message_id}


def _css_token(name: str) -> str:
    """Read one custom property out of tokens.css, which is the single source of truth."""
    with open(TOKENS_CSS, encoding='utf-8') as handle:
        source = handle.read()
    match = re.search(rf'^\s*--{re.escape(name)}:\s*([^;]+);', source, re.MULTILINE)
    assert match, f'--{name} not found in tokens.css'
    return match.group(1).strip()


# ── design tokens must match the site ──────────────────────────────────────────

@pytest.mark.parametrize('constant,token', [
    ('COLOR_TEXT', 'text'),
    ('COLOR_TEXT_MUTED', 'text-muted'),
    ('COLOR_BORDER', 'border'),
    ('COLOR_SURFACE', 'surface'),
    ('COLOR_BG_SECONDARY', 'bg-secondary'),
    ('COLOR_ACCENT', 'accent'),
    ('COLOR_LIME', 'lime'),
])
def test_every_inlined_colour_matches_tokens_css(constant, token):
    assert getattr(ve, constant).lower() == _css_token(token).lower(), (
        f'{constant} has drifted from --{token} in tokens.css; change tokens.css first'
    )


def test_the_html_uses_the_named_constants_not_loose_hex():
    """Any hex literal in the output must be one of the declared tokens, so a hand-typed
    colour cannot slip in unnoticed."""
    body = ve.html_body(CODE)
    declared = {getattr(ve, name).lower() for name in dir(ve)
                if name.startswith('COLOR_')}
    for found in {h.lower() for h in re.findall(r'#[0-9a-fA-F]{6}\b', body)}:
        assert found in declared, f'{found} is not a declared design token'


# ── sender and configuration set ───────────────────────────────────────────────

def test_the_sender_is_the_verified_identity():
    assert ve.SENDER_ADDRESS == 'one@wecare.digital'


def test_the_configuration_set_is_attached():
    """It exists on the account and was previously wired to nothing, so a bounce on a
    verification email produced no event at all."""
    client = FakeSes()
    ve.send(client, to_address='asha@example.com', code=CODE)
    assert client.calls[0]['ConfigurationSetName'] == 'wecare-digital'


def test_the_from_header_carries_the_display_name():
    client = FakeSes()
    ve.send(client, to_address='asha@example.com', code=CODE)
    assert client.calls[0]['FromEmailAddress'] == 'WECARE.DIGITAL <one@wecare.digital>'


def test_the_from_address_is_not_caller_supplied():
    """Under DMARC p=reject an unaligned From hard-bounces, so it is a deployment decision."""
    import inspect
    signature = inspect.signature(ve.send)
    assert 'from_address' not in signature.parameters
    assert 'sender' not in signature.parameters


def test_send_returns_the_ses_message_id():
    client = FakeSes(message_id='abc-123')
    assert ve.send(client, to_address='a@b.com', code=CODE) == 'abc-123'


def test_only_the_one_recipient_is_addressed():
    client = FakeSes()
    ve.send(client, to_address='asha@example.com', code=CODE)
    assert client.calls[0]['Destination'] == {'ToAddresses': ['asha@example.com']}
    assert 'CcAddresses' not in client.calls[0]['Destination']
    assert 'BccAddresses' not in client.calls[0]['Destination']


# ── content ────────────────────────────────────────────────────────────────────

def test_the_code_is_absent_from_the_subject():
    """A subject line is visible on a lock screen and in every notification preview."""
    assert CODE not in ve.subject_line()
    assert ve.subject_line() == 'Verify your email'


def test_both_alternatives_are_sent():
    """Some corporate gateways strip HTML, and a blank verification email is
    indistinguishable from one that never arrived."""
    body = ve.build_message(CODE)['Simple']['Body']
    assert CODE in body['Text']['Data']
    assert CODE in body['Html']['Data']
    assert body['Text']['Charset'] == body['Html']['Charset'] == 'UTF-8'


def test_the_email_contains_no_link():
    """A 'click here to verify' URL is a phishing template, and it would break the property
    that the code only works in the tab that asked for it."""
    for rendered in (ve.html_body(CODE), ve.text_body(CODE)):
        assert 'http://' not in rendered
        assert 'https://' not in rendered
        assert '<a ' not in rendered.lower()


def test_the_expiry_is_stated_in_both_parts():
    assert '10 minutes' in ve.html_body(CODE, ttl_minutes=10)
    assert '10 minutes' in ve.text_body(CODE, ttl_minutes=10)
    assert '5 minutes' in ve.html_body(CODE, ttl_minutes=5)


def test_a_first_name_is_used_when_supplied_and_omitted_otherwise():
    assert 'Hi Asha,' in ve.html_body(CODE, first_name='Asha')
    assert 'Hi Asha,' in ve.text_body(CODE, first_name='Asha')
    assert 'Hi,' in ve.html_body(CODE)
    assert 'Hi,' in ve.text_body(CODE)


def test_a_name_is_escaped_into_the_html():
    """The name is customer-supplied and reaches an HTML document."""
    body = ve.html_body(CODE, first_name='<script>alert(1)</script>')
    assert '<script>' not in body
    assert '&lt;script&gt;' in body


def test_the_code_is_escaped_too():
    """A no-op for digits today, which is precisely why it is easy to omit and be wrong later."""
    body = ve.html_body('<b>')
    assert '<b>' not in body.replace('<body', '').replace('</body', '')
    assert '&lt;b&gt;' in body


def test_the_support_channels_are_present():
    for rendered in (ve.html_body(CODE), ve.text_body(CODE)):
        assert 'one@wecare.digital' in rendered
        assert '+91 93309 94400' in rendered


def test_the_anti_social_engineering_line_is_present():
    for rendered in (ve.html_body(CODE), ve.text_body(CODE)):
        assert 'never ask you for this code' in rendered


def test_a_preheader_exists_so_the_inbox_preview_is_not_markup():
    body = ve.html_body(CODE)
    assert 'display:none' in body
    assert 'verification code' in body.lower()


def test_the_html_is_table_based_for_outlook():
    """Outlook renders with Word's engine, which supports neither flexbox nor grid."""
    body = ve.html_body(CODE)
    assert '<table' in body
    assert 'display:flex' not in body
    assert 'display:grid' not in body


def test_no_order_or_payment_data_can_appear():
    """The email is for verification only. Nothing about an order belongs in it."""
    import inspect
    for fn in (ve.html_body, ve.text_body):
        params = set(inspect.signature(fn).parameters)
        assert params <= {'code', 'first_name', 'ttl_minutes'}, (
            f'{fn.__name__} accepts more than a code, a name and a TTL: {params}'
        )


# ── failure handling ───────────────────────────────────────────────────────────

def test_an_ses_failure_raises_without_echoing_the_address_or_code():
    client = FakeSes(fail=RuntimeError('Email address is not verified: asha@example.com'))
    with pytest.raises(ve.VerificationEmailFailed) as caught:
        ve.send(client, to_address='asha@example.com', code=CODE)

    message = str(caught.value)
    assert 'asha@example.com' not in message
    assert CODE not in message
    assert 'RuntimeError' in message


@pytest.mark.parametrize('kwargs', [
    {'to_address': '', 'code': CODE},
    {'to_address': 'a@b.com', 'code': ''},
])
def test_missing_arguments_are_refused_before_any_send(kwargs):
    client = FakeSes()
    with pytest.raises(ValueError):
        ve.send(client, **kwargs)
    assert client.calls == []


# ── nothing sensitive in a log expression ──────────────────────────────────────

def test_no_log_call_references_the_code_or_the_address():
    """CodeQL tracks taint across function boundaries; reducing a secret to a bool does not
    launder it. So the check is that the names never appear in a logging expression at all."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(ve))
    forbidden = {'code', 'to_address', 'safe_code', 'first_name'}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not ast.unparse(node.func).startswith('logger.'):
            continue
        rendered = ast.unparse(node)
        for name in forbidden:
            assert not re.search(rf'\b{name}\b', rendered), \
                f'log call references {name!r}: {rendered}'
