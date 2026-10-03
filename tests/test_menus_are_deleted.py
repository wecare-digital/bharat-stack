"""Every WhatsApp menu is deleted from the inbound handler, and nothing goes silent.

The owner's instruction on 2026-10-02 was to delete the menu entirely and build a
fresh one later. A previous change tried to do it by emptying
`DEFAULT_ONE_MENU['sections']`, which was worse than leaving it alone: the
interactive-list sender short-circuited on an empty `sections`, so a greeting
produced TOTAL SILENCE while all the dispatch machinery stayed behind.

So this file pins both halves of the real deletion:

* the menu configs, their getters, the row-id dispatch table and the
  interactive-list sender are **gone**, not emptied; and
* the three trigger paths that used to open a menu - greeting keywords, the
  button/ice-breaker texts and the self-service keywords - now reach a plain-text
  placeholder. The trigger SETS deliberately survive: they are live on Meta's side
  as QR prefills, ice breakers and slash commands, and you cannot answer a trigger
  word without a trigger-word set.

A tap on a list row still sitting in a customer's chat history gets the placeholder
too. That is the accepted cost of deleting the dispatch table rather than hiding it.

The module is loaded by explicit file path under a unique name, the same as
`test_own_prefill_triggers_menu.py`: every Lambda entry point in this repo is called
`handler.py` and `conftest.py` clears `sys.modules['handler']` between tests, so a
plain `import handler` resolves to whichever one is first on the path.
"""
import ast
import importlib.util
import os
import re
import sys

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_INBOUND_DIR = os.path.join(_ROOT, 'amplify', 'functions', 'messaging',
                            'inbound-whatsapp-handler')
HANDLER_PATH = os.path.join(_INBOUND_DIR, 'handler.py')
AI_HANDLER_PATH = os.path.join(_ROOT, 'amplify', 'functions', 'ai',
                               'ai-generate-response', 'handler.py')

# The agreed stand-in copy. Asserted character for character: it is customer-facing,
# and it is the only thing a greeting produces now.
PLACEHOLDER = "We're refreshing our menu - please type *menu* and we'll help you."

# Menu configs, their getters, and the interactive-list sender. None of these may
# come back as a module attribute.
DELETED_NAMES = [
    'DEFAULT_ONE_MENU',
    'DEFAULT_MAIN_MENU',
    'DEFAULT_SELFSERVICE_MENU',
    'DEFAULT_BHARAT_STACK_MENU',
    'DEFAULT_LANGUAGE_PICKER',
    'REGION_LANGUAGE_LISTS',
    '_get_welcome_config',
    '_get_selfservice_menu',
    '_get_bharat_stack_menu',
    '_get_language_picker_config',
    '_get_region_language_list',
    '_send_interactive_list',
]

# The three trigger paths that used to open a menu. Each is a function-local set, so
# it is checked against the source rather than imported.
TRIGGER_SETS = ['HI_KEYWORDS', 'BUTTON_MENU_TRIGGERS', 'SELFSERVICE_KEYWORDS']


@pytest.fixture(scope='module')
def handler_source():
    with open(HANDLER_PATH, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def handler_tree(handler_source):
    return ast.parse(handler_source)


@pytest.fixture(scope='module')
def wa():
    """The inbound handler, loaded under a UNIQUE module name - see the docstring."""
    for path in (os.path.join(_ROOT, 'amplify', 'functions', 'shared'),
                 _INBOUND_DIR,
                 os.path.join(_INBOUND_DIR, 'modules')):
        if path not in sys.path:
            sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location('inbound_wa_menus_deleted', HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules['inbound_wa_menus_deleted'] = module
    spec.loader.exec_module(module)
    return module


def _nested_literal(source: str, name: str):
    """literal_eval a `NAME = {...}` assignment at ANY nesting depth."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f'{name} not found in source')


def _function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'{name} not found')


def _trigger_branch(source: str, name: str) -> str:
    """The source from a trigger set's ASSIGNMENT to the first `return` after it.

    That slice is the whole branch: the set literal, the guard, the logging and the
    send. Anchored on the assignment rather than any mention of the name, because
    two comments elsewhere in the file reference HI_KEYWORDS by name.
    """
    lines = source.splitlines()
    starts = [i for i, line in enumerate(lines)
              if re.match(r'\s*' + name + r'\s*=', line)]
    assert len(starts) == 1, f'expected exactly one {name} assignment, found {len(starts)}'
    start = starts[0]
    for i in range(start, len(lines)):
        if re.match(r'\s*return\b', lines[i]):
            return '\n'.join(lines[start:i + 1])
    raise AssertionError(f'no return found after the {name} assignment')


class TestEveryMenuIsGone:
    @pytest.mark.parametrize('name', DELETED_NAMES)
    def test_the_module_no_longer_defines_it(self, wa, name):
        assert not hasattr(wa, name), f'{name} is back in the inbound handler'

    def test_the_row_id_dispatch_table_is_gone(self, handler_tree):
        """MENU_TO_KEYWORD was function-local, so an attribute check cannot see it.

        Walked rather than grepped: the table used to sit inside _handle_list_reply.
        """
        for node in ast.walk(handler_tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assert target.id != 'MENU_TO_KEYWORD', \
                            f'MENU_TO_KEYWORD is back at line {node.lineno}'

    def test_nothing_calls_the_interactive_list_sender(self, handler_tree):
        """A surviving call would be a NameError at runtime, not a dead branch."""
        for node in ast.walk(handler_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != '_send_interactive_list', \
                    f'interactive list send survives at line {node.lineno}'

    def test_the_welcome_text_config_survives(self, wa):
        """Scope guard. `_get_welcome_config_key` and `_load_welcome_text` read the
        welcome_message TEXT config, not a menu, and must NOT be collateral."""
        assert callable(wa._get_welcome_config_key)
        assert callable(wa._load_welcome_text)

    def test_typed_keyword_flows_survive(self, wa):
        """DEFAULT_FLOW_TRIGGERS drives typed keywords and is untouched, so nothing
        the menu offered becomes unreachable by EVERY route."""
        assert wa.DEFAULT_FLOW_TRIGGERS
        assert callable(wa._get_flow_triggers_config)


class TestNobodyGetsSilence:
    def test_the_placeholder_copy_is_exact(self, wa):
        assert wa.MENU_PLACEHOLDER_TEXT == PLACEHOLDER

    def test_the_placeholder_sender_exists(self, wa):
        assert callable(wa._send_menu_placeholder)

    @pytest.mark.parametrize('name', TRIGGER_SETS)
    def test_the_trigger_set_survives(self, handler_source, name):
        """The sets stay and only what they DO changes: each is live on Meta as a QR
        prefill, an ice breaker or a slash command."""
        assert re.search(r'\s' + name + r'\s*=\s*\{', handler_source), \
            f'{name} was removed - its trigger words would stop being answered'

    @pytest.mark.parametrize('name', TRIGGER_SETS)
    def test_the_trigger_path_reaches_the_placeholder(self, handler_source, name):
        branch = _trigger_branch(handler_source, name)
        assert '_send_menu_placeholder' in branch, \
            f'the {name} path sends no reply - that is the silence this forbids'
        assert '_send_interactive_list' not in branch


class TestATappedRowStillAnswers:
    def test_handle_list_reply_keeps_its_signature(self, handler_tree):
        """Callers pass all five by keyword, so the signature is load-bearing even
        though `sender_phone` is now unused."""
        fn = _function(handler_tree, '_handle_list_reply')
        assert [a.arg for a in fn.args.args] == [
            'list_id', 'contact_id', 'phone_number_id', 'sender_phone', 'request_id']

    def test_handle_list_reply_sends_the_placeholder(self, handler_source, handler_tree):
        fn = _function(handler_tree, '_handle_list_reply')
        body = ast.get_source_segment(handler_source, fn)
        assert '_send_menu_placeholder' in body
        assert 'list_reply_received' in body, \
            'the correlation log line is the only handle on a tapped row id'


class TestTheRivalMenuIsGone:
    """Carried forward from tests/test_one_menu.py, which this file replaces.

    `ai-generate-response` once carried a sixth menu of its own. Its delivery path
    was dead code, but a menu defined anywhere is a menu that can come back.
    """

    @pytest.fixture(scope='class')
    def ai_source(self):
        with open(AI_HANDLER_PATH, encoding='utf-8') as fh:
            return fh.read()

    def test_ai_handler_defines_no_menu(self, ai_source):
        bot_flow = _nested_literal(ai_source, 'DEFAULT_BOT_FLOW')
        assert 'mainMenu' not in bot_flow, 'a second main menu is back in ai-generate-response'
        assert 'subMenus' not in bot_flow
