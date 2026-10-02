"""The SPI handler against the documented contract: three paths, exact shapes, nine errors.

Design reference: `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md`
sections 1.1 (the measured schemas), 1.1.1 (Wix documents NO error body), 5.2 (why the route carries
no authorizer) and 7.4 (error handling), and the test list in section 9.1 (tests 22-41, including
28a and 28b).

The handler is driven END TO END here - a real signed JWT in, a real HTTP response dict out, with
the ledger behind an in-memory table. The only things stubbed are the Secrets Manager read, the
DynamoDB resource and the clock, because those are the three ambient dependencies and everything
else is the contract under test.

Tests 16 and 17 from the auth list live here too, and deliberately: "verification happens before the
body is interpreted" and "before any table access" are properties of the HANDLER's ordering, and the
only way to assert them is with the store as a spy that records zero calls.
"""

from __future__ import annotations

import ast
import base64
import importlib.util
import json
import pathlib
import sys
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from coupon_fake_dynamo import FakeTable  # noqa: E402
from lambda_utils.ecommerce import gift_card_settlement as gcs  # noqa: E402
from lambda_utils.ecommerce import gift_card_spi_auth as auth  # noqa: E402
from lambda_utils.ecommerce import gift_card_store as gc  # noqa: E402

HANDLER_PATH = ROOT / "amplify/functions/ecommerce/wix-giftcard-spi/handler.py"
HANDLER_SOURCE = HANDLER_PATH.read_text(encoding="utf-8")
HANDLER_TREE = ast.parse(HANDLER_SOURCE, filename=str(HANDLER_PATH))
FIXTURES = ROOT / "tests" / "fixtures"

APP_ID = "11111111-2222-4333-8444-555555555555"
INSTANCE_ID = "99999999-8888-4777-8666-555555555555"
PEPPER = "pepper-for-tests-only"
CODE = "WDGC0000TEST0001"
PIN = "4321"
NOW = 1_700_000_000
WIX_ORDER = "cc000000-0000-4000-8000-00000000ord1"


@pytest.fixture(scope="module")
def keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {
        "private": private,
        "public_pem": private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii"),
    }


@pytest.fixture(scope="module")
def spi():
    """The handler module, loaded by path because its directory name carries a dash."""
    spec = importlib.util.spec_from_file_location("wix_giftcard_spi_handler", HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wix_giftcard_spi_handler"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("wix_giftcard_spi_handler", None)


def _segment(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def sign(keypair, payload: dict, *, alg: str = "RS256") -> str:
    header = {"alg": alg, "typ": "JWT"}
    signing_input = (_segment(json.dumps(header).encode("utf-8")) + "."
                     + _segment(json.dumps(payload).encode("utf-8")))
    signature = keypair["private"].sign(signing_input.encode("ascii"), padding.PKCS1v15(),
                                        hashes.SHA256())
    return signing_input + "." + _segment(signature)


def payload(name: str, **request_overrides) -> dict:
    body = json.loads((FIXTURES / f"wix_spi_{name}_jwt_payload.json").read_text(
        encoding="utf-8"))
    body.pop("_fixture", None)
    body["iat"] = NOW - 10
    body["exp"] = NOW + 600
    for key, value in request_overrides.items():
        if value is None:
            body["data"]["request"].pop(key, None)
        else:
            body["data"]["request"][key] = value
    return body


class Ledger:
    """The two tables the SPI may touch, behind one `_table(name)` and recording every call."""

    def __init__(self):
        self.cards = FakeTable(key_attr=gc.KEY_ATTRIBUTE,
                              indexes={gc.STATUS_INDEX: (gc.STATUS_ATTRIBUTE, "createdAt")})
        self.attempts = FakeTable(key_attr="paymentAttemptId")
        self.resolved: list = []

    def resolve(self, name):
        self.resolved.append(name)
        return self.attempts if "PaymentAttempt" in name else self.cards

    @property
    def touched(self) -> bool:
        return bool(self.cards.calls or self.attempts.calls or self.resolved)


@pytest.fixture
def ledger(spi, keypair, monkeypatch):
    """A seeded ledger with the ambient three stubbed: the secret, the tables and the clock."""
    book = Ledger()
    gc.issue(book.cards, initial_value_paise=100000, pepper=PEPPER, code=CODE, pin=PIN,
             clock=lambda: NOW)
    book.cards.calls.clear()

    secret = {auth.PUBLIC_KEY_FIELD: keypair["public_pem"],
              auth.APP_ID_FIELD: APP_ID,
              auth.INSTANCE_ID_FIELD: INSTANCE_ID,
              gc.PEPPER_FIELD: PEPPER}
    monkeypatch.setattr(spi, "_read_secret", lambda _secret_id: secret)
    monkeypatch.setattr(spi, "_table", book.resolve)
    monkeypatch.setattr(spi, "_now", lambda: NOW)
    return book


def call(spi, route: str, token, *, is_base64=False, headers=None):
    return spi.handler({
        "body": token,
        "isBase64Encoded": is_base64,
        "headers": headers or {"content-type": "application/jwt"},
        "requestContext": {"routeKey": route, "http": {"method": route.split(" ")[0],
                                                       "path": route.split(" ", 1)[1]}},
    }, None)


def digest() -> str:
    return gc.code_hash(CODE, pepper=PEPPER)


def body_of(response) -> dict:
    return json.loads(response["body"])


# ── 22 / 23: the path surface ─────────────────────────────────────────────────

def test_the_three_documented_paths_are_served(spi, ledger, keypair):
    """`v1/balance`, `v1/redeem`, `v1/void`. Wix appends these to the registered `deploymentUri`."""
    assert set(spi.SPI_ROUTES) == {"POST /wix-giftcards/v1/balance",
                                   "POST /wix-giftcards/v1/redeem",
                                   "POST /wix-giftcards/v1/void"}
    balance = call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, payload("get_balance")))
    assert balance["statusCode"] == 200
    redeem = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    assert redeem["statusCode"] == 200
    transaction_id = body_of(redeem)["transactionId"]
    void = call(spi, "POST /wix-giftcards/v1/void",
                sign(keypair, payload("void", transactionId=transaction_id)))
    assert void["statusCode"] == 200


def test_no_fourth_spi_path_exists(spi, ledger, keypair):
    """The surface stays as wide as the design and no wider. Deliberately not a `{proxy+}`."""
    assert len(spi.SPI_ROUTES) == 3
    for unknown in ("POST /wix-giftcards/v1/issue", "POST /wix-giftcards/v1/disable",
                    "GET /wix-giftcards/v1/balance", "POST /wix-giftcards/v2/balance"):
        response = call(spi, unknown, sign(keypair, payload("get_balance")))
        assert response["statusCode"] == 404
    # And no table was touched on an unknown path, even with a VALID token.
    assert not ledger.cards.calls


# ── 24 / 25 / 26 / 27: exact response shapes ──────────────────────────────────

def test_get_balance_returns_exactly_balance_currency_and_external_id(spi, ledger, keypair):
    """No extra field. The guidance is explicit that a response not matching the specification will
    not be handled correctly, so an "extra but harmless" field is a contract breach."""
    response = call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, payload("get_balance")))
    assert response["statusCode"] == 200
    assert set(body_of(response)) == {"balance", "currencyCode", "externalId"}
    assert body_of(response)["balance"] == 1000.00
    assert body_of(response)["currencyCode"] == "INR"


def test_redeem_returns_exactly_remaining_balance_currency_and_transaction_id(spi, ledger,
                                                                             keypair):
    response = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    assert response["statusCode"] == 200
    assert set(body_of(response)) == {"remainingBalance", "currencyCode", "transactionId"}
    assert body_of(response)["remainingBalance"] == 600.00
    assert 1 <= len(body_of(response)["transactionId"]) <= 100


def test_void_returns_exactly_remaining_balance_and_currency(spi, ledger, keypair):
    redeemed = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    response = call(spi, "POST /wix-giftcards/v1/void",
                    sign(keypair, payload("void",
                                         transactionId=body_of(redeemed)["transactionId"])))
    assert response["statusCode"] == 200
    assert set(body_of(response)) == {"remainingBalance", "currencyCode"}
    assert body_of(response)["remainingBalance"] == 1000.00
    assert "transactionId" not in body_of(response), "VoidResponse carries no transactionId"


def test_external_id_is_the_gift_card_id_never_the_code(spi, ledger, keypair):
    """`externalId` is documented as "External ID in the gift card provider's system". Ours is a
    UUIDv7 - opaque, not secret, and nothing derived from the code."""
    response = call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, payload("get_balance")))
    external = body_of(response)["externalId"]
    card = gc.get_card(ledger.cards, code_hash=digest())
    assert external == card["giftCardId"]
    assert external != CODE
    assert CODE not in response["body"]
    assert digest() not in response["body"]
    assert "0001" not in external


# ── 28 / 28a / 28b: the nine documented errors ────────────────────────────────

#: Transcribed from each method's own `errors[]` array. `AlreadyVoided`'s application code is
#: `ALREADY_VOIDED`, which revision 2 left blank and which made this test unwritable for that row.
DOCUMENTED_ERRORS = [
    ("GiftCardNotFound", "GIFT_CARD_NOT_FOUND", 404),
    ("GiftCardDisabled", "GIFT_CARD_DISABLED", 428),
    ("GiftCardExpired", "GIFT_CARD_EXPIRED", 428),
    ("MissingCurrency", "MISSING_CURRENCY", 428),
    ("InsufficientFunds", "INSUFFICIENT_FUNDS", 428),
    ("AlreadyRedeemed", "ALREADY_REDEEMED", 409),
    ("CurrencyNotSupported", "CURRENCY_NOT_SUPPORTED", 400),
    ("TransactionNotFound", "TRANSACTION_NOT_FOUND", 404),
    ("AlreadyVoided", "ALREADY_VOIDED", 409),
]


@pytest.mark.parametrize("name,application_code,http_code", DOCUMENTED_ERRORS)
def test_every_documented_error_maps_to_its_documented_status(name, application_code, http_code):
    """The full section 1.1 table, against the error classes that carry it."""
    assert gc.SPI_ERRORS[name] == (application_code, http_code)
    matching = [cls for cls in vars(gc).values()
                if isinstance(cls, type) and issubclass(cls, gc.GiftCardError)
                and getattr(cls, "spi_name", "") == name]
    assert len(matching) == 1, f"{name} has {len(matching)} error classes"
    assert matching[0].status == http_code
    assert matching[0]().application_code == application_code


def test_the_nine_documented_errors_are_all_of_them():
    """No tenth row invented, and none dropped. `errorType` is `SPI` on every one."""
    assert set(gc.SPI_ERRORS) == {name for name, _, _ in DOCUMENTED_ERRORS}
    assert len(gc.SPI_ERRORS) == 9


def test_each_documented_error_is_reachable_through_the_handler(spi, ledger, keypair,
                                                                monkeypatch):
    """Driving all nine, because a mapping nothing produces is a mapping nothing checks.

    `GiftCardExpired` is driven by moving the CLOCK rather than by editing the row, so the expiry
    comparison is exercised rather than asserted.
    """
    seen = {}

    def record(response):
        seen[body_of(response)["name"]] = response["statusCode"]

    # GiftCardNotFound - an unknown code.
    record(call(spi, "POST /wix-giftcards/v1/balance",
                sign(keypair, payload("get_balance", code="WDGC0000NOSUCH01", pin=None))))
    # MissingCurrency - the envelope carries no currency on a balance call.
    no_currency = payload("get_balance")
    no_currency["data"]["metadata"].pop("currency")
    record(call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, no_currency)))
    # CurrencyNotSupported - a redeem in another currency.
    record(call(spi, "POST /wix-giftcards/v1/redeem",
                sign(keypair, payload("redeem", currencyCode="USD"))))
    # InsufficientFunds - above the balance. Under its OWN Wix order id, because a failed redeem
    # leaves an unsettled claim keyed on that order, and a later call for the same order with a
    # different amount is a conflict rather than a replay.
    record(call(spi, "POST /wix-giftcards/v1/redeem",
                sign(keypair, payload("redeem", amount=2000.00,
                                      orderId="ee000000-0000-4000-8000-00000000ord9"))))
    # TransactionNotFound - a void for nothing.
    record(call(spi, "POST /wix-giftcards/v1/void",
                sign(keypair, payload("void", transactionId="01JNOSUCHTRANSACTION00001"))))
    # AlreadyRedeemed - a card already held by one of our own purchases.
    gc.hold(ledger.cards, code_hash=digest(), attempt_id="attempt-1", amount_paise=40000,
            clock=lambda: NOW)
    record(call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem"))))
    gc.release(ledger.cards, code_hash=digest(), attempt_id="attempt-1", clock=lambda: NOW)
    # AlreadyVoided - the same transaction twice.
    redeemed = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    transaction_id = body_of(redeemed)["transactionId"]
    void_token = sign(keypair, payload("void", transactionId=transaction_id))
    assert call(spi, "POST /wix-giftcards/v1/void", void_token)["statusCode"] == 200
    record(call(spi, "POST /wix-giftcards/v1/void", void_token))
    # GiftCardDisabled.
    gc.disable(ledger.cards, code_hash=digest(), clock=lambda: NOW)
    record(call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, payload("get_balance"))))

    # GiftCardExpired - a fresh card with an expiry, and a clock past it.
    expiring = Ledger()
    gc.issue(expiring.cards, initial_value_paise=100000, pepper=PEPPER, code=CODE, pin=PIN,
             expires_at_ms=(NOW + 60) * 1000, clock=lambda: NOW)
    monkeypatch.setattr(spi, "_table", expiring.resolve)
    expired_payload = payload("get_balance")
    expired_payload["exp"] = NOW + 7200
    monkeypatch.setattr(spi, "_now", lambda: NOW + 3600)
    record(call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, expired_payload)))

    assert seen == {name: status for name, _, status in DOCUMENTED_ERRORS}


def test_an_error_body_carries_exactly_name_and_application_code(spi, ledger, keypair):
    """28a. Wix publishes NO error-response schema - `responses` declares only `200` on all three
    methods, and the nine failures exist only as `x-wix-docs.errors[]` annotations. So the STATUS is
    the contract we honour exactly, and the body is minimal rather than an invented wrapper: a
    consumer that ignores the body still sees the right status, whereas a consumer looking for a
    guessed key finds nothing either way.

    If Wix later publishes an envelope, this test and one function are the whole diff.
    """
    response = call(spi, "POST /wix-giftcards/v1/balance",
                    sign(keypair, payload("get_balance", code="WDGC0000NOSUCH01", pin=None)))
    assert response["statusCode"] == 404
    body = body_of(response)
    assert list(body) == ["name", "applicationCode"]
    assert body == {"name": "GiftCardNotFound", "applicationCode": "GIFT_CARD_NOT_FOUND"}
    for invented in ("spiErrorData", "details", "error", "message", "statusCode", "errorType"):
        assert invented not in body


def test_the_spi_error_name_is_the_spi_error_data_name_not_the_wix_error_class(spi, ledger,
                                                                              keypair):
    """28b. Both strings appear on the docs page: the OUTER `name` is Wix's own error class
    (`AlreadyVoidedWixError`) and `spiErrorData.name` is the value WE return (`AlreadyVoided`).
    Confusing them puts the wrong value in the right place."""
    redeemed = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    token = sign(keypair, payload("void",
                                 transactionId=body_of(redeemed)["transactionId"]))
    call(spi, "POST /wix-giftcards/v1/void", token)
    second = call(spi, "POST /wix-giftcards/v1/void", token)

    assert body_of(second)["name"] == "AlreadyVoided"
    assert "WixError" not in second["body"]
    for name in gc.SPI_ERRORS:
        assert not name.endswith("WixError")


# ── 29 / 30: no validity oracle ───────────────────────────────────────────────

def test_a_malformed_code_answers_not_found_not_bad_request(spi, ledger, keypair):
    """A malformed code is not a DIFFERENT answer from an unknown one, and that is deliberate."""
    for malformed in ("short", "has spaces", "x" * 25, "", "a_b_c_d_e_f_g"):
        response = call(spi, "POST /wix-giftcards/v1/balance",
                        sign(keypair, payload("get_balance", code=malformed, pin=None)))
        assert response["statusCode"] == 404
        assert body_of(response)["name"] == "GiftCardNotFound"


def test_a_wrong_pin_is_indistinguishable_from_an_unknown_code(spi, ledger, keypair):
    """Byte-identical responses. Three distinct answers for a malformed code, an unknown code and a
    wrong PIN would turn the endpoint into a code-validity oracle."""
    wrong_pin = call(spi, "POST /wix-giftcards/v1/balance",
                     sign(keypair, payload("get_balance", pin={"value": "0000"})))
    unknown = call(spi, "POST /wix-giftcards/v1/balance",
                   sign(keypair, payload("get_balance", code="WDGC0000NOSUCH01",
                                         pin={"value": "0000"})))
    assert wrong_pin["statusCode"] == unknown["statusCode"] == 404
    assert wrong_pin["body"] == unknown["body"]

    # And a missing PIN on a PIN-protected card answers the same way.
    missing = call(spi, "POST /wix-giftcards/v1/balance",
                   sign(keypair, payload("get_balance", pin=None)))
    assert missing["body"] == unknown["body"]


# ── 31 / 32 / 33: no float, anywhere ──────────────────────────────────────────

def test_amount_is_parsed_as_decimal_never_float(spi, ledger, keypair, monkeypatch):
    """`float` itself is made to raise, and a full redeem runs through the handler.

    The SPI sends `"amount": 400.00` as a JSON NUMBER, so the risk is at the entry point, before any
    of our own logic. `parse_float=Decimal` is the mitigation and it is not optional.
    """
    import builtins

    token = sign(keypair, payload("redeem"))

    def refuse(*_args, **_kwargs):
        raise AssertionError("a float was constructed on the SPI money path")

    monkeypatch.setattr(builtins, "float", refuse)
    response = call(spi, "POST /wix-giftcards/v1/redeem", token)
    assert response["statusCode"] == 200
    assert ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"] == 60000


def test_a_sub_paise_amount_is_refused_rather_than_rounded(spi, ledger, keypair):
    """`12.345` is a request for a fraction of a paise. Rounding it would charge a figure nobody
    agreed to, so it is refused - and the balance does not move."""
    before = ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"]
    for bad in (12.345, 0.001, 400.001):
        response = call(spi, "POST /wix-giftcards/v1/redeem",
                        sign(keypair, payload("redeem", amount=bad)))
        assert response["statusCode"] == 400
        assert body_of(response)["applicationCode"] == "SUB_PAISE_AMOUNT"
    assert ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"] == before


def test_the_balance_response_renders_a_json_number_without_constructing_a_float(spi, ledger,
                                                                                keypair,
                                                                                monkeypatch):
    """A JSON number, composed by integer arithmetic. `int` division and `%02d`, so `float(paise)
    / 100` - precisely the construction R6.1 forbids - never happens."""
    import builtins

    monkeypatch.setattr(builtins, "float",
                        lambda *_a, **_k: (_ for _ in ()).throw(
                            AssertionError("a float was constructed while rendering a balance")))
    response = call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, payload("get_balance")))

    # The raw body carries a bare number, not a quoted string.
    assert '"balance": 1000.00' in response["body"]
    assert '"1000.00"' not in response["body"]
    parsed = json.loads(response["body"], parse_float=Decimal)
    assert parsed["balance"] == Decimal("1000.00")
    assert isinstance(parsed["balance"], Decimal)


@pytest.mark.parametrize("paise,expected", [
    (0, "0.00"), (1, "0.01"), (99, "0.99"), (100, "1.00"), (12345, "123.45"),
    (99_999_999_999, "999999999.99"),
])
def test_the_amount_token_is_exact_at_every_boundary(spi, paise, expected):
    """Including the SPI maximum, which is the figure the whole ceiling exists to keep reportable."""
    assert spi._amount_token(paise) == expected


# ── 34 / 35 / 36 ──────────────────────────────────────────────────────────────

def test_a_non_inr_currency_is_refused_with_currency_not_supported(spi, ledger, keypair):
    """Compared EXPLICITLY, never inferred from the amount. An amount tells you a magnitude, not
    which currency it is in, and a wrong currency here is a wrong price charged."""
    response = call(spi, "POST /wix-giftcards/v1/redeem",
                    sign(keypair, payload("redeem", currencyCode="USD")))
    assert response["statusCode"] == 400
    assert body_of(response)["name"] == "CurrencyNotSupported"
    assert ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"] == 100000

    # Absence is a DIFFERENT fault from a different currency, and gets a different answer.
    response = call(spi, "POST /wix-giftcards/v1/redeem",
                    sign(keypair, payload("redeem", currencyCode=None)))
    assert response["statusCode"] == 428
    assert body_of(response)["name"] == "MissingCurrency"


def test_the_deprecated_app_instance_id_is_never_used_for_identity(spi, ledger, keypair):
    """Identity comes from the verified JWT. Trusting a BODY field for it would make the signature
    pointless - anyone could send any `appInstanceId`."""
    hostile = payload("get_balance", appInstanceId="ff000000-0000-4000-8000-00000000evil")
    response = call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, hostile))
    assert response["statusCode"] == 200, "a wrong appInstanceId must not change the outcome"

    # And the real check is on the ENVELOPE's instanceId, which a body field cannot reach.
    wrong_instance = payload("get_balance")
    wrong_instance["data"]["metadata"]["instanceId"] = {"value": "ff000000-0000-4000-8000-0bad"}
    assert call(spi, "POST /wix-giftcards/v1/balance",
                sign(keypair, wrong_instance))["statusCode"] == 401

    # Structurally: `appInstanceId` is read nowhere for a decision.
    reads = [node.lineno for node in ast.walk(HANDLER_TREE)
             if isinstance(node, ast.Constant) and node.value == "appInstanceId"]
    assert not reads, f"line {reads}: the handler reads appInstanceId"


def test_location_id_is_accepted_and_ignored(spi, ledger, keypair):
    """Single-location seller. Accepted and bounded so a hostile value cannot grow a row, and
    otherwise ignored rather than refused - refusing it would make a conforming call fail."""
    for value in ({"value": "loc-1"}, "loc-1", None):
        response = call(spi, "POST /wix-giftcards/v1/balance",
                        sign(keypair, payload("get_balance", locationId=value)))
        assert response["statusCode"] == 200
        assert "locationId" not in body_of(response)

    too_long = call(spi, "POST /wix-giftcards/v1/balance",
                    sign(keypair, payload("get_balance", locationId={"value": "x" * 300})))
    assert too_long["statusCode"] == 400


# ── 37 / 38 / 39: the AlreadyRedeemed refusal ─────────────────────────────────

def test_a_wix_redeem_for_a_card_with_a_hold_is_already_redeemed(spi, ledger, keypair):
    """HIGH-4's first half. A `/v1/redeem` carrying a WIX ORDER GUID against a card holding a
    `GCHOLD#<codeHash>#<paymentAttemptId>` row returns 409 and deducts NOTHING.

    Stricter than idempotency, deliberately: our `paymentAttemptId` and Wix's `orderId` are
    different namespaces, so a shared claim key cannot be the guard under any naming. The guard has
    to be the existence check, and it is keyed on the CARD - the one thing both sides agree on.
    """
    gc.hold(ledger.cards, code_hash=digest(), attempt_id="attempt-1", amount_paise=40000,
            clock=lambda: NOW)
    before = ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"]

    response = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    assert response["statusCode"] == 409
    assert body_of(response) == {"name": "AlreadyRedeemed",
                                "applicationCode": "ALREADY_REDEEMED"}
    assert ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"] == before
    assert not [key for key in ledger.cards.rows if key.startswith(gc.PREFIX_CLAIM)]


def test_a_wix_redeem_for_an_already_claimed_card_deducts_nothing(spi, ledger, keypair):
    """The same against a `GCORDER#` claim, with the balance asserted before and after. This is the
    test the review asked for by name."""
    gc.redeem(ledger.cards, code_hash=digest(), attempt_id="attempt-1", amount_paise=30000,
              clock=lambda: NOW)
    before = ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"]
    assert before == 70000

    response = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    assert response["statusCode"] == 409
    assert body_of(response)["applicationCode"] == "ALREADY_REDEEMED"
    assert ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"] == before


def test_the_already_redeemed_check_is_one_exact_key_get_not_a_prefix_scan(spi, ledger, keypair):
    """DECISION 5. The existence fact lives on the row whose key is already known, so the check is a
    `GetItem` on `GIFTCARD#<codeHash>` reading `activeHoldAttemptId` - never a prefix query and
    never a scan, because a GSI is eventually consistent and cannot gate a money decision."""
    gc.hold(ledger.cards, code_hash=digest(), attempt_id="attempt-1", amount_paise=40000,
            clock=lambda: NOW)
    ledger.cards.calls.clear()
    call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))

    assert ledger.cards.operations() == ["get_item"]
    assert ledger.cards.calls[0][1]["Key"] == {gc.KEY_ATTRIBUTE: gc.PREFIX_CARD + digest()}
    card = gc.get_card(ledger.cards, code_hash=digest())
    assert gc.reserved_by(card, now_ms=NOW * 1000) == "attempt-1"


def test_a_wix_redeem_with_no_hold_and_no_claim_is_honoured_and_marked_wix_spi(spi, ledger,
                                                                              keypair, caplog):
    """The conforming path, so the refusal above is NARROW rather than a blanket rejection.

    Section 1.3 predicts Wix never calls this endpoint, so `source: WIX_SPI` appearing IS the
    detector for that prediction being wrong - which is why it emits the metric the
    `wecare-gift-card-wix-spi-redemption` alarm fires on at a threshold of one.
    """
    import logging

    with caplog.at_level(logging.WARNING):
        response = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    assert response["statusCode"] == 200

    transaction = next(row for key, row in ledger.cards.rows.items()
                       if key.startswith(gc.PREFIX_TRANSACTION)
                       and not key.startswith(gc.PREFIX_TRANSACTION_ID))
    assert transaction["source"] == gc.SOURCE_WIX_SPI
    assert transaction["kind"] == gc.KIND_REDEEM

    emitted = " ".join(record.getMessage() for record in caplog.records)
    assert spi.METRIC_WIX_SPI_REDEMPTION in emitted
    assert "gift_card_wix_spi_redemption" in emitted
    assert CODE not in emitted, "a code reached a log line"


def test_a_replayed_wix_redeem_for_the_same_order_is_idempotent(spi, ledger, keypair):
    """A Wix-originated redemption has no `paymentAttemptId`, so the claim key is derived from the
    Wix order GUID. That keeps a REPLAY idempotent, which is the one property the claim row owes."""
    first = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    assert first["statusCode"] == 200
    # The card now carries a claim, so the stricter refusal applies on the second call.
    second = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    assert second["statusCode"] == 409
    assert ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"] == 60000
    claims = [key for key in ledger.cards.rows if key.startswith(gc.PREFIX_CLAIM)]
    assert claims == [gc.PREFIX_CLAIM + digest() + "#" + spi.WIX_ATTEMPT_PREFIX + WIX_ORDER]


# ── 40 / 41: the two pointer rows ─────────────────────────────────────────────

def test_a_wix_order_id_resolves_to_our_reference_through_the_pointer_row(spi, ledger, keypair):
    """`GCWIXORDER#<wixOrderId>` -> `paymentAttemptId`. It is what lets a Wix-originated call about
    a Wix order GUID be resolved to the purchase our own claim is keyed on."""
    call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    resolved = gc.resolve_attempt(ledger.cards, wix_order_id=WIX_ORDER)
    assert resolved == spi.WIX_ATTEMPT_PREFIX + WIX_ORDER
    with pytest.raises(gc.TransactionNotFound):
        gc.resolve_attempt(ledger.cards, wix_order_id="no-such-wix-order")


def test_a_void_arriving_by_transaction_id_reconciles_to_the_purchase(spi, ledger, keypair):
    """And when the redemption was OURS, the void additionally advances the attempt to `GC_VOIDED`
    through `advance()` - the write DECISION 9 made composable by putting `paymentAttemptId` on the
    pointer row."""
    ledger.attempts.seed({"paymentAttemptId": "attempt-1",
                          gcs.RANK_ATTRIBUTE: gcs.STAGE_RANK[gcs.GC_REDEEMED]})
    outcome = gc.redeem(ledger.cards, code_hash=digest(), attempt_id="attempt-1",
                        amount_paise=30000, clock=lambda: NOW)

    response = call(spi, "POST /wix-giftcards/v1/void",
                    sign(keypair, payload("void", transactionId=outcome["transactionId"])))
    assert response["statusCode"] == 200
    assert ledger.attempts.rows["attempt-1"][gcs.RANK_ATTRIBUTE] == \
        gcs.STAGE_RANK[gcs.GC_VOIDED]
    assert ledger.cards.rows[gc.PREFIX_CARD + digest()]["balancePaise"] == 100000


def test_a_void_of_a_wix_originated_redemption_writes_no_attempt_stage(spi, ledger, keypair):
    """A Wix-originated claim key is synthetic - there is no attempt row behind it - so advancing a
    stage against it would write a row that represents no purchase. Skipped deliberately, and the
    prefix is how the handler knows."""
    redeemed = call(spi, "POST /wix-giftcards/v1/redeem", sign(keypair, payload("redeem")))
    ledger.attempts.calls.clear()
    response = call(spi, "POST /wix-giftcards/v1/void",
                    sign(keypair, payload("void",
                                         transactionId=body_of(redeemed)["transactionId"])))
    assert response["statusCode"] == 200
    assert ledger.attempts.calls == []


# ── 16 / 17: verification is FIRST ────────────────────────────────────────────

def test_verification_happens_before_the_body_is_interpreted(spi, ledger, keypair):
    """The store as a spy: ZERO calls on a bad token, on every one of the three paths."""
    forged = sign(keypair, payload("redeem"))
    tampered = forged[:-8] + ("A" * 8 if forged[-8:] != "A" * 8 else "B" * 8)
    for route in spi.SPI_ROUTES:
        ledger.cards.calls.clear()
        ledger.attempts.calls.clear()
        response = call(spi, route, tampered)
        assert response["statusCode"] == 401
        assert response["body"] == ""
        assert ledger.cards.calls == []
        assert ledger.attempts.calls == []


def test_verification_happens_before_any_table_access(spi, ledger, keypair):
    """Pins the ordering section 5.2 relies on. The route carries no API Gateway authorizer - Wix
    presents its own JWT, not a Cognito token - so with WAF removed this handler-level check plus
    stage throttling is the WHOLE filter in front of the endpoint."""
    for body in ("", "{}", "not.a.jwt", json.dumps({"data": {"request": {"code": "x"}}})):
        ledger.cards.calls.clear()
        ledger.resolved.clear()
        response = call(spi, "POST /wix-giftcards/v1/balance", body)
        assert response["statusCode"] == 401
        assert not ledger.touched, f"a table was resolved for body {body!r}"

    # Structurally: `spi_auth.verify` is called above the route lookup, so a bad token cannot even
    # reveal which of the three paths exists.
    function = next(node for node in ast.walk(HANDLER_TREE)
                    if isinstance(node, ast.FunctionDef) and node.name == "handler")
    rendered = ast.unparse(function)
    assert rendered.index("spi_auth.verify") < rendered.index("SPI_ROUTES.get")
    assert rendered.index("spi_auth.verify") < rendered.index("GIFT_CARDS_TABLE")


def test_an_expired_token_is_refused_by_the_handler_with_an_empty_body(spi, ledger, keypair):
    stale = payload("get_balance")
    stale["exp"] = NOW - 3600
    response = call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, stale))
    assert response["statusCode"] == 401
    assert response["body"] == ""
    assert response["headers"] == {}
    assert not ledger.cards.calls


def test_an_unreadable_secret_is_a_refusal_rather_than_a_five_hundred(spi, ledger, keypair,
                                                                     monkeypatch):
    """Fail CLOSED on our own misconfiguration. A 500 here would tell a caller the difference
    between "your token is wrong" and "our key is missing"."""
    def explode(_secret_id):
        raise RuntimeError("AccessDeniedException")

    monkeypatch.setattr(spi, "_read_secret", explode)
    response = call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, payload("get_balance")))
    assert response["statusCode"] == 401
    assert response["body"] == ""


# ── the structural guarantees ─────────────────────────────────────────────────

def test_the_spi_handler_cannot_issue_a_card():
    """IAM cannot distinguish issuance from a transaction record - both are a `PutItem` on the same
    table, and this function must write `GCTXN#`, `GCTXNID#` and `GCORDER#` rows. So the guarantee
    is STRUCTURAL: `issue` is never named here, and there is no code path to it."""
    calls = {ast.unparse(node.func) for node in ast.walk(HANDLER_TREE)
             if isinstance(node, ast.Call)}
    assert "store.issue" not in calls
    assert "gift_card_store.issue" not in calls
    # Over the AST, not the text: the paragraph explaining why issuance is elsewhere necessarily
    # names it.
    reached = {node.attr for node in ast.walk(HANDLER_TREE)
              if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
              and node.value.id == "store"}
    for forbidden in ("issue", "generate_code", "pin_hash", "disable", "credit"):
        assert forbidden not in reached, f"the SPI handler reaches store.{forbidden}"


def test_the_handler_reads_its_secret_lazily_and_logs_nothing_from_it(spi, ledger, keypair):
    """One read per request, and nothing derived from the value reaches a logging expression - not
    even reduced to a bool, because CodeQL tracks taint across function boundaries."""
    reads: list = []
    original = spi._read_secret
    spi._read_secret = lambda secret_id: (reads.append(secret_id) or original(secret_id))
    try:
        call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, payload("get_balance")))
        call(spi, "POST /wix-giftcards/v1/balance", sign(keypair, payload("get_balance")))
    finally:
        spi._read_secret = original
    assert reads == [spi.SPI_SECRET_ID, spi.SPI_SECRET_ID], "the secret was cached"

    tainted = {"secret", "pepper", "public_key", "public_key_pem", "code"}
    for node in ast.walk(HANDLER_TREE):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "logger"):
            continue
        reached = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
        assert not reached & tainted, (
            f"line {node.lineno} logs {sorted(reached & tainted)}")


def test_no_decision_in_the_handler_compares_a_raw_payment_word():
    """`captured` is AST-banned at decision points across the fleet. This handler has no
    payment-status decision - the gift-card ladder is its own module - so the ban applies while the
    import assertion does not, which is why both new handlers belong in `RAW_SCAN_ONLY_FILES`."""
    offenders = []
    for node in ast.walk(HANDLER_TREE):
        if not isinstance(node, ast.Compare):
            continue
        literals = {operand.value for operand in [node.left, *node.comparators]
                    if isinstance(operand, ast.Constant) and isinstance(operand.value, str)}
        if "captured" in literals:
            offenders.append(f"line {node.lineno}: compares 'captured' raw")
    assert not offenders, "\n  ".join(offenders)
    # Over the AST: a prose reference to `payment_status.entity_summary` explaining why paise are
    # loggable is not an import, and a text search cannot tell the two apart.
    imports = {(node.module or "") for node in ast.walk(HANDLER_TREE)
               if isinstance(node, ast.ImportFrom)}
    imported = {alias.name for node in ast.walk(HANDLER_TREE)
                if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert not any("payment_status" in module for module in imports)
    assert "payment_status" not in imported, (
        "an unused payment_status import would make the gate's import assertion mean less")
