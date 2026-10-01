# Design review — payment-integrity closure

**Reviewed 2026-10-01 (Asia/Kolkata), read-only.** Target:
`.agents/tasks/payment-integrity-closure-2026-10-01/design.md`, against
`audit-reconcile.md` and the real source at the tree below. No file was edited, nothing was
staged, no AWS mutation, no `get-secret-value` in any spelling, no credential value appears here.

Reviewed cold: I did not have the context that produced the design, and every claim it makes about
existing code was re-read rather than taken on trust.

| Item | Value |
|---|---|
| Branch | `stack` |
| HEAD at review time | `25eace20` — "fix: stop the public surface sending customers into the staff workspace" |
| HEAD the design claims | `43b26d4a` — **already stale** (see NIT-2) |
| `wecare-razorpay-webhook` `live` | not re-measured; the design's v45 is consistent with the audit |

**Verdict: CHANGES_REQUESTED** — 6 HIGH, 12 MEDIUM, 5 NIT.

The shape of the design is right, and three of its central ideas are better than what they replace:
the disposition layer, the stage/park split, and the cross-channel `PROVIDERPAYMENT#` claim. The
findings below are not objections to that structure. They are places where the specified behaviour
still allows a captured payment to produce **zero** paid orders with no durable record, where two
sections contradict each other on a money path, and where the verification story rests on a test
fixture that cannot evaluate the conditions the design is built from.

---

## Findings

### HIGH-1 — `ATTEMPT_NOT_PAYABLE` is classified as "no money moved", but one of its two return sites fires *after* a verified capture

**Where.** §3.1 set membership (`NO_ORDER_OUTCOMES = frozenset({NOT_PAID, ATTEMPT_NOT_PAYABLE})`,
"money did not move"), §3.2 (`NO_MONEY`), §3.3 (`NO_MONEY` → "200, lease closes, nothing owed, no
alarm"), §12 (no row for it at all).

**The problem.** `order_creation.reconcile_payment` returns `ATTEMPT_NOT_PAYABLE` in two places, and
they are on opposite sides of the provider call:

```python
# BEFORE the provider call — money state genuinely unknown
if attempt.get("checkoutMode") not in (None, "WIX_HEADLESS"):
    return _blocked(ATTEMPT_NOT_PAYABLE, "unsupported checkout origin")

# AFTER `paid` is True and after amount+currency matched — THE MONEY IS OURS
if not payment_attempt.may_create_order({**attempt, "status": payment_attempt.PAYMENT_PAID}):
    return _blocked(ATTEMPT_NOT_PAYABLE,
                    "a verified capture did not satisfy the order-eligibility rule", ...)
```

The second site sits below the design's own line *"Everything past this point: THE MONEY IS OURS."*
Under the design, it produces: `NO_MONEY` → **200, dedup lease closed, one INFO line, no
`PAID_BUT_NO_ORDER` alarm, no recovery row.** The provider stops retrying. The payment is captured,
no order exists, and nothing durable records that. The first site is nearly as bad: a reference whose
attempt carries a foreign `checkoutMode` is refused before verification, so we never learn whether
money moved, and we close the lease anyway.

This is the exact condition the brief names as HIGH ("a captured payment could produce zero ... paid
order").

**Fix.** Split the outcome by side of the provider call, and keep only the pre-verification one in
`NO_MONEY`:

```python
ATTEMPT_NOT_PAYABLE  = "ATTEMPT_NOT_PAYABLE"    # refused BEFORE verifying: no provider call made
PAID_BUT_NOT_ELIGIBLE = "PAID_BUT_NOT_ELIGIBLE" # verified capture failed the eligibility rule

NO_ORDER_OUTCOMES         = frozenset({NOT_PAID, ATTEMPT_NOT_PAYABLE})
PAID_BUT_BLOCKED_OUTCOMES = frozenset({..., PAID_BUT_NOT_ELIGIBLE})
PERMANENT_OUTCOMES        = frozenset({..., PAID_BUT_NOT_ELIGIBLE})
```

and change the pre-verification `checkoutMode` refusal so it does not close the lease on an
unverified capture: either verify first and then refuse (preferred — it is one authenticated read and
it turns a guess into a fact), or classify it `TRANSIENT` until a human confirms the reference is not
ours. Add a §12 row for each, and a test
`test_a_verified_capture_that_fails_eligibility_is_paid_but_blocked` asserting one alarm, one
recovery row, and a closed lease.

---

### HIGH-2 — event-supplied `notes.purpose` still selects the subject, so two financial branches run before any materialized order and one of them leaves no record

**Where.** §3.3 claims "`_handle_payment_captured` is restructured so that **no financial side effect
is lexically reachable without a materialized order**", and lists five effects now confined to
`_handle_legacy_capture`. §7 restructures the wallet branch. §5.2 records the secure-files path as
"examined and deliberately unchanged".

**The problem.** Both of the early branches are *above* the restructured block in
`_handle_payment_captured`, and both `return`:

```python
if (notes or {}).get('purpose') == 'wallet_topup' and (notes or {}).get('wabaId'):
    ... partner_billing.topup(...) ...
    return
if (notes or {}).get('purpose') == 'secure_file_download' and order_id:
    _dispatch_download_grant_confirmation(order_id, request_id)
    return
```

`notes` is event-supplied. The design is explicit everywhere else that notes are "lookup keys only",
yet `purpose` still decides **which verification boundary applies at all**. Consequences as specified:

- A genuine commerce capture whose notes carry `purpose: wallet_topup` is routed to the wallet path,
  resolves no intent, lands as `STRUCTURAL` with a *wallet* recovery row, and **never reaches commerce
  reconciliation**. The sweep re-runs "the top-up path for a top-up", so it never tries commerce
  either. Zero paid orders, permanently, absent a human who reads the row and realises it is
  misclassified.
- A commerce capture carrying `purpose: secure_file_download` plus an `order_id` returns after a
  fire-and-forget invoke with **no recovery row at all**. That branch is unchanged by the design and
  writes nothing durable about an unresolved commerce payment.
- So §3.3's "lexically unreachable" claim is false as written: two money-touching branches precede the
  structure that is supposed to make it true.

**Fix.** Resolve the subject from **server state**, not from `purpose`. Before any branch:

```python
subjects = _resolve_subjects(reference_id, notes, payment)   # consults STORAGE only
#   commerce : order_keys.resolve_payment_reference(keys, reference_id)   (ConsistentRead)
#   topup    : TOPUPINTENT#<id> / TOPUPLINK#<link id>
#   legacy   : InvoicesTable referenceId-index, provenance == LEGACY_WHATSAPP_INVOICE
#   file     : the secure-files grant for order_id
if len(subjects) != 1:
    _record_unresolved(..., outcome='AMBIGUOUS_SUBJECT' if subjects else 'NO_STORED_SUBJECT')
    return            # PERMANENT: more than one stored subject, or none
```

`notes.purpose` may then be logged as a hint and compared for corroboration (`subject_hint_disagree`),
exactly as §6 downgrades `notes.referenceId` from authority to corroboration. Pin it with
`test_notes_purpose_cannot_route_a_commerce_capture_away_from_commerce` and
`test_a_capture_with_no_stored_subject_always_leaves_a_recovery_row`.

---

### HIGH-3 — the inbound-WhatsApp `authorize()` call never names a server-stored expected amount, so obligation 4 is self-referential on that channel

**Where.** §5.3. `authorize` is called with `stored_binding` = the outbound row's
`{paymentConfigName, awsPhoneNumberId, referenceId}` and `verify` = the Meta lookup closure.
`expected_amount_paise` and `expected_currency` are not specified for this call.

**The problem.** The only amount in scope at that point in `_process_payment_status` is
`actual_amount`, which is derived from the inbound webhook payload. If that is what is passed, the
amount obligation compares the event against itself and passes unconditionally — and the four side
effects behind it are `_mark_invoice_paid_by_reference`, `_send_order_status_message`,
`_generate_invoice_for_captured_payment` (a GST document) and the balance-due notification. An
under-payment or a forged amount would mark an invoice paid and issue a tax document for it. §5.1
obligation 4 is the one obligation that cannot be satisfied by a value taken from the thing being
verified, and this is the only call site where the design does not say where it comes from.

**Fix.** State the source explicitly and make it storage:

```python
invoice = _sole_invoice_for_reference(reference_id)        # exactly one row, else refuse
expected = money.positive_paise(invoice['amountPaise'])    # stored integer paise, NOT invoice['total']
authority = capture_authority.authorize(
    channel="whatsapp_meta", subject_kind=SUBJECT_LEGACY_INVOICE,
    subject_id=invoice['invoiceId'], stored_binding=outbound_binding,
    verify=_meta_payment_lookup, expected_amount_paise=expected,
    expected_currency="INR", claim_table=keys)
```

If `amountPaise` is not stored on those invoice rows, say so and add it to the producer in the same
change — a display `total` a staff edit can move is not an authority, which §6 already argues for the
Razorpay legacy path and must argue identically here. Add
`test_the_whatsapp_path_compares_against_the_stored_invoice_amount` driving a lookup that reports a
different amount and asserting no invoice write and no GST document.

---

### HIGH-4 — the legacy path's "permanent" refusals are specified as `raise CaptureUnresolved`, which is the transport's TRANSIENT signal

**Where.** §6 `_legacy_binding` docstring: "Absence of ANY part -> `CaptureUnresolved('LEGACY_BINDING_ABSENT')`,
classified **PERMANENT**". §6 `_handle_legacy_capture` pseudocode: `_sole_legacy_invoice(reference_id)
# exactly one row, else PERMANENT`. Against §3.3, where `raise CaptureUnresolved(...)` is the
**TRANSIENT** arm, and §12, where `CaptureUnresolved` → 500, lease open.

**The problem.** The design gives `CaptureUnresolved` one meaning in the transport ("retry me") and the
opposite meaning inside the legacy path ("never retry me"). Only one can hold. The two readings
produce different failures, and both are bad:

- If the raise reaches the outer `except Exception`, a permanently unbindable legacy capture returns
  500 with the lease open and is retried by Razorpay until it gives up — the unbounded-retry defect of
  audit §4.3 that §3.3 claims to have closed, reintroduced on the legacy branch. Whether a recovery
  row is written is also unstated, because `_record_unresolved` is only shown on the
  `not authority.allowed` path, not on the raising paths.
- If something catches it and maps it to `PERMANENT`, the catch site, the recovery-row write and the
  200 are all unspecified.

This matters more than it looks, because HIGH-2's misrouting and MEDIUM-2's `load_attempt` collapse
both funnel genuine commerce captures into exactly this branch.

**Fix.** Make the legacy path return a verdict rather than raise, so one mechanism routes everything:

```python
def _handle_legacy_capture(payment, reference_id, request_id) -> None:
    verdict = _legacy_verdict(payment, reference_id)      # never raises CaptureUnresolved
    if verdict['disposition'] == order_creation.MATERIALIZED:
        _run_legacy_effects(verdict); return
    _record_unresolved(verdict, payment, reference_id, request_id)   # ALWAYS, before anything else
    if verdict['disposition'] == order_creation.PERMANENT:
        return                                            # 200, lease closed
    raise CaptureUnresolved(verdict['outcome'])            # TRANSIENT only
```

with `LEGACY_BINDING_ABSENT`, `LEGACY_INVOICE_AMBIGUOUS` and `LEGACY_NOTES_DISAGREE` added as
outcomes in `PERMANENT_OUTCOMES`, and `CaptureUnresolved`'s docstring amended to say it means
TRANSIENT and nothing else. Add §12 rows for each.

---

### HIGH-5 — the named tests cannot run: `FakeDynamo` rejects every condition shape the design is built from

**Where.** §15 ("Unit-testable offline, no network, no AWS, against `tests/crm_fake_dynamo.FakeDynamo`:
... `recovery` (every state transition, lease CAS, backoff ...), `payment_attempt.gateway_binding`,
`initiation.bind_gateway_order`, `finalization` stage monotonicity, ...
`partner_billing.credit_topup_once` ..."), §15.2 test inventory, §18 landing sequence (tests at every
step, full suite green at step 7).

**The problem.** Measured in `tests/crm_fake_dynamo.py`, the fake:

- **raises `AssertionError("this fake does not implement OR; teach it before using one")`** on any
  condition containing ` OR `;
- understands only `attribute_exists(X)`, `attribute_not_exists(X)` and `X = :v`, joined by `AND`, and
  **raises** `unrecognised condition fragment` on anything else — so `<=`, `<`, `>=` and
  `contains(...)` are all hard errors;
- supports `ADD` of **a numeric placeholder to one attribute** only — no string-set `ADD`;
- exposes `Table()` resources with no `transact_write_items`, so §7.1's two-`Put` transaction has no
  fake at all.

Every monotonic and idempotency primitive the design specifies trips one of those: `_stage`
(`attribute_not_exists(#rank) OR #rank <= :rank`), `record_paid` (which already carries an OR today,
which is precisely why `finalization.py` has zero tests), `binding_condition_expression()` (OR),
`recovery`'s `stateRank` conditions (OR + comparison), `credit_topup_once`
(`attribute_not_exists(appliedTopups) OR NOT contains(appliedTopups, :key)` + set `ADD`), and
`lease()`'s CAS. It fails loudly rather than silently, which is better — but it means the listed test
files cannot be written as described, and this change has **no other evidence**: no deploy, no live
verification, `live` stays at v45.

**Fix.** Make the fixture work a named, first step with its own acceptance criteria, before step 1 of
§18:

> **Step 0.** Extend `tests/crm_fake_dynamo.py` to evaluate: `OR` with correct precedence against
> parenthesised groups; the comparison operators `<`, `<=`, `>`, `>=` against numeric placeholders;
> `contains(attr, :v)` and `NOT contains(...)` over string sets and strings; `ADD` of a string set;
> and add a `FakeClient.transact_write_items` honouring per-item `ConditionExpression` with
> all-or-nothing semantics and a `TransactionCanceledException` carrying `CancellationReasons`.
> Acceptance: `tests/test_fake_dynamo_grammar.py` asserts each new form **refuses** the case real
> DynamoDB refuses, and that an unparsed fragment still raises rather than passing.

The alternative — asserting on the expression strings instead of evaluating them — must be rejected
explicitly if chosen, because a test that only pins the text of a ConditionExpression cannot catch the
`OR`-precedence bug §9.3 correction 2 exists to prevent.

---

### HIGH-6 — `credit_topup_once` reports a never-credited top-up as success

**Where.** §7.3: *"A `ConditionalCheckFailedException` on the `contains` arm means ALREADY CREDITED and
is returned as success with `credited: False`"*, with
`ConditionExpression: attribute_exists(wabaId) AND (attribute_not_exists(appliedTopups) OR NOT contains(appliedTopups, :key))`.

**The problem.** DynamoDB does not tell you which arm failed. `attribute_exists(wabaId)` and the set
check raise the identical exception, so "on the `contains` arm" is not a distinction the code can
make. A verified, captured top-up against a wallet row that does not exist therefore returns
`{credited: False}` = success, the recovery row is marked `RESOLVED`, and the money is never credited
and never flagged. Two supporting facts from the real module make this reachable rather than
theoretical:

- `partner_billing.topup` calls `ensure_wallet(waba_id, currency)` first precisely because the wallet
  row may not exist. `credit_topup_once` as specified drops that call.
- `topup` also sets `#s = :active` (`status = 'ACTIVE'`). `credit_topup_once` drops that too, so a
  suspended wallet paying to un-suspend itself stays suspended — which is the main reason a partner
  tops up.

**Fix.** Disambiguate by read-back, and keep the two behaviours the existing writer has:

```python
def credit_topup_once(waba_id, amount_paise, *, idempotency_key, ...):
    ensure_wallet(waba_id)                       # same precondition topup() has always had
    try:
        resp = wallet.update_item(
            Key={'wabaId': waba_id},
            UpdateExpression=('SET balance = balance + :amount, #s = :active, updatedAt = :now '
                              'ADD appliedTopups :keyset'),
            ConditionExpression=('attribute_exists(wabaId) AND '
                                 '(attribute_not_exists(appliedTopups) '
                                 ' OR NOT contains(appliedTopups, :key))'), ...)
    except ClientError as exc:
        if not _conditional(exc):
            raise
        row = wallet.get_item(Key={'wabaId': waba_id}, ConsistentRead=True).get('Item')
        if row is None:
            raise WalletMissing(waba_id)                       # TRANSIENT: recovery row stays open
        if idempotency_key in (row.get('appliedTopups') or set()):
            return {'credited': False, 'balance': row['balance']}   # genuinely already credited
        raise                                                  # anything else is unexplained
```

Add `test_a_credit_against_a_missing_wallet_is_never_reported_as_credited` and
`test_a_verified_topup_reactivates_a_suspended_wallet`.

---

### MEDIUM-1 — the outcome enumeration is not a partition, and `disposition()` is not total over what the handler actually returns

**Where.** §3.1 sets, §3.2 (`disposition` "raises `ValueError` for an unrecognised outcome" and a test
"asserts the function is total over every `*_OUTCOMES` member plus `ORDER_CREATED` /
`ORDER_ALREADY_EXISTS` / `RECONCILIATION_ERROR`"), §3.3 (`disp = verdict.get('disposition')`).

Three concrete holes:

1. **`NOT_A_COMMERCE_REFERENCE` is in no set.** It is the one outcome that unlocks the legacy branch,
   and the stated totality test would not cover it.
2. **`RECONCILIATION_ERROR` is not a constant.** It is a raw string literal in
   `razorpay-webhook/handler.py`'s `except` fallback; the test as written cannot reference it from
   `order_creation`, and it is in no set, so `disposition('RECONCILIATION_ERROR')` raises.
3. **`NO_PROVIDER_ID` is unclassified and un-dispositioned.** `_create_order_for_captured_payment`
   returns `{'outcome': 'NO_PROVIDER_ID', 'hasOrder': False}` early, with no `disposition` key. §3.3's
   `verdict.get('disposition')` is then `None`, which matches none of the four branches, so control
   reaches `_record_unresolved` with no `classification` and then
   `raise CaptureUnresolved('NO_PROVIDER_ID')` → 500, lease open, retried forever on an event that can
   never acquire a provider id.

**Fix.** One source of truth and a partition test:

```python
ALL_OUTCOMES = frozenset({ORDER_CREATED, ORDER_ALREADY_EXISTS, RECONCILIATION_ERROR,
                          NO_PROVIDER_ID, NOT_A_COMMERCE_REFERENCE}
                         | NO_ORDER_OUTCOMES | PAID_BUT_BLOCKED_OUTCOMES)
```

promote `RECONCILIATION_ERROR` and `NO_PROVIDER_ID` to constants in `order_creation`, classify both as
`TRANSIENT` and `PERMANENT` respectively, and assert in `tests/test_order_creation.py`:
`disposition` is total over `ALL_OUTCOMES`; `PERMANENT_OUTCOMES | TRANSIENT_OUTCOMES ==
PAID_BUT_BLOCKED_OUTCOMES` exactly (no overlap, no gap); and every return in
`_create_order_for_captured_payment` sets `disposition` (walk the AST of the function and assert each
`Return` of a dict literal carries the key).

---

### MEDIUM-2 — `load_attempt`'s two-valued contract cannot express the split that closes audit §4.2

**Where.** §3.1: "`load_attempt` returns `None` — a clean read, no row → `NOT_A_COMMERCE_REFERENCE`"
versus "the stored attempt carries no `paymentAttemptId` → `UNKNOWN_REFERENCE`", and the claim that
"a lost or lagging `PAYREF#` row now produces `ATTEMPT_STORE_UNAVAILABLE` or `UNKNOWN_REFERENCE`, both
paid-but-blocked, and can no longer be mistaken for 'this is a legacy invoice'".

**The problem.** The real `_load_attempt` in the webhook already collapses both facts into `None`:

```python
row = order_keys.resolve_payment_reference(table, ref)
if not row or not row.get('paymentAttemptId'):
    return None
```

So "no `PAYREF#` row" and "a `PAYREF#` row that exists but is unusable" are indistinguishable to
`reconcile_payment`, and both become `NOT_A_COMMERCE_REFERENCE` → `NOT_OURS` → the legacy branch. The
quoted claim is therefore not true of the specified code. (The one piece of good news I verified:
`order_keys._read_row` does use `ConsistentRead=True`, so a *lagging* read is not a source of this —
a lost or half-written row still is.)

**Fix.** Give the injected callable a three-valued contract and say so in both docstrings:

```python
class AttemptBindingUnusable(RuntimeError):
    """A PAYREF row exists for this reference but does not resolve to a usable attempt."""

def _load_attempt(ref):
    row = order_keys.resolve_payment_reference(table, ref)   # ConsistentRead
    if not row:
        return None                                  # positively not a commerce reference
    if not row.get('paymentAttemptId'):
        raise AttemptBindingUnusable('PAYREF row carries no paymentAttemptId')
    attempt = attempts.get_item(..., ConsistentRead=True).get('Item')
    if not attempt:
        raise AttemptBindingUnusable('PAYREF row names an attempt that does not exist')
    ...
```

and in `reconcile_payment` catch `AttemptBindingUnusable` → `UNKNOWN_REFERENCE` (paid-but-blocked,
PERMANENT) *before* the generic `except Exception` → `ATTEMPT_STORE_UNAVAILABLE`. Pin with
`test_a_payref_row_without_an_attempt_is_never_treated_as_legacy`.

---

### MEDIUM-3 — the verifier's selector rewrite would GET `/payments/<order id>` on the normal checkout path

**Where.** §4.4 point 1: "The current `target = bound_payment or payment_id` ... That line goes. The
selector is `bound_payment or bound_order`, and `providerOrderId` is required".

**The problem.** In `razorpay_verify.verifier_for_event`, `target` is used two ways: as the path
segment for `/payments/<target>`, and as the identity the returned payment must equal. Assigning
`bound_order` to it sends a Razorpay **order** id to the **payments** endpoint whenever
`providerPaymentId` is absent — and §4.2 says `providerPaymentId` is "optional at creation; present
only when the flow mints one up front", which for Razorpay Standard Checkout means it is normally
absent until capture. Result: a 404 → `RazorpayUnavailable` → `PROVIDER_UNAVAILABLE` → `TRANSIENT` on
**every real capture**, which is the retry-forever behaviour the design set out to remove, now reached
through a different door. It also contradicts §4.4's own branch structure, which still describes
reading `/orders/<bound order>/payments` when there is no bound payment.

**Fix.** Keep the two selectors distinct and never let one stand in for the other:

```python
if not bound_order:
    raise RazorpayBindingMissing("attempt carries no providerOrderId")
payment_selector = bound_payment            # may be "" — it is not a fallback for bound_order
if payment_selector:
    payments = [_get(f"/payments/{quote(payment_selector, safe='')}")]
else:
    payments = (_get(f"/orders/{quote(bound_order, safe='')}/payments").get("items") or [])
# the event's payment_id is only ever matched INSIDE this server-selected set
```

and state that the event's `payment_id` never appears in a URL. Add
`test_an_attempt_with_no_bound_payment_id_is_verified_through_the_order_endpoint`.

---

### MEDIUM-4 — `providerAmountPaise` creates a second authoritative amount with no stated relation to `attempt.amountPaise`

**Where.** §4.2 (`providerAmountPaise` — "the amount the gateway order was created FOR"), §4.3
(`bind_gateway_order`'s `ConditionExpression` asserts `referenceId` but not the amount), §4.4 point 3
(the verifier compares the provider's amount to `providerAmountPaise`), against
`order_creation.reconcile_payment`, which compares the provider's amount to `attempt['amountPaise']`.

**The problem.** After this change there are two stored amounts for one payment and nothing says they
must agree. Today they are both compared, so a divergence fails closed — but which one is the
*authority* is now undefined, `finalization` writes `attempt['amountPaise']` onto the order row, and a
future reader has no rule to apply. A binding written for a different amount than the attempt it
binds is a bug that should be impossible to write, not one caught downstream.

**Fix.** Assert equality at the seam, in the condition, so a divergent binding cannot be stored:

```python
ConditionExpression = ('attribute_exists(paymentAttemptId) AND referenceId = :ref '
                       'AND amountPaise = :amt '          # the attempt's authoritative total
                       'AND (' + payment_attempt.binding_condition_expression() + ')')
```

and add one line to §14: *"`attempt.amountPaise` is the single authoritative total;
`providerAmountPaise` is a stored copy of what was sent to the gateway and may only ever equal it."*
Test: `test_binding_a_different_amount_than_the_attempt_is_refused`.

---

### MEDIUM-5 — `providerMode` has no named source on the verification side, and the obvious one is secret-derived

**Where.** §4.4 point 3: "`payment` liveness vs `providerMode`". §11.1/§13 list `providerMode` as a
compared field. U-3 degrades only `account_id` when absent, not mode.

**The problem.** "Payment liveness" names no field. A Razorpay payment object does not carry a
documented `live`/`test` discriminator, and the natural substitute is the credential:
`key_id.startswith('rzp_live_')`. That path is a direct collision with §11.3 and with this
repository's own history — CodeQL `py/clear-text-logging-sensitive-data` has failed twice here on a
value reduced from a secret, including across function boundaries, and a ternary on a secret's
content is precisely the shape that was blocked. There is also an unstated redundancy worth writing
down: a live key cannot read a test payment, so the API read is already mode-scoped.

**Fix.** Pick one and write it down:

- **Preferred:** state that mode is enforced structurally by the credential used for the read, record
  `providerMode` on the binding for provenance only, and remove it from the compared obligations —
  with a comment saying why, so nobody re-adds the comparison.
- If it must be compared, name the exact response field, add it to U-3's degradation rule (absent →
  INFO line, remaining obligations stand), and state explicitly that the derived mode value **must
  not appear in any logging expression**, not even as a bool.

---

### MEDIUM-6 — the side-effect effect names do not add up, and the legacy/WhatsApp effects have no members in the closed set

**Where.** §2 module map ("`side_effect_guard.py` | two new effects in `KNOWN_EFFECTS`"), §9.4 (adds
`CART_COMPLETION`, `NOTIFICATION` and `WALLET_CREDIT` — three), §6 ("each behind `side_effect_guard`
keyed on `(invoiceId, effect)`" over six effects), §5.3 ("each of the four side effects in that handler
also becomes individually guarded by `side_effect_guard` keyed on the invoice id").

**The problem.** Three separate defects in one mechanism:

1. **Count disagreement**: two in §2, three in §9.4.
2. **A duplicate**: `KNOWN_EFFECTS` already contains `CONFIRMATION = "confirmation"`, and §9.4 adds
   `NOTIFICATION = "notification"` for the same effect, so one business action gets two namespaced
   marker keys and the "at most once" guarantee is per-name, not per-action.
3. **Missing members**: the legacy and WhatsApp paths are said to guard
   `_store_payment_record`, `_mark_invoice_paid_by_reference`, `_post_payment_handler` (the GST
   document), `_log_ctwa_purchase` (the Meta Purchase conversion), the `order_status` send and
   `_trigger_post_payment_flow`. None of those has a member in `KNOWN_EFFECTS`, and
   `side_effect_guard._validate` raises `ValueError` on an unknown effect — which, inside
   `_handle_legacy_capture` after the claim has been taken, means a 500 and an open lease on a payment
   that was successfully authorised.

**Fix.** Enumerate every effect the design guards, in the module, in one edit:

```python
WIX_ORDER = "wix_order"; WIX_PAYMENT = "wix_payment"; RECEIPT = "receipt"
CONFIRMATION = "confirmation"        # the WhatsApp order_status / confirmation message. REUSED.
CART_COMPLETION = "cart_completion"
PAYMENT_RECORD = "payment_record"    # _store_payment_record
INVOICE_PAID = "invoice_paid"        # _mark_invoice_paid_by_reference
GST_DOCUMENT = "gst_document"        # _post_payment_handler
META_PURCHASE = "meta_purchase"      # _log_ctwa_purchase
POST_PAYMENT_FLOW = "post_payment_flow"
WALLET_CREDIT = "wallet_credit"
```

Drop `NOTIFICATION`. Say in §9.4 that the count is nine additions, not two. And state the key
convention for a non-order subject, since `claim()`'s parameter is named `order_id` and `_validate`
requires it non-empty: either pass `LEGACY_INVOICE#<invoiceId>` / `TOPUPINTENT#<intentId>` as the
subject key, or rename the parameter to `subject_key` and update the existing callers and
`tests/test_side_effect_guard.py` in the same step.

---

### MEDIUM-7 — §9.4's `accept_paid` rewrite drops the purchased-snapshot precondition

**Where.** §9.4 pseudocode (`record_paid` → `PAYMENT_VERIFIED` → `orders.put_item(...)` → the effect
loop). §9.1 still lists `PURCHASED_SNAPSHOT_MISSING` as a `finalizationReason`.

**The problem.** The current `accept_paid` checks the snapshot **before** writing the order row and
parks when it is absent. The rewrite omits that check, and the order row it writes is built from
`attempt['purchasedSnapshot']` and `attempt['snapshotHash']` — so a paid attempt with no snapshot
raises `KeyError` rather than parking, and on the reading where the snapshot is simply omitted from
the item, an internal order would commit with no immutable purchased snapshot, which the brief treats
as part of what an order *is*.

**Fix.** Keep the gate, and keep it before the order write:

```python
    record_paid(...)
    if reached < STAGE_RANK["PAYMENT_VERIFIED"]:
        _stage(..., "PAYMENT_VERIFIED")
    snapshot = attempt.get('purchasedSnapshot')
    if not isinstance(snapshot, dict) or not snapshot.get('cart') or not attempt.get('snapshotHash'):
        _park("PURCHASED_SNAPSHOT_MISSING"); return      # paid state retained, no order row
    if reached < STAGE_RANK["INTERNAL_ORDER_CREATED"]:
        ...
```

Test: `test_a_paid_attempt_with_no_snapshot_parks_and_writes_no_order_row`.

---

### MEDIUM-8 — extending the AST gate to `in (...)` finds a second live offender the design does not mention

**Where.** §11.2: "The one live offender it then finds, `invoice-engine/handler.py:766`
`ex_ps in ('captured', 'refunded')` ..."; §18 step 11; §15's "Gate before any commit: ... fully
green".

**The problem.** Measured across the six `CONSULTING_FILES` after extending the walk to `ast.In` /
`ast.NotIn`, there are **two** offenders, not one:

```
payments/invoice-engine/handler.py:766          ex_ps in ('captured', 'refunded')
messaging/inbound-whatsapp-handler/handler.py:3943
        inv_ps not in ('captured', 'paid', 'refunded')
```

The second is a payment decision too — it selects which other invoices for the same phone are still
unpaid — and it misses `authorized` and `disputed` for the same reason the first misses `disputed`.
So the "full suite green" gate cannot hold at step 11 as written, and the design names no fix for it.

**Fix.** Add it to §11.2 and to the owned-paths list, with the same rank rewrite:

```python
if (inv_local10 == local10 and len(local10) == 10 and inv_ref != paid_reference_id
        and pay_status.rank(inv_ps) < pay_status.STATUS_RANK[pay_status.CAPTURED]):
```

and state that the extended gate must be run against all `CONSULTING_FILES` **before** the new entries
are added, so the blast radius is known rather than discovered at step 11.

---

### MEDIUM-9 — the recovery sweep's replay inputs are unspecified, and its only pointer to the event is a TTL'd row

**Where.** §8.2 (PK `recoveryId` = `"<channel>#<dedupKey>"`), §8.4 (`record(..., webhook_log_id="")`),
§8.5 ("re-run the same authoritative path the original delivery would have taken
(`_create_order_for_captured_payment` for commerce ...)"), §8.1 (`RazorpayWebhookLogTable` "has no
state, no queue and a 180-day TTL").

Three gaps:

1. `_create_order_for_captured_payment(payment, reference_id, request_id)` takes a Razorpay payment
   **entity dict**. The design never says how the sweep reconstructs it.
2. The only stored route back to the event body is `webhook_log_id`, into a table with a **180-day
   TTL**, while the recovery row deliberately has none. So "an `ACKNOWLEDGED` event is still
   recoverable ... long after the provider has stopped retrying" is silently bounded at 180 days —
   which contradicts §8.2's stated reason for disabling TTL on the recovery table.
3. `dedupKey` is never defined. `payment_status.dedup_key()` exists; if `recoveryId` is derived from
   the Razorpay *event* id instead, two event types describing one capture (`order.paid` and
   `payment.captured`) produce two rows for one payment, and the "deterministic, so a redelivery
   converges on one row" property is lost for the case that matters.

**Fix.** Make the row self-sufficient and name the key:

```python
#: recoveryId = f"{channel}#{subject_kind}#{provider_payment_id or provider_order_id}"
#: Keyed on the PAYMENT, not on the delivery: two event types describing one capture must converge.
```

and specify that `record()` stores the minimal replay inputs — `providerPaymentId`, `providerOrderId`,
`referenceId`, `channel`, `subjectKind`, `subjectId` — and that the sweep rebuilds
`{'id': providerPaymentId, 'order_id': providerOrderId}` from them and **re-reads the provider**,
never the log row and never the stored amount. `webhook_log_id` stays as a convenience pointer that
the sweep must not depend on. Test:
`test_the_sweep_replays_from_the_recovery_row_alone` with the log table emptied.

---

### MEDIUM-10 — §7.1's own conversion rounds the fractional paise the same paragraph says it rejects

**Where.** §7.1:

```python
amount_paise = money.positive_paise(int(Decimal(str(body["amount"])) * 100))
```

followed by "A fractional-paise amount is rejected with 400, not rounded."

**The problem.** `int()` on a `Decimal` truncates. `Decimal('100.555') * 100 == Decimal('10055.5')`
→ `int(...) == 10055`, silently discarding half a paise, which is exactly the rounding the sentence
forbids and the kind of artefact that later produces a one-paise mismatch against the gateway total.
`money.positive_paise` would have caught it — it refuses a non-integral `Decimal` — but the `int()`
launders the value before it gets there.

**Fix.**

```python
paise = Decimal(str(body["amount"])) * 100
if paise != paise.to_integral_value():
    return cors_response(400, {'error': 'amount must not have fractional paise'}, origin)
amount_paise = money.positive_paise(paise)        # refuses bool/float/negative/zero/overflow
```

Test: `test_a_fractional_paise_topup_is_rejected_not_rounded` with `'100.555'`.

---

### MEDIUM-11 — the float inventory is incomplete, so §11.1's claim overstates the remaining surface

**Where.** §11.1: "**Three live float sites are removed**", listing `handler.py:628`,
`handler.py:1264` and `partner-onboarding` `float(body.get('amount'))`.

**The problem.** `partner-onboarding/handler.py` has **two** `float(body.get('amount') or 0)` sites:
`_do_topup_order` at `:587` (the one the design fixes) and `_do_topup` at `:427`, the admin credit,
which passes the float straight into `billing.topup` → `_dec(amount)`. The design keeps `topup()`
unchanged for the admin path, which is a defensible scope call — but as written §11.1 reads as a
complete inventory of live float money inputs, and it is not.

**Fix.** Either validate the admin input through the same boundary (`Decimal(str(...))` +
integral-paise check, keeping `topup()`'s signature) or amend §11.1 to say: *"a fourth float money
input remains at `partner-onboarding/handler.py:427` (`_do_topup`, admin-only, human-initiated, no
provider event); it is out of scope and recorded so the inventory is honest."* Silence is the only
option that is wrong.

---

### MEDIUM-12 — the credit's audit row is written into a table with a TTL, and its sort key changes

**Where.** §7.3: "A ledger row is written after the credit with sort key `TOPUP#<intentId>` and a
conditional put, so the audit trail is also once-only."

**The problem.** `PartnerLedger` rows carry `'ttl': int(time.time()) + LEDGER_TTL_DAYS * 86400`, with
`LEDGER_TTL_DAYS` defaulting to **400**. So the only record of what a real money credit was for
expires — in a design that elsewhere disables TTL on the recovery table, the attempts table and the
commerce-keys table for precisely this reason ("a recovery row that expires is a paid payment that
stops being recoverable"). Separately, the table's sort key is `ts` (an ISO timestamp) and every
existing reader and the `_ledger` writer assume that; writing `TOPUP#<intentId>` into it changes the
ordering semantics of the wallet ledger with no statement about who reads it.

**Fix.** Keep `ts` as the sort key, add `intentId` as a plain attribute with the conditional put
expressed on a separate uniqueness row if once-only is wanted, and write the durable provenance where
it cannot expire: onto the `TOPUPINTENT#` row (`creditedAt`, `creditedAmountPaise`,
`providerPaymentId`) and onto the recovery row at `resolve()`. State plainly that `PartnerLedger` is a
400-day operational view, not the audit record.

---

### NIT-1 — the PON-5 stale-comment list is short by one site and its line numbers have drifted

`order_keys.py` contains six "12-character"/"12 characters" occurrences. Three are correct (they
describe the legacy form at `:145`, `:213`, and the matcher comment). The design names `:415`, `:530`
and `:160-166`; the actual stale sites are **`:422`** (`reserve_public_order_number` docstring),
**`:546`** (the `ValueError` text), `:164` (the comment), and a fourth the list omits: **`:28`**, the
module docstring's "12 characters, unambiguous alphabet, and deliberately NOT time-ordered". Fix all
four and re-derive the numbers at edit time.

### NIT-2 — the design's baseline is already stale, and the dirty-path map with it

§0 pins HEAD at `43b26d4a`; HEAD is now `25eace20`. `git status --short` now also shows
`scripts/provision_legacy_redirects.py`, `src/components/seo/InstructionsContent.tsx`,
`src/content/products.ts`, `src/lib/seo-page-prompt.ts`, `src/pages/404.tsx` and
`tests/test_legacy_redirect_rollback_snapshot.py` as modified, plus several new untracked
`docs/execution/` and `tests/` files — none of them owned by this task. The index is still clean
(column 1 is a space on every row), so the §0 observation holds in substance. Re-derive the ownership
map and `git status --short` immediately before step 1, and keep `git commit --only <paths>` as §U-9
already requires — with `tests/test_url_host_routing_rules.py` and the `src/**` changes explicitly
left alone.

### NIT-3 — two incompatible `verify` contracts are never reconciled in text

`capture_authority.authorize(verify: Callable[[], Dict[str, Any]])` expects the provider's record as a
dict; `order_creation.reconcile_payment(verify_payment=...)` expects
`(paid, provider_payment_id, amount_paise, currency)`. Both are correct for their callers, and §5.2
does say the commerce path is "the reference implementation, not a second one" — but the design never
states which module performs which obligation on the commerce path, so §5.2's "delegates obligations 3
and 4 to `capture_authority.status_is_captured` / `amounts_match`" is unactionable as written. Add one
sentence: obligation 3 is performed inside `razorpay_verify` (which owns the provider record),
obligation 4 inside `order_creation` (which owns the authoritative amount), and `authorize()` is used
by the three non-commerce channels only.

### NIT-4 — `money` is edited at step 1 but is absent from the owned-paths list and the module map

§18 step 1 is "`money` / `payment_attempt` / `order_keys` contract additions", but
`lambda_utils/ecommerce/money.py` appears in neither §0's owned-paths list nor §2's module map. Add
the full path (note it is `ecommerce/money.py`, not `lambda_utils/money.py`, which does not exist), or
state that `money` is used unchanged — which is my reading of §11.1, since `positive_baise`'s existing
refusals already cover bool, non-integral `Decimal`, non-`int`, `<= 0` and `> 2**53-1`.

### NIT-5 — no gate ties the `live` alias move to the seam having a caller

§11.4 and U-8 say no deploy happens, which is correct for this change. But `BINDING_MISSING` is the
expected state for every real capture until the checkout workstream calls `bind_gateway_order`, and
that state closes the dedup lease — so a deployment ordered before the caller exists converts
"provider keeps retrying" into "provider gave up, a human owns it". Add one line to §18: *"Do not
publish a version or move the `live` alias until `bind_gateway_order` has a caller, or until the owner
accepts paid-and-blocked captures in writing."*

---

## Verified Assumptions

Re-read in the real source at `25eace20` plus the working tree, and found accurate:

| Design claim | Verified |
|---|---|
| `razorpay_verify.verifier_for_event` requires a stored binding and raises when absent | yes — `bound_payment = attempt.get("providerPaymentId")`, `bound_order = attempt.get("providerOrderId")`, `raise RazorpayUnavailable("payment attempt has no verified provider binding")` |
| `target = bound_payment or payment_id` lets an event id select the payment | yes, verbatim — and it is the right thing to remove (see MEDIUM-3 for how) |
| The Razorpay credential is read lazily from `wecare/razorpay/api` and `_get` logs status only | yes — `_credentials()` is called inside `_get`, caches per sandbox, raises naming the secret id and nothing about its contents; `HTTPError` becomes `f"Razorpay returned HTTP {exc.code}"` |
| `payment_status` exposes `canonical`, `rank`, `STATUS_RANK`, `CAPTURED`, `AUTHORIZED`, `REFUNDED`, `DISPUTED`, `condition_expression` | yes |
| `FORBIDDEN_RAW == {"captured"}` and `test_paid_is_deliberately_not_in_the_forbidden_set` pins it | yes |
| `pay_status.canonical(x) == pay_status.CAPTURED` passes the gate "for the right reason" | yes, twice over: `is_canonicalised` matches an `Attribute` call named `canonical`, **and** the comparison contains no string `Constant` at all, so the literal filter never fires |
| `invoice-engine/handler.py:766` compares `ex_ps in ('captured','refunded')` raw and misses `disputed` | yes |
| The adjacent `status in ('paid','cancelled')` is the document lifecycle and is not flagged | yes — it is at `:2007`, `paid` is not in `FORBIDDEN_RAW` |
| `_mark_invoice_paid_by_phone_and_amount`'s call site is dead | yes — `_verify_legacy_invoice_capture` raises `CaptureUnresolved('UNKNOWN_REFERENCE')` at `:580` when `reference_id` is falsy, so the `else:` branch below is unreachable |
| `_verify_legacy_invoice_capture` takes its binding authority from `notes` and compares a raw `'captured'` | yes — `actual_notes.get('referenceId') or ... or ref`, a `WD`-prefixed `description` fallback, and `actual.get('status') != 'captured'` |
| `finalization.record_paid` hardcodes `:rank': 100` and omits `payment_attempt.condition_expression()` | yes |
| `payment_attempt.condition_expression()` contains a bare `OR`, so §9.3's parenthesisation point is necessary | yes |
| `finalization._stage` conditions only on `#s = :paid`, with no rank | yes — which is the forward-only gap |
| `accept_paid` writes `NEEDS_RECONCILIATION` *into* `finalizationStage` in three places | yes — the §9.1 removal is correct |
| `side_effect_guard` fails closed, does not auto-expire, and a pending marker is not permission to repeat | yes, and its docstring says so explicitly |
| `webhook_dedup.claim_event_with_lease` already does CAS on the observed `leaseExpiresAt` | yes — reusing it for `recovery.lease` is the right call |
| `_log_webhook_event` runs before dispatch, so closing a lease loses no raw evidence | yes — called at `handler.py:148`, before the event-type routing |
| `initiation.reserve` uses three `Put`s and no `ConditionCheck` | yes — consistent with the audit's `ConditionCheckItem: implicitDeny` measurement and with §4.3's "no ConditionCheck" rule |
| `initiation.py` has zero callers; `bind_gateway_order` is testable without owning the checkout handler | yes — it takes an injected `attempts` table and holds no AWS client, so `tests/test_gateway_binding_seam.py` is achievable (subject to HIGH-5's fixture work) |
| `order_keys` facts: `WD-ORD-` prefix, `ENTROPY = 8`, 30-symbol alphabet, `is_current_public_order_number`, `PROVIDER_PAYMENT_PREFIX`, `mint_payment_reference(prefix=...)` parameterised | yes, all six |
| `order_keys._read_row` / `resolve_payment_reference` use `ConsistentRead=True` | yes |
| PON-6 is SUPERSEDED | yes — `wix-store/handler.py` raises `OrderIdentityUnavailable` on the read failure, reserves via `order_keys.reserve_order_number` **before** returning, and raises on a store failure. Nothing returns an unstored number |
| `_money_amount`'s latent defect is SUPERSEDED | yes — it validates with `Decimal(text)` and returns `''`; the trailing `str(value)` is gone |
| The inbound handler's `reject` expression is quoted verbatim and `PAYMENT_LOOKUP_REQUIRED` defaults off | yes — `UNVERIFIED_NO_CONFIG` and `UNVERIFIED_LOOKUP_FAILED` do accept the capture today |
| `_do_topup_order` stores nothing server-side and binds only `notes {purpose, wabaId}` | yes — and it sends `int(round(amount * 100))`, a float conversion |
| `partner_billing.topup` is an unconditional `balance = balance + :a` | yes — and it also calls `ensure_wallet` and sets `status = ACTIVE`, both of which MEDIUM/HIGH-6 address |
| The wallet branch reads `amount_paise / 100` as a float at `handler.py:628`, and `_store_payment_record` stores a float-derived `amountInRupees` | yes |

## Unverified / Wrong Assumptions

**Wrong, measured against source:**

1. *"The one live offender it then finds, `invoice-engine/handler.py:766`"* — there are two; the second
   is `inbound-whatsapp-handler/handler.py:3943`. (MEDIUM-8)
2. *"Unit-testable offline ... against `tests/crm_fake_dynamo.FakeDynamo`"* for `recovery`,
   `finalization` monotonicity, the binding seam and `credit_topup_once` — the fake raises on `OR`, on
   comparison operators, on `contains`, has no string-set `ADD` and no `transact_write_items`.
   (HIGH-5)
3. *"a lost or lagging `PAYREF#` row now produces `ATTEMPT_STORE_UNAVAILABLE` or `UNKNOWN_REFERENCE`"*
   — the handler's `_load_attempt` returns `None` for both "no row" and "row present but unusable", so
   the latter still routes to the legacy branch. (MEDIUM-2)
4. *"no financial side effect is lexically reachable without a materialized order"* — the wallet-credit
   and secure-file branches precede the restructured block and `return`. (HIGH-2)
5. *"two new effects in `KNOWN_EFFECTS`"* (§2) vs three (§9.4) vs the nine the design actually guards;
   and `NOTIFICATION` duplicates the existing `CONFIRMATION`. (MEDIUM-6)
6. *"Three live float sites are removed"* — a fourth remains at `partner-onboarding/handler.py:427`.
   (MEDIUM-11)
7. PON-5's three stale comment sites and their line numbers (`:415`, `:530`) — four sites, at `:28`,
   `:164`, `:422`, `:546`. (NIT-1)
8. Baseline HEAD `43b26d4a` — now `25eace20`, with six more modified paths. (NIT-2)

**Not verifiable here, and correctly flagged by the design — restated so a later step does not treat
them as settled:**

- **U-3**, whether a Razorpay payment object carries an account identifier. I could not confirm it
  from source or from a live read (a live read would be the only way, and this review takes none).
  MEDIUM-5 adds that `providerMode` has the same problem and no stated fallback.
- **U-4**, which event carries a payment-link id. Unconfirmed; the §7.2 resolution order and its
  fail-closed third branch are the right shape for an unknown.
- **U-5**, the `PaymentsTable` / `InvoicesTable` / `OrderTable` row counts. Dated 2026-09-23 and not
  re-measured by the audit, by the design, or by this review. §5.3 makes the `--select COUNT` a
  precondition; keep it as a hard gate, because HIGH-3 changes what happens to existing invoice rows.
- The audit's `dynamodb:ConditionCheckItem: implicitDeny` IAM measurement. Not re-run here; the design
  relies on it to justify avoiding `ConditionCheck` in both transactions, which is the safe direction
  whether or not the measurement still holds.
- `wecare-razorpay-webhook:live` at v45 and `OrderTable` at 0 rows. Not re-measured; both are claims
  the implementer should re-derive before landing, per the execution rule against dated counts.
