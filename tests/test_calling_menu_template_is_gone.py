"""The whatsapp-calling half of the menu wipe, pinned.

`tests/test_menus_are_deleted.py` covers the inbound handler. This file covers the
other Lambda the wipe touched, because nothing else does: `tests/test_calling.py`
patches `_send_call_whatsapp_notification` wholesale and never inspects its
arguments, so its pass count was identical before and after the change.

Two LIVE production send paths were rewritten here - the post-call SIP follow-up and
the call-connect notification. Both used to send the `wd_menu` WhatsApp template,
which the owner DELETED at Meta, so every send referencing it fails now. Both now
send `MENU_PLACEHOLDER_TEXT` as a plain text message.

What would otherwise break silently, and is therefore asserted below:

* `wd_menu` coming back, in either path;
* `_send_menu_placeholder_text` being switched to `_send_via_aws`, which would break
  the auto-thumbs-up: `_react_thumbs_up` requires the wamid to belong to the same
  `meta_id` that produced it, and only `_meta_api_call` guarantees that;
* either call site quietly dropping the send, which is the silence the wipe forbids;
* the placeholder copy drifting between the two Lambdas. They share no module, so
  each holds its own module-level copy of the string and a divergence is invisible
  at runtime - one WABA would say something different from the other;
* the IVR button menu, which is NOT a wiped menu and must not be collateral.

Both handlers are loaded by explicit file path under unique module names, with
`boto3.resource` and `boto3.client` patched: every Lambda entry point in this repo is
called `handler.py` and `conftest.py` clears `sys.modules['handler']` between tests,
so a plain `import handler` resolves to whichever one is first on the path.
"""
import ast
import importlib.util
import os
import sys
from unittest.mock import patch

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_SHARED_DIR = os.path.join(_ROOT, 'amplify', 'functions', 'shared')
_CALLING_DIR = os.path.join(_ROOT, 'amplify', 'functions', 'messaging',
                            'whatsapp-calling')
_INBOUND_DIR = os.path.join(_ROOT, 'amplify', 'functions', 'messaging',
                            'inbound-whatsapp-handler')
CALLING_HANDLER_PATH = os.path.join(_CALLING_DIR, 'handler.py')
INBOUND_HANDLER_PATH = os.path.join(_INBOUND_DIR, 'handler.py')

# The deleted WhatsApp template, and the sender that built it.
DELETED_TEMPLATE = 'wd_menu'

# Not menus, and not deleted. These three are the call-side behaviours the wipe must
# not touch, so they are checked as a scope guard. The five IVR BUTTON MENU names
# that used to sit in this list moved to IVR_DELETED_NAMES below: phase 1 pinned
# them as out of scope, phase 2 deleted them on 2026-10-02.
IVR_KEEP_NAMES = [
    '_react_thumbs_up',
    '_is_auto_thumb_reaction_enabled',
    '_is_postcall_wa_enabled',
]

# The IVR button menu, deleted 2026-10-02. The audio greeting survives as a plain
# constant, which is why the call lifecycle is unaffected.
IVR_DELETED_NAMES = [
    '_SHARED_IVR_MENU',
    'IVR_MENUS',
    'IVR_DEFAULT_MENU',
    'IVR_RESPONSES',
    '_get_ivr_menu',
]

# The two live paths the wipe rewrote.
SEND_SITES = ['_handle_post_call_sip', '_send_call_whatsapp_notification']


def _load(path: str, module_name: str, extra_paths=()):
    for entry in (_SHARED_DIR,) + tuple(extra_paths):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    with patch('boto3.resource'), patch('boto3.client'):
        spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def calling_source():
    with open(CALLING_HANDLER_PATH, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def calling_tree(calling_source):
    return ast.parse(calling_source)


@pytest.fixture(scope='module')
def calling():
    return _load(CALLING_HANDLER_PATH, 'calling_menu_wipe', (_CALLING_DIR,))


@pytest.fixture(scope='module')
def inbound():
    return _load(INBOUND_HANDLER_PATH, 'inbound_menu_wipe',
                 (_INBOUND_DIR, os.path.join(_INBOUND_DIR, 'modules')))


def _function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'{name} not found')


def _called_names(node) -> set:
    return {call.func.id for call in ast.walk(node)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}


class TestTheDeletedTemplateIsGone:
    def test_the_template_name_appears_nowhere(self, calling_source):
        """The template no longer exists at Meta, so any reference is a dead send."""
        assert DELETED_TEMPLATE not in calling_source, \
            f'{DELETED_TEMPLATE} is back - that template was deleted at Meta'

    def test_the_menu_sender_is_gone(self, calling):
        assert not hasattr(calling, '_send_ivr_menu'), \
            '_send_ivr_menu is back in whatsapp-calling'


class TestThePlaceholderCopyIsShared:
    def test_both_lambdas_hold_the_same_string(self, calling, inbound):
        """Byte-identical, not merely similar.

        The two Lambdas share no module, so each carries its own module-level copy.
        A drift would make one WABA answer differently from the other, and nothing
        at runtime would notice.
        """
        assert calling.MENU_PLACEHOLDER_TEXT == inbound.MENU_PLACEHOLDER_TEXT


class TestThePlaceholderSendStaysOnMetaApi:
    def test_it_calls_meta_api_and_not_the_aws_path(self, calling_tree):
        """`_send_via_aws` would return a wamid from another conversation, and
        `_react_thumbs_up` requires the id to belong to the same meta_id."""
        called = _called_names(_function(calling_tree, '_send_menu_placeholder_text'))
        assert '_meta_api_call' in called
        assert '_send_via_aws' not in called, \
            'the returned wamid would no longer belong to meta_id - see _react_thumbs_up'

    def test_the_payload_is_a_text_message(self, calling_tree):
        """A template send is what the wipe removed; this must stay a plain text."""
        fn = _function(calling_tree, '_send_menu_placeholder_text')
        types = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (isinstance(key, ast.Constant) and key.value == 'type'
                            and isinstance(value, ast.Constant)):
                        types.append(value.value)
        assert types == ['text'], f'expected one text payload, found {types}'

    @pytest.mark.parametrize('name', SEND_SITES)
    def test_the_live_path_still_sends(self, calling_tree, name):
        assert '_send_menu_placeholder_text' in _called_names(_function(calling_tree, name)), \
            f'{name} sends nothing - that is the silence the wipe forbids'


class TestTheCallSideBehavioursAreNotCollateral:
    @pytest.mark.parametrize('name', IVR_KEEP_NAMES)
    def test_the_symbol_survives(self, calling, name):
        assert hasattr(calling, name), f'{name} was deleted - it is not a wiped menu'


class TestTheIvrButtonMenuIsGone:
    """Phase 2, 2026-10-02. The owner's instruction was that every WhatsApp menu
    goes, including the IVR button menu this file previously protected."""

    @pytest.mark.parametrize('name', IVR_DELETED_NAMES)
    def test_the_symbol_is_deleted(self, calling, name):
        assert not hasattr(calling, name), f'{name} is back - every menu was deleted'

    def test_the_audio_greeting_survives_as_a_constant(self, calling):
        """The greeting the Polly path speaks used to be read from the menu dict. It
        is a module constant now, so a caller still hears words."""
        assert isinstance(calling.IVR_GREETING_TEXT, str)
        assert calling.IVR_GREETING_TEXT.strip()

    def test_the_sms_and_audio_constants_are_untouched(self, calling):
        """IVR_SMS_CONTENT / IVR_SMS_DLT_TEMPLATE_KEY / DEFAULT_IVR_URL are an SMS
        body, a DLT key and an audio URL. None is a menu; all three must stay."""
        assert calling.IVR_SMS_CONTENT.strip()
        assert calling.IVR_SMS_DLT_TEMPLATE_KEY == 'ivr-default'
        assert calling.DEFAULT_IVR_URL.startswith('https://')
