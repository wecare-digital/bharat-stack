"""Two defects found while refactoring the Meta-attribution and Wix monoliths.

**`ad-attribution` read unbounded, from an ordinary HTTP route.**

    max_results = int(params.get('limit', '50'))     # ?limit=abc -> 500
    ...
    while len(items) < max_results:
        response = table.scan(**scan_kwargs)          # no Limit AT ALL

Two separate problems. The limit is unvalidated, so a non-numeric query parameter is a
500 and a huge one is an unbounded read. And no `Limit` reaches DynamoDB, so asking for
one item still transfers up to 1 MB per page — and with a `FilterExpression` it can
read the entire table while collecting almost nothing, because filtering happens
*after* the read is paid for. `_get_stats` was worse: a bare `while True` full scan on
every call.

**`WIX_CREDENTIALS_DISABLED` was a switch that did nothing.**

Measured on the live function: `WIX_CREDENTIALS_DISABLED=true` and
`CREDENTIAL_PURGE_EPOCH=2026-09-23T03:05:00Z` are both set, and **neither name appears
anywhere in the repository**. Somebody disabled Wix with a variable the code never
reads. What actually stops Wix today is the absence of `WIX_API_KEY_SECRET`, which
makes `_load_wix_api_key()` raise — so the integration is off by accident rather than
by the switch.

That is the same shape as `InternalChatTab`'s tool checkboxes in 6.3: a control that
looks like it works, doesn't, and invites someone to rely on it. A kill switch nobody
can trust is worse than no kill switch, because the next person flips it and believes
they are safe.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify/functions/shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

ATTRIBUTION = ROOT / "amplify/functions/messaging/ad-attribution/handler.py"
WIX = ROOT / "amplify/functions/ecommerce/wix-store/handler.py"


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTable:
    """Pages forever if allowed to, and records how it was asked."""

    def __init__(self, total=5000):
        self.total = total
        self.calls = []

    def scan(self, **kwargs):
        self.calls.append(kwargs)
        limit = kwargs.get("Limit", 1000)
        start = int((kwargs.get("ExclusiveStartKey") or {}).get("id", 0))
        end = min(start + limit, self.total)
        items = [{"id": str(i), "sourceId": "ad-1",
                  "sourceType": "ad", "createdAt": i} for i in range(start, end)]
        out = {"Items": items, "Count": len(items)}
        if end < self.total:
            out["LastEvaluatedKey"] = {"id": str(end)}
        return out

    def put_item(self, Item):  # noqa: N803
        self.calls.append({"put": Item})


@pytest.fixture()
def attribution(monkeypatch):
    module = _load(ATTRIBUTION, "ad_attribution_under_test")
    table = FakeTable()

    class FakeResource:
        def Table(self, name):  # noqa: N802
            return table

    monkeypatch.setattr(module, "dynamodb", FakeResource())
    module._table = table
    return module


# ==========================================================================
# ad-attribution: bounded, and unbreakable by a query string
# ==========================================================================
@pytest.mark.parametrize("bad", ["abc", "", "-1", "0", None, "1e9", "٣"])
def test_a_junk_limit_does_not_raise(attribution, bad):
    """`int(params.get('limit', '50'))` turns `?limit=abc` into a 500 on a route
    reachable from the internet."""
    params = {} if bad is None else {"limit": bad}
    result = attribution._list_attributions(params, "req-1")
    assert result["statusCode"] == 200


def test_a_limit_is_sent_to_dynamodb_not_only_applied_in_python(attribution):
    """Slicing afterwards still pays for and transfers everything."""
    attribution._list_attributions({"limit": "10"}, "req-1")
    scans = [c for c in attribution._table.calls if "Limit" in c]
    assert scans, "no Limit reached DynamoDB"
    assert scans[0]["Limit"] <= 100


def test_the_listing_reads_one_page_and_stops(attribution):
    attribution._list_attributions({"limit": "50"}, "req-1")
    scans = [c for c in attribution._table.calls if "put" not in c]
    assert len(scans) == 1, f"paginated {len(scans)} times"


def test_a_huge_limit_is_clamped(attribution):
    attribution._list_attributions({"limit": "999999999"}, "req-1")
    scans = [c for c in attribution._table.calls if "Limit" in c]
    assert scans[0]["Limit"] <= 100


def test_the_listing_reports_truncation(attribution):
    """"50 results" and "at least 50 results" are different claims, and whichever the
    caller is handed is what it renders as a total."""
    import json
    body = json.loads(
        attribution._list_attributions({"limit": "10"}, "req-1")["body"])
    assert body["truncated"] is True
    assert body["returned"] <= 10


def test_stats_does_not_scan_the_whole_table(attribution):
    """It was a bare `while True` on every call."""
    attribution._get_stats({}, "req-1")
    scans = [c for c in attribution._table.calls if "put" not in c]
    assert len(scans) == 1, f"stats paginated {len(scans)} times"
    assert scans[0].get("Limit", 10 ** 9) <= 100


def test_stats_says_it_is_partial_rather_than_implying_a_total(attribution):
    """A count from one bounded page is not a total, and a dashboard will render it
    as one unless told otherwise."""
    import json
    body = json.loads(attribution._get_stats({}, "req-1")["body"])
    assert body.get("partial") is True


def test_the_handler_uses_the_shared_helpers_rather_than_its_own_loop():
    """Asserts the MECHANISM is gone, not that a phrase is absent.

    The docstrings now quote `while True` to explain what was removed, so a word match
    reports the documentation as the defect. What matters is that no raw `.scan(` and
    no `ExclusiveStartKey` remain: `read_page` structurally cannot paginate, so there
    is no loop left to find.
    """
    import io
    import tokenize

    text = ATTRIBUTION.read_text()
    lines = text.splitlines()
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            row, col = tok.start
            lines[row - 1] = lines[row - 1][:col]
    code = "\n".join(lines)

    assert "dynamo_reads" in code
    assert ".scan(" not in code, "a raw scan remains"
    assert "ExclusiveStartKey" not in code, "manual pagination remains"


def test_recording_an_attribution_still_works(attribution):
    """The write path must be untouched: this is the CTWA click record."""
    result = attribution._record_attribution(
        {"phone": "+918100640044",
         "referral": {"source_id": "ad-1", "source_type": "ad",
                      "ctwa_clid": "clid-1"}},
        "req-1")
    assert result["statusCode"] == 200
    assert any("put" in c for c in attribution._table.calls)


# ==========================================================================
# wix-store: the kill switch now does something
# ==========================================================================
def test_the_disable_switch_is_actually_read():
    """It was set on the live function and appeared in zero lines of code."""
    assert "WIX_CREDENTIALS_DISABLED" in WIX.read_text()


def test_the_switch_refuses_before_any_credential_load(monkeypatch):
    monkeypatch.setenv("WIX_CREDENTIALS_DISABLED", "true")
    module = _load(WIX, "wix_disabled_under_test")

    def explode(*a, **k):
        raise AssertionError("a credential load was attempted while disabled")

    monkeypatch.setattr(module.secrets_client, "get_secret_value", explode)
    with pytest.raises(RuntimeError, match="disabled"):
        module._load_wix_api_key()


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_the_switch_accepts_the_usual_spellings(monkeypatch, value):
    monkeypatch.setenv("WIX_CREDENTIALS_DISABLED", value)
    module = _load(WIX, f"wix_switch_{value}")
    with pytest.raises(RuntimeError):
        module._load_wix_api_key()


def test_an_unset_switch_does_not_disable_wix(monkeypatch):
    """The switch must not become the reason Wix is off - that would make its absence
    load-bearing and hide a real misconfiguration."""
    monkeypatch.delenv("WIX_CREDENTIALS_DISABLED", raising=False)
    monkeypatch.delenv("WIX_API_KEY_SECRET", raising=False)
    module = _load(WIX, "wix_enabled_under_test")
    with pytest.raises(RuntimeError) as excinfo:
        module._load_wix_api_key()
    # Still refuses, but for the HONEST reason: nothing is configured.
    assert "disabled" not in str(excinfo.value).lower()


def test_the_snapstart_claim_is_corrected_not_merely_deleted():
    """The docstring asserted `SnapStart.ApplyOn=PublishedVersions`. Measured on the
    live function it is `None`, as on all 62.

    Asserted positively — that the correction is stated — rather than negatively on the
    old string, because the new docstring quotes the false claim in order to correct
    it. Deleting the sentence silently would leave the next reader to rediscover that
    SnapStart is off; saying so is the useful part, since lazy loading is still right
    for a different reason.
    """
    text = WIX.read_text()
    assert "SnapStart is `None` everywhere" in text
    assert "It does not" in text


def test_the_env_fallback_claim_is_corrected_not_merely_deleted():
    """It said "Secrets Manager first, env as migration fallback". There is no env
    fallback — the loader raises when the secret is absent. The claim invited someone to
    put a plaintext credential in an environment variable and expect it to work, which
    is exactly what the workspace secret-handling rule forbids."""
    text = WIX.read_text()
    assert "There is no env fallback" in text
    assert "Resolve the Wix API key from Secrets Manager. No env fallback." in text
