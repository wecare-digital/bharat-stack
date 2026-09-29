"""One definition of "are Wix credentials switched off", for every path that loads one.

WHY THIS EXISTS, AND THE PRECISE DEFECT IT CLOSES.

`WIX_CREDENTIALS_DISABLED` was set to `true` on the live functions while appearing in zero
lines of code - somebody disabled Wix with a variable nothing read. That was fixed on
2026-09-23 in `amplify/functions/ecommerce/wix-store/handler.py`, and
`tests/test_attribution_and_wix_guards.py` documents it.

But the fix landed in ONE of the credential paths. Measured 2026-09-29, there are three:

    amplify/functions/ecommerce/wix-store/handler.py  _load_wix_api_key()   honoured it
    amplify/functions/operations/seo-tools/wix.py     _load_api_key()       DID NOT
    scripts/wix_blog_migrate.py                       load_api_key()        DID NOT

The two that ignored it are the BLOG paths - the ones the Blog Production system uses to
publish. So a switch named as though it disables Wix disabled the store and left blog
publishing running. That is the same failure as before wearing a different hat: an operator
flips it, reads the commit that says it was fixed, and believes they are safe.

## What it does NOT block, deliberately

Only the **API key** path. `wix.py` also holds `_load_visitor_access_token()`, which uses
the public `WIX_CLIENT_ID` to obtain an anonymous visitor token for READS. That is not a
credential, and it is what serves the public blog - 1,140 posts and the sitemap.

If this guard covered that path, setting the switch would take the entire public blog
offline, and `generate-sitemap.js` would refuse to write a sitemap. An incident control
whose side effect is a site outage will not be used during an incident, which is the only
time it matters. So: writes and authenticated reads stop, the public site keeps serving.
"""
from __future__ import annotations

import os

FLAG = "WIX_CREDENTIALS_DISABLED"

#: The spellings an operator actually types. Kept identical to
#: `wix-store/handler.py::_credentials_disabled` and to `cost_flags._TRUTHY`; a test asserts
#: the three agree, because a switch that works in two of three places is the bug above.
TRUTHY = ("1", "true", "yes", "on", "enabled")


def credentials_disabled() -> bool:
    """Whether the operator has switched Wix credentials off.

    Read on EVERY call rather than captured at import. This is an incident control, and a
    value that only takes effect once every warm Lambda sandbox recycles is not one - the
    operator flips it, nothing changes for minutes, and they conclude it does not work.
    """
    return str(os.environ.get(FLAG, "")).strip().lower() in TRUTHY


def refuse_if_disabled(context: str = "") -> None:
    """Raise before any credential read when the switch is on.

    Called FIRST in each loader, so a disabled integration performs no Secrets Manager
    read at all. That ordering is the point: it means the switch is provable by asserting
    no credential call was attempted, which is exactly how the existing test verifies the
    store path.
    """
    if not credentials_disabled():
        return
    where = f" ({context})" if context else ""
    raise RuntimeError(
        f"Wix credentials are disabled by {FLAG}{where}. This is deliberate; clear that "
        "variable to re-enable rather than working around it. Note this does NOT affect "
        "anonymous visitor reads, so the public blog continues to serve."
    )
