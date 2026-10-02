"""The Wix Coupons V2 mirror adapter. Three calls, no credential, no boto3, no arithmetic.

Design reference: `.agents/tasks/wix-coupons-giftcards-20261001/coupons-20261001.md`, sections
1.1 (Create Coupon), 1.1.1 (Get Coupon), 1.1.2 (Update Coupon) and 4.2 (the boundary conversion).

    POST   https://www.wixapis.com/stores/v2/coupons
    GET    https://www.wixapis.com/stores/v2/coupons/{id}
    PATCH  https://www.wixapis.com/stores/v2/coupons/{id}

Note the path: coupons live under `/stores/v2/`, NOT under `/ecom/`. That is the service's own
server mapping, so `wix_ecom.WIX_API_BASE` + `/stores/v2/coupons` is the whole URL.

Constructed exactly like `cart_v2.py`
-------------------------------------
The request callable is INJECTED. This module holds no boto3 client, reads no secret and knows
nothing about Secrets Manager, so it is fully testable offline and cannot leak a credential into
a log line it does not have. The handler wires `wix_ecom._request` into it.

WHY EVERY WIX-BOUND AMOUNT IS A WHOLE-RUPEE `int`
-------------------------------------------------
`Specification.moneyOffAmount`, `percentOffRate`, `fixedPriceAmount` and `minimumSubtotal` are
JSON **numbers** in decimal rupees. All five documented Create examples send bare integers (`5`,
`10`, `123`), while `startTime` in the *same* bodies is quoted - so Wix's string-encoded-int64
convention demonstrably does not extend to the money fields, and nothing on any fetched page says
a string is accepted there.

`wix_ecom._request` serialises with a plain `json.dumps(body or {})` and no custom encoder, and
that module is read-only here. So a `Decimal` would raise `TypeError` before the request left the
process, and a `Money.to_wix()` string would be the wrong JSON type. The resolution is to carry
integer paise internally and emit `paise // 100` - an `int`, which `json.dumps` handles natively
and which is unambiguously a JSON number. `//` on two ints is an int, so no float is constructed
anywhere on this path.

A value that is not a whole multiple of 100 paise never reaches here: `coupon_store` refuses it at
creation as `SUB_RUPEE_DISCOUNT_NOT_SUPPORTED`. Rounding would silently change what a customer was
promised, which is a worse outcome than a refusal.

NOTHING NUMERIC IS EVER READ BACK
---------------------------------
`wix_ecom._request` calls `json.loads` with no `parse_float`, so a Wix coupon `number` would
arrive as a **float** before any of our logic ran - `"moneyOffAmount": 10` becomes `10.0`. We
cannot fix that at the parser, because `wix_ecom.py` is read-only. So the rule is positive rather
than mitigated:

    this adapter reads `coupon.id`, `specification.active`, `specification.type` and
    `specification.code` from a Wix response, and NO NUMERIC FIELD, EVER.

The authority for every money value is our own row. A response carrying `moneyOffAmount` is
ignored, not stored. `specification.code` is in the set for one reason only - `WIX_CODE_CONFLICT`
is defined in terms of it (section 5.3.1) and is otherwise undetectable - and it is a string, so
the no-numeric rule is untouched.

A STATUS IS NEVER PARSED OUT OF AN EXCEPTION
--------------------------------------------
`wix_ecom._request` collapses every non-2xx into one `WixEcomError` whose message carries the
status as prose, and `Create Coupon` documents `errors: []` - no failure of any kind, no name, no
`applicationCode`. So no status can be special-cased, and branching on a parsed message substring
would make a money decision depend on an exception's wording. Every create failure of every status
leaves the row `PENDING_WIX`, which `coupon_store.evaluate` refuses. `WIX_CODE_CONFLICT` is raised
only by an explicit `Get Coupon` probe.

`Delete A Coupon` exists at `DELETE /stores/v2/coupons/{id}` and is deliberately not implemented.
Deactivation preserves the definition a settled order references; deletion destroys it. The
guarantee is "the code is absent", which a test can enumerate, rather than "the code is guarded".
"""
from __future__ import annotations

from typing import Any, Callable, Dict

from . import coupon_store

#: `wix_ecom.WIX_API_BASE` + this is the full URL. `/stores/v2/`, never `/ecom/`.
BASE = "/stores/v2/coupons"

#: Wix's documented maximum for `Specification.code`. Our own issuance validation is the same
#: number, so a coupon we created can never be refused by Wix for length.
MAX_CODE_LENGTH = coupon_store.MAX_CODE_LENGTH

#: Exactly the keys this adapter may read off a Wix coupon response. Pinned by
#: `tests/test_wix_coupons_contract.py` as an exact set, so a later "just read numberOfUsages"
#: has to change the test and read this comment first.
READABLE_RESPONSE_KEYS = frozenset({"coupon", "id", "specification", "active", "type", "code"})

#: Wix response fields that are JSON numbers. Named so the ban on reading them is executable
#: rather than a convention.
NUMERIC_RESPONSE_KEYS = frozenset({"moneyOffAmount", "percentOffRate", "fixedPriceAmount",
                                  "minimumSubtotal", "numberOfUsages", "discountedCycleCount",
                                  "usageLimit", "limitPerCustomer"})


class WixCouponError(RuntimeError):
    """A Wix coupon call failed. Carries no response body, which can echo buyer detail."""

    code = "WIX_MIRROR_FAILED"


class WixCouponConflict(WixCouponError):
    """Wix holds a different coupon under our id. Surfaced for a human, never auto-resolved.

    Both resolutions - adopt the Wix coupon, or rename ours - change what a customer is
    promised, so neither is automated.
    """

    code = "WIX_CODE_CONFLICT"


def _rupees(paise: Any) -> int:
    """Integer paise to a whole-rupee `int`, by integer division only.

    `//` on two ints yields an int, so no float exists on this path even transiently. A
    fractional value cannot arrive: `coupon_store` refused it at creation.
    """
    if isinstance(paise, bool) or type(paise) is not int or paise < 0:
        raise WixCouponError("a Wix-bound amount must be nonnegative integer paise")
    if paise % coupon_store.PAISE_PER_RUPEE:
        raise WixCouponError("a Wix-bound amount must be a whole number of rupees")
    return paise // coupon_store.PAISE_PER_RUPEE


def _percent(bps: Any) -> int:
    """Integer basis points to a whole-percent `int`. 500 bps is 5, not 5.0 and not "5"."""
    if isinstance(bps, bool) or type(bps) is not int or not 0 < bps <= 10000:
        raise WixCouponError("a Wix-bound rate must be integer basis points")
    if bps % coupon_store.PAISE_PER_RUPEE:
        raise WixCouponError("a Wix-bound rate must be a whole percent")
    return bps // coupon_store.PAISE_PER_RUPEE


def _epoch_ms_string(value: Any) -> str:
    """Epoch milliseconds as a STRING.

    The one place a string genuinely is documented: `startTime` and `expirationTime` are
    `format: int64` with `minimum: 1000000000000`, and every documented example quotes them
    (`"1719390501000"`). So this is Wix's string-encoded-int64 convention, which the money
    fields demonstrably do not share.
    """
    if isinstance(value, bool) or type(value) is not int \
            or value < coupon_store.WIX_MIN_TIME_MS:
        raise WixCouponError("a Wix-bound time must be epoch milliseconds")
    return str(value)


def specification(definition: Dict[str, Any]) -> Dict[str, Any]:
    """The `specification` object for Create Coupon, built from one stored definition row.

    `type` is never sent: the schema marks it read-only and derives it from whichever discount
    field was set, so sending it is at best ignored and at worst a conflict.
    """
    if not isinstance(definition, dict):
        raise WixCouponError("a coupon definition row is required")
    code = definition.get("code")
    if not isinstance(code, str) or not 1 <= len(code) <= MAX_CODE_LENGTH:
        raise WixCouponError("a coupon code of 1 to %d characters is required"
                             % MAX_CODE_LENGTH)
    name = definition.get("name")
    if not isinstance(name, str) or not name:
        raise WixCouponError("a coupon name is required")

    body: Dict[str, Any] = {
        "name": name,
        "code": code,
        "startTime": _epoch_ms_string(definition.get("startTimeMs")),
    }
    if definition.get("expirationTimeMs") is not None:
        body["expirationTime"] = _epoch_ms_string(definition.get("expirationTimeMs"))

    kind = definition.get("discountKind")
    if kind == coupon_store.MONEY_OFF:
        body["moneyOffAmount"] = _rupees(definition.get("moneyOffPaise"))
    elif kind == coupon_store.PERCENT_OFF:
        body["percentOffRate"] = _percent(definition.get("percentOffBps"))
    elif kind == coupon_store.FIXED_PRICE:
        body["fixedPriceAmount"] = _rupees(definition.get("fixedPricePaise"))
    elif kind == coupon_store.FREE_SHIPPING:
        body["freeShipping"] = True
    elif kind == coupon_store.BUY_X_GET_Y:
        buy_x, buy_y = definition.get("buyX"), definition.get("buyY")
        for quantity in (buy_x, buy_y):
            if isinstance(quantity, bool) or type(quantity) is not int or quantity < 1:
                raise WixCouponError("buyXGetY needs two positive integers")
        body["buyXGetY"] = {"x": buy_x, "y": buy_y}
    else:
        raise WixCouponError("exactly one discount kind is required")

    if definition.get("minimumSubtotalPaise") is not None:
        body["minimumSubtotal"] = _rupees(definition.get("minimumSubtotalPaise"))

    namespace = definition.get("scopeNamespace")
    if namespace:
        scope: Dict[str, Any] = {"namespace": namespace}
        group = definition.get("scopeGroupName")
        if group:
            entity_id = definition.get("scopeEntityId")
            if not isinstance(entity_id, str) or not entity_id:
                raise WixCouponError("a scope group needs an entityId")
            scope["group"] = {"name": group, "entityId": entity_id}
        body["scope"] = scope

    for stored, field in (("usageLimit", "usageLimit"),
                          ("limitPerCustomer", "limitPerCustomer")):
        value = definition.get(stored)
        if value is not None:
            if isinstance(value, bool) or type(value) is not int or value < 1:
                raise WixCouponError(f"{field} must be a positive integer")
            body[field] = value
    body["limitedToOneItem"] = bool(definition.get("limitedToOneItem", False))

    if definition.get("tags"):
        body["tags"] = list(definition.get("tags"))
    return body


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 64 \
            or "/" in value or "?" in value:
        raise WixCouponError("a Wix coupon id is required")
    return value.strip()


class WixCoupons:
    """Three Wix coupon calls over an injected request callable."""

    def __init__(self, request: Callable[..., Dict[str, Any]]):
        self.request = request

    # ── create ────────────────────────────────────────────────────────────────

    def create(self, definition: Dict[str, Any]) -> str:
        """`POST /stores/v2/coupons`. Returns the new coupon's Wix id.

        The response is read as an ID ONLY. `CreateCouponResponse` is documented as `{"id":
        "..."}` and every documented example returns exactly that - not the created coupon - so
        relying on an echoed body would be relying on something Wix does not send.
        """
        response = self.request(BASE, method="POST",
                                body={"specification": specification(definition)})
        coupon_id = _coupon_id(response)
        if not coupon_id:
            raise WixCouponError("Create Coupon returned no coupon id")
        return coupon_id

    # ── read ──────────────────────────────────────────────────────────────────

    def get(self, wix_coupon_id: Any) -> Dict[str, Any]:
        """`GET /stores/v2/coupons/{id}`. No request body.

        Returns only the four keys this adapter is allowed to read. Nothing numeric is
        returned, so nothing numeric can be stored by a caller either.
        """
        coupon_id = _identifier(wix_coupon_id)
        response = self.request(f"{BASE}/{coupon_id}", method="GET")
        return _coupon_view(response)

    def assert_mirrors(self, *, wix_coupon_id: Any, code: Any) -> Dict[str, Any]:
        """Probe the mirror, raising `WixCouponConflict` on a two-owners-one-code disagreement.

        This is the ONLY path to `WIX_CODE_CONFLICT`, and it is deliberately not reachable from
        a create failure: `Create Coupon` documents no errors at all, so a duplicate code looks
        exactly like a network timeout to us and both are retried the same way. That is
        acceptable because our own conditional put on `COUPON#<codeUpper>` has already refused
        every duplicate *we* could have created - the only way to reach a Wix-side duplicate is
        a coupon created in the Wix dashboard outside this system.

        Compared on the NORMALISED code, because Wix does not document its `code` uniqueness as
        case-insensitive and a case-only difference is not a different coupon to a customer.
        """
        view = self.get(wix_coupon_id)
        expected = coupon_store.normalise_code(code)
        seen = view.get("code")
        if not isinstance(seen, str):
            raise WixCouponError("Get Coupon returned no code to compare")
        if coupon_store.normalise_code(seen) != expected:
            raise WixCouponConflict(
                "Wix holds a different coupon under this id; a human must adjudicate")
        if view.get("id") != _identifier(wix_coupon_id):
            raise WixCouponConflict(
                "Wix returned a foreign coupon id for our code")
        return view

    # ── deactivate ────────────────────────────────────────────────────────────

    def deactivate(self, wix_coupon_id: Any) -> None:
        """`PATCH /stores/v2/coupons/{id}` with exactly `{"specification": {"active": false}}`.

        PATCH, not PUT, and patch SEMANTICS - the method's own prose says only the properties
        passed in `specification` are updated and all others remain the same, and the official
        example sends `active: false` and nothing else. So this cannot wipe the discount, the
        scope, the limits or the expiry.

        `fieldMask` is deliberately absent. It is optional, the documented example omits it, and
        sending a mask whose behaviour we have not measured would reintroduce exactly the
        replace-semantics risk this narrow body removes.

        Never `DELETE`. The definition a settled order references has to survive.
        """
        coupon_id = _identifier(wix_coupon_id)
        self.request(f"{BASE}/{coupon_id}", method="PATCH",
                     body={"specification": {"active": False}})


def _coupon_id(response: Any) -> str:
    """The coupon id out of either response shape, and nothing else.

    `Create Coupon` answers `{"id": ...}`; `Get Coupon` answers `{"coupon": {"id": ...}}`.
    """
    if not isinstance(response, dict):
        return ""
    nested = response.get("coupon")
    if isinstance(nested, dict):
        value = nested.get("id")
    else:
        value = response.get("id")
    return value if isinstance(value, str) else ""


def _coupon_view(response: Any) -> Dict[str, Any]:
    """The four readable keys of a Get Coupon response. Nothing numeric, by construction."""
    coupon = (response or {}).get("coupon") if isinstance(response, dict) else None
    spec = coupon.get("specification") if isinstance(coupon, dict) else None
    spec = spec if isinstance(spec, dict) else {}
    return {
        "id": _coupon_id(response),
        "active": spec.get("active"),
        "type": spec.get("type"),
        "code": spec.get("code"),
    }


__all__ = ["BASE", "MAX_CODE_LENGTH", "NUMERIC_RESPONSE_KEYS", "READABLE_RESPONSE_KEYS",
           "WixCouponConflict", "WixCouponError", "WixCoupons", "specification"]
