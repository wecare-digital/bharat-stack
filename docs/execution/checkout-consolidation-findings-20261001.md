# Checkout consolidation — current ground truth, 2026-10-01

Read-only investigation. No code changed, nothing committed, nothing deployed. Every AWS call
was a read (`sts get-caller-identity`, `lambda get-alias` / `get-function-configuration` /
`get-function`, `apigatewayv2 get-routes` / `get-api`, `dynamodb describe-table`). No secret
value was read or printed.

- Tree: `/Users/wecaredigital/wecare-store`, branch `stack`, HEAD
  **`6a5d6e9ea6fe0097bf246a34ab6138c6919935d7`** (2026-10-01 03:42 IST,
  "Fix the sys.modules pollution that failed 281 blog tests in the full suite (#162)").
- Pre-existing dirty state, left untouched: ` M .kiro/steering/META-BETA-REQUEST-EMAIL.md`,
  `?? scripts/retired_url_equity.py`.
- Line numbers below are current at this HEAD, not the dated audit's.

---

## Summary answer

**The headless checkout path is written but not connected, and it is broken in four places at once.
Three of the four are silent — they produce a customer who has paid, an invoice marked paid, a
WhatsApp confirmation, and no order, with nothing raised to a human.**

| # | Finding | Status vs audit claim |
|---|---|---|
| C1 | `_create_order_for_captured_payment` is called for effect only; its return value is discarded and every post-payment side effect runs regardless | **CONFIRMED** |
| C2 | No native-vs-headless mode switch exists in runtime code. `WIX_NATIVE_PROVIDER` and `submitEvent` live **only** in the retired prototype and its prompt | **CONFIRMED** (and cleaner than feared) |
| C3 | `_send_order_details` posts to `/wa-business/messages/send/interactive-payment`, which the business-API dispatcher answers **404**. A second, undocumented break: the readiness readback posts `/wa-business/payment-config/raw` with `wabaId`, and the dispatcher answers **400 phoneId required** | **CONFIRMED + one new break** |
| C4 | Nothing anywhere in the tree ever *writes* `providerPaymentId` or `providerOrderId`. The verifier requires one of them, so reconciliation can never succeed | **CONFIRMED — hard deadlock** |
| C5 | Checkout uses `wix_ecom.create_checkout` → `POST /ecom/v1/checkouts` (V1) and stores `wixCheckoutId`. Cart V2 is wired only into `wix-store`, and the two paths never meet | **CONFIRMED** |
| C6 | `PAYMENT_PAID` is never written to `PaymentAttemptsTable`; the status endpoint never resolves an order number; the status page requires both before it will redirect | **CONFIRMED** |
| C7 | No `wecare-checkout` function and no `/ecommerce/*` route exist. Packaging is **bundled, not layered**. `wix-store:live` v31 contains none of the ecommerce modules | **CONFIRMED** |

Two compounding facts make this worse than a list of gaps:

1. **The blocked outcome is classified as "no money moved."** `PROVIDER_UNAVAILABLE` sits in
   `NO_ORDER_OUTCOMES`, so `needs_human` is `False`. The one failure this domain must never have
   silently is the one that is currently wired to be silent.
2. **236 tests pass.** They pass because each stub sits exactly where production breaks: the
   verifier is replaced by `lambda _r: (True, TXN, AMOUNT, 'INR')`, and the checkout test's fake
   Lambda returns a `data`-bearing payload for any path containing `payment-config` and `200` for
   the send. The suite proves the modules; it cannot see the seams.

---

## C1 — the order-creation result is discarded

**CONFIRMED.**

`amplify/functions/payments/razorpay-webhook/handler.py`, inside `_handle_payment_captured`:

```python
# line 663-664
    if reference_id:
        _create_order_for_captured_payment(payment, reference_id, request_id)

# line 667-673
    if reference_id:
        _mark_invoice_paid_by_reference(reference_id, request_id)
    else:
        clean_phone = (contact or '').replace('+', '').replace(' ', '').replace('-', '')
        if clean_phone:
            _mark_invoice_paid_by_phone_and_amount(clean_phone, amount_rupees, request_id)

# line 676
    _post_payment_handler(payment_id, amount_rupees, currency, contact, email, description, notes, request_id)

# line 681
    _log_ctwa_purchase(contact, amount_rupees, currency, order_id, notes, request_id)
```

The callee is declared `-> Dict[str, Any]` (line 431-432) and returns `outcome.as_dict()` at line
505, or `{'outcome': 'RECONCILIATION_ERROR', 'hasOrder': False}` at line 517. **No caller binds
that value.** There is no `if result['hasOrder']:` guard, no early return, no branch. The invoice
is marked paid, the GST invoice is generated and sent on WhatsApp, the Meta Conversions Purchase
event fires, and an `order_status` message is sent to the customer — all with equal confidence
whether an order exists or not.

The function's own docstring says it "does not perform the downstream side effects … which are
separately guarded so that a failure in the last one does not re-run the first" (line 444-446).
That separation is real inside `wix_writeback`; it is absent at this call site, where the
downstream effects are not guarded on the upstream outcome at all.

Severity is raised by the outcome classification in
`amplify/functions/shared/lambda_utils/ecommerce/order_creation.py`:

```python
# line 70-73
NO_ORDER_OUTCOMES = frozenset({
    NOT_PAID, UNKNOWN_REFERENCE, ATTEMPT_NOT_PAYABLE, PROVIDER_UNAVAILABLE,
})
```

`PROVIDER_UNAVAILABLE` — which, per C4, is the outcome production will always reach — is in the
"money did NOT move" set, so `needs_human` (line 105-107) is `False` and the webhook logs a
`warning`, not the `PAID_BUT_NO_ORDER` error at handler line 496-503.

The deployed package agrees with source on this shape: `wecare-razorpay-webhook:live` v45 contains
`_create_order_for_captured_payment` called once at its line 662, also unbound.

---

## C2 — no dual-mode router exists

**CONFIRMED.** The mode switch the audit worried about was never built into runtime code. Complete
occurrence list for `WIX_NATIVE_PROVIDER`, `WIX_HEADLESS`, `submitEvent`, `CHECKOUT_MODE`:

| Path:line | Symbol | Class |
|---|---|---|
| `amplify/functions/ecommerce/checkout/handler.py:75` | `CHECKOUT_MODE = "WIX_HEADLESS"` | **active runtime code** — a constant marker, not a switch |
| `amplify/functions/ecommerce/checkout/handler.py:261` | `"checkoutMode": CHECKOUT_MODE` on the `PAYREF#` row | active runtime code |
| `amplify/functions/ecommerce/checkout/handler.py:275` | `attempt["checkoutMode"] = CHECKOUT_MODE` | active runtime code |
| `tests/test_checkout_handler.py:158,162` | `assert attempts[0]['checkoutMode'] == 'WIX_HEADLESS'` | test |
| `integrations/wix-velo-payment/backend/http-functions.js:8` | `submitEvent: event => wixPaymentProviderBackend.submitEvent(event)` | **retired prototype** |
| `integrations/wix-velo-payment/backend/wecare/notifications.js:5,29` | `submitEvent` injected + called | retired prototype |
| `integrations/wix-velo-payment/tests/notifications.test.js:24,32,63,72` | `submitEvent` | retired prototype test |
| `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:15,659,755,968,969,1079,1089,1093,1431,1457,1465,1564,1607,1679` | `WIX_NATIVE_PROVIDER`, `submitEvent` | **doc/prompt — superseded** |
| `integrations/wix-velo-payment/INSTALLATION.md:14,35,41,52` | `submitEvent` | doc — superseded |

`grep` for `WIX_NATIVE_PROVIDER` in `amplify/`, `src/`, `scripts/`, `config/`: **zero hits.**
`grep -in "velo\|psp\|PROVIDER_MODE"` in `config/lambda-env-manifest.json`: **zero hits.**

`CHECKOUT_MODE` is a one-way label written onto the attempt so a test can assert provenance — it is
never read back to select behaviour. There is no router to dismantle. Retirement is a deletion,
not a refactor.

---

## C3 — the WhatsApp handoff posts to a path that 404s, and the readiness readback 400s

**CONFIRMED, plus a second break the audit did not name.**

### The send path

`amplify/functions/ecommerce/checkout/handler.py`, `_send_order_details`, line 363-377:

```python
    invoke_event = {
        "httpMethod": "POST",
        "path": "/wa-business/messages/send/interactive-payment",
        "body": json.dumps({
            "to": "".join(ch for ch in str(phone or "") if ch.isdigit()),
            "reference_id": reference_id,
            ...
```

`amplify/functions/messaging/whatsapp-business-api/handler.py` dispatches on `'/messages/send/' in
path` (line 5799) into `_route_send_message` (line 2179-2199):

```python
def _route_send_message(path: str, body: Dict) -> Dict:
    """Dispatch /messages/send/{type}."""
    if path.rstrip('/').endswith('/text'):
        ...
    if path.rstrip('/').endswith('/interactive'):
        return _send_interactive_msg(body)
    ...
    return _resp(404, {'error': f'Unknown send path: {path}'})
```

`"/wa-business/messages/send/interactive-payment".endswith("/interactive")` is `False`. Every
suffix test fails; the call returns **404**. `_send_order_details` reads
`int(result.get("statusCode") or 500) < 300` (line 386) → `False` → the handler returns
`502 SEND_FAILED`. The route does not exist. `interactive-payment` appears nowhere else in the
whatsapp-business-api handler, in any dispatcher, or in the API Gateway route table.

Also relevant: **there are no `/wa-business/messages/send/*` routes on API `zllr9lrg7j` at all.**
That does not matter for this call (checkout invokes the Lambda directly, not through the API), but
it means the send surface cannot be exercised over HTTP either.

### The readiness readback — new finding

`_fetch_payment_configurations`, line 121-129, posts a *different* invented path:

```python
    invoke_event = {
        "httpMethod": "GET",
        "path": "/wa-business/payment-config/raw",
        "queryStringParameters": {"wabaId": waba_id},
    }
```

The dispatcher's ordering (handler.py lines 6101-6125) tests `'/payment-config/check' in path`
first — no match — then `/payment-lookup`, `/payment-refund`, then:

```python
        elif '/payment-config' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
```

`/payment-config/raw` **does** contain `/payment-config`, so it matches — and the checkout sends
`wabaId`, not `phoneId`. The response body is `{'error': 'phoneId required'}`.

`payment_readiness.evaluate` (`amplify/functions/shared/lambda_utils/payment_readiness.py`
line 258-259) then does:

```python
    if response.get("error"):
        return _blocked(META_UNAVAILABLE, "Meta returned an error for payment_configurations")
```

So the readiness gate returns `META_UNAVAILABLE` — a blocking state — on every call, and the
checkout returns `409 payment_unavailable` before it ever reaches the send. **The readiness gate
can never pass with the current path.** `/wa-business/payment-config/raw` does not exist; the
existing route that returns raw Meta configurations is `GET /wa-business/payment-config/check`
(handler line 6101, `_check_payment_gateway(waba_id)`), which *does* take `wabaId` and *is* on the
API.

Both breaks are invisible to the test suite. `tests/test_checkout_handler.py:43-63`:

```python
class _FakeLambda:
    """Captures internal invokes: the payment-config read and the order_details send."""
    def invoke(self, FunctionName=None, InvocationType=None, Payload=None, **_):
        ...
        if 'payment-config' in path:
            inner = {'statusCode': 200, 'body': json.dumps({'data': [...]})}
        else:
            inner = {'statusCode': 200 if self.send_ok else 502, 'body': '{}'}
```

The fake answers `payment-config` by substring and answers everything else `200`. It cannot
distinguish a real route from an invented one.

---

## C4 — the provider binding is required and never written

**CONFIRMED. This is a hard deadlock, not a gap.**

### What the verifier requires

`amplify/functions/shared/lambda_utils/integrations/razorpay_verify.py`, `verifier_for_event`,
line 159-178:

```python
def verifier_for_event(payment_id: str = "", order_id: str = "", *, load_attempt=None):
    """...
    The attempt must already carry a providerOrderId or providerPaymentId derived
    from payment initiation or an authenticated Meta lookup. A webhook must not
    supply its own binding. Missing bindings fail closed for reconciliation.
    """
    ...
    def verify(reference_id: str) -> Tuple[bool, str, int, str]:
        attempt = load_attempt(reference_id) if load_attempt else None
        if not attempt:
            raise RazorpayUnavailable("payment attempt binding is unavailable")
        bound_payment = str(attempt.get("providerPaymentId") or "")
        bound_order = str(attempt.get("providerOrderId") or "")
        if not bound_payment and not bound_order:
            raise RazorpayUnavailable("payment attempt has no verified provider binding")
```

### What initiation actually persists

`payment_attempt.build` (`payment_attempt.py` line 165-179) writes a fixed record:

```python
    record = {
        "paymentAttemptId": ..., "customerId": ..., "referenceId": ...,
        "amountPaise": amount_paise, "currency": currency,
        "configurationName": configuration_name, "provider": "razorpay",
        "status": CREATED, RANK_ATTRIBUTE: rank(CREATED),
        "attemptNumber": attempt_number, "createdAt": moment, "updatedAt": moment,
    }
    for key, value in (("cartId", cart_id), ("wixCheckoutId", wix_checkout_id),
                       ("retryOf", retry_of)):
```

No provider fields. The only writer is `transition()` (line 279-282), and only if a caller passes
them:

```python
    if provider_payment_id:
        out["providerPaymentId"] = provider_payment_id
    if provider_order_id:
        out["providerOrderId"] = provider_order_id
```

The checkout handler calls `transition` once, with neither kwarg
(`checkout/handler.py:276-277`):

```python
    attempt = payment_attempt.transition(
        attempt, payment_attempt.PAYMENT_READINESS_CHECKED)
```

and `_mark_request_sent` (line 396-419) updates only `status`, `attemptRank`, `updatedAt`.

The `PAYREF#` row is written by `order_keys.allocate_payment_reference` with
(`checkout/handler.py:258-263`):

```python
            extra={"customerId": identity.customer_id,
                   "amountPaise": amount_paise, "currency": "INR",
                   "wixCheckoutId": wix_checkout_id, "checkoutMode": CHECKOUT_MODE},
```

— again no provider fields. And the webhook's `_load_attempt` reads exactly that row
(`razorpay-webhook/handler.py:465-473`):

```python
            return {
                'paymentAttemptId': row['paymentAttemptId'],
                'customerId': row.get('customerId', ''),
                'amountPaise': row.get('amountPaise'),
                'providerPaymentId': row.get('providerPaymentId', ''),
                'providerOrderId': row.get('providerOrderId', ''),
                'currency': row.get('currency', ''),
            }
```

Both keys resolve to `''`.

### Tree-wide proof

`grep -rn "providerPaymentId\|providerOrderId" --include="*.py" amplify/ scripts/` returns exactly
seven lines: two *reads* in the webhook (465-473 above), two *conditional assignments* in
`payment_attempt.transition` (280, 282), and three lines in `razorpay_verify` (163, 175, 176) that
read them. **There is no production writer.**

### Consequence

`verifier_for_event` raises `RazorpayUnavailable("payment attempt has no verified provider
binding")` on every real capture → `order_creation.reconcile_payment` catches it at line 223-227
and returns `PROVIDER_UNAVAILABLE` → which is in `NO_ORDER_OUTCOMES`, so `needs_human` is `False`
→ and per C1 the return value is discarded anyway. Money is taken, the invoice is marked paid, the
confirmation is sent, no order exists, and the log line is a `warning`.

The requirement is deliberate and correctly tested in isolation —
`tests/test_razorpay_binding.py:14-17` asserts precisely this refusal:

```python
def test_event_alone_cannot_prove_payment_binding(monkeypatch):
    monkeypatch.setattr(rv, '_get', lambda _: pytest.fail('must not fetch event-selected payment'))
    with pytest.raises(rv.RazorpayUnavailable):
        rv.verifier_for_event(payment_id='pay_attacker', load_attempt=lambda _: {})('ref')
```

The integration test that would have caught the missing writer stubs the verifier out
(`tests/test_razorpay_webhook_order_creation.py:64-66`):

```python
            with patch('lambda_utils.integrations.razorpay_verify.verifier_for_event',
                       return_value=verifier):
```

with `verifier=lambda _r: (True, TXN, AMOUNT, 'INR')` — and its `_seed_attempt` helper (line 52-57)
writes a `PAYREF#` row with no provider fields, exactly as production does. The fixture reproduces
the bug and the stub hides it.

---

## C5 — Checkout V1, not Cart V2

**CONFIRMED.** `amplify/functions/ecommerce/checkout/handler.py:225-236`:

```python
    try:
        checkout = wix_ecom.create_checkout(line_items)
        currency = wix_ecom.checkout_currency(checkout)
        if currency != "INR":
            ...
        amount_paise = wix_ecom.authoritative_total_paise(checkout)
    ...
    wix_checkout_id = str(checkout.get("id") or "")
```

`amplify/functions/shared/lambda_utils/wix_ecom.py:139-157`:

```python
def create_checkout(line_items: List[Dict[str, Any]], *,
                    channel_type: str = "OTHER_PLATFORM") -> Dict[str, Any]:
    ...
    result = _request("/ecom/v1/checkouts", method="POST", body=body)
```

That is Wix **Checkout V1** (`/ecom/v1/checkouts`), and `wixCheckoutId` is stored on both the
attempt (`payment_attempt.build(..., wix_checkout_id=...)`) and the `PAYREF#` row.

Cart V2 exists and is wired somewhere else entirely. `cart_v2` / `customer_cart` importers, whole
tree:

- `amplify/functions/ecommerce/wix-store/handler.py:363-364` — inside `_customer_cart`
- `amplify/functions/shared/lambda_utils/ecommerce/customer_cart.py:15` — imports from `cart_v2`
- `tests/test_cart_v2.py`

The checkout handler imports neither. There is **no cart-to-checkout handoff**: `_create` takes
`lineItems` from the request body and builds a fresh V1 checkout from them, so the phone-keyed
`CUSTOMERCART#<phone>` cart the WhatsApp flow builds is never the thing that gets priced.

This contradicts the spec directly. `.kiro/specs/whatsapp-wix-commerce/design.md:90-93` (D4):

> **Cart V2, confirmed live 2026-10-01.** … Cart V2 unifies cart and checkout into one entity:
> there is **no checkout step and no `wixCheckoutId`** — the cart id identifies the unified cart

and D7 lists the V1 removal date: `design.md:88` — Wix removes Cart V1 / Checkout V1 on
**2027-02-01**. The active code is on the path the design says does not exist and the vendor is
deleting.

`_customer_cart` is additionally gated off (`wix-store/handler.py:370-371`):

```python
    if os.environ.get('WIX_CART_V2_ENABLED', '').lower() != 'true':
        return _response(503, {'error': 'CART_UNAVAILABLE'})
```

and `WIX_CART_V2_ENABLED` is **absent** from the live `wecare-wix-store` environment (measured;
see C7).

---

## C6 — the status contract is broken at both ends

**CONFIRMED**, including the order-number defaulting the audit named.

### Producer: nothing writes `PAYMENT_PAID` to `PaymentAttemptsTable`

`order_creation.reconcile_payment` touches the attempt status exactly once, and only as a local
dict for an eligibility check (`order_creation.py:266-267`):

```python
    if not payment_attempt.may_create_order(
            {**attempt, "status": payment_attempt.PAYMENT_PAID}):
```

Every write it performs goes to the commerce-keys table via `order_keys` (`claim_order_for_payment`
line 282-287, `reserve_public_order_number` in `_finish_numbering` line 352+). Grep for
`PAYMENT_PAID` across `amplify/`: the only production occurrences are the constant definition
(`payment_attempt.py:67`), the eligibility set (`line 74`), the `paidAt` branch in `transition`
(`line 268-269`), and the local dict above. **No handler ever persists it.** The webhook does not
open `PaymentAttemptsTable` at all — `_load_attempt` reads the `PAYREF#` row in `WixOrderIds`.

So an attempt's stored status stays at `PAYMENT_REQUEST_SENT` forever.

### Status endpoint: order number defaults to `None`, always

`checkout/handler.py:329-331`:

```python
    entry = payment_attempt.payment_history_entry(owned)
    return cors_response(200, {"status": entry.get("status"), "attempt": entry}, origin)
```

`payment_history_entry` (`payment_attempt.py:291`) signature is
`(attempt, *, order_number: str = "")`. The caller passes no `order_number`, so
(`payment_attempt.py:307`):

```python
        "orderNumber": order_number if (settled and order_number) else None,
```

is `None` unconditionally — and line 313-315 strips it again for any non-paid state. Nothing in the
handler resolves the order number from `order_keys.resolve_order_for_payment`. **The endpoint
cannot ever return an order number.**

### UI: the success redirect requires both

`src/pages/checkout/status.tsx:69-74`:

```tsx
function viewFor ( status: string | undefined, orderNumber: string | null | undefined ): View {
  const s = String( status || '' ).toUpperCase();
  if ( s === 'PAYMENT_PAID' )
  {
    return orderNumber ? 'confirming' /* momentary; redirect fires */ : 'finalizing';
  }
```

and line 125-131:

```tsx
      if ( String( attempt.status || '' ).toUpperCase() === 'PAYMENT_PAID' && attempt.orderNumber )
      {
        const n = encodeURIComponent( String( attempt.orderNumber ) );
        window.location.replace( `/checkout/success/?o=${n}` );
        return true;
      }
```

`PAYMENT_REQUEST_SENT` maps to `'confirming'` (line 76-81), which keeps polling until
`POLL_CEILING_MS = 5 * 60 * 1000` (line 53) and then simply stops. The customer sits on
"Confirming your payment" for five minutes and then on a dead screen — while their invoice says
paid and WhatsApp has told them the order is confirmed.

`src/pages/checkout/success.tsx:4` states the contract it was built against:
"It is reached only after the status screen has seen a PAID attempt WITH an order number" —
a state the backend cannot produce.

The page also polls `${API_BASE}/ecommerce/checkout/status` (`status.tsx:47`), and there is no
`/ecommerce/*` route on the API (C7), so the fetch would 404 → `setView('unavailable')` before any
of the above even matters.

---

## C7 — deployment reality

### Not deployed

- `wecare-checkout`: `GetFunctionConfiguration` → `ResourceNotFoundException: Function not found`.
  `GetAlias … :live` → `ResourceNotFoundException`. **The function does not exist.**
- API `zllr9lrg7j`: **359 routes, `NextToken: null`** (complete page). Filtering for
  `ecommerce|checkout|cart|messages/send`:

  ```
  GET  /payments
  GET  /payments/{paymentId}
  GET  /wa-business/payment-config/check
  POST /invoices/from-payment
  POST /invoices/{invoiceId}/send-payment-link
  ```

  **Zero `/ecommerce/*` routes. Zero `/messages/send/*` routes.** The Cart V2 customer route
  `/wix-store/cart` that D7 names is reachable only as a side effect of the existing
  `GET|POST /wix-store/{proxy+}` catch-all.
- `config/lambda-env-manifest.json` has no `checkout` entry, no `CHECKOUT_INITIATION_ENABLED`, no
  `EXPECTED_CONFIGURATION_NAME`, no `EXPECTED_PROVIDER_MID`, no `COMMERCE_KEYS_TABLE`. Its only
  match is `"SENDER_FUNCTION": "wecare-whatsapp-business-api:live"` at line 134.
- First creation is owned by `scripts/provision_checkout.py` (13,837 B), which
  `scripts/deploy_all_lambdas.py:210-212` records as `provisioned_by`. That script deliberately
  sets `"EXPECTED_CONFIGURATION_NAME": ""` (line 223) and skips both readiness vars on update
  (lines 269-271), so a provisioned function starts in a refusing state — correct, and worth
  preserving.

### Packaging model: bundled, not layered

`scripts/deploy_all_lambdas.py:383-402` — `build_zip` copies the **entire** `lambda_utils` tree
into each non-standalone function's own zip:

```python
    if not spec.standalone:
        for path in _iter_dir(LAMBDA_UTILS):
            if path.suffix == ".py":
                members[f"lambda_utils/{path.relative_to(LAMBDA_UTILS).as_posix()}"] = path.read_bytes()
```

Layers exist only for native wheels (`cryptography-python312:1` on whatsapp-business-api); they
carry no `lambda_utils`. So a fresh `deploy_all_lambdas.py` run *would* ship the current shared
modules everywhere — the gap is purely that these functions have not been redeployed.

### Live alias versions and actual package contents

Measured 2026-10-01 by downloading each `live` package and listing its entries.

| Function | `live` version | Last modified | Code size | Layers |
|---|---|---|---|---|
| `wecare-wix-store` | **31** | 2026-09-29T00:55:13Z | 289,270 B | none |
| `wecare-razorpay-webhook` | **45** | 2026-09-30T06:07:02Z | 366,347 B | none |
| `wecare-whatsapp-business-api` | **57** | 2026-09-30T11:02:22Z | 820,021 B | `cryptography-python312:1` |
| `wecare-checkout` | — | — | — | does not exist |

Shared-module presence in the deployed `live` packages:

| Module | wix-store v31 | razorpay-webhook v45 | wa-business-api v57 |
|---|---|---|---|
| `ecommerce/cart_v2.py` | **ABSENT** | ABSENT | ABSENT |
| `ecommerce/customer_cart.py` | **ABSENT** | ABSENT | ABSENT |
| `ecommerce/payment_attempt.py` | ABSENT | PRESENT (identical to HEAD) | PRESENT (identical) |
| `ecommerce/order_creation.py` | ABSENT | PRESENT, **DIFFERENT** (18,237 B vs 19,252 B) | PRESENT, DIFFERENT |
| `ecommerce/order_keys.py` | **ABSENT** | PRESENT, **DIFFERENT** (28,521 B vs 33,081 B) | PRESENT, DIFFERENT |
| `ecommerce/wix_writeback.py` | ABSENT | **ABSENT** | ABSENT |
| `ecommerce/side_effect_guard.py` | ABSENT | **ABSENT** | ABSENT |
| `integrations/razorpay_verify.py` | ABSENT | PRESENT, **DIFFERENT** (7,743 B vs 8,978 B) | PRESENT, DIFFERENT |
| `payment_readiness.py` | ABSENT | PRESENT, **DIFFERENT** (22,473 B vs 23,726 B) | PRESENT, DIFFERENT |
| `wix_ecom.py` | **ABSENT** | ABSENT | ABSENT |

Handler drift:

| Function | deployed vs HEAD `handler.py` |
|---|---|
| `wecare-wix-store` | **DIFFERENT** (60,182 B vs 64,379 B) |
| `wecare-razorpay-webhook` | **DIFFERENT** (99,985 B vs 100,148 B) |
| `wecare-whatsapp-business-api` | **SAME** (290,069 B, byte-identical) |

The deployed wix-store v31 is internally consistent rather than broken: its `lambda_utils/ecommerce/`
holds only `__init__.py` and `wix_domain.py`, and its handler's top-level imports stop at
`from lambda_utils.ecommerce.wix_domain import (...)`. It contains no mention of `cart_v2`,
`customer_cart` or `WIX_CART_V2_ENABLED`. HEAD's handler adds
`from lambda_utils.ecommerce import order_keys` at line 35 — a module-level import of a file absent
from v31 — so **deploying HEAD's handler without the shared tree would break wix-store at cold
start.** The bundled model makes that a non-issue as long as `deploy_all_lambdas.py` is used.

`wix_writeback` and `side_effect_guard` are absent from every deployed package *and* have no
non-test importer anywhere in `amplify/` or `scripts/`. Phase 11's Wix order writeback exists as a
module and as tests, and is wired to nothing.

### Live environment: stale provider identifiers

| Function | Variable | Live value | Manifest / source expectation |
|---|---|---|---|
| `wecare-whatsapp-business-api` | `RAZORPAY_MID` | `[retired Razorpay account]` | `acc_TTFSyolquKEZEy` — **stale on live** |
| `wecare-whatsapp-business-api` | `RAZORPAY_UPI_ID` | `[retired UPI VPA]` | `wecaredigitalbh511413.rzp@rxairtel` — **stale on live** |
| `wecare-wix-store` | `WIX_CART_V2_ENABLED` | **absent** | `true` required by D7 |
| `wecare-wix-store` | `WIX_SITE_ID` | `fcd82f0c-9572-49c7-acfb-88fb05042ece` | matches R0.10 confirmed id |
| `wecare-razorpay-webhook` | `COMMERCE_KEYS_TABLE` / `WIX_ORDER_IDS_TABLE` | both absent | falls back to the hardcoded `stack-wecare-digital-WixOrderIds`, which exists — benign |

This confirms the `tasks.md` note that the manifest MID/VPA correction "is **not yet pushed live**".
`payment_readiness.evaluate` compares against `expected_provider_mid` and refuses on disagreement,
so a live readiness check run today with the live env would return `RAZORPAY_MID_MISMATCH` — a
blocking state, correctly.

---

## Retirement inventory

### Files

`integrations/wix-velo-payment/` — 14 files, 124 KB:

```
DEPLOYMENT-STATUS.md
INSTALLATION.md
KIRO-IMPLEMENTATION-PROMPT.md          <- superseded master prompt, 1700+ lines
TEST-RESULTS.txt
backend/http-functions.js
backend/wecare/core.js
backend/wecare/notifications.js
backend/wecare/runtime.js
backend/wecare/security.js
package.json                           name: wecare-wix-velo-handoff, private
tests/adapter.test.js
tests/notifications.test.js
velo-service-plugin/wecare-config.js
velo-service-plugin/wecare.js
```

`integrations/wix-psp/` — 4 files, 16 KB:

```
README.md
package.json                           name: wecare-wix-psp-auth, private
request-auth.js
tests/request-auth.test.js
```

### Every reference, classified

| Reference | Path:line | Classification |
|---|---|---|
| Audit narrative | `.agents/tasks/section68-current-state-audit-20261001.md:282,405` | **safe to remove** (doc cross-reference only; keep as history) |
| Change-authority record | `docs/execution/change-authority-matrix.md:531,534` | **keep** — the authorization record for their creation; annotate, do not delete |
| Prior-session scratch | `.scratch/phase-a-retirement-inventory-20261001.md:16,17,37` | gitignored scratch; not a dependency |
| `.github/workflows/**` | *no matches* | **no CI dependency** |
| Root `package.json` | no `workspaces` key; no script references `integrations/` | **not part of any build** |
| `vitest.config.*` | `include: [ 'src/**/*.{test,spec}.{ts,tsx}' ]` | **their tests never run** in CI or `npm test` |
| `config/lambda-env-manifest.json` | no `velo` / `psp` / `PROVIDER_MODE` key | **no env dependency** |
| Python imports | no `.py` file references either directory | **no runtime dependency** |
| UI entry | no `src/**` reference | **none** |
| AWS Lambda | `list-functions` filtered for `velo\|psp\|bridge\|checkout\|cart` → **empty** | **no deployed surface** |
| API routes | 359 routes filtered for `velo\|notification\|lease\|claim\|ack` → no bridge routes | **no deployed surface** |

**Conclusion: both directories are fully isolated. There is no active dependency to rewire.** They
are source-only, npm-private, excluded from the build, excluded from CI, excluded from vitest, and
have no AWS footprint. Removal is a pure deletion.

### The one genuinely reusable utility

`integrations/wix-psp/request-auth.js` — `verifyWixRequest({ digest, rawBody, publicKey, now })`.
A hardened RS256 Digest-JWT verifier: pinned operator public key (never from the JWT header),
`alg` allowlist, `crit`/`b64` rejection, base64url round-trip validation, `iat`/`exp`/`nbf`
bounds, `timingSafeEqual` on a SHA-256 of the exact raw bytes, 1 MiB body cap, single opaque
error. 16 offline tests.

It is **not** reusable as-is for this architecture — it verifies *Wix PSP* requests, and there is
no Wix PSP. Its value is as a reference pattern for webhook signature verification generally
(specifically: pinned key, raw-bytes digest, constant-time compare, opaque failure). If any of that
discipline is missing from the Meta or Razorpay verification paths, extract the pattern rather than
the file. Otherwise it goes with the rest.

`backend/wecare/security.js` and `backend/wecare/core.js` were not audited for extractable
patterns — **UNKNOWN** whether they hold anything not already present in
`lambda_utils/integrations/`.

### Superseded checkout plans that claim native/Velo is the architecture

| File | Claim | Disposition |
|---|---|---|
| `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:15` | "This document supersedes the earlier pasted prompt. The new checkout path is WIX_NATIVE_PROVIDER." | **the primary competing master prompt.** Directly contradicts the owner decision. Must be marked superseded or removed |
| same:755 | "checkoutMode = WIX_NATIVE_PROVIDER" | superseded |
| same:969 | "Never call create-order for WIX_NATIVE_PROVIDER" | superseded — the active path *must* create the order |
| same:1089 | "use wix-payment-provider-backend.submitEvent" | superseded |
| `integrations/wix-velo-payment/INSTALLATION.md` | Velo install procedure | superseded |
| `integrations/wix-velo-payment/DEPLOYMENT-STATUS.md` | already self-corrects: "A Git push of this package does not deploy Velo" (2026-10-01 recheck) | **keep as evidence** — it is the record that the prototype was never deployable |
| `integrations/wix-psp/README.md` | external PSP onboarding plan, blocked on owner PSP-licence clarification | superseded by the owner decision; keep the licence question as history |

No `.kiro/steering/` file claims native or Velo is the architecture. `whatsapp-payments-india-reference.md`
is consistent with the headless decision. `.kiro/specs/whatsapp-wix-commerce/tasks.md:3-5` already
carries the correct owner decision header dated 2026-10-01. The contradiction is confined to
`integrations/`.

One live steering-vs-code contradiction worth noting separately, because it is not about Velo:
`whatsapp-payments-india-reference.md` says `_build_payment_settings` in `messaging/outbound-whatsapp`
"is the single place that resolves" the payment configuration name and that task 9.4 says to reuse
it. The checkout handler does not call it — it passes `EXPECTED_CONFIGURATION_NAME` through an
invented route to `whatsapp-business-api` instead. Task 9.4 is still open, so this is a gap rather
than a violation.

---

## Spec state

`.kiro/specs/whatsapp-wix-commerce/` — requirements 550 lines, design 495, tasks 463.
**30 tasks `[x]`, 84 tasks `[ ]`.**

### R5.4 — Cart V2 unifies cart and checkout

`requirements.md` R5, criterion 4:

> The system SHALL support add, update quantity, remove, and recalculate on a Wix **Cart V2**
> entity. There is no separate "create checkout" step: Cart V2 unifies cart and checkout, so the
> authoritative total comes from **Calculate Cart** … (Cart V1 / Checkout V1 are removed by Wix on
> 2027-02-01; see design D7.)

Satisfied by task **8.2 `[x]`**. **The active checkout handler contradicts it** (C5): it calls
Checkout V1 and stores `wixCheckoutId`, the exact artifact D4 says does not exist.

### R7 — Payment reconciliation (8 criteria)

- R7.1 requires loading "the immutable PaymentAttempt and its bound Cart V2 calculation, and
  confirm the provider payment belongs to that attempt." The binding requirement is implemented in
  `razorpay_verify`; the *bound Cart V2 calculation* does not exist (V1 checkout, no calculation
  snapshot, no price verification token stored). Task **10.1 `[ ]`**.
- R7.2 Wix order exactly once from the bound Cart V2 snapshot — task **10.2 `[ ]`**, module
  `wix_writeback.py` exists, **unwired and undeployed**.
- R7.3 record external payment — task **11.1 `[ ]`**.
- R7.4 no reachable Wix call can charge again, with an enumerating test — task **11.2 `[ ]`**.
  `tests/test_wix_writeback.py` exists and passes; whether it satisfies the enumeration
  requirement was not assessed — **UNKNOWN**.
- R7.5 unique `providerTransactionId` — task **11.3 `[ ]`**. `order_keys.claim_order_for_payment`
  writes a `PROVIDERPAYMENT#` row, so the mechanism exists.
- R7.6 wait and retry when Wix has not reconciled — task **10.3 `[ ]`**.
- R7.7 recoverable state, never lose a paid order — task **10.4 `[ ]`**. Per C1+C4 this is the
  criterion currently violated in the most dangerous direction.
- R7.8 fail closed and **raise for staff attention** on amount/currency mismatch — task
  **10.5 `[ ]`**. `PAID_BUT_BLOCKED_OUTCOMES` implements the raise; C1 discards it at the call
  site and C4 routes the real-world failure into the non-alarming set instead.

### D4 / D7

Both are design decisions, not tasks. D4 (`design.md:76-100`) fixes the phone-keyed backend cart
with **no Wix checkout page and no `wixCheckoutId`**. D7 (`design.md:101-164`) documents the V2
mechanics: Calculate Cart for the total, `summary.violations` as the blocking surface, Create Order
+ Add Payments after capture, Place Order excluded, and four deployment attestations
(`WIX_WRITEBACK_ENABLED`, `WIX_ECOM_WRITE_CONFIRMED`,
`WIX_CART_V2_WRITE_CONTRACT=cart-v2-external-v1`, plus the R0.10 site id). **None of the three
flag attestations is present in any live environment**; `WIX_CART_V2_ENABLED` is also absent.

### Phases 8-11

| Phase | State | Reality |
|---|---|---|
| 8 — Cart V2 | **8.1, 8.2, 8.3 all `[x]`** | source-complete, **not deployed** (absent from wix-store v31) and **not enabled** (`WIX_CART_V2_ENABLED` unset). Never reached by the checkout path |
| 9 — WhatsApp payment request | 9.1-9.4 all `[ ]` | consistent: the send path is an invented route (C3) |
| 10 — Reconciliation | 10.1-10.5 all `[ ]` | consistent, but `_create_order_for_captured_payment` **is already live** on v45 in a state that satisfies none of them |
| 11 — Wix order + external payment | 11.1-11.5 all `[ ]` | consistent: `wix_writeback` unwired and undeployed |

### Tasks marked DONE that depend on a not-yet-deployed boundary

| Task | Claim | Why the claim outruns reality |
|---|---|---|
| **8.1** `[x]` | "Backend cart keyed on phone … conditional locks, durable request IDs and logical expiry" | `customer_cart.py` is absent from `wecare-wix-store:live` v31. No deployed code can create a `CUSTOMERCART#` row |
| **8.2** `[x]` | Cart V2 adapter in `wix-store`, verified by "contract test against the live V2 boundary (read/calc only)" | `cart_v2.py` is absent from v31. The evidence cited in D7 is a probe (`scripts/probe_wix_capabilities.py`) plus a redacted fixture — neither exercises the deployed function. The doc is honest about this: "The fixture proves populated Cart V2 shapes; it is not evidence of a successful payable checkout" |
| **8.3** `[x]` | Integer-minor-unit money, no floats | `money.py` is genuinely float-free and `ecommerce/money.py` is absent from every deployed package, so the property holds in source and is untested in production |
| **1.4** `[x]` | Unified payment status vocabulary | `payment_status.py` **is** deployed and byte-identical on all three functions. This one is real |
| **2.1-2.6** `[x]` | Identifier subsystem | `order_keys.py` is deployed on razorpay-webhook and wa-business-api but at an **older revision** (28,521 B vs 33,081 B). The reserved-number and `PAYREF#` behaviour live today may differ from what the tasks describe — re-verify before relying on it |

Also: `PaymentAttemptsTable`, `PaymentsTable`, `OrderTable` and `WixOrderIds` all report
`ItemCount: 0`, `ACTIVE`. No production data exists on any of these paths, which is the one piece
of good news: nothing has been mis-ordered yet, because nothing has been ordered.

---

## Dated AWS inventory — 2026-10-01

```
aws sts get-caller-identity
  Account : 775261844268
  Arn     : arn:aws:iam::775261844268:user/wecare-admin
  UserId  : AIDA3JAJU6MWDGITV2A7L
Region    : us-east-1        Profile: wecare-prod
```

| Item | Value |
|---|---|
| Lambda functions | **66** (unique names, `list-functions` fully paginated) |
| HTTP API | `zllr9lrg7j` — `wecare-digital-api`, `https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com` |
| Routes | **359** (`NextToken: null`) |
| `/ecommerce/*` routes | **0** |
| `/messages/send/*` routes | **0** |
| `wecare-wix-store:live` | **v31**, modified 2026-09-29T00:55:13Z, 289,270 B, no layers |
| `wecare-razorpay-webhook:live` | **v45**, modified 2026-09-30T06:07:02Z, 366,347 B, no layers |
| `wecare-whatsapp-business-api:live` | **v57**, modified 2026-09-30T11:02:22Z, 820,021 B, layer `cryptography-python312:1` |
| `wecare-checkout` | **does not exist** |
| `stack-wecare-digital-PaymentAttemptsTable` | ACTIVE, 0 items |
| `stack-wecare-digital-PaymentsTable` | ACTIVE, 0 items |
| `stack-wecare-digital-OrderTable` | ACTIVE, 0 items |
| `stack-wecare-digital-WixOrderIds` | ACTIVE, 0 items |

Packaging model: **bundled** — `scripts/deploy_all_lambdas.py:390-398` copies the whole
`lambda_utils` tree into each function zip. Layers carry native wheels only, no shared Python.

Test suite (`.venv/bin/python -m pytest`, 8 checkout-related files): **236 passed in 0.37s.**

Not verified in this pass, marked **UNKNOWN**: any live Meta `payment_configurations` readback (no
send or Graph call was made); the actual current Razorpay account state; whether the four Meta
payment configurations the owner reported on 2026-09-30 are still Active; whether
`tests/test_wix_writeback.py` satisfies R7.4's enumeration requirement; whether
`integrations/wix-velo-payment/backend/wecare/{security,core}.js` hold extractable patterns.

---

## Conclusions

1. **The headless checkout is four independent breaks away from working, and they are in series.**
   Readiness readback (C3b) → payment send (C3a) → provider binding (C4) → status/order-number
   contract (C6). Fixing any one alone changes nothing observable.
2. **C1 + C4 together are the dangerous combination.** The missing binding makes reconciliation
   return `PROVIDER_UNAVAILABLE`, which is classified as "money did not move", so it neither alarms
   nor blocks. The webhook then marks the invoice paid, generates the GST invoice, sends it on
   WhatsApp, fires a Meta Purchase conversion, and sends an `order_status` message — for an order
   that does not exist. `OrderTable` holding 0 rows is the only reason this has not happened yet.
3. **The active code is on the Wix API version the design says does not exist**, and which Wix
   removes on 2027-02-01. Cart V2 is fully built, fully tested, deployed nowhere, enabled nowhere,
   and unreachable from checkout.
4. **The test suite cannot see any of it.** Every stub sits at a seam. This is not sloppiness —
   each stub is individually reasonable — but the net effect is a green suite over a
   non-functioning path, and that pattern will repeat unless at least one test drives a real route
   name and a real (unstubbed) verifier against a real attempt record.
5. **Velo and PSP retirement is free.** No imports, no CI, no env keys, no AWS surface, no build
   participation. The only thing that needs care is `KIRO-IMPLEMENTATION-PROMPT.md`, which is an
   actively misleading competing master prompt.

## Recommendations (not implemented)

Ordered by what unblocks the most, and by which ones are safe to do without a live payment.

1. **Decide the Wix API version first, then write the binding.** Everything else depends on it. If
   Cart V2 is the answer (D4/D7 say it is), `checkout/handler.py` must resolve the phone-keyed
   `CUSTOMERCART#` cart and call Calculate Cart instead of `create_checkout`, and the attempt must
   carry the cart id + revision + calculation snapshot instead of `wixCheckoutId`. Doing the
   binding work against V1 first would have to be redone.
2. **Make something write `providerOrderId`.** The verifier's docstring names the two legitimate
   sources: "payment initiation or an authenticated Meta lookup". Initiation cannot supply a
   Razorpay order id (Meta creates it), so the realistic source is the Meta Payment Lookup route —
   `GET /wa-business/payment-lookup` already exists (`whatsapp-business-api/handler.py:6105-6110`,
   `_payment_lookup(phone_id, config_name, reference_id)`) and is the authenticated read that can
   bind the reference to a provider order id before the webhook needs it. Store it via
   `payment_attempt.transition(..., provider_order_id=...)` **and** on the `PAYREF#` row, since
   the webhook reads the latter.
3. **Reclassify `PROVIDER_UNAVAILABLE` for the post-capture case, or split it.** "We could not
   reach the provider" and "the attempt has no binding, so we structurally cannot verify" are
   different facts with different operational responses. The second should alarm.
4. **Consume the reconciliation outcome at the call site.** Gate `_mark_invoice_paid_by_reference`,
   `_post_payment_handler`, `_log_ctwa_purchase` and the `order_status` send on
   `result['hasOrder']`, with the paid-but-no-order case going to the `PAID_BUT_NO_ORDER` alarm
   instead. Note the legitimate constraint: invoice-only payments that never had an attempt must
   keep working, so the gate needs to distinguish "no attempt exists" (existing flows — proceed)
   from "an attempt exists and reconciliation failed" (stop and alarm).
5. **Fix the two invented routes.** Point `_fetch_payment_configurations` at
   `/wa-business/payment-config/check` with `wabaId` (it exists, it takes that parameter, and it is
   on the API), and either add an `interactive-payment` branch to `_route_send_message` or route the
   send through `outbound-whatsapp`'s `_build_payment_settings` as task 9.4 and the payments
   steering both instruct.
6. **Close the status loop.** Have reconciliation write `PAYMENT_PAID` (with the provider payment
   id) to `PaymentAttemptsTable` under the existing monotonic `condition_expression()`, and have
   `_status` resolve the order number via `order_keys.resolve_order_for_payment` and pass it as
   `payment_history_entry(owned, order_number=...)`. Then provision the `/ecommerce/checkout` and
   `/ecommerce/checkout/status` routes the frontend already calls.
7. **Add one seam test that does not stub.** Assert the literal route string the checkout posts is
   accepted by `_route_send_message`, and drive `reconcile_payment` through the *real*
   `verifier_for_event` against an attempt record built by the *real* initiation path. Either test
   alone would have caught C3 and C4 respectively.
8. **Retire Velo/PSP as a deletion.** Before removing, annotate
   `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md` as superseded rather than silently
   deleting it, and preserve `DEPLOYMENT-STATUS.md` plus the
   `docs/execution/change-authority-matrix.md:531-534` entry as the evidence trail. Consider
   extracting the pinned-key / raw-bytes / constant-time verification pattern from
   `integrations/wix-psp/request-auth.js` into a note if the Meta and Razorpay paths lack any of it.
9. **Redeploy before trusting any `[x]` in Phases 2 or 8.** `order_keys.py`, `order_creation.py`,
   `razorpay_verify.py` and `payment_readiness.py` are all deployed at older revisions than HEAD,
   and `cart_v2`/`customer_cart`/`wix_writeback`/`side_effect_guard` are not deployed at all. Push
   the corrected `RAZORPAY_MID` / `RAZORPAY_UPI_ID` with it, or readiness will keep returning
   `RAZORPAY_MID_MISMATCH`.
