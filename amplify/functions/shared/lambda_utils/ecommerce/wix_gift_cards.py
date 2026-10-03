"""The Wix-native Gift Cards (B1) adapter. Four calls, no credential, no boto3, no arithmetic.

Design reference: `.agents/tasks/wix-coupon-giftcard-sample-20261002/design.md` revision 8,
§2.5, with every schema fact measured in
`docs/execution/wix-contract-verification-20261002.md`.

    POST   https://www.wixapis.com/gift-cards/v1/gift-cards
    POST   https://www.wixapis.com/gift-cards/v1/gift-cards/query
    GET    https://www.wixapis.com/gift-cards/v1/gift-cards/{giftCardId}
    POST   https://www.wixapis.com/gift-cards/v1/gift-cards/{giftCardId}/disable

Note the path: `/gift-cards/v1/`, NOT `/ecom/` and NOT `/stores/`.

DELIBERATELY UNWIRED
--------------------
No handler imports this module, and a structural test asserts that. The adapter being CORRECT is
what this change demonstrates; the adapter being IN THE REQUEST PATH needs one owner-run live
verification plus a deploy decision, and a deploy is a standing refusal here. Wiring it now would
also mean our gift-card handlers and this adapter are both live against the same cards, which is
a worse state than either end point. The sequence is: demonstrate -> verify live -> wire and
retire. The guard is what makes that sequence hold rather than being a good intention - the
module cannot reach production by drift, only by somebody adding an import and deleting a test.

It ships in no Lambda package until some handler imports it, because
`scripts/deploy_all_lambdas.py` packages per-function sources and validates top-level imports.

CONSTRUCTED EXACTLY LIKE `wix_coupons.py`
-----------------------------------------
The request callable is INJECTED. This module holds no boto3 client, reads no secret and knows
nothing about Secrets Manager, so it is fully testable offline and cannot leak a credential into
a log line it does not have. It also holds no logger: there is no `logger`, no `logging` and no
`print(` in this file, so no logging expression can touch bearer value even reduced to a bool.

THE PEPPER IS A REQUIRED KEYWORD, NEVER A READ
----------------------------------------------
`card_code` takes `pepper` keyword-only with **no default**, and the caller obtains it exactly as
`ecommerce/gift-cards/handler.py` already does - `store.read_pepper(_read_secret,
secret_id=SPI_SECRET_ID)`, lazily, per request. That keeps three properties at once: this module
stays import-free, the secret stays by-reference, and a rotation takes effect on the next request
rather than on the next sandbox recycle. The existing field is
`wecare/wix/giftcard-spi:code_pepper` - one key, two purposes, domain-separated by
`CODE_DOMAIN_TAG` on the MESSAGE.

MONEY
-----
Every Wix money field in this API is a **decimal string** (`format DECIMAL_VALUE`,
`maxScale: 2`), which is the asymmetry that makes this API safer than the coupon one: there is no
numeric field to read back, so `wix_ecom._request`'s `json.loads` with no `parse_float` has
nothing to turn into a float. Amounts go out through `Money(paise).to_wix()` and come back
through `Money.from_wix(...)`, whose regex refuses anything that is not an exact decimal string.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
from hashlib import sha256
from typing import Any, Callable, Dict, Optional

from .money import Money

#: `wix_ecom.WIX_API_BASE` + this is the full URL.
BASE = "/gift-cards/v1/gift-cards"

#: Compared EXPLICITLY, never inferred from an amount.
CURRENCY = "INR"

#: Wix's `Source` enum is `{ORDER, MANUAL}` and the field is required and immutable. `ORDER` is
#: narrowed out rather than merely defaulted away: it means *this card was purchased through an
#: order*, which is a provenance claim, and nothing here creates a card from an order.
SOURCE_MANUAL = "MANUAL"
SOURCES = frozenset({SOURCE_MANUAL})

#: Wix: `idempotencyKey` `minLength 1, maxLength 100`.
MAX_IDEMPOTENCY_KEY = 100

#: Wix: `code` `minLength 8, maxLength 20`.
MIN_CODE_LENGTH, MAX_CODE_LENGTH = 8, 20

#: Wix: `codeSuffix` `minLength 4, maxLength 4`, read-only.
CODE_SUFFIX_LENGTH = 4

#: Wix `Money` permits 0; a gift card worth nothing is a defect, not a card.
MIN_INITIAL_VALUE_PAISE = 1

#: BORROWED, not measured. The verification transcript records NO Wix-side maximum
#: (`decimalValue {"gte":"0","maxScale":2}` and nothing more). The SPI ceiling is reused so the
#: two gift-card legs of the demo are bounded identically and therefore comparable - not because
#: Wix is known to stop here. A real measured maximum would replace this.
MAX_INITIAL_VALUE_PAISE = 99_999_999_999

#: Domain separation from `gift_card_store.code_hash`, which HMACs under the SAME pepper with the
#: SAME construction over a caller-supplied string. Prefixed to the MESSAGE, never to the output,
#: so the two derivations cannot collide for ANY input rather than merely for the inputs they
#: happen to receive today.
CODE_DOMAIN_TAG = b"wix-gc-code:"


class WixGiftCardError(RuntimeError):
    """Input this adapter refuses to send, or a Wix answer it refuses to trust.

    Mirrors `wix_coupons.WixCouponError` in the detail that matters: a stable, enumerable
    `.code` for a caller to branch on, and the message slot left for prose. The reason is a
    FIELD, never message text, because a handler cannot branch on an interpolated string and a
    log cannot group by one.
    """

    code = "WIX_GIFT_CARD_REFUSED"

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


#: The closed reason set. Named so a caller can branch and a log can group, and so adding one is
#: a deliberate edit rather than a new string literal.
REFUSAL_CODES = frozenset({
    "A_PEPPER_IS_REQUIRED", "CODE_SUFFIX_MISSING", "AMBIGUOUS_CODE",
    "INVALID_AMOUNT", "INVALID_CURRENCY", "INVALID_CODE", "INVALID_SOURCE",
    "INVALID_IDEMPOTENCY_KEY", "INVALID_EXPIRATION", "INVALID_GIFT_CARD_ID",
})


# ── derivations ───────────────────────────────────────────────────────────────

def idempotency_key(*, reference_id: str) -> str:
    """Deterministic in `reference_id` ALONE, so a retry cannot mint a second key.

    No clock, no counter, no `secrets`. A fresh key on retry is how a replay becomes a second
    gift card, which is the one failure this adapter exists to prevent.

    UNKEYED on purpose, and that is safe HERE: an idempotency key is not bearer value. It buys
    nothing for a holder - Wix answers a replayed key with the card that already exists, which
    is the card the reference already identifies. Being unkeyed also makes it
    ROTATION-INVARIANT, which is what stops a post-rotation replay minting a second card. See
    `card_code` for why the same reasoning does NOT transfer to the code.
    """
    digest = hashlib.sha256(reference_id.encode("utf-8")).hexdigest()
    return ("wd-gc-" + digest)[:MAX_IDEMPOTENCY_KEY]


def card_code(*, reference_id: str, pepper: str) -> str:
    """The production derivation. KEYED, because the code IS bearer value.

    `hmac.new(pepper, CODE_DOMAIN_TAG + reference_id, sha256)`, then `"WDGC"` + 16 hex,
    upper-cased: exactly 20 characters, which is Wix's documented MAXIMUM. The length sits at
    the ceiling deliberately - 16 hex digits is 64 bits of margin where 12 would be 48, and Wix
    permits the extra four characters at no cost.

    The pepper is what makes this safe, and the reason is specific to this repository rather
    than general caution. `reference_id` is NOT a secret here - the standing payments rule says
    it "may be logged in full", and it is, deliberately, as the correlation id that lets a
    payment log line be traced with no masked field. So any UNKEYED function of `reference_id`
    is recoverable by anyone who can read a log line, and a gift-card code recovered that way
    is spendable. Keying it means the log discloses nothing the holder of the pepper does not
    already have.

    Determinism is unaffected: the pepper is fixed per environment, so the derivation is still
    stable across retries, which is what resolve-before-create needs. The one case where it is
    not - a pepper rotation - is covered by `idempotency_key` being rotation-invariant.

    The return value is bearer value. It is never logged, never put in an exception message and
    never returned to a caller by `create`, which answers with `codeLast4` instead.
    """
    if not isinstance(pepper, str) or not pepper:
        raise WixGiftCardError("A_PEPPER_IS_REQUIRED", "a pepper is required to derive a code")
    mac = hmac.new(pepper.encode("utf-8"),
                   CODE_DOMAIN_TAG + reference_id.encode("utf-8"), sha256)
    return ("WDGC" + mac.hexdigest()[:16]).upper()


def demo_code(*, reference_id: str) -> str:
    """DEMO ONLY. UNKEYED, therefore NOT usable for a real gift card.

    Identical in shape AND LENGTH to `card_code` - 20 characters, Wix's maximum - so the demo
    crosses the same length boundary production will, and derived from `reference_id` with no
    key, so the value it returns is recoverable from any log line carrying the reference.

    It is NOT a prefix or a substring of `idempotency_key(reference_id)` - the prefixes and the
    casing differ, `"WDGC"` against `"wd-gc-"`. Saying that it is understates the problem by
    pointing at the wrong property. The true and dangerous property is that **both values expose
    the same unkeyed sha256 digest of the same input, so either value yields the other**: strip
    the decoration from one and it is a prefix of the stripped other. For
    `"wd-gc-sample-2026-10-02"` the shared fragment is `b4a4841861208fa8`.

    All of that is acceptable only because every code in the offline harness and demo is a
    fixture placeholder and no live Wix response can reach either process.

    Production must call `card_code(reference_id=..., pepper=...)`. A structural assertion fails
    if any file under `amplify/` references this function.
    """
    return ("WDGC" + hashlib.sha256(reference_id.encode("utf-8")).hexdigest()[:16]).upper()


# ── validation ────────────────────────────────────────────────────────────────

def _amount(initial_value_paise: Any) -> str:
    """Integer paise to Wix's decimal string, with the type gate first.

    EXACT type, not `isinstance`, because `bool` *is* an `int` in Python and `True` would
    otherwise be an amount of one paise. `Money.__post_init__` is the second gate.
    """
    if type(initial_value_paise) is not int:
        raise WixGiftCardError("INVALID_AMOUNT", "an initial value must be integer paise")
    if not MIN_INITIAL_VALUE_PAISE <= initial_value_paise <= MAX_INITIAL_VALUE_PAISE:
        raise WixGiftCardError(
            "INVALID_AMOUNT",
            f"an initial value must be {MIN_INITIAL_VALUE_PAISE}"
            f" to {MAX_INITIAL_VALUE_PAISE} paise")
    try:
        return Money(initial_value_paise).to_wix()
    except ValueError as error:
        raise WixGiftCardError("INVALID_AMOUNT", "an initial value must be integer paise") \
            from error


def _currency(value: Any) -> str:
    if value != CURRENCY:
        raise WixGiftCardError("INVALID_CURRENCY", f"this adapter sends {CURRENCY} only")
    return CURRENCY


def _code(value: Any) -> Optional[str]:
    """`None` lets Wix generate one. Otherwise exactly Wix's length window."""
    if value is None:
        return None
    if not isinstance(value, str) or not MIN_CODE_LENGTH <= len(value) <= MAX_CODE_LENGTH:
        raise WixGiftCardError(
            "INVALID_CODE",
            f"a code must be {MIN_CODE_LENGTH} to {MAX_CODE_LENGTH} characters")
    return value


def _source(value: Any) -> str:
    if value not in SOURCES:
        raise WixGiftCardError("INVALID_SOURCE", f"source must be one of {sorted(SOURCES)}")
    return str(value)


def _idempotency_key(value: Any) -> str:
    """An empty key is a refusal, not a "no idempotency" fallback."""
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_IDEMPOTENCY_KEY:
        raise WixGiftCardError(
            "INVALID_IDEMPOTENCY_KEY",
            f"an idempotency key must be 1 to {MAX_IDEMPOTENCY_KEY} characters")
    return value


def _expiration(value: Any) -> Optional[str]:
    """`None`, or a string `datetime.fromisoformat` accepts.

    NOT range-checked: a past expiry is Wix's to reject, and guessing its rule would be
    inventing a contract. `fromisoformat` on 3.12 accepts a trailing `Z`, which Wix's own
    documented example carries.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise WixGiftCardError("INVALID_EXPIRATION", "an expiry must be an ISO-8601 string")
    try:
        datetime.datetime.fromisoformat(value)
    except (ValueError, TypeError) as error:
        raise WixGiftCardError("INVALID_EXPIRATION",
                               "an expiry must be an ISO-8601 string") from error
    return value


def _gift_card_id(value: Any) -> str:
    """Non-empty string; no shape assumption beyond that, since `format: GUID` is Wix's."""
    if not isinstance(value, str) or not value.strip() or "/" in value or "?" in value:
        raise WixGiftCardError("INVALID_GIFT_CARD_ID", "a Wix gift card id is required")
    return value.strip()


# ── the response view ─────────────────────────────────────────────────────────

#: The ONE authoritative enumeration of what both public functions return, on BOTH branches.
VIEW_KEYS = ("giftCardId", "codeLast4", "balancePaise", "currency", "resolved", "disabled",
             "expirationDate")


def _code_last4(card: Dict[str, Any]) -> str:
    """Wix's own `codeSuffix`, NEVER a parse of `code`.

    The obfuscated `code` is documented only through one hyphen-grouped example
    (`****-****-****-4444`), and our codes are 20 unhyphenated characters, so what Wix returns
    for OUR shape is genuinely unmeasured. It does not matter: `codeSuffix` is a dedicated
    read-only field carrying exactly the four characters we want, on both responses. Absent or
    not exactly four characters is a REFUSAL, with no fallback to slicing bearer value - a
    fallback that parses bearer value is the one place a rule must not be lenient.
    """
    suffix = card.get("codeSuffix")
    if not isinstance(suffix, str) or len(suffix) != CODE_SUFFIX_LENGTH:
        raise WixGiftCardError("CODE_SUFFIX_MISSING",
                               "Wix returned no usable codeSuffix to report")
    return suffix


def _view(card: Dict[str, Any], *, amount_key: str, resolved: bool) -> Dict[str, Any]:
    """The seven-key view, the same on every branch of both public functions.

    `amount_key` is `"initialValue"` on a create and `"balance"` on a resolve - the only
    difference between the two paths, and the reason `resolved` is in the dict.
    """
    amount = ((card.get(amount_key) or {}) if isinstance(card.get(amount_key), dict) else {}) \
        .get("amount")
    if not isinstance(amount, str):
        raise WixGiftCardError("INVALID_AMOUNT",
                               f"Wix returned no {amount_key} decimal string")
    try:
        money = Money.from_wix(amount)
    except ValueError as error:
        raise WixGiftCardError("INVALID_AMOUNT",
                               f"Wix {amount_key} was not an exact decimal string") from error
    return {
        "giftCardId": _gift_card_id(card.get("id")),
        "codeLast4": _code_last4(card),
        "balancePaise": money.paise,
        "currency": _currency(card.get("currency")),
        "resolved": resolved,
        # Derived from Wix's own read-only timestamp, because there is no separate status field.
        "disabled": bool(card.get("disabledDate")),
        # Passed through UNPARSED. This adapter makes no expiry decision: comparing a Wix
        # timestamp against our clock is a decision with a timezone and a skew in it, and the
        # authority on whether a Wix card is spendable is Wix. The caller gets the fact.
        "expirationDate": card.get("expirationDate"),
    }


# ── the four calls ────────────────────────────────────────────────────────────

class WixGiftCards:
    """Four Wix gift-card calls over an injected request callable.

    There is no `delete`: Wix has none. `disable` is the whole of the removal surface, which is
    the right shape anyway - a disabled card retains its liability record.
    """

    def __init__(self, request: Callable[..., Dict[str, Any]]):
        self.request = request

    # -- create -----------------------------------------------------------

    def create(self, *, initial_value_paise: int, code: Optional[str],
               idempotency_key: str, source: str = SOURCE_MANUAL,
               currency: str = CURRENCY,
               expiration_iso: Optional[str] = None) -> Dict[str, Any]:
        """`POST /gift-cards/v1/gift-cards`, and it RESOLVES BEFORE IT GENERATES.

        When a deterministic `code` is supplied, this calls `find_by_code` first. A hit returns
        the existing card - **including a disabled or expired one**, with `disabled` /
        `expirationDate` saying so - and issues NO create. Only the `{}` miss proceeds to
        `POST`, carrying `idempotencyKey` as the server-side backstop for the window between the
        two calls.

        Both layers are needed and neither is redundant: the query makes a replay observable to
        US (so a test can assert "one create call, not two"), while `idempotencyKey` is what
        actually closes the query-then-create TOCTOU race INSIDE Wix. This is the guarantee
        coupons cannot have, and it is why the two verdicts differ.

        Returning a dead card on a resolve hit is deliberate: minting a second card for one
        reference is the worse failure, and it is the failure this adapter exists to prevent.

        `balancePaise` MEANS TWO DIFFERENT FACTS. On a genuine create it is the card's
        `initialValue`; on a resolve hit it is the card's CURRENT balance, which may already be
        lower. A caller that needs the distinction must read `resolved`. A caller that treats
        `balancePaise` as "what I just issued" is wrong on the replay path - which is precisely
        the path this adapter is built to make common.
        """
        # Every validation runs BEFORE any amount is formatted and before any request is
        # composed, so a refusal costs no HTTP call. Currency first and explicitly.
        currency_value = _currency(currency)
        source_value = _source(source)
        code_value = _code(code)
        key_value = _idempotency_key(idempotency_key)
        expiration_value = _expiration(expiration_iso)
        amount = _amount(initial_value_paise)

        if code_value is not None:
            existing = self.find_by_code(code_value)
            if existing:
                return existing

        body: Dict[str, Any] = {
            "giftCard": {
                "initialValue": {"amount": amount},
                "currency": currency_value,
                "source": source_value,
                # Merged in rather than sent as `null`. A `"code": null` is a DIFFERENT request
                # from a request with no `code`, and the documented meaning of OMITTING `code`
                # is *Wix generates one* - so sending `null` would be asking for an
                # undocumented behaviour at a money boundary.
                **({"code": code_value} if code_value is not None else {}),
                **({"expirationDate": expiration_value} if expiration_value is not None else {}),
            },
            "idempotencyKey": key_value,
        }
        # No other key is ever added. `balance`, `codeSuffix`, `createdDate`, `id` and
        # `disabledDate` are read-only in the schema; `orderInfo` and `notificationInfo` are
        # writable and deliberately not sent - `orderInfo` would be a false provenance claim and
        # `notificationInfo` triggers a Wix-sent email, which is a live customer send.
        response = self.request(BASE, method="POST", body=body)
        card = (response or {}).get("giftCard")
        if not isinstance(card, dict):
            raise WixGiftCardError("INVALID_GIFT_CARD_ID",
                                   "Create Gift Card returned no gift card")
        return _view(card, amount_key="initialValue", resolved=False)

    # -- read -------------------------------------------------------------

    def find_by_code(self, code: str) -> Dict[str, Any]:
        """`POST /gift-cards/v1/gift-cards/query` with `$eq` on the FULL code.

        Three branches, and `create` depends on the first:

        * MISS -> `{}`. An empty `giftCards` list is NOT an error; it is the signal `create`
          resolves on, so the empty dict is the contract and a `None` or a raise would both make
          the resolve path a try/except.
        * ONE HIT -> the same seven keys `create` returns, with `resolved: True`.
        * MORE THAN ONE -> `AMBIGUOUS_CODE`, with no further request. `code` is unique in Wix,
          so two matches mean the filter was not honoured as documented. Reading `giftCards[0]`
          under those conditions is a money read from an arbitrary row, and refusing is the only
          safe answer.

        `giftCards[0]` is read ONLY after the length check, so no money field is ever read from
        an arbitrary row. `balance` and `currency` are on the Query response (measured), so the
        resolve path is ONE request, not a query followed by a get.
        """
        code_value = _code(code)
        if code_value is None:
            raise WixGiftCardError("INVALID_CODE", "a code is required to find a card")
        response = self.request(
            f"{BASE}/query", method="POST",
            body={"query": {"filter": {"code": {"$eq": code_value}}}})
        cards = (response or {}).get("giftCards")
        cards = cards if isinstance(cards, list) else []
        if not cards:
            return {}
        if len(cards) > 1:
            raise WixGiftCardError("AMBIGUOUS_CODE",
                                   f"the code filter matched {len(cards)} cards")
        card = cards[0]
        if not isinstance(card, dict):
            raise WixGiftCardError("INVALID_GIFT_CARD_ID", "Wix returned no gift card")
        return _view(card, amount_key="balance", resolved=True)

    def get(self, gift_card_id: str) -> Dict[str, Any]:
        """`GET /gift-cards/v1/gift-cards/{giftCardId}`. No request body."""
        identifier = _gift_card_id(gift_card_id)
        response = self.request(f"{BASE}/{identifier}", method="GET")
        card = (response or {}).get("giftCard")
        if not isinstance(card, dict):
            raise WixGiftCardError("INVALID_GIFT_CARD_ID", "Wix returned no gift card")
        return _view(card, amount_key="balance", resolved=True)

    # -- disable ----------------------------------------------------------

    def disable(self, gift_card_id: str) -> None:
        """`POST /gift-cards/v1/gift-cards/{giftCardId}/disable`. Never a delete."""
        identifier = _gift_card_id(gift_card_id)
        self.request(f"{BASE}/{identifier}/disable", method="POST", body={})


__all__ = ["BASE", "CODE_DOMAIN_TAG", "CODE_SUFFIX_LENGTH", "CURRENCY",
           "MAX_CODE_LENGTH", "MAX_IDEMPOTENCY_KEY", "MAX_INITIAL_VALUE_PAISE",
           "MIN_CODE_LENGTH", "MIN_INITIAL_VALUE_PAISE", "REFUSAL_CODES", "SOURCES",
           "SOURCE_MANUAL", "VIEW_KEYS", "WixGiftCardError", "WixGiftCards", "card_code",
           "demo_code", "idempotency_key"]
