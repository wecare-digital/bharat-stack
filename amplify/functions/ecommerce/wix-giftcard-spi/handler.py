"""`wecare-wix-giftcard-spi` - the three Wix Gift Cards Service Plugin endpoints, and nothing else.

Design reference: `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md`
sections 1.1 (the measured contract), 1.1.1 (there is no documented error body), 5 (JWT
verification), 7.1 (the routes), 7.4 (error handling) and 10.1 (the scoped role).

| Route | Verifies | Returns |
|---|---|---|
| `POST /wix-giftcards/v1/balance` | the section 5 JWT | `{balance, currencyCode, externalId}` |
| `POST /wix-giftcards/v1/redeem` | the section 5 JWT | `{remainingBalance, currencyCode, transactionId}` |
| `POST /wix-giftcards/v1/void` | the section 5 JWT | `{remainingBalance, currencyCode}` |

Exactly three paths. Response shapes are exactly the documented schemas and NOTHING more - the
service-plugin guidance is explicit that a response not matching the specification will not be
handled correctly. `externalId` is `giftCardId`, never the code and never anything derived from it.

VERIFICATION IS FIRST
---------------------
Before the body is interpreted and before any table is touched. The route necessarily carries
`AuthorizationType=NONE` - Wix presents its own JWT, not a Cognito token - so handler-level
verification plus stage/route throttling is the entire filter in front of it. WAF was removed by
owner decision on 2026-09-28, so there is no per-IP layer behind this either. The ordering is
asserted by tests 16 and 17 rather than trusted.

THIS FUNCTION CANNOT ISSUE A CARD
---------------------------------
Not by IAM - `PutItem` on `GiftCardsTable` is needed by both functions, because this one writes
`GCTXN#`, `GCTXNID#` and `GCORDER#` rows, so a permission boundary cannot tell issuance from a
transaction record. The guarantee is STRUCTURAL: `gift_card_store.issue` is never imported or
called here, and test 104 asserts it by AST.

WIX SHOULD NEVER CALL /v1/redeem
--------------------------------
Section 1.3: Redeem fires on `Place Order`, which this architecture never calls, so a `WIX_SPI`
redemption is the detector for that prediction being wrong rather than an expected path. It is
alarmed on at a threshold of one, and a redeem for a card already holding a hold or a claim is
refused with `AlreadyRedeemed` rather than deducted - the two `orderId` namespaces are not
comparable, so refusal keyed on the CARD is the only sound guard.

THE ERROR BODY IS MINIMAL BY MEASUREMENT
----------------------------------------
Wix declares only `200` on all three methods and publishes no error schema at all; the nine
documented failures exist only as `x-wix-docs.errors[]` annotations. So the STATUS is the contract
we can honour exactly, and the body carries exactly `spiErrorData`'s own two fields, flat. Every
wrapper is an invention, and an invented wrapper is strictly worse than a minimal one.
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional

from lambda_utils.ecommerce import gift_card_settlement as settlement
from lambda_utils.ecommerce import gift_card_spi_auth as spi_auth
from lambda_utils.ecommerce import gift_card_store as store
from lambda_utils.ecommerce import payment_attempt
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

#: Secret NAME only. Every field is read by reference, lazily, inside the request.
SPI_SECRET_ID = os.environ.get(store.SECRET_ENV_KEY, store.SECRET_ID)

GIFT_CARDS_TABLE = os.environ.get(store.TABLE_ENV_KEY, store.DEFAULT_TABLE_NAME)
PAYMENT_ATTEMPTS_TABLE = os.environ.get("PAYMENT_ATTEMPTS_TABLE",
                                        payment_attempt.DEFAULT_TABLE_NAME)

#: The base path Wix appends `v1/balance` / `v1/redeem` / `v1/void` to.
ROUTE_PREFIX = "/wix-giftcards/"

#: route key -> the function that serves it. Exactly three, declared so the provisioner's route
#: list and this dispatch cannot drift and so a test can assert no fourth path exists.
SPI_ROUTES: Dict[str, str] = {
    "POST /wix-giftcards/v1/balance": "_balance",
    "POST /wix-giftcards/v1/redeem": "_redeem",
    "POST /wix-giftcards/v1/void": "_void",
}

#: A Wix-originated redemption has no `paymentAttemptId` - our attempts are minted by our own
#: checkout producers and a Wix `Place Order` never reaches one. The claim key still has to be
#: stable so a REPLAY is idempotent, so it is derived from the Wix order GUID under this prefix.
#: The prefix is also how `_void` knows not to write a stage onto an attempt row that does not
#: exist.
WIX_ATTEMPT_PREFIX = "WIXORDER-"

#: The two section 6.5 detectors. A single occurrence of either is actionable, which is why the
#: alarms sit at `Sum >= 1` rather than at a rate.
METRIC_NAMESPACE = "WecareGiftCards"
METRIC_WIX_SPI_REDEMPTION = "WixSpiRedemption"
METRIC_CHARGED_VS_CAPTURED = "ChargedVsCapturedMismatch"


# ── lazily built collaborators ────────────────────────────────────────────────

def _table(name: str):
    """A DynamoDB table resource, built per request.

    `boto3` is imported here rather than at module scope so the shared modules stay importable with
    no AWS at all, which is what makes the offline tests possible.
    """
    import boto3
    return boto3.resource("dynamodb",
                          region_name=os.environ.get("AWS_REGION", "us-east-1")).Table(name)


def _read_secret(secret_id: str) -> Mapping[str, Any]:
    """Read the SPI secret by id, at request time. No cache, deliberately.

    A module-scope read is frozen into a warm sandbox, so a key rotation would not take effect
    until every sandbox recycled - the defect fixed in `payments/razorpay-webhook` on 2026-09-19.
    Nothing here logs the result, not even its shape or its truthiness: CodeQL tracks taint across
    function boundaries and a ternary on a secret is still a finding.
    """
    import boto3
    client = boto3.client("secretsmanager",
                          region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return json.loads(client.get_secret_value(SecretId=secret_id)["SecretString"])


# ── responses ─────────────────────────────────────────────────────────────────

#: Substituted into the serialised body so a money field lands as a JSON NUMBER without a float
#: ever being constructed. See `_amount_token`.
_NUMBER_MARKER = "__WECARE_SPI_NUMBER_{}__"


def _amount_token(paise: Any) -> str:
    """The exact decimal rendering of integer paise, composed by integer arithmetic only.

    `int` division and `%02d`, so no float exists at any point. The SPI sends and expects JSON
    numbers (`"balance": 50.00`), and `float(paise) / 100` is precisely the construction R6.1
    forbids - `0.1 + 0.2 != 0.3`, and a one-paise error against the authoritative total must fail
    the payment closed rather than be rounded away.
    """
    value = int(paise)
    if value < 0:
        raise ValueError("a reported balance may not be negative")
    return f"{value // 100}.{value % 100:02d}"


def _render(fields: Dict[str, Any], numbers: Dict[str, int]) -> str:
    """Serialise a response body, with the named fields emitted as bare JSON numbers."""
    payload = dict(fields)
    tokens: Dict[str, str] = {}
    for index, key in enumerate(sorted(numbers)):
        marker = _NUMBER_MARKER.format(index)
        payload[key] = marker
        tokens[marker] = _amount_token(numbers[key])
    text = json.dumps(payload)
    for marker, token in tokens.items():
        text = text.replace(json.dumps(marker), token)
    return text


def _ok(fields: Dict[str, Any], numbers: Dict[str, int]) -> Dict[str, Any]:
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"},
            "body": _render(fields, numbers)}


def _unauthorized() -> Dict[str, Any]:
    """401 with an EMPTY body.

    No error detail, because the caller is either Wix - which does not need it - or an attacker,
    who must not get it.
    """
    return {"statusCode": 401, "headers": {}, "body": ""}


def _spi_error(error: store.GiftCardError) -> Dict[str, Any]:
    """Exactly `{"name", "applicationCode"}` at the documented status, and no third key."""
    name = error.spi_name or "GiftCardNotFound"
    application_code, status = store.SPI_ERRORS[name]
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"name": name, "applicationCode": application_code})}


def _metric(name: str, detail: Dict[str, Any]) -> None:
    """One EMF line, so the two section 6.5 alarms have something to alarm on.

    Amounts in paise and our own identifiers only. `payment_status.entity_summary` already draws
    that line the same way: paise are not a disclosure and are what makes the line reconcilable.
    """
    logger.warning(json.dumps({
        **detail,
        "_aws": {"CloudWatchMetrics": [{"Namespace": METRIC_NAMESPACE, "Dimensions": [[]],
                                        "Metrics": [{"Name": name, "Unit": "Count"}]}]},
        name: 1,
    }))


# ── request validation ────────────────────────────────────────────────────────

def _exact_paise(amount: Any) -> int:
    """A documented SPI `amount` (a JSON number) as integer paise, or refuse it.

    Arrives as a `Decimal` because `gift_card_spi_auth` parses every claim with
    `parse_float=Decimal`. A third decimal place is a request for a fraction of a paise and is
    REFUSED rather than rounded: rounding would charge a figure nobody agreed to.
    """
    if isinstance(amount, bool):
        raise store.GiftCardValidationError("INVALID_AMOUNT", "an amount is required")
    if isinstance(amount, int):
        value = Decimal(amount)
    elif isinstance(amount, Decimal):
        value = amount
    elif isinstance(amount, str):
        # Accepted because a conforming caller may quote the number; parsed exactly, never
        # through `float`.
        try:
            value = Decimal(amount)
        except Exception as error:  # noqa: BLE001
            raise store.GiftCardValidationError("INVALID_AMOUNT",
                                                "the amount is not a decimal") from error
    else:
        raise store.GiftCardValidationError("INVALID_AMOUNT", "the amount is not a number")
    if not value.is_finite():
        raise store.GiftCardValidationError("INVALID_AMOUNT", "the amount is not finite")
    scaled = value * 100
    if scaled != scaled.to_integral_value():
        raise store.GiftCardValidationError(
            "SUB_PAISE_AMOUNT", "an amount finer than one paise is refused, never rounded")
    return store.value_paise(int(scaled))


def _optional_text(value: Any, *, maximum: int) -> str:
    """`locationId` and friends: accepted, bounded, and ignored. Single-location seller."""
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("value")
    if value is None:
        return ""
    text = str(value)
    if len(text) > maximum:
        raise store.GiftCardValidationError("INVALID_FIELD", "an optional field is too long")
    return text


def _pin(request: Mapping[str, Any]) -> Optional[str]:
    value = request.get("pin")
    if isinstance(value, dict):
        value = value.get("value")
    if value in (None, ""):
        return None
    return str(value)


def _currency(request: Mapping[str, Any], context: spi_auth.Context, *,
              from_request: bool) -> str:
    """`INR`, compared explicitly.

    `RedeemRequest` carries `currencyCode`; `GetBalanceRequest` and `VoidRequest` do not, so those
    two read the envelope's own `metadata.currency`, which is documented ISO 4217. Absence is
    `MissingCurrency` (428) and a different currency is `CurrencyNotSupported` (400) - two
    different answers because they are two different faults.
    """
    declared = request.get("currencyCode") if from_request else context.currency
    return store.assert_currency(declared, required=True)


# ── the three methods ─────────────────────────────────────────────────────────

def _balance(request: Mapping[str, Any], context: spi_auth.Context, *,
             cards: Any, secret: Mapping[str, Any], now: int) -> Dict[str, Any]:
    """`{balance, currencyCode, externalId}` and no fourth field."""
    currency = _currency(request, context, from_request=False)
    _optional_text(request.get("locationId"), maximum=50)
    card = _resolve_card(request, cards=cards, secret=secret, now=now)
    logger.info(json.dumps({"event": "gift_card_balance_read",
                            "requestId": context.request_id,
                            "giftCardId": card.get("giftCardId"),
                            "codeLast4": store.masked(card.get("codeLast4"))}))
    return _ok({"currencyCode": currency,
                "externalId": str(card.get("giftCardId") or "")},
               {"balance": int(card.get("balancePaise") or 0)})


def _redeem(request: Mapping[str, Any], context: spi_auth.Context, *,
            cards: Any, secret: Mapping[str, Any], now: int) -> Dict[str, Any]:
    """`{remainingBalance, currencyCode, transactionId}`.

    Refuses with `AlreadyRedeemed` (409) and deducts NOTHING when the card already carries a hold
    or a claim. Under DECISION 5 that check is one exact-key `GetItem` on `GIFTCARD#<codeHash>`,
    not a prefix scan - and it is the whole of the two-namespace double-spend defence, because our
    `paymentAttemptId` and Wix's `orderId` are not comparable under any naming.
    """
    currency = _currency(request, context, from_request=True)
    _optional_text(request.get("locationId"), maximum=50)
    order_id = str(request.get("orderId") or "")
    if not order_id:
        raise store.GiftCardValidationError("INVALID_ORDER_ID", "an orderId is required")
    amount = _exact_paise(request.get("amount"))
    card = _resolve_card(request, cards=cards, secret=secret, now=now)
    digest = card["giftCardKey"][len(store.PREFIX_CARD):]

    holder = store.reserved_by(card, now_ms=now * 1000)
    if holder:
        _metric(METRIC_WIX_SPI_REDEMPTION, {
            "event": "gift_card_wix_spi_redeem_refused",
            "requestId": context.request_id,
            "giftCardId": card.get("giftCardId"),
            "codeLast4": store.masked(card.get("codeLast4")),
            "reason": "ALREADY_RESERVED"})
        raise store.AlreadyRedeemed("this gift card is already spoken for")

    attempt_id = WIX_ATTEMPT_PREFIX + order_id
    store.bind_wix_order(cards, wix_order_id=order_id, attempt_id=attempt_id)
    outcome = store.redeem(cards, code_hash=digest, attempt_id=attempt_id,
                           amount_paise=amount, source=store.SOURCE_WIX_SPI,
                           wix_order_id=order_id)
    # Section 1.3 predicts this never happens. Its appearance IS the detector for that prediction
    # being wrong, which is why a single occurrence alarms.
    _metric(METRIC_WIX_SPI_REDEMPTION, {
        "event": "gift_card_wix_spi_redemption",
        "requestId": context.request_id,
        "giftCardId": card.get("giftCardId"),
        "codeLast4": store.masked(card.get("codeLast4")),
        "amountPaise": amount,
        "transactionId": outcome["transactionId"]})
    return _ok({"currencyCode": currency, "transactionId": outcome["transactionId"]},
               {"remainingBalance": int(outcome["remainingBalancePaise"])})


def _void(request: Mapping[str, Any], context: spi_auth.Context, *,
          cards: Any, secret: Mapping[str, Any], now: int) -> Dict[str, Any]:
    """`{remainingBalance, currencyCode}`.

    Resolved from the `transactionId` ALONE, because `VoidRequest` carries no code. DECISION 9 put
    `paymentAttemptId` on the `GCTXNID#` pointer row, which is what makes the `GC_VOIDED` stage
    write composable from here - without it the SPI would hold an `UpdateItem` grant on
    PaymentAttemptsTable for a call it could not build.
    """
    currency = _currency(request, context, from_request=False)
    _optional_text(request.get("locationId"), maximum=50)
    transaction_id = str(request.get("transactionId") or "")
    if not transaction_id:
        raise store.GiftCardValidationError("INVALID_TRANSACTION_ID",
                                            "a transactionId is required")
    outcome = store.void(cards, transaction_id=transaction_id)

    attempt_id = outcome.get("paymentAttemptId") or ""
    if attempt_id and not attempt_id.startswith(WIX_ATTEMPT_PREFIX):
        try:
            settlement.advance(_table(PAYMENT_ATTEMPTS_TABLE), attempt_id=attempt_id,
                               stage=settlement.GC_VOIDED)
        except settlement.StageRegressed:
            # The ledger already moved and is authoritative. A refused stage write means another
            # writer got there first, which is not a reason to tell Wix the void failed.
            logger.error(json.dumps({"event": "gift_card_void_stage_regressed",
                                     "requestId": context.request_id,
                                     "paymentAttemptId": attempt_id}))
    logger.warning(json.dumps({"event": "gift_card_voided",
                               "requestId": context.request_id,
                               "paymentAttemptId": attempt_id,
                               "codeLast4": store.masked(outcome.get("codeLast4")),
                               "transactionId": outcome["transactionId"],
                               "voided": outcome["voided"]}))
    return _ok({"currencyCode": currency},
               {"remainingBalance": int(outcome["remainingBalancePaise"])})


def _resolve_card(request: Mapping[str, Any], *, cards: Any, secret: Mapping[str, Any],
                  now: int) -> Dict[str, Any]:
    """Code -> HMAC -> exact-key read -> spendable -> PIN. One answer for every refusal.

    A malformed code, an unknown code and a wrong PIN all raise `GiftCardNotFound`: three distinct
    answers would turn the endpoint into a code-validity oracle, and a gift-card code is bearer
    value.

    `appInstanceId` is deprecated and is never consulted for identity - identity comes from the
    verified JWT, and trusting a body field for it would make the signature pointless.
    """
    pepper = store.read_pepper(lambda _secret_id: secret, secret_id=SPI_SECRET_ID)
    digest = store.code_hash(request.get("code"), pepper=pepper)
    card = store.get_card(cards, code_hash=digest)
    card = store.assert_spendable(card, now_ms=now * 1000)
    store.verify_pin(card, _pin(request), pepper=pepper)
    return card


# ── dispatch ──────────────────────────────────────────────────────────────────

def _route_key(event: Mapping[str, Any]) -> str:
    context = event.get("requestContext") or {}
    http = context.get("http") or {}
    method = str(http.get("method") or event.get("httpMethod") or "").upper()
    raw = context.get("routeKey") or event.get("routeKey") or ""
    if raw and " " in str(raw):
        return str(raw)
    path = str(http.get("path") or event.get("path") or "")
    if ROUTE_PREFIX in path:
        path = ROUTE_PREFIX + path.split(ROUTE_PREFIX, 1)[1]
    return f"{method} {path}"


def handler(event, context):  # noqa: ARG001 - Lambda signature
    """Verify FIRST, then route, then touch a table. In that order, always.

    The verification call sits above the route lookup deliberately: a bad token must not reveal
    which of the three paths exists, and it must not reach a table even on a path that does not.
    """
    route = _route_key(event or {})
    now = _now()

    try:
        secret = _read_secret(SPI_SECRET_ID)
        verified = spi_auth.verify(
            (event or {}).get("body"),
            headers=(event or {}).get("headers") or {},
            now=now,
            reader=lambda _secret_id: secret,
            is_base64_encoded=bool((event or {}).get("isBase64Encoded")),
            secret_id=SPI_SECRET_ID)
    except spi_auth.SpiUnauthorized:
        # No detail, no claim value, no token segment. The WARN line carries the route only.
        logger.warning(json.dumps({"event": "gift_card_spi_unauthorized", "route": route}))
        return _unauthorized()
    except Exception as exc:  # noqa: BLE001 - an unreadable secret is still a refusal, not a 500
        logger.error(json.dumps({"event": "gift_card_spi_verification_failed",
                                 "route": route, "reason": type(exc).__name__}))
        return _unauthorized()

    served = SPI_ROUTES.get(route)
    if not served:
        logger.warning(json.dumps({"event": "gift_card_spi_unknown_route", "route": route,
                                   "requestId": verified.context.request_id}))
        return {"statusCode": 404, "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"name": "TransactionNotFound",
                                    "applicationCode": "TRANSACTION_NOT_FOUND"})}

    try:
        return globals()[served](verified.request, verified.context,
                                 cards=_table(GIFT_CARDS_TABLE), secret=secret, now=now)
    except store.GiftCardError as refusal:
        if refusal.spi_name:
            logger.info(json.dumps({"event": "gift_card_spi_refused", "route": route,
                                    "requestId": verified.context.request_id,
                                    "name": refusal.spi_name}))
            return _spi_error(refusal)
        # A refusal with no documented SPI counterpart - a sub-paise amount, an absent orderId,
        # an amount above the ceiling. Section 7.4 maps all three to a bare 400, and the body
        # keeps the same two-key shape so a consumer parses one form rather than two.
        logger.info(json.dumps({"event": "gift_card_spi_invalid_argument", "route": route,
                                "requestId": verified.context.request_id,
                                "refusalCode": refusal.code}))
        return {"statusCode": 400, "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"name": refusal.code, "applicationCode": refusal.code})}
    except store.GiftCardStoreUnavailable as exc:
        logger.error(json.dumps({"event": "gift_card_spi_store_unavailable", "route": route,
                                 "requestId": verified.context.request_id,
                                 "reason": type(exc).__name__}))
        return {"statusCode": 503, "headers": {}, "body": ""}
    except Exception as exc:  # noqa: BLE001
        logger.error(json.dumps({"event": "gift_card_spi_failed", "route": route,
                                 "requestId": verified.context.request_id,
                                 "reason": type(exc).__name__}))
        return {"statusCode": 503, "headers": {}, "body": ""}


def _now() -> int:
    """Epoch SECONDS as an int. `int(time.time())`, never the float itself.

    One conversion at the boundary, so no float reaches a comparison or a stored value.
    """
    return int(time.time())
