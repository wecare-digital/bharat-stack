# Design review — Wix coupon + gift card sample (revision 4)

Reviewed: `.agents/tasks/wix-coupon-giftcard-sample-20261002/design.md` at worktree
`32b632e3b319b278d76f630f349c9fa96bf3b3bd`, read cold. Every repository claim the design makes
that a finding below depends on was re-read from that tree; the ones that held are listed in
*Verified assumptions* rather than left implicit, because this is the third pass and the cheapest
thing a reviewer can do is re-litigate what is already right.

**Verdict: CHANGES_REQUESTED — 2 HIGH, 6 MEDIUM, 5 NIT.**

The architecture is sound and I am not asking for it to move. The transport boundary is in the
right place, the `TransactWriteItems`-conditioned-on-the-claim fix is a genuine
optimistic-concurrency design rather than a narrowed race, the concurrency test is genuinely
threaded and latches on a property that survives the fix, the integer-paise discipline is
specified at the serialisation hop and not merely asserted, INR is compared explicitly, and the
owner checklist is by-name-only with a credential path I confirmed exists. The two HIGH findings
are both of the shape this document has already been bitten by twice: **a mechanism that cannot
do the job it is specified to do.** One is an assertion that would fail against correct
post-fix code; the other is a derivation that makes bearer value a pure function of an
identifier the repository mandates logging in full.

---

## Findings

### 1. HIGH — the gift-card code is a deterministic function of `reference_id`, which is logged in full, so the clear code is recoverable from logs

**Where:** §2.5 (`sample_code(*, reference_id)`), §2.4 Group C, §4.2/§4.4/§4.5 (`--reference-id`
is "leg 2's single identity input"), and §2.5's rule that *"Both layers depend on `code` and
`idempotency_key` being deterministic in one input"*.

The design spends real length on keeping the clear code out of reach: it exists in exactly one
expression, is reduced to `last4` in the same function, the module has nothing to log with
(Group D), and the renderer masks it. All of that is defeated by the derivation itself.
`sample_code(reference_id=R)` is `("WDGC" + sha256(R).hexdigest()[:12]).upper()` — unkeyed, with
no secret input. `reference_id` is, by this repository's own standing rule, **not** a secret:

> `reference_id` … **is not a secret and it is not a phone number**, so it may be logged in full.
> That is deliberate: it is the correlation id that lets a log line be traced without any masked
> field, which is why `contactId` and `referenceId` appear together in almost every payment log.

So anyone with read access to a payment log can compute the gift-card code. Worse, the two
derivations share one digest, so the code is a visible prefix of the `idempotencyKey` — and the
`idempotencyKey` travels in a request body the design explicitly permits recording verbatim
(§2.3) and prints in the §4.4 transcript at full length
(`wd-gc-b4a4841861208fa8a47ba149ded8cdb1d01d57660fc8a259d336a7b56c5e311d`, whose first twelve hex
characters are exactly the `B4A484186120` in the code above it).

This is not an offline-only problem that §2.3's fixture-placeholder argument covers. §2.5 states
the module is "the artifact a future (A) decision wires up in one line", and §2.5's own reasoning
requires the production code to be deterministic in one input. A keyed derivation would satisfy
that requirement identically; an unkeyed one does not have to.

**Concrete fix.** Separate the two concerns the one function currently conflates:

* `idempotency_key(*, reference_id)` stays exactly as designed. It is not bearer value, it is
  correctly derivable, and deriving it from a logged id is the point.
* The **code** must not be derivable from a non-secret. Specify it as a keyed derivation under
  the pepper the store already reads by reference, through an injected reader so the module keeps
  its no-`boto3`/no-`os` guarantee:

  ```python
  def card_code(*, reference_id: str, pepper: str) -> str:
      """Deterministic in (reference_id, pepper). The pepper is what stops a logged
      reference_id from yielding bearer value; `reference_id` alone must never be enough.
      """
      digest = hmac.new(pepper.encode("utf-8"), reference_id.encode("utf-8"),
                        "sha256").hexdigest()
      return ("WDGC" + digest[:12]).upper()
  ```

  `hmac` joins `hashlib` as the second stdlib import; Group D's denylist is unaffected.
* Keep `sample_code` if the demo wants a pepper-free value, but **rename it so it cannot be
  mistaken for the production derivation** (e.g. `demo_code`), give it a docstring saying it is
  demo-only *because* it is unkeyed, and add a Group D assertion that no production caller
  references it.
* Add one sentence to §2.5 stating the confidentiality requirement on the derivation input, so
  the next reader does not have to rediscover that `reference_id` is logged.

If the owner prefers to let Wix generate the code (`code=None`), say so explicitly and state the
consequence: `find_by_code` is then unavailable as a resolve step, `idempotencyKey` is the sole
idempotency layer, and §2.4 Group C's "one create call, not two" assertion has to be re-expressed
against Wix's response rather than against a local query.

---

### 2. HIGH — the proposed `transact_write_items` arm of the access-pattern gate cannot pass against the code §5.3 specifies

**Where:** §5.5's row for `test_every_dynamodb_access_is_an_exact_key_operation_or_the_status_index_query`:

> An `elif` for `transact_write_items` asserts the rendered call contains both `TableName` and
> `Key` and no `IndexName`.

Read from the tree, the gate works on `ast.unparse(node)` of the **call node**:

```python
elif operation in exact:
    rendered = ast.unparse(node)
    assert "Key=" in rendered or "Item=" in rendered, (
        f"line {node.lineno}: {operation} without an explicit key")
    assert "IndexName" not in rendered
```

§5.3 builds the transaction items in separate assignments (`card_item = {"Update": {...}}`), so
the call site is `table.meta.client.transact_write_items(TransactItems=[card_item, claim_item])`.
`ast.unparse` of that node renders the **variable names**, not the dict contents — it contains
neither `TableName` nor `Key`. The assertion fails against correct post-fix code.

This is the same failure shape as revision 4's finding 1 (`calls == 1` reading `2`), and it has
the same downstream hazard: the natural repair under time pressure is to loosen or delete the
arm, which leaves the module's only balance-moving write invisible to the one test that
enumerates reach — the exact regression §5.5 added the row to prevent.

**Concrete fix.** Do not assert this from the AST at all; assert it from the recording, where the
item contents actually exist. Keep the AST gate's job as "no scan, one query, every single-item
op names a key" and add a *runtime* assertion in the new concurrency/transaction tests:

```python
def assert_transaction_items_are_exact_key_updates(table):
    for name, kwargs in table.calls:
        if name != "transact_write_items":
            continue
        for item in kwargs["TransactItems"]:
            assert set(item) == {"Update"}, f"unsupported transaction item {set(item)}"
            update = item["Update"]
            assert update.get("TableName"), "a transaction item without a TableName"
            assert update.get("Key"), "a transaction item without an exact Key"
            assert "IndexName" not in update, "a transaction item cannot name an index"
```

If an AST-level guard is still wanted (and it is worth having, because a runtime check only sees
paths a test drives), make it a *presence* assertion that does not depend on unparsing the item:
assert the module contains exactly one `transact_write_items` call, that it is inside
`_commit_redemption` and the void committer, and that the names it passes are resolved from
module-local assignments — then let the runtime check above own the shape. State in §5.5 which
of the two owns which half, so neither is later deleted as redundant.

---

### 3. MEDIUM — `money.value_paise` does not exist, and the function that does exist contradicts the stated rule

**Where:** §2.5's validation table, `initial_value_paise` row:

> `type(...) is int` (so `bool` and `Decimal` are refused by type, matching `money.value_paise`)

Read from the tree: `amplify/functions/shared/lambda_utils/ecommerce/money.py` defines
`positive_paise`, not `value_paise`. `value_paise` lives in `gift_card_store.py:543` — a module
the design is otherwise careful that `wix_gift_cards.py` must not depend on, since it is slated
for retirement. And `money.positive_paise` does **not** refuse an integral `Decimal`; it converts
one:

```python
if isinstance(value, Decimal):
    if not value.is_finite() or value != value.to_integral_value():
        raise ValueError("amount must be positive integer paise")
    value = int(value)
```

So an implementer who follows the citation either cannot find the named function, or finds
`positive_paise` and matches behaviour the design explicitly forbids.

**Concrete fix.** Drop the cross-module citation and name the gate that actually enforces the
rule, which the design already identified correctly two sentences later:

> `type(initial_value_paise) is not int` → `WixGiftCardError`. `bool` is an `int` in Python, so
> the `type(...) is` form is required rather than `isinstance`. The value then goes through
> `Money(...)`, whose `__post_init__` is `type(self.paise) is not int or not 0 <= … or
> self.currency != "INR"` — the second gate, and the one that also pins INR.

Add one line noting that `money.positive_paise` is deliberately **not** the model here, because
it accepts an integral `Decimal`, so nobody "fixes" the adapter to match it.

---

### 4. MEDIUM — the Wix create body is under-specified relative to the transcript and the byte-exact assertions

**Where:** §2.5's `create` signature, §2.4 Group C's body-shape row, §4.4 leg 2.

The §4.4 transcript sends:

```json
{ "giftCard": { "initialValue": {"amount": "2500.50"},
                "currency": "INR", "source": "MANUAL",
                "code": "WDGCB4A484186120" },
  "idempotencyKey": "..." }
```

`source` is in the body. It is **not** a parameter of `create(*, initial_value_paise, code,
idempotency_key, currency, expiration_iso)`, it has no row in the §2.5 validation table, and §3.3
records it only as *"`"MANUAL"` in the documented example"* — not as a field we are specified to
send, nor as writable. Separately, `expiration_iso` **is** a parameter but the design never names
the JSON key it maps to (`expirationDate`? `expiryDate`?), so the one field whose Wix spelling is
load-bearing is the one field not spelled out.

This matters more here than it would elsewhere because the design's own standard for Group A is
byte-exact whole-body comparison, with the reason stated: *"A per-key check passes while an extra
key rides along, and an extra key in a coupon specification is a different promise to a
customer."* A body with an unspecified field cannot be asserted byte-exactly against a specified
expectation.

**Concrete fix.** Pin the full body in §2.5, field by field, and make the signature able to
produce it:

* add `source: str = "MANUAL"` to `create`'s keyword arguments with a validation row
  (`in {"MANUAL"}` until another value is measured), or remove `source` from the transcript and
  from Group C and record in §3.3 that it is not sent;
* name the Wix key for `expiration_iso` explicitly, with the §3.3 row that was read to get it; if
  it was not measured, say so and drop the parameter from this change rather than guessing a key
  name into a money request;
* state the field order / exact dict the body must equal, so Group C can compare whole-body the
  way Group A does rather than key by key.

---

### 5. MEDIUM — the resolve-hit path reads two money/identity fields whose availability is not recorded anywhere

**Where:** §2.5's return contract (`balancePaise` is "the card's **current balance**" on a resolve
hit; `codeLast4` on both paths), §3.3, §4.4 leg 2's
`← 200 balance "2500.50" → 250050 paise`.

Two reads the design depends on and never measures:

1. **Does `QueryGiftCardsResponse` carry `balance.amount`?** §3.3 records the query's *filter*
   operator map (`balance: ["$exists"]`) and concludes "balance is not a filterable magnitude" —
   which is a statement about filtering, not about the response. Nothing in §1.2 or §3.3 records
   that the returned `giftCards[]` objects include `balance`. The resolve-hit branch returns a
   money figure sourced from that response.
2. **How is `codeLast4` derived on a resolve hit?** The query response's `code` is obfuscated, and
   the documented example is `"****-****-****-4444"` — hyphen-grouped. Our `sample_code` produces
   a 16-character unhyphenated code, so what Wix returns for *our* code shape is unmeasured. The
   design never states the extraction rule, and "last four characters of a string that may or may
   not contain hyphens" is exactly the kind of detail that silently yields `-444` or `4444`
   depending on the input.

**Concrete fix.**

* Add two rows to §3.3, measured from `Query Gift Cards`' response schema: whether
  `giftCards[].balance.amount` is present, and whether `giftCards[].currency` is. Record an
  absence the same way §3 records the coupon absences.
* If `balance` is not in the query response, specify the resolve path as `find_by_code` →
  `get(gift_card_id)` (the documented `GET /{giftCardId}`) and say so in §2.5, so the balance
  comes from a call documented to return it. Note the cost: one extra request on the replay path,
  which is the correct price for a money field.
* Specify `codeLast4` as a single rule applied on both paths — e.g. the last four characters of
  the code after stripping every non-alphanumeric character — and add the obfuscation format for
  a custom unhyphenated code to §6.2's step (c) as a thing the owner's one live read confirms.

---

### 6. MEDIUM — "one create call, not two" is enforced by an untyped FIFO queue, so a second create consumes the next queued response instead of emptying the queue

**Where:** §2.3 (`expect(...)` queues a response, `__call__` pops the head) and §2.4 Group C:

> a replay **derived from the same `reference_id`** consumes **one** create call, not two — the
> stub's queue holds a single create, and a second one trips `WixTransport`'s empty-queue
> `UnexpectedWixCall`

The queue is one list of responses with no endpoint or method attached. Resolve-before-create
means the sequence for the replay scenario is **query(miss) → create → query(hit)**, so at least
three responses are queued. A regression that issued a second `POST .../gift-cards` would pop the
queued *query* response, not find an empty queue — and `create`'s parser would read a
`QueryGiftCardsResponse`, most likely finding no `giftCard` and returning an empty id or raising
something the test then misattributes. The named enforcement mechanism does not fire.

This is the one property that distinguishes the gift-card verdict (A) from the coupon verdict
(B), so it is worth enforcing properly.

**Concrete fix.** Make the queue a contract rather than a list. Two changes, either sufficient,
both cheap:

* give `expect` the call it is answering, and refuse a mismatch at pop time:

  ```python
  def expect(self, *, method: str, endpoint: str, status: int = 200,
             body: dict | None = None, raw: bytes | None = None) -> "WixTransport": ...

  # in __call__, before serving:
  if (request.get_method(), request.full_url) != (head.method, WIX_API_BASE + head.endpoint):
      raise UnexpectedWixCall(
          f"expected {head.method} {head.endpoint}, got "
          f"{request.get_method()} {request.full_url}")
  ```
* and assert the counts directly from the recording, which is where the property actually lives:

  ```python
  creates = [r for r in transport.requests
             if r.method == "POST" and r.url == wix_ecom.WIX_API_BASE + "/gift-cards/v1/gift-cards"]
  assert len(creates) == 1, "a replay issued a second create"
  ```

Update §2.3's failure-mode table with the new mismatch row, and update §2.4 Group C's row to name
the recording assertion as the enforcement rather than the empty queue.

---

### 7. MEDIUM — §3's re-fetch rule has no halt condition for the four facts that carry a verdict

**Where:** §0 and §3:

> If a re-fetch at implementation time disagrees with a row below, the artifact wins and the row
> is corrected — the tables are a dated reading.

That rule is right for a dated count and wrong for the four facts §3 itself labels mandatory,
because those four *are* the verdicts. If the implementation-time fetch finds `idempotencyKey`
absent from `CreateGiftCardRequest`, or a `code` operator map present on `Query Coupons`, then
"correct the row" silently inverts §1.2.2 or §1.3.1 while the rest of the document — the
adapter's resolve-before-create guarantee, the §0.1 retirement gate, the memo — carries on
asserting the old verdict. The design is otherwise scrupulous about this kind of coupling (§1.3's
revisit trigger for coupons is exactly the right shape) and the gift-card side has no equivalent.

**Concrete fix.** Split the rule in §3:

> **A disagreement on a non-verdict row** is corrected in place; the artifact wins.
>
> **A disagreement on any of the four verdict-carrying facts halts implementation.** They are:
> `idempotencyKey` absent from `CreateCouponRequest`; `Query Coupons`' `filter` typed `string`
> with no operator map; `idempotencyKey` present on `CreateGiftCardRequest`; the `code` operator
> map present on `Query Gift Cards`. Any of the four moving re-runs §1 and re-states the verdict
> before a line of code is written — a row edit is not a sufficient response to a verdict
> changing.

---

### 8. MEDIUM — §7 names CI as the demo's anti-rot mechanism, but no CI change is in §8 and the existing CI cannot run a script

**Where:** §7's row *"the demo itself | integration-ish, offline | **run it in CI** with `--json`;
exit non-zero on any contract mismatch"*, against §8's Modified table, which lists no workflow
file.

Measured: `.github/workflows/` contains no reference to `demo_`, and the full-suite step is
`python -m pytest -q`, which collects `tests/` and will not execute `scripts/demo_*.py`. §7's own
"Running:" line gives the demo as a **manual** command. So the mechanism §4.2 says "stops it from
rotting silently" does not exist as specified, and the exit-code contract (0/1/2) has no
enforcer.

**Concrete fix.** Pick one and put the file in §8:

* add `tests/test_demo_coupon_giftcard_sample.py`, which imports the demo's `main()` and runs it
  with `--json` and `--no-colour` in-process, asserting exit status `0` and that the parsed JSON
  reports three legs and zero mismatches. In-process rather than `subprocess`, so it inherits the
  harness's `boto3` sabotage and `_key_cache` seeding and still proves zero AWS use; or
* add an explicit step to the workflow that already runs the suite, and list the workflow in §8
  Modified.

Then make §7's row say which one it is, since the claim is about a guarantee and not about an
intention.

---

### 9. NIT — `_marshal`'s refusal puts a message in the `code` slot of `GiftCardValidationError`

**Where:** §5.3.

```python
raise GiftCardValidationError(f"UNMARSHALABLE_VALUE: {type(value).__name__}")
```

`GiftCardError.__init__(self, code: str, message: str = "")` sets `self.code = code`, and `.code`
is the stable, enumerable field handlers surface. Every other site in the module passes a constant
code and a separate prose message — including §5.3.1's own
`GiftCardValidationError("BALANCE_CEILING_EXCEEDED")`. Folding the type name into the code makes
it unenumerable.

**Fix:** `GiftCardValidationError("UNMARSHALABLE_VALUE", f"cannot marshal {type(value).__name__}")`.

---

### 10. NIT — §5.5's property sentence for the balance-floor test is true of the money move, not of the surviving `update_item`

**Where:** §5.5, row `test_the_balance_floor_is_a_condition_expression_not_a_read_then_write`,
property preserved: *"the floor is a condition, and no read precedes it"*.

Post-fix a read **does** precede the only surviving `update_item` on that path: §5.3 adds a
post-commit balance read before the best-effort `balanceAfterPaise` follow-up. The existing test
asserts `"get_item" not in operations[:operations.index("update_item")]`, which would then be
false. §5.3's prose has this right — *"The existing contract that no read **precedes** the money
move is preserved and strengthened: the decision was the condition"* — so only the §5.5 row needs
the same words.

**Fix:** restate the row's property as "the floor is a condition on the transaction, and no read
precedes the money move", and say the rewritten assertion indexes on the
`transact_write_items` call rather than on `update_item`.

---

### 11. NIT — the cross-session ownership check covers `gift_card_store.py` but not the shared test fake

**Where:** §9 question 6.

The question asks who owns `gift_card_store.py` before the §5 edit lands, which is right.
`tests/coupon_fake_dynamo.py` is the other shared file this change edits — it gains an `RLock`
around every operation, a new `applied` log, a new `transact_write_items`, a constructor keyword
and two attributes — and it is imported by **seven** test files (confirmed), three of which belong
to the coupon side and four to gift cards. §5.5 already lists them for re-run; the ownership
question does not mention them.

**Fix:** extend question 6 to name `tests/coupon_fake_dynamo.py` and its seven importers, and
state the commit discipline the workspace requires for a shared file: stage by explicit path and
`git commit --only <paths>`, so a dirty index from another session cannot absorb them.

---

### 12. NIT — the synthetic event for `handler._create` is unspecified, and the `_staff` stub silently changes `created_by`

**Where:** §2.4 Group B, §4.3.

Both drive `handler._create(event, origin=...)`, which reads the payload through `_body(event)`
and takes the creator from `(event.get("_auth") or {}).get("username")`. In production
`middleware.require_auth` populates `_auth`; with `_staff` stubbed to `lambda event: None`,
nothing does, so `created_by` is `None` on every harness and demo run. That is harmless but it is
a difference between the driven path and the real one, and the design's whole argument for driving
the handler is that there is no such difference.

**Fix:** specify the event (`{"body": json.dumps(payload), "_auth": {"username": "demo-operator"},
"headers": {...}}`) in §2.4 Group B, and note that the stub supplies `_auth` itself precisely so
`created_by` matches production.

---

### 13. NIT — the error tables are exhaustive for the transaction and silent on the writes that follow it

**Where:** §5.3's and §5.3.1's per-condition tables.

Both cover every way the transaction can fail and stop there. After the transaction, `redeem`
still writes the `GCTXN#` record and the `GCTXN-ID#` pointer with plain `_put`s. Post-fix,
`settled` is latched atomically with the money, so a failure of either put is never re-driven — a
retry short-circuits on `settled` and the ledger row that a `void()` resolves by is permanently
absent. I checked the pre-fix path and the same hole exists there once `_mark_settled` succeeds,
so this is **not** introduced by the change and is not a reason to block. It is worth one row
rather than silence, because a reader comparing the two tables will reasonably assume they are
complete.

**Fix:** add a row to §5.3's table — *`GCTXN#` record or pointer put fails | unchanged from
today; the claim is settled so a retry does not re-drive it | out of scope for this fix, recorded
so it is not read as introduced* — and, if the retirement gate does not clear, file it as a named
follow-up.

---

## Verified assumptions

Every one of these was read from the worktree at `32b632e3` and held exactly as the design states.
Listed because this is revision 4 and the document's line citations have been a finding twice.

| Claim | Verified |
|---|---|
| `wix_ecom._request` is the single HTTP boundary; `_api_key()` at `:96` inside the `headers` literal, `try:` at `:103`, `urlopen` at `:104`, `.read()` at `:105`, bare `except Exception` at `:109` | ✅ exact |
| `json.dumps(body or {})` with no custom encoder; `json.loads(payload)` with no `parse_float` | ✅ |
| `_api_key()` short-circuits on `if "key" in _key_cache` before its `import boto3`; `_secrets` stays `None` when the cache hits | ✅ |
| `_request` imports `urllib.request` inside the function body, so a module-level `monkeypatch.setattr("urllib.request.urlopen", …)` is in effect | ✅ |
| `coupons/handler._create` at `:204-235`, `except Exception` at `:229`, 202 at `:233`, 201 at `:235`; it is the only place claim-row → Wix create → `mark_mirrored` is composed | ✅ |
| `_wix()` returns `WixCoupons(wix_ecom._request)`, so stubbing `urlopen` reaches it | ✅ |
| `handler._staff` is `middleware.require_auth(event, STAFF_ROLE)` at `:138-140`; `STAFF_ROLE = "Operator"` | ✅ |
| `middleware.py:24` constructs a `cognito-idp` client at module scope (import at `:16`); `rate_limit.py:48` a `dynamodb` resource (import at `:42`) — so `"boto3" not in sys.modules` is false once the handler is imported | ✅ exact |
| `coupon_store` does not import `wix_coupons`, so `coupon_store.create → WixCoupons.create` is not a chain that exists | ✅ |
| `WixCoupons.get` at `:244` raises nothing; both `WixCouponConflict` raises and the normalised-code comparison are in `assert_mirrors` at `:254-280`; `_coupon_view` selects `{id, active, type, code}` | ✅ |
| `wix_coupons.BASE == "/stores/v2/coupons"`; `specification()` never sends `type`; `_rupees` refuses a non-whole-rupee paise value at `:107-117` | ✅ |
| `tests/fixtures/wix_coupon_get_response.json` contains only JSON integers (`moneyOffAmount: 10`, `minimumSubtotal: 5000`, `numberOfUsages: 3`) — so a float-hazard row against it would prove nothing | ✅ |
| `Money.from_wix` requires `isinstance(amount, str)` matching `[0-9]{1,14}(\.[0-9]{1,2})?` at `money.py:21-25`, so `from_wix(10.0)` raises `ValueError`; `to_wix()` emits exactly two places; `250050 → "2500.50" → 250050` and `"999.75" → 99975` | ✅ |
| `Money.__post_init__` enforces `type(self.paise) is int`, non-negative, and `currency == "INR"` | ✅ |
| `gift_card_store.py` is 1,513 lines; `APPLIED_CLAIM_PREFIX` `:194`, `_decrement` `:1277`, `_drop_applied_marker` `:1337`, `_mark_settled` `:1363`, `_mark_credited` `:1376`, `void` `:1395`, `credit(once_key=…)` `:951` with the marker built at `:973`, `void`'s only `once_key` call at `:1471` | ✅ |
| The §5.1 window is real: `_decrement` sets `appliedClaim#<attempt>` under `attribute_not_exists` **in the same expression as the balance move**, and `_drop_applied_marker` ends its lifetime; `balancePaise >= :amount` stops an overdraw, not a second deduction. The replay short-circuit reads `settled` off a different item | ✅ the module's own comments say so |
| `_mark_settled` has no condition beyond `attribute_exists`, and the trailing `_put(record)` is unconditional, so thread B overwrites `GCTXN#.balanceAfterPaise` with the lower figure | ✅ |
| `balanceAfterPaise` appears at exactly three sites (`:1259`, `:1367`, `:1478`), all writes | ✅ exact |
| `_is_conditional_failure` at `:377-384` reads `response["Error"]["Code"]` and is consulted by six non-transactional callers | ✅ |
| `import secrets as _secrets` at `:89` and `import time` at `:90`, so `_secrets.randbelow` and an injected `time.sleep` default need no new import | ✅ |
| `test_the_store_holds_no_boto3_client_and_reads_no_secret_itself` at `:1152` walks every `ast.Import`/`ast.ImportFrom` and forbids `boto3`, `botocore`, `os` — so `TypeSerializer` genuinely cannot be imported, and the hand-written `_marshal` is the right call. It also forbids `client`/`resource` as **call** attributes, which `table.meta.client.transact_write_items(...)` does not trip | ✅ and the design's reading is correct |
| `test_no_float_is_constructed_anywhere_on_the_store_money_path` at `:1066`; `test_every_dynamodb_access_…` at `:1094` | ✅ |
| `APPLIED_*` referenced at five sites owned by four tests: `:453-454`, `:513`, `:519`, `:762`, `:793` | ✅ exact |
| `test_a_plain_credit_is_not_made_idempotent_…` has two halves; the second is five lines calling `credit(..., once_key="void-abc")` twice — a `TypeError` once the parameter goes, not a stale assertion | ✅ the design's correction is right |
| `_CreditThrottles` fires only on `"ADD balancePaise :amount"`, which the void conversion removes, so both its tests would stop firing silently | ✅ |
| `void` already treats `credited` absent as complete, via `if original.get("credited") is not False` at `:1441` — so §5.3.1's three-valued table matches existing behaviour | ✅ |
| `FakeTable.calls.append` precedes the arm-check and the condition evaluation (`update_item`: append `:275`, condition `:285`, raise `:286`), so `calls` is an attempt log and the `applied` outcome log is genuinely required | ✅ exact |
| `FakeClientError.__init__(self, code)` builds only `{"Error": {...}}`, so it cannot carry `CancellationReasons` as written | ✅ |
| `FakeTable` has no `.name` and no `.meta`, and `__init__` is `(key_attr, indexes)` | ✅ |
| `tests/coupon_fake_dynamo.py` is imported by exactly seven test files | ✅ exact |
| `test_gift_cards_iam_and_table.py`'s `== ["dynamodb:UpdateItem"]` assertion covers the SPI's **PaymentAttemptsTable** statement, not the gift-card ledger — the ledger action sets are pinned by no test | ✅ the design's correction of its own earlier claim is right |
| `wix-giftcard-spi/handler.py` emits `{"remainingBalance": int(outcome["remainingBalancePaise"])}` at `:323` (redeem) and `:361` (void), so the figure is customer-visible and §5.3's invariant is the right response | ✅ |
| `ecommerce/initiation.py:10,79,82` and `notifications/store.py:239` are the two existing `transact_write_items` call sites and both marshal explicitly | ✅ |
| `test_payment_vocabulary_at_decision_points.py` resolves paths under `amplify/functions`, so `scripts/` is outside its scan; `FORBIDDEN_RAW == {"captured"}`; `coupons/handler.py` and both gift-card handlers are in `RAW_SCAN_ONLY_FILES` and none of them is edited by this design | ✅ |
| `conftest.py` raises `pytest.UsageError` below Python 3.12 (`REQUIRED = (3, 12)`) | ✅ |
| CI runs `python -m pytest -q` over the whole tree | ✅ (and see finding 8) |
| `scripts/provision_coupons_role.py` grants `secretsmanager:GetSecretValue` under Sid `ReadWixApiKey` at `:118` | ✅ |
| `asm-exec` is not on `PATH`, and `~/.local/share/razorpay-mcp-server/asm-exec-env.py` exists at mode `0700` with the documented `asm-exec <command> [args...]` contract and `--` support | ✅ exact |
| The §6.2 and §6.5 blocks carry `{{resolve:secretsmanager:wecare/wix/headless-api-key:SecretString:apiKey}}` — a by-reference form the inline-secret guard allows — and `wix_ecom._api_key` does try `apiKey`, then `value`, then `key` | ✅ |
| Prohibitions respected: no live Wix write authored, no deploy, no provisioning, no `get-secret-value`, no credential value, no payment capture/refund/configuration change, no live-send flag, nothing deleted, no guard weakened, and no file in the out-of-bounds list edited (`coupons/handler.py` is driven, not modified) | ✅ |
| Concurrency boundary: `.worktrees/direct-razorpay-20261002`, `ecommerce/checkout/handler.py`, `payment_readiness.py`, `payments/razorpay-webhook/handler.py` and `amplify/functions/messaging/` appear in neither the New nor the Modified table | ✅ |

On the review brief's specific questions, for the record: the harness **does** drive real code
paths (two production functions stubbed, `_staff` and `_coupons_table`, with a Group D source
assertion covering the first); Wix **is** stubbed at the transport layer only (`urlopen`, with
all five of `_request`'s behaviours executing); the integer-paise and explicit-INR rules **are**
correctly specified, including the serialisation hop that revision 3 missed; resolve-before-
generate is **sound in design** and under-enforced in the harness (finding 6); the `redeem()` fix
**is** a genuine conditional-write design with a genuinely concurrent test, and the test now
discriminates pre-fix from post-fix because it asserts attempts and outcomes separately;
payment-state decisions **are** absent rather than routed, which is the right answer here, and
the gate's scope limitation is stated rather than assumed; the Wix contract check **does** name
concrete versions and endpoints; and the owner checklist **is** actionable and by-name-only. The
bearer-value rule is the one that fails, and it fails in the derivation rather than in the
logging (finding 1).

## Unverified / wrong assumptions

| # | Assumption in the design | Status |
|---|---|---|
| 1 | *"matching `money.value_paise`"* | **WRONG.** No such function. `money.positive_paise` exists and accepts an integral `Decimal`, which contradicts the rule being cited for. Finding 3 |
| 2 | The `transact_write_items` arm of the access-pattern gate can assert `TableName` and `Key` from `ast.unparse` of the call | **WRONG.** The items are separate variables; the unparsed call contains neither. Finding 2 |
| 3 | A `reference_id`-derived gift-card code is safe because the clear code is masked at the renderer and never returned | **WRONG as a guarantee.** The code is an unkeyed function of an identifier the repository mandates logging in full, and is a visible prefix of the `idempotencyKey`. Finding 1 |
| 4 | `QueryGiftCardsResponse` carries `balance.amount` (relied on by the resolve-hit `balancePaise`) | **UNVERIFIED.** §3.3 records the filter operator map only. Finding 5 |
| 5 | `codeLast4` is extractable from the obfuscated query response for our 16-character unhyphenated custom code | **UNVERIFIED.** The only documented obfuscation example is hyphen-grouped; no extraction rule is specified. Finding 5 |
| 6 | `source: "MANUAL"` is a field we send, and `expiration_iso` maps to a known Wix key | **UNVERIFIED.** `source` is in the transcript but not in the signature or the validation table; the expiry key is never named. Finding 4 |
| 7 | An extra `create` call would empty the stub queue and raise `UnexpectedWixCall` | **WRONG.** The queue is an untyped FIFO holding query responses too; a second create pops one of those. Finding 6 |
| 8 | The demo is kept honest by running in CI | **WRONG today.** No workflow references it and pytest does not execute scripts. Finding 8 |
| 9 | Correcting a §3 row is a sufficient response to a re-fetch disagreement | **WRONG for four rows.** Those four *are* the verdicts. Finding 7 |
| 10 | `FakeTable` models real `TransactWriteItems` semantics for the two-`Update` shape | **UNVERIFIED, and correctly declared as such** by §7 and §9 assumption 3. Not a finding — the design names it as the largest piece of trust in §5 rather than hiding it, and the `RLock` plus the strict-refusal posture are the right mitigations available offline |
| 11 | Wix's `idempotencyKey` is actually idempotent on this site, and a fractional-INR amount with a custom code is accepted | **UNVERIFIED, and correctly gated** on §0.1 condition 3 / §6.2 step (b), owner-run. Not a finding |
| 12 | The §3 Wix schema readings and the §0.1 AWS probes are current | **DATED SNAPSHOTS, correctly declared** with instructions to re-derive. Not a finding |

---

## Verdict

2 HIGH + 6 MEDIUM → **CHANGES_REQUESTED**.

Findings 1 and 2 are blocking in the strict sense: as written, one would ship a mechanism that
cannot protect what it claims to protect, and the other would ship an assertion that goes red on
correct code — and the repair most likely to be reached for under pressure (loosening the
assertion) is the one that removes the guarantee. Findings 3 to 8 are each a short edit against a
fact this review measured. Nothing in §1's evidence, §2.1's boundary, §5.3's fix shape or §6's
owner checklist needs to move.
