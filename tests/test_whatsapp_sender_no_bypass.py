"""A reply must leave from the phone the customer actually messaged.

outbound-whatsapp used to end its sender resolution with:

    if not meta_phone_id:
        meta_phone_id = '1055232054343117'   # "the working one"

That is a cross-WABA bypass, and none of its three consequences were visible at
the call site:

  1. A customer who messaged Phone 1 was answered from Phone 2 - a number they
     never contacted, which on their side is a message from a stranger.
  2. It leaves the 24-hour customer service window. The window belongs to the
     conversation opened on THAT number, so a free-form reply from the other
     number has no open window: Meta rejects it, or bills a new conversation.
  3. It contradicts the "NEVER cross-WABA" rule asserted elsewhere in this
     codebase, including in the payment handlers, while quietly doing the
     opposite.

These tests assert the refusal. A message that does not go out is a visible bug;
a message from the wrong business number is a support incident.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

SHARED = pathlib.Path(__file__).resolve().parents[1] / "amplify/functions/shared"
HANDLER_PATH = (pathlib.Path(__file__).resolve().parents[1]
                / "amplify/functions/messaging/outbound-whatsapp/handler.py")
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))


def _load():
    """Load under a UNIQUE module name.

    Importing this as plain `handler` collides in sys.modules with every other
    function handler the suite loads, so whichever test ran first wins and this
    file silently tests the wrong module. It passed alone and failed in the full
    run. Same spec_from_file_location pattern as tests/test_outbound_sms.py.
    """
    spec = importlib.util.spec_from_file_location(
        "outbound_whatsapp_sender_handler", HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ow = _load()

PHONE1 = "phone-number-id-waba1-direct-1016149501586345"
PHONE2 = "phone-number-id-waba-t-direct-1055232054343117"
WABA2_META = "1055232054343117"


# --------------------------------------------------------------------------
# each phone answers its own conversation
# --------------------------------------------------------------------------

def test_phone1_resolves_to_phone1_not_phone2():
    assert ow._resolve_meta_phone_id(PHONE1) == "1016149501586345"


def test_phone2_resolves_to_phone2():
    assert ow._resolve_meta_phone_id(PHONE2) == WABA2_META


def test_direct_api_id_is_derived_exactly_not_guessed():
    """The Direct API id embeds the Meta phone id, so deriving it is exact.
    This is not a fallback and must keep working for ids outside the map."""
    assert ow._resolve_meta_phone_id(
        "phone-number-id-waba9-direct-1234567890") == "1234567890"


# --------------------------------------------------------------------------
# the bypass must be gone
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "",
    "unknown-phone",
    "phone-number-id-waba1",          # no -direct- segment
    "some-other-system-id",
])
def test_unresolvable_sender_raises_instead_of_defaulting(bad):
    with pytest.raises(ow.UnresolvedSenderPhone):
        ow._resolve_meta_phone_id(bad)


def test_non_numeric_direct_segment_is_refused_not_used_as_a_phone_id():
    """'-direct-' followed by junk must not be handed to Graph as a phone id."""
    with pytest.raises(ow.UnresolvedSenderPhone):
        ow._resolve_meta_phone_id("phone-number-id-waba1-direct-notanumber")


def test_no_unresolved_input_can_ever_yield_waba2():
    """The specific regression: nothing unmappable may resolve to WABA2."""
    for bad in ("", "nope", "phone-number-id-waba1", "x-direct-", "garbage"):
        try:
            got = ow._resolve_meta_phone_id(bad)
        except ow.UnresolvedSenderPhone:
            continue
        assert got != WABA2_META, (
            f"{bad!r} silently resolved to WABA2 - the bypass is back")


def test_the_hardcoded_default_is_not_in_the_resolver_source():
    """Belt and braces: catch a future edit that reintroduces the literal."""
    import inspect
    src = inspect.getsource(ow._resolve_meta_phone_id)
    # The literal may appear in the explanatory docstring, but not in code.
    code = "\n".join(
        line for line in src.splitlines()
        if not line.strip().startswith("#")
    )
    body = code.split('"""')[-1]  # everything after the docstring
    assert WABA2_META not in body, (
        "a hardcoded WABA2 phone id is back in the resolver body")
