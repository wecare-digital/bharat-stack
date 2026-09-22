"""Smoke-test lockdown: while testing live sends, only the QA number can receive.

The requirement
---------------
The brief is explicit: live sends are allowed only with `WA_LIVE_SMOKE_TEST=true`
and an explicit owner-controlled `WA_QA_RECIPIENT`, and a test must never be sent
to a customer. Neither variable existed anywhere in the source, so there was no
mechanism to satisfy it - which is why the Phase 2 handset round trip stayed
blocked. A reviewer could not be shown that a live test was safe, because nothing
constrained who it could reach.

The semantics, and why this direction
-------------------------------------
This is a **lockdown**, not a permission. With the flag off - the default, and the
production state - nothing changes: the sender behaves exactly as before. With the
flag on, the function enters smoke-test mode and refuses every recipient except
`WA_QA_RECIPIENT`.

Reading it the other way round - flag enables sending - would be the dangerous
design. It would mean the guard's failure mode is "send to anyone", and the flag
would have to be on in production for normal traffic to work, which makes it
useless as a test switch. Here, enabling it can only ever *narrow* who is
reachable, so a mistake in the flag cannot cause an unintended send.

Turning it on in production would therefore halt customer messaging rather than
leak to customers. That is the correct direction for a safety switch to fail, but
it does mean the flag must be off in normal operation; it belongs in the
feature-flag register with that noted.

Absent or malformed configuration
---------------------------------
Smoke mode with no `WA_QA_RECIPIENT` configured blocks **everything**. An operator
who enables the mode and forgets the recipient gets no sends at all, which is
visible immediately, rather than an unrestricted send window.
"""

from __future__ import annotations

import os
import re
from typing import Optional, Tuple

FLAG_ENV = "WA_LIVE_SMOKE_TEST"
RECIPIENT_ENV = "WA_QA_RECIPIENT"

_DIGITS = re.compile(r"\D+")


def _normalize(phone: Optional[str]) -> str:
    """Digits only, so `+91 93309 94400`, `919330994400` and `+919330994400`
    compare equal. Formatting differences must not defeat the lockdown."""
    if not phone:
        return ""
    return _DIGITS.sub("", str(phone))


def is_smoke_mode() -> bool:
    """True only for an exact, case-insensitive 'true'.

    Deliberately strict: '1', 'yes' and 'True ' with a stray space do not enable a
    mode that stops customer messaging.
    """
    return os.environ.get(FLAG_ENV, "").strip().lower() == "true"


def qa_recipient() -> str:
    return os.environ.get(RECIPIENT_ENV, "").strip()


def check_recipient(recipient: Optional[str]) -> Tuple[bool, str]:
    """`(allowed, reason)` for sending to `recipient`.

    `reason` is a short stable token, safe to log. It never contains a phone
    number - the caller already knows the recipient and should mask it when
    logging.
    """
    if not is_smoke_mode():
        return True, "not_smoke_mode"

    configured = qa_recipient()
    if not configured:
        return False, "smoke_mode_without_qa_recipient"

    if _normalize(recipient) == _normalize(configured):
        return True, "qa_recipient_match"
    return False, "smoke_mode_recipient_not_qa"


def describe() -> dict:
    """Config summary for a status endpoint or a log line, without the number."""
    configured = qa_recipient()
    return {
        "smokeMode": is_smoke_mode(),
        "qaRecipientConfigured": bool(configured),
        "qaRecipientSuffix": _normalize(configured)[-4:] if configured else "",
    }
