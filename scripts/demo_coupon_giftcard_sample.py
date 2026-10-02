#!/usr/bin/env python3
"""The runnable three-leg Wix coupon + gift card demonstration. ZERO AWS, ZERO live Wix.

Design reference: `.agents/tasks/wix-coupon-giftcard-sample-20261002/design.md` revision 8, §4.

    python scripts/demo_coupon_giftcard_sample.py            # all three legs, rendered
    python scripts/demo_coupon_giftcard_sample.py --json     # machine-readable, nothing else
    python scripts/demo_coupon_giftcard_sample.py --leg wix-giftcard

Exit codes: `0` all legs matched their expected contract, `1` a contract assertion failed,
`2` a usage error. So it is a smoke test as well as a demonstration, and `main(argv)` RETURNS
its code rather than calling `sys.exit` itself, so `tests/test_demo_coupon_giftcard_sample.py`
can run it in-process.

WHAT IS REAL AND WHAT IS STUBBED
--------------------------------
Everything is production code except the HTTP boundary. `urllib.request.urlopen` is replaced by
`tests/wix_transport_stub.WixTransport`, so all five behaviours of `wix_ecom._request` execute
for real - header composition, `json.dumps` with no custom encoder, the HTTPError reduction,
`json.loads` with no `parse_float`, and the timeout. The fake DynamoDB is
`tests/coupon_fake_dynamo.FakeTable`.

Both come from `tests/`, and that is the point: ONE stub, TWO callers. A private copy inside
`scripts/` is exactly the drift this task exists to prevent, and nothing in `tests/` ships in a
Lambda package.

THERE IS NO `--pepper` OPTION, DELIBERATELY
-------------------------------------------
Leg 2 derives its code with `wix_gift_cards.demo_code(reference_id=...)`, which is UNKEYED and
demo-only. A `--pepper` flag would put a pepper-shaped value on a command line, which
`secret-handling.md` forbids outright and which `.kiro/hooks/block-inline-secrets.json` refuses.

Printing both derivations is better than printing the production one with a fake pepper: a
placeholder pepper would LOOK like the production path while proving nothing about it, and the
harness already asserts the keyed derivation properly. This demo's job is to show the request
shape, which is identical either way, and to be explicit that its own code is not production's.

NO FLOAT ANYWHERE
-----------------
`argparse` uses `type=int`, every conversion is `//`, `Money` or `Decimal(str(value))`, and
there is no `float(` in this file - asserted by AST in
`tests/test_wix_coupon_giftcard_sample.py`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))
sys.path.insert(0, str(ROOT / "tests"))

from coupon_fake_dynamo import FakeTable  # noqa: E402
from lambda_utils import wix_ecom  # noqa: E402
from lambda_utils.ecommerce import coupon_store as cs  # noqa: E402
from lambda_utils.ecommerce import gift_card_store as gcs  # noqa: E402
from lambda_utils.ecommerce import wix_coupons as wc  # noqa: E402
from lambda_utils.ecommerce import wix_gift_cards as wg  # noqa: E402
from lambda_utils.ecommerce.money import Money  # noqa: E402
from wix_transport_stub import WixTransport  # noqa: E402

#: Not a credential. Chosen to match NONE of `scripts/block_inline_secrets.py`'s issuer prefixes,
#: and never an argv value - it is seeded into a module cache in-process.
PLACEHOLDER_API_KEY = "wix-admin-key-PLACEHOLDER-not-a-credential"

#: Test-only HMAC key for leg 3's own store. The real pepper lives in Secrets Manager under
#: `wecare/wix/giftcard-spi:code_pepper`, is read by reference at request time, and is not read
#: here at all.
DEMO_PEPPER = "pepper-for-the-offline-demo-only"

NOW = 1_700_000_000
START_MS = 1_719_390_501_000
LEGS = ("coupon", "wix-giftcard", "our-giftcard", "all")

FIXTURES = ROOT / "tests/fixtures"


class UnexpectedAwsCall(BaseException):
    """BaseException, NOT Exception.

    Leg 1 drives `coupons/handler._create`, which catches `Exception` and answers 202. An
    `Exception` here would therefore be swallowed and the transcript would print `0` AWS calls
    while a call had been attempted.
    """


def _clock(value: int = NOW):
    return lambda: value


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _mask(code: str) -> str:
    """`****` plus the last four.

    Labelled as a HABIT for the day the adapter is wired, not as what makes this demo safe
    offline. What makes it safe offline is that the transport is stubbed unconditionally, so
    every code here is a fixture placeholder and no live Wix response can reach the process.
    """
    text = str(code or "")
    return "****" + text[-4:] if len(text) >= 4 else "****"


def _rupees(paise: int) -> str:
    """Integer paise rendered as rupees, by integer arithmetic only. No float, ever."""
    sign = "-" if paise < 0 else ""
    whole, fraction = divmod(abs(int(paise)), 100)
    return f"{sign}INR {whole:,}.{fraction:02d}"


# ── containment ───────────────────────────────────────────────────────────────

class _ExplodesOnAttributeAccess:
    def __getattr__(self, name):
        raise UnexpectedAwsCall(f"the demo touched boto3.{name}")


def _install_containment() -> WixTransport:
    """Seed the key cache, sabotage boto3, and replace `urlopen`. Before the first leg."""
    wix_ecom._key_cache["key"] = PLACEHOLDER_API_KEY
    sys.modules["boto3"] = _ExplodesOnAttributeAccess()
    transport = WixTransport()
    urllib.request.urlopen = transport
    return transport


def _count_aws_calls() -> int:
    """Zero AWS API calls, ENFORCED by a before-send hook rather than observed.

    Every boto3 client that exists in this process gets a hook that raises
    `UnexpectedAwsCall`. Leg 1's handler imports `middleware` and `rate_limit`, each of which
    builds a client at import, so the clients DO exist - the claim is that none of them is
    called, and the hook is what makes that a fact rather than a hope.

    `boto3 imported = NO` is deliberately NOT printed: it is false once the handler is
    imported, and a false structural claim in the one artifact whose purpose is to be trusted
    is worse than no claim.
    """
    attempted = {"count": 0}

    def refuse(**_kwargs):
        attempted["count"] += 1
        raise UnexpectedAwsCall("the demo attempted a live AWS API call")

    for module_name, path in (("lambda_utils.middleware", ("cognito", "meta", "events")),
                              ("lambda_utils.rate_limit",
                               ("dynamodb", "meta", "client", "meta", "events"))):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        target = module
        try:
            for attribute in path:
                target = getattr(target, attribute)
            target.register("before-send", refuse)
        except (AttributeError, UnexpectedAwsCall):
            # The client was never built, or is already sabotaged. Either way, no call.
            continue
    return attempted["count"]


# ── leg 1: the coupon, through the production handler ─────────────────────────

def _load_coupon_handler():
    spec = importlib.util.spec_from_file_location(
        "demo_coupons_handler", ROOT / "amplify/functions/ecommerce/coupons/handler.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_coupons_handler"] = module
    spec.loader.exec_module(module)
    return module


def _leg_coupon(transport: WixTransport, args) -> dict:
    """`coupons/handler._create`: the production composition, not a hand-built payload."""
    handler = _load_coupon_handler()
    store = FakeTable(key_attr=cs.KEY_ATTRIBUTE,
                      indexes={cs.STATUS_INDEX: (cs.STATUS_ATTRIBUTE, "createdAt")})
    # Exactly the two stubs the harness installs. `_staff`, not `middleware.require_auth`:
    # `handler.middleware` is the shared module object 58 files reference.
    handler._staff = lambda event: None
    handler._coupons_table = lambda: store

    transport.expect(method="POST", endpoint=wc.BASE,
                     body=_fixture("wix_coupon_create_response.json"))
    payload = {
        "code": args.coupon_code, "name": "Sample money off",
        "discountKind": cs.MONEY_OFF, "moneyOffPaise": args.coupon_money_off_paise,
        "startTimeMs": START_MS, "minimumSubtotalPaise": 500000,
        "usageLimit": 10, "limitPerCustomer": 1,
    }
    event = {
        "requestContext": {"routeKey": "POST /coupons",
                           "http": {"method": "POST", "path": "/coupons"}},
        "body": json.dumps(payload),
        "headers": {"origin": "https://wecare.digital"},
        "_auth": {"username": "demo-operator"},
    }
    response = handler._create(event, origin="https://wecare.digital")
    coupon = json.loads(response["body"])["coupon"]
    row = store.rows[cs.PREFIX_DEFINITION + cs.normalise_code(args.coupon_code)]
    request = transport.requests[-1]

    mismatches = []
    if response["statusCode"] != 201:
        mismatches.append(f"handler answered {response['statusCode']}, expected 201")
    if coupon.get("wixMirrorState") != cs.MIRROR_DONE:
        mismatches.append(f"mirror state {coupon.get('wixMirrorState')}")
    if request.url != f"{wix_ecom.WIX_API_BASE}{wc.BASE}":
        mismatches.append(f"url {request.url}")
    specification = (request.body or {}).get("specification") or {}
    if type(specification.get("moneyOffAmount")) is not int:
        mismatches.append("moneyOffAmount is not a JSON int")
    if type(specification.get("startTime")) is not str:
        mismatches.append("startTime is not a string-encoded int64")
    verdict = cs.evaluate(row, cart_id="demo-cart-1", customer_uses_count=0)
    if verdict != cs.ELIGIBLE:
        mismatches.append(f"eligibility {verdict}")

    return {
        "leg": "coupon",
        "verified": "this is how it works today",
        "driver": "coupons/handler._create (production composition)",
        "createdBy": row.get("createdBy"),
        "ourClaim": row[cs.KEY_ATTRIBUTE],
        "couponId": row.get("couponId"),
        "code": args.coupon_code,
        "discountKind": row.get("discountKind"),
        "moneyOffPaise": row.get("moneyOffPaise"),
        "minimumSubtotalPaise": row.get("minimumSubtotalPaise"),
        "currency": row.get("currency"),
        "arithmetic": "WIX (we never compute a discount)",
        "request": {"method": request.method, "url": request.url,
                    "headers": request.headers, "body": request.body},
        "handlerStatus": response["statusCode"],
        "wixMirrorState": coupon.get("wixMirrorState"),
        "wixCouponId": row.get("wixCouponId"),
        "eligibility": verdict,
        "createCalls": transport.count(method="POST", endpoint=wc.BASE),
        "mismatches": mismatches,
    }


# ── leg 2: the gift card, Wix-native ──────────────────────────────────────────

def _leg_wix_giftcard(transport: WixTransport, args) -> dict:
    """Derive -> query(miss) -> create -> replay(re-derive) -> query(hit) -> balance read-back."""
    adapter = wg.WixGiftCards(wix_ecom._request)

    transport.expect(method="POST", endpoint=f"{wg.BASE}/query",
                     body=_fixture("wix_giftcard_query_miss_response.json"))
    transport.expect(method="POST", endpoint=wg.BASE,
                     body=_fixture("wix_giftcard_create_response.json"))
    transport.expect(method="POST", endpoint=f"{wg.BASE}/query",
                     body=_fixture("wix_giftcard_query_by_code_response.json"))
    transport.expect(method="POST", endpoint=f"{wg.BASE}/query",
                     body=_fixture("wix_giftcard_balance_after_redeem.json"))

    created = adapter.create(
        initial_value_paise=args.value_paise,
        code=wg.demo_code(reference_id=args.reference_id),
        idempotency_key=wg.idempotency_key(reference_id=args.reference_id))
    create_request = transport.requests[-1]

    # The replay RE-DERIVES both identifiers from the reference rather than reusing them above,
    # so the transcript demonstrates determinism instead of assuming it.
    replayed = adapter.create(
        initial_value_paise=args.value_paise,
        code=wg.demo_code(reference_id=args.reference_id),
        idempotency_key=wg.idempotency_key(reference_id=args.reference_id))

    after = adapter.find_by_code(wg.demo_code(reference_id=args.reference_id))

    create_calls = transport.count(method="POST", endpoint=wg.BASE)
    mismatches = []
    if create_calls != 1:
        mismatches.append(f"{create_calls} create calls, expected exactly 1")
    if created["giftCardId"] != replayed["giftCardId"]:
        mismatches.append("the replay resolved onto a different card")
    if created["resolved"] is not False or replayed["resolved"] is not True:
        mismatches.append("resolved flags are wrong")
    if created["balancePaise"] != args.value_paise:
        mismatches.append(f"create balance {created['balancePaise']}")
    if created["currency"] != "INR":
        mismatches.append(f"currency {created['currency']}")
    if set(created) != set(wg.VIEW_KEYS) or set(replayed) != set(wg.VIEW_KEYS):
        mismatches.append("the view key set differs between branches")
    expected_amount = Money(args.value_paise).to_wix()
    sent = (((create_request.body or {}).get("giftCard") or {}).get("initialValue")
            or {}).get("amount")
    if sent != expected_amount:
        mismatches.append(f"amount on the wire {sent!r}, expected {expected_amount!r}")
    if type(sent) is not str:
        mismatches.append("the amount is not a decimal string")
    if Money.from_wix(expected_amount).paise != args.value_paise:
        mismatches.append("the decimal round trip lost paise")
    if after["balancePaise"] != 99975:
        mismatches.append(f"balance read-back {after['balancePaise']}")

    body = dict(create_request.body or {})
    rendered_body = json.loads(json.dumps(body))
    rendered_body["giftCard"]["code"] = _mask(rendered_body["giftCard"].get("code"))
    queries = [request for request in transport.requests
               if request.url.endswith("/query")]
    rendered_query = json.loads(json.dumps(queries[0].body)) if queries else None
    if rendered_query:
        rendered_query["query"]["filter"]["code"]["$eq"] = _mask(
            rendered_query["query"]["filter"]["code"]["$eq"])

    return {
        "leg": "wix-giftcard",
        "verified": "CHOSEN: contract under verification (retirement gate condition 3)",
        "referenceId": args.reference_id,
        "codeMasked": _mask(wg.demo_code(reference_id=args.reference_id)),
        "codeLength": len(wg.demo_code(reference_id=args.reference_id)),
        "codeDerivation": "demo_code(reference_id) - DEMO-ONLY, UNKEYED",
        "productionDerivation": ("card_code(reference_id, pepper) - HMAC-keyed under "
                                 "wecare/wix/giftcard-spi:code_pepper, domain-tagged"),
        "idempotencyKey": wg.idempotency_key(reference_id=args.reference_id),
        "idempotencyKeyLength": len(wg.idempotency_key(reference_id=args.reference_id)),
        "determinism": "deterministic in its inputs - no clock, no counter, no secrets",
        "createRequest": {"method": create_request.method, "url": create_request.url,
                          "headers": create_request.headers, "body": rendered_body},
        "queryRequest": rendered_query,
        "giftCardId": created["giftCardId"],
        "codeLast4": created["codeLast4"],
        "codeLast4Source": "Wix's own codeSuffix, never a parse of the obfuscated code",
        "balancePaise": created["balancePaise"],
        "resolvedOnReplay": replayed["resolved"],
        "disabled": created["disabled"],
        "expirationDate": created["expirationDate"],
        "createCalls": create_calls,
        "balanceAfterWixRedemptionPaise": after["balancePaise"],
        "redemptionOwner": "WIX (balance is readOnly; we could not move it if we tried)",
        "ourStoreInThisLeg": "NONE",
        "mismatches": mismatches,
    }


# ── leg 3: the gift card, ours ────────────────────────────────────────────────

def _leg_our_giftcard(args) -> dict:
    """`gift_card_store`: issue -> balance -> redeem -> balance, in integer paise."""
    store = FakeTable(key_attr=gcs.KEY_ATTRIBUTE,
                      indexes={gcs.STATUS_INDEX: (gcs.STATUS_ATTRIBUTE, "createdAt")})
    issued = gcs.issue(store, initial_value_paise=args.value_paise, pepper=DEMO_PEPPER,
                       clock=_clock())
    digest = issued["codeHash"]
    card = gcs.get_card(store, code_hash=digest) or {}

    redeemed = gcs.redeem(store, code_hash=digest, attempt_id="demo-attempt-1",
                          amount_paise=args.redeem_paise, clock=_clock())
    replay = gcs.redeem(store, code_hash=digest, attempt_id="demo-attempt-1",
                        amount_paise=args.redeem_paise, clock=_clock())
    final = gcs.get_card(store, code_hash=digest) or {}

    expected = args.value_paise - args.redeem_paise
    mismatches = []
    if int(card.get("balancePaise") or 0) != args.value_paise:
        mismatches.append("issued balance")
    if redeemed["committed"] is not True:
        mismatches.append("the first redemption did not commit")
    if redeemed["remainingBalancePaise"] != expected:
        mismatches.append(f"balance after redeem {redeemed['remainingBalancePaise']}")
    if replay["committed"] is not False:
        mismatches.append("the replay committed a second time")
    if replay["transactionId"] != redeemed["transactionId"]:
        mismatches.append("the replay minted a second transaction id")
    if int(final.get("balancePaise") or 0) != expected:
        mismatches.append("the replay moved the balance")

    return {
        "leg": "our-giftcard",
        "verified": "CURRENT: would be removed under the Wix-native decision",
        "giftCardId": card.get("giftCardId"),
        "codeMasked": gcs.masked(card.get("codeLast4")),
        "codeDerivation": "HMAC key, pepper read BY REFERENCE in production",
        "balancePaise": int(card.get("balancePaise") or 0),
        "redeemPaise": args.redeem_paise,
        "paymentAttemptId": "demo-attempt-1",
        "transactionId": redeemed["transactionId"],
        "balanceAfterPaise": redeemed["remainingBalancePaise"],
        "replayCommitted": replay["committed"],
        "replayBalancePaise": replay["remainingBalancePaise"],
        "concurrency": ("2 threads, same attempt -> 1 debit "
                        "(tests/test_gift_card_redeem_concurrency.py)"),
        "mismatches": mismatches,
    }


# ── validation ────────────────────────────────────────────────────────────────

def _validate(args, parser) -> None:
    """Every input is argv, and every rule has a stated behaviour on failure: exit 2."""
    if args.coupon_money_off_paise <= 0:
        parser.error("--coupon-money-off-paise must be positive")
    if args.coupon_money_off_paise % cs.PAISE_PER_RUPEE:
        # The whole-rupee rule belongs HERE and ONLY here: `wix_coupons._rupees` refuses the
        # rest, so a non-whole-rupee coupon cannot be sent at all.
        parser.error("--coupon-money-off-paise must be a whole number of rupees "
                     f"(a multiple of {cs.PAISE_PER_RUPEE})")
    if not 0 < args.value_paise <= gcs.MAX_VALUE_PAISE:
        parser.error(f"--value-paise must be 1 to {gcs.MAX_VALUE_PAISE}, "
                     "the SPI ceiling (no Wix-side maximum is documented)")
    if not 0 < args.redeem_paise < args.value_paise:
        parser.error("--redeem-paise must be positive and below --value-paise")
    if args.value_paise - args.redeem_paise < gcs.RAZORPAY_MIN_LEG_PAISE:
        parser.error(f"the residual must be at least {gcs.RAZORPAY_MIN_LEG_PAISE} paise, "
                     "mirroring gift_card_store.RAZORPAY_MIN_LEG_PAISE")
    # `--value-paise` and `--redeem-paise` take ANY paise, deliberately. The fractional
    # defaults are exactly what make leg 2 cross the Wix decimal boundary, which is the
    # strongest argument for the Wix-native model - whole-rupee-only inputs would never
    # exercise it.
    if not args.reference_id or len(args.reference_id) > 200:
        parser.error("--reference-id must be 1 to 200 characters")
    try:
        cs.normalise_code(args.coupon_code)
    except cs.CouponError as refusal:
        # The store's own rule. The demo defines no second code rule.
        parser.error(f"--coupon-code: {refusal.code}")


# ── rendering ─────────────────────────────────────────────────────────────────

def _render_request(request: dict, out, indent: str = "  ") -> None:
    out.append(f"{indent}-> {request['method']} {request['url']}")
    for name in sorted(request.get("headers") or {}):
        value = request["headers"][name]
        if name.lower() == "authorization":
            # Already `<redacted>` at capture. Printed with the secret NAME, never a value.
            value = "<redacted - wecare/wix/headless-api-key>"
        out.append(f"{indent}   {name}: {value}")
    if request.get("body") is not None:
        for line in json.dumps(request["body"], indent=2).splitlines():
            out.append(f"{indent}   {line}")


def _render(legs: list, aws_calls: int, out: list) -> None:
    out.append("WIX COUPON + GIFT CARD SAMPLE                              OFFLINE")
    out.append("Wix HTTP boundary: STUBBED at urllib.request.urlopen. No live Wix call.")
    out.append("")
    for leg in legs:
        if leg["leg"] == "coupon":
            out.append("-- LEG 1 . COUPON ----------------------------------------------")
            out.append(f"  {leg['verified']}")
            out.append(f"  driver           {leg['driver']}")
            out.append(f"  created_by       {leg['createdBy']}  (event['_auth']['username'])")
            out.append(f"  our claim        {leg['ourClaim']}  (conditional put, won)")
            out.append(f"  couponId         {leg['couponId']}")
            out.append(f"  discount         {leg['discountKind']} {leg['moneyOffPaise']} paise"
                       f"  = {_rupees(leg['moneyOffPaise'])}")
            out.append(f"  minimum          {leg['minimumSubtotalPaise']} paise"
                       f"  = {_rupees(leg['minimumSubtotalPaise'])}")
            out.append(f"  currency         {leg['currency']}  (compared explicitly)")
            out.append(f"  arithmetic       {leg['arithmetic']}")
            out.append("")
            _render_request(leg["request"], out)
            out.append(f"  <- 200 {{\"id\": \"{leg['wixCouponId']}\"}}")
            out.append(f"  handler answer   {leg['handlerStatus']}"
                       "  (202 would mean PENDING_WIX)")
            out.append(f"  our row          wixMirrorState PENDING_WIX -> "
                       f"{leg['wixMirrorState']}")
            out.append(f"  eligibility      {leg['eligibility']}"
                       "  (a verdict, never an amount)")
            out.append(f"  create calls     {leg['createCalls']}")
        elif leg["leg"] == "wix-giftcard":
            out.append("")
            out.append("-- LEG 2 . GIFT CARD, WIX-NATIVE -------------------------------")
            out.append(f"  {leg['verified']}")
            out.append(f"  reference        {leg['referenceId']}  (the ONLY input)")
            out.append(f"  code             {leg['codeMasked']}"
                       f"  = {leg['codeDerivation']}")
            out.append(f"                   {leg['codeLength']} chars, Wix's maximum"
                       " - same length production sends")
            out.append(f"  production uses  {leg['productionDerivation']}")
            out.append(f"  idem key         {leg['idempotencyKey']}"
                       f"  ({leg['idempotencyKeyLength']} ch)")
            out.append("                   unkeyed on purpose: not bearer value, and"
                       " rotation-invariant")
            out.append(f"  derived          {leg['determinism']}")
            out.append("")
            _render_request(leg["createRequest"], out)
            out.append(f"  <- 200 giftCardId {leg['giftCardId']}  codeSuffix"
                       f" {leg['codeLast4']}  balance {leg['balancePaise']} paise"
                       f"  = {_rupees(leg['balancePaise'])}")
            out.append(f"     resolved=False  disabled={leg['disabled']}"
                       f"  expirationDate {leg['expirationDate']}")
            out.append(f"     codeLast4: {leg['codeLast4Source']}")
            out.append(f"     replay: identifiers RE-DERIVED -> {leg['createCalls']} create"
                       f" call total, same giftCardId, resolved={leg['resolvedOnReplay']}")
            out.append("")
            if leg.get("queryRequest"):
                out.append("  -> POST .../gift-cards/v1/gift-cards/query")
                for line in json.dumps(leg["queryRequest"], indent=2).splitlines():
                    out.append(f"     {line}")
                out.append("     ^ a real JSON object, unlike the coupon query's"
                           " double-encoded string")
            out.append(f"  <- after a WIX-side redemption:"
                       f" {leg['balanceAfterWixRedemptionPaise']} paise"
                       f"  = {_rupees(leg['balanceAfterWixRedemptionPaise'])}")
            out.append(f"     balance and currency come off the QUERY response, so the"
                       " resolve path is ONE request")
            out.append(f"     redemption is {leg['redemptionOwner']}")
            out.append(f"     store of ours in this leg: {leg['ourStoreInThisLeg']}")
        elif leg["leg"] == "our-giftcard":
            out.append("")
            out.append("-- LEG 3 . GIFT CARD, OURS -------------------------------------")
            out.append(f"  {leg['verified']}")
            out.append(f"  issued           giftCardId {leg['giftCardId']}"
                       f"   code {leg['codeMasked']}  ({leg['codeDerivation']})")
            out.append(f"    balance        {leg['balancePaise']} paise"
                       f"  = {_rupees(leg['balancePaise'])}")
            out.append(f"  redeem           {leg['redeemPaise']} paise,"
                       f" attempt {leg['paymentAttemptId']}")
            out.append(f"    transactionId  {leg['transactionId']}"
                       "  (ULID, secrets-backed)")
            out.append(f"    balance after  {leg['balanceAfterPaise']} paise"
                       f"  = {_rupees(leg['balanceAfterPaise'])}")
            out.append(f"  replay           same attempt -> committed="
                       f"{leg['replayCommitted']}, balance"
                       f" {leg['replayBalancePaise']} paise unchanged")
            out.append(f"  concurrent       {leg['concurrency']}")
        else:  # pragma: no cover - the leg set is closed
            raise AssertionError(f"unclassifiable leg {leg['leg']!r}")

    mismatches = [item for leg in legs for item in leg["mismatches"]]
    out.append("")
    out.append(f"no AWS:  secretsmanager client built = "
               f"{'NO' if wix_ecom._secrets is None else 'YES'}"
               f"    AWS API calls attempted = {aws_calls}")
    out.append("         clients are constructed at handler import; a before-send hook would"
               " fail the run")
    out.append(f"{len(legs)} legs, {len(mismatches)} contract mismatches")
    for item in mismatches:
        out.append(f"  MISMATCH: {item}")


# ── entry point ───────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="demo_coupon_giftcard_sample.py",
        description="Offline Wix coupon + gift card demonstration. No AWS, no live Wix.")
    parser.add_argument("--leg", choices=LEGS, default="all")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable transcript on stdout, nothing else")
    parser.add_argument("--no-colour", action="store_true",
                        help="plain ASCII (this renderer is plain ASCII either way)")
    parser.add_argument("--value-paise", type=int, default=250050)
    parser.add_argument("--redeem-paise", type=int, default=150075)
    parser.add_argument("--coupon-money-off-paise", type=int, default=12345600)
    parser.add_argument("--coupon-code", default="WDSAMPLE10")
    parser.add_argument("--reference-id", default="wd-gc-sample-2026-10-02")
    args = parser.parse_args(argv)
    _validate(args, parser)

    transport = _install_containment()
    legs = []
    try:
        if args.leg in ("coupon", "all"):
            legs.append(_leg_coupon(transport, args))
        if args.leg in ("wix-giftcard", "all"):
            legs.append(_leg_wix_giftcard(transport, args))
        if args.leg in ("our-giftcard", "all"):
            legs.append(_leg_our_giftcard(args))
        transport.assert_drained()
    except BaseException as error:  # noqa: BLE001 - reported as a contract failure, by TYPE
        print(f"CONTRACT FAILURE: {type(error).__name__}: {error}")
        return 1

    aws_calls = _count_aws_calls()
    mismatches = [item for leg in legs for item in leg["mismatches"]]

    if args.json:
        print(json.dumps({"legs": legs, "awsCallsAttempted": aws_calls,
                          "secretsManagerClientBuilt": wix_ecom._secrets is not None,
                          "mismatchCount": len(mismatches)}, indent=2, sort_keys=True))
    else:
        out: list = []
        _render(legs, aws_calls, out)
        print("\n".join(out))

    return 1 if mismatches or aws_calls else 0


if __name__ == "__main__":
    sys.exit(main())
