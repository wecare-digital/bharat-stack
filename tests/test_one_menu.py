"""ONE menu. These tests exist to stop a second one growing back.

Context, measured 2026-09-26 before this change. The owner's instruction was that
there be a single menu. There were five interactive-list configs in the inbound
handler and a sixth in `ai-generate-response`, and **two** of them were reachable
by a customer on **both** WABAs:

    main menu          9 rows   `hi`, `/menu`, `Get Started`, new contact, ...
    self-service menu  9 rows   `/selfservice`, `/service`, `Selfservice`, menu_selfservice
    Bharat Stack       6 rows   unreachable (nothing maps to _bharat_stack_menu)
    language picker    4 rows   only from a stale cached row; all 4 rows dead-ended
    region lists      25 rows   unreachable
    ai-generate-response mainMenu + 2 sub-menus   delivery path was dead code

The command surface was read live off Meta and is identical on both numbers:
ice breakers `Get Started` / `Subscribe` / `Selfservice`, and commands `menu`,
`subscribe`, `selfservice`, `pay`. `selfservice` — a registered command AND an ice
breaker on both numbers — was the one that opened the second list.

Meta caps a list at 10 rows across all sections, so one menu is a choice of 10,
not a merge of 18. The eight rows that came off are reachable by keyword and are
named in the Help reply. That is why several tests here are about keywords and
about ids that are no longer on any menu: a row id already delivered to a handset
stays tappable for months, so the dispatch table has to keep answering for every
id this business has ever rendered.
"""
import ast
import importlib.util
import os
import sys

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_INBOUND_DIR = os.path.join(_ROOT, 'amplify', 'functions', 'messaging',
                            'inbound-whatsapp-handler')
HANDLER_PATH = os.path.join(_INBOUND_DIR, 'handler.py')
AI_HANDLER_PATH = os.path.join(_ROOT, 'amplify', 'functions', 'ai',
                               'ai-generate-response', 'handler.py')

# Meta's interactive-list limits.
# https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-list-messages
MAX_ROWS_TOTAL = 10
MAX_SECTIONS = 10
MAX_ROW_TITLE = 24
MAX_ROW_DESCRIPTION = 72
MAX_SECTION_TITLE = 24
MAX_HEADER = 60
MAX_FOOTER = 60
MAX_BUTTON = 20

# Actions in MENU_TO_KEYWORD that are handled by an explicit branch rather than by
# looking the string up in DEFAULT_FLOW_TRIGGERS.
PSEUDO_ACTIONS = {
    '_main_menu', '_cta_help', '_cta_faq', '_cta_about', '_cta_store',
    '_cta_gift_card', '_cta_bharat_stack',
    # Retired branches, kept for a one-line revert. Nothing may MAP to these.
    '_selfservice_menu', '_bharat_stack_menu', '_language_menu',
}
RETIRED_MENU_ACTIONS = {'_selfservice_menu', '_bharat_stack_menu', '_language_menu'}

# `pay` is matched by its own branch. `find id` is a known dead end: the list-reply
# path has no subscriber-lookup branch, so it falls through to the generic
# "You selected: ..." acknowledgement. It is not on the one menu; it is kept in the
# table because the previous main menu shipped it and those rows are still tappable.
NON_FLOW_ACTIONS = {'pay', 'find id'}


@pytest.fixture(scope='module')
def handler_source():
    with open(HANDLER_PATH, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def wa():
    """Load the inbound handler under a unique module name.

    Every Lambda entry point in this repo is called handler.py and conftest clears
    `sys.modules['handler']` between tests, so a plain import resolves to whichever
    handler is first on the path. Same approach as test_own_prefill_triggers_menu.py.
    """
    for path in (os.path.join(_ROOT, 'amplify', 'functions', 'shared'),
                 _INBOUND_DIR,
                 os.path.join(_INBOUND_DIR, 'modules')):
        if path not in sys.path:
            sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location('inbound_wa_one_menu', HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules['inbound_wa_one_menu'] = module
    spec.loader.exec_module(module)
    return module


def _nested_literal(source: str, name: str):
    """literal_eval a `NAME = {...}` assignment at ANY nesting depth.

    MENU_TO_KEYWORD and the keyword sets are local to their functions, so they
    cannot be imported. Parsing beats regex here because the table carries
    comments and nested quotes.
    """
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f'{name} not found in source')


@pytest.fixture(scope='module')
def menu_to_keyword(handler_source):
    return _nested_literal(handler_source, 'MENU_TO_KEYWORD')


def _rows(config):
    return [row for section in config.get('sections', []) for row in section.get('rows', [])]


def _flow_keywords(wa):
    """Every keyword that resolves to a flow, lowercased."""
    out = {}
    for key, trigger in wa.DEFAULT_FLOW_TRIGGERS.items():
        for keyword in trigger.get('keywords', []):
            out[keyword.lower()] = key
    return out


class TestThereIsExactlyOneMenu:
    def test_every_send_site_uses_the_same_getter(self, handler_source):
        """No customer-facing path may build a list from anything but the one menu.

        `_get_welcome_config` is the single getter. The language picker and region
        lists are allowed here only because they live inside the dead AI path; the
        assertions below pin that nothing ROUTES to them.
        """
        forbidden = ('list_config=_get_selfservice_menu()',
                     'list_config=_get_bharat_stack_menu()')
        for call in forbidden:
            assert handler_source.count(call) <= 1, (
                f'{call} is reachable from more than the single retired branch — '
                'a second menu is growing back'
            )

    def test_nothing_routes_to_a_retired_submenu(self, menu_to_keyword):
        """The load-bearing assertion. If a row id maps to a retired submenu
        action, that submenu is live again and there are two menus."""
        offenders = {k: v for k, v in menu_to_keyword.items() if v in RETIRED_MENU_ACTIONS}
        assert offenders == {}, f'these ids open a second menu: {offenders}'

    def test_selfservice_trigger_opens_the_one_menu(self, handler_source):
        """`/selfservice`, `/service` and the `Selfservice` ice breaker are live on
        both numbers and must not open a separate list."""
        block = handler_source.split('SELFSERVICE_KEYWORDS = {', 1)[1].split('return', 1)[0]
        assert '_get_welcome_config()' in block
        assert '_get_selfservice_menu()' not in block

    def test_selfservice_keywords_are_still_answered(self, handler_source):
        """Retiring the menu must not retire the trigger — these are a registered
        Meta command and a registered ice breaker on both WABAs."""
        keywords = _nested_literal(handler_source, 'SELFSERVICE_KEYWORDS')
        for required in ('selfservice', 'self service', 'self-service', '/selfservice', '/service'):
            assert required in keywords

    def test_selfservice_button_tap_is_not_silent(self, handler_source):
        """An ice-breaker tap can arrive as msg_type='button', which skips the whole
        text-keyword block. Before this change that tap matched nothing at all."""
        triggers = _nested_literal(handler_source, 'BUTTON_MENU_TRIGGERS')
        assert 'selfservice' in triggers

    def test_the_one_menu_is_what_the_getter_serves(self, handler_source):
        body = handler_source.split('def _get_welcome_config()', 1)[1].split('\ndef ', 1)[0]
        assert 'DEFAULT_ONE_MENU' in body
        assert 'DEFAULT_MAIN_MENU' not in body, 'the getter still serves the retired menu'

    def test_getter_takes_no_phone_argument(self, wa):
        """One menu for both WABAs. A phone parameter is how two menus start."""
        import inspect
        assert inspect.signature(wa._get_welcome_config).parameters == {}


class TestTheOneMenuFitsMeta:
    def test_exactly_ten_rows(self, wa):
        assert len(_rows(wa.DEFAULT_ONE_MENU)) == MAX_ROWS_TOTAL

    def test_section_count(self, wa):
        assert 1 <= len(wa.DEFAULT_ONE_MENU['sections']) <= MAX_SECTIONS

    def test_row_ids_are_unique(self, wa):
        ids = [r['id'] for r in _rows(wa.DEFAULT_ONE_MENU)]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize('field,limit', [('title', MAX_ROW_TITLE),
                                             ('description', MAX_ROW_DESCRIPTION)])
    def test_row_field_lengths(self, wa, field, limit):
        for row in _rows(wa.DEFAULT_ONE_MENU):
            assert len(row[field]) <= limit, f"{row['id']} {field} is {len(row[field])} chars"

    def test_section_titles(self, wa):
        for section in wa.DEFAULT_ONE_MENU['sections']:
            assert 0 < len(section['title']) <= MAX_SECTION_TITLE

    def test_envelope_lengths(self, wa):
        menu = wa.DEFAULT_ONE_MENU
        assert len(menu['header']) <= MAX_HEADER
        assert len(menu['footer']) <= MAX_FOOTER
        assert len(menu['buttonText']) <= MAX_BUTTON
        assert menu['body']


class TestEveryRowIdResolves:
    """A row id missing from MENU_TO_KEYWORD logs `list_reply_unhandled` and the
    customer gets no reply at all. An id mapped to None does the same. Before this
    change, 9 ids mapped to None and 19 more were absent entirely."""

    def test_one_menu_rows_resolve(self, wa, menu_to_keyword):
        for row in _rows(wa.DEFAULT_ONE_MENU):
            assert row['id'] in menu_to_keyword, f"{row['id']} would be silent"
            assert menu_to_keyword[row['id']] is not None

    def test_no_id_maps_to_none(self, menu_to_keyword):
        assert [k for k, v in menu_to_keyword.items() if v is None] == []

    @pytest.mark.parametrize('config_name', ['DEFAULT_MAIN_MENU',
                                             'DEFAULT_SELFSERVICE_MENU',
                                             'DEFAULT_BHARAT_STACK_MENU'])
    def test_retired_menu_rows_still_resolve(self, wa, menu_to_keyword, config_name):
        """These menus are no longer sent, but they were, and those messages are
        still in customers' chats. Every row must still answer."""
        for row in _rows(getattr(wa, config_name)):
            assert row['id'] in menu_to_keyword, f"{row['id']} would be silent"
            assert menu_to_keyword[row['id']] is not None

    def test_ai_era_row_ids_still_resolve(self, menu_to_keyword):
        """The rival menu deleted from ai-generate-response. Its delivery path was
        dead, but handsets that received one of those lists can still tap it."""
        ai_era = [
            'menu_store', 'menu_self_service', 'menu_pay', 'menu_subscribe',
            'menu_app', 'menu_about', 'menu_audio', 'menu_language',
            'menu_notifications', 'menu_human',
            'menu_submit_request', 'menu_amend_request', 'menu_track_request',
            'menu_rx_slot', 'menu_drop_docs', 'menu_hours', 'menu_enterprise',
            'menu_back',
            'store_bnb_club', 'store_no_fault', 'store_expo_week',
            'store_ritual_guru', 'store_legal_champ', 'store_swdhya',
            'store_gift_card',
        ]
        for row_id in ai_era:
            assert row_id in menu_to_keyword, f'{row_id} would be silent'
            assert menu_to_keyword[row_id] is not None

    def test_every_action_is_dispatchable(self, wa, menu_to_keyword):
        """An action string must hit an explicit branch or a flow keyword,
        otherwise the customer gets 'You selected: X. Processing...' and nothing."""
        flow_keywords = _flow_keywords(wa)
        for row_id, action in menu_to_keyword.items():
            if action in PSEUDO_ACTIONS or action in NON_FLOW_ACTIONS:
                continue
            assert action in flow_keywords, \
                f'{row_id} -> {action!r} matches no flow keyword and no branch'


class TestRowTitlesAreTypeable:
    """The menu invites a phrase, so the phrase has to work when typed. These sets
    are exact-match and `strip_decorative_edges` is deliberately NOT applied to the
    flow-trigger or pay sets, so the emoji-prefixed form needs listing too."""

    EXPECTED = {
        'menu_request_new': 'submit_request',
        'menu_request_track': 'track_request',
        'menu_request_change': 'amend_request',
        'menu_visit_book': 'schedule_appointment',
        'menu_visit_rx': 'rx_slot',
        'menu_docs_send': 'drop_docs',
        'menu_business': 'enterprise_assist',
        'menu_subscribe': 'subscribe',
    }

    def test_flow_row_titles_reach_their_flow(self, wa):
        flow_keywords = _flow_keywords(wa)
        by_id = {r['id']: r for r in _rows(wa.DEFAULT_ONE_MENU)}
        for row_id, flow_key in self.EXPECTED.items():
            title = by_id[row_id]['title'].lower()
            plain = wa.strip_decorative_edges(title)
            assert flow_keywords.get(title) == flow_key or flow_keywords.get(plain) == flow_key, \
                f'typing {by_id[row_id]["title"]!r} does not open the {flow_key} flow'

    def test_pay_row_title_is_typeable(self, wa, handler_source):
        title = [r for r in _rows(wa.DEFAULT_ONE_MENU) if r['id'] == 'menu_pay'][0]['title']
        plain = wa.strip_decorative_edges(title.lower())
        assert plain in _nested_literal(handler_source, 'PAY_KEYWORDS')

    def test_help_row_title_is_typeable(self, wa, handler_source):
        title = [r for r in _rows(wa.DEFAULT_ONE_MENU) if r['id'] == 'menu_help'][0]['title']
        plain = wa.strip_decorative_edges(title.lower())
        assert plain in _nested_literal(handler_source, 'HELP_ABOUT_KEYWORDS')


class TestNothingWasTakenAway:
    def test_appointment_keywords_survive(self, wa):
        """"Appointment" is out of customer-facing copy, but it stays as an inbound
        alias: it is live in Meta's ice breakers, in a wa.me link, and in customers'
        habits. Same precedent as Bharat Stack."""
        keywords = wa.DEFAULT_FLOW_TRIGGERS['schedule_appointment']['keywords']
        for required in ('appointment', 'schedule appointment', 'book appointment'):
            assert required in keywords
        for added in ('book a visit', 'visit'):
            assert added in keywords

    def test_dropped_rows_are_still_reachable_by_keyword(self, wa, handler_source):
        """Eight rows came off the menu to fit Meta's cap of 10. None was deleted."""
        flow_keywords = _flow_keywords(wa)
        assert 'leave review' in flow_keywords
        assert 'order notes' in flow_keywords
        for name, keyword in (('MY_ID_KEYWORDS', 'my id'),
                              ('STORE_KEYWORDS', 'store'),
                              ('GIFT_KEYWORDS', 'gift card'),
                              ('BHARAT_KEYWORDS', 'bharat stack'),
                              ('ABOUT_KEYWORDS', 'about')):
            assert keyword in _nested_literal(handler_source, name)

    def test_help_reply_names_the_dropped_rows(self, handler_source):
        """The Help reply is the only place a customer is told these still exist."""
        body = handler_source.split('def _send_help_about', 1)[1].split('\ndef ', 1)[0]
        for mention in ('*my id*', '*store*', '*gift card*', '*order notes*',
                        '*review*', '*bharat stack*'):
            assert mention in body, f'{mention} is not discoverable anywhere'


class TestTheRivalMenuIsGone:
    @pytest.fixture(scope='class')
    def ai_source(self):
        with open(AI_HANDLER_PATH, encoding='utf-8') as fh:
            return fh.read()

    def test_ai_handler_defines_no_menu(self, ai_source):
        bot_flow = _nested_literal(ai_source, 'DEFAULT_BOT_FLOW')
        assert 'mainMenu' not in bot_flow, 'a second main menu is back in ai-generate-response'
        assert 'subMenus' not in bot_flow

    def test_ai_handler_returns_to_the_one_menu(self, ai_source):
        """Its menu-response actions must point at showMainMenu, which the inbound
        handler resolves to the one menu."""
        bot_flow = _nested_literal(ai_source, 'DEFAULT_BOT_FLOW')
        for row_id in ('menu_store', 'menu_self_service'):
            assert bot_flow['menuResponses'][row_id]['action'] == 'show_main_menu'
