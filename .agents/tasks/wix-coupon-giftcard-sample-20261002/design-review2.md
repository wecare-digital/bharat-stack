# Design review — Wix coupon + gift card sample (revision 8)

Reviewed: `.agents/tasks/wix-coupon-giftcard-sample-20261002/design.md` at worktree
`32b632e3b319b278d76f630f349c9fa96bf3b3bd` (confirmed from `git log -1`), read cold. Every
repository fact a finding below rests on was re-read from that tree rather than taken from the
design's dispositions in §14-§17; the ones that held are listed under *Verified assumptions*.

**Verdict: CHANGES_REQUESTED — 0 HIGH, 3 MEDIUM, 4 NIT.**

All thirteen findings of the prior review (`design-review.json`: 2 HIGH / 6 MEDIUM / 5 NIT) are
**confirmed resolved against the tree**, including both HIGHs, which the brief asked about
specifically. The architecture, the two verdicts, the transport boundary, the `TransactWriteItems`
fix shape, the §0.1 retirement gate, the owner checklist and the locked decisions are sound and
none of them is asked to move. The locked decisions were not relitigated.

The three MEDIUMs are narrower than the three consecutive HIGHs this document has worked through,
but they are the **same family** it has now named five times: a mechanism whose number, scope or
existence was written against the intent of a test rather than against what the test will execute.
Revision 8 removed three instances of that family and in doing so left three more at the edges of
the same repair — one fault-injection mechanism that cannot fire the number of times the new count
requires, one new shared helper that now carries the property the deleted literal used to carry and
has no definition or home, and one stale count inside the very section that was made the single
source for it. Each is a short, local edit. None moves a decision.

---

## Confirmation of the prior review's findings

Checked against the tree, not against §14's dispositions. The brief's specific CONFIRM list is
answered in rows 1-8.

| # | Prior sev | Confirmed resolved? | How I checked |
|---|---|---|---|
| 1 | HIGH | ✅ **yes, on all four parts the brief named** | **Keyed under the existing pepper:** `card_code(*, reference_id, pepper)` is `hmac.new(pepper.encode("utf-8"), CODE_DOMAIN_TAG + reference_id.encode("utf-8"), sha256)`. The pepper is the incumbent one — I read `SECRET_ID = "wecare/wix/giftcard-spi"` (`gift_card_store.py:104`), `PEPPER_FIELD = "code_pepper"` (`:106`), `SecretReader` (`:367`), `read_pepper` (`:389`) and `code_hash`'s identical construction (`:442`) — so **no new secret name is introduced**, and §9 assumption 11 records the one consequence (if the SPI secret is deleted with the backend, `card_code` loses its pepper) as a §6.4 line item. **Injected-reader pattern:** `pepper` is a required keyword-only argument with no default; the module reads nothing, and Group D pins `get_secret_value`/`batch_get_secret_value`/`client`/`resource` absent plus a `boto3`/`botocore`/`urllib`/`os` import denylist, with the caller obtaining the pepper the way `ecommerce/gift-cards/handler.py:143` already does (`store.read_pepper(_read_secret, secret_id=SPI_SECRET_ID)` — verified). **`sample_code` → `demo_code`, guarded:** `sample_code` survives only in the historical dispositions; the live spec uses `demo_code`, fenced by an AST walk over every `.py` under `amplify/` across `Attribute`/`Name`/`ImportFrom`, with the reason the defining module passes (a `FunctionDef`'s own name is not a `Name` node) written down and "do not special-case the file" stated. **No clear bearer value in a log:** the module contains no `logger`/`logging`/`print(`, `codeLast4` comes from Wix's `codeSuffix` rather than a slice of the clear code (`CODE_SUFFIX_MISSING`, no fallback), the clear code is not among the seven returned keys, and §2.3/§4.3 hand the caller-side obligations over explicitly with the offline-placeholder argument stated rather than assumed |
| 2 | HIGH | ✅ **yes, and the split will not false-fail** | The AST arm keeps **presence and location only** — one `transact_write_items` call, owned by `_transact_with_retry`, itself called from exactly `_commit_redemption` and `_commit_void` — and §5.5 now spells out that facts two and three need an `ast.Name` predicate because the gate's existing filter is `isinstance(node.func, ast.Attribute)` (`tests/test_gift_card_store.py:1106`, read directly). `transact_write_items` is **not** in the gate's `exact` set, so the `ast.unparse` assertions at `:1105-1110` cannot reach it — the revision-4 false-fail is structurally impossible now. The runtime half, `assert_transaction_items_are_exact_key_updates(store)`, reads `table.calls` (not `applied`, so a cancelled attempt is still shape-checked), **opens by refusing an empty recording**, returns its count, and is sited on tests that really drive a transaction. I re-confirmed the diagnosis that forced the re-siting: the gate's entire runtime tail is `store = table()` + `pytest.raises(AssertionError): store.scan()` on a fresh `FakeTable` (`:1125-1127`). See MEDIUM 2 and MEDIUM 3: the split is right; the instrument that replaced the per-test literal is unspecified, and the caller count is still stated two ways inside §5.5 |
| 3 | MEDIUM | ✅ yes | `money.py` defines `positive_paise` and nothing named `value_paise`; `value_paise` is `gift_card_store.py:543`. `positive_paise` does convert an integral `Decimal` (`money.py:34-37`), exactly as the finding said. The design states the `type(...) is int` rule standalone, names `Money.__post_init__` by what it enforces (verified: `type(self.paise) is not int or not 0 <= … or self.currency != "INR"`, `money.py:16-18`), and records that `positive_paise` is deliberately **not** the model |
| 4 | MEDIUM | ✅ yes | The gift-card create body is pinned as one dict with the conditional-merge form, `source` is a validated parameter narrowed to `{"MANUAL"}` with `ORDER` argued out, `expiration_iso` maps to the named key `expirationDate`, the optional keys are omitted rather than sent as `null`, and Group C compares the **whole body**. The coupon body keeps the same byte-exact standard in Group A. The Wix-side schema facts behind both are unverifiable from here — *Unverified* 1 |
| 5 | MEDIUM | ✅ yes | §2.5 carries a per-key source table giving the create-path and resolve-path read for all seven keys; `balancePaise` on a resolve hit comes from `giftCards[0].balance.amount` with the measurement cited, `codeLast4` from `codeSuffix` with `CODE_SUFFIX_MISSING` and **no** fallback to slicing the obfuscated `code`, and `giftCards[0]` is stated as reachable only after the length check (`{}` on a miss, `AMBIGUOUS_CODE` above one). The resolve path is one request, not two. Wix-side facts unverifiable from here |
| 6 | MEDIUM | ✅ yes | `expect(*, method, endpoint, status=200, body=None, raw=None)` is typed by the call it answers; `__call__` compares `(get_method(), full_url)` **before** popping and raises `UnexpectedWixCall` naming expected vs actual; §2.3's failure table has the mismatch row; and Group C names the **recording count** (`len([r for r in transport.requests if …]) == 1`) as the enforcement, with the typed queue demoted to "what makes the failure legible" |
| 7 | MEDIUM | ✅ yes | §3.0 splits the rule, names V1-V4, and says a disagreement **HALTS** and re-runs §1, with the sentence *a row edit is not a sufficient response to a verdict changing*. §3.0.1 and §3.4 record the rule firing on its own author, including the sharpest version of the argument: the pre-revision-5 URLs now 404 and return a schema-free shell, so the old command set would have failed **toward** a wrong verdict |
| 8 | MEDIUM | ✅ yes, and the CI claim is now backed by measurement | Measured: `.github/workflows/` references neither `demo_` nor `scripts/demo`, and `route-auth.yml:111` is a bare `python -m pytest -q` full-suite step — so `tests/test_demo_coupon_giftcard_sample.py` is collected with **no workflow edit**, which is the repair §7 says it took, with the comparison table and the `main(argv)`-returns-its-code consequence both stated |
| 9 | NIT | ✅ yes | `GiftCardValidationError("UNMARSHALABLE_VALUE", f"cannot marshal …")`, two-argument, with the `.code`-is-the-enumerable-field reason and the `GiftCardValidationError`-not-`GiftCardStoreUnavailable` argument recorded |
| 10 | NIT | ✅ yes | The row's property is restated as "a condition on the transaction, and no read precedes the money move", and the re-index onto `transact_write_items` is stated. See NIT 3 for the line numbers in that row |
| 11 | NIT | ✅ yes | §9 question 6 names `tests/coupon_fake_dynamo.py` and lists its importers; I measured **seven** and they are exactly the seven named (four gift-card, three coupon). `git commit --only <paths>` and the `git add`-first caveat for a new file are both stated |
| 12 | NIT | ✅ yes | §2.4 Group B specifies the event including `_auth`, with the measured reason (`_create` reads `(event.get("_auth") or {}).get("username")`) and the note that the stub supplies `_auth` so `created_by` matches production; §4.4's transcript shows `created_by demo-operator` |
| 13 | NIT | ✅ yes | §5.3's table carries the `GCTXN#` / `GCTXN-ID#` row with the paragraph stating the hole pre-exists, the verification that it already exists pre-fix once `_mark_settled` succeeds, and the follow-up's shape |

The three MEDIUMs of the intervening re-review are also resolved: the per-test literal is gone and
replaced by a committer **set** (§5.5), Group C's non-recoverability assertions are rewritten onto
case-normalised digest bodies with the demo derivation's weakness asserted **positively**, and
§5.6 scopes the no-float rule to **amounts** with the retry delay permitted as a duration and the
integer-millisecond alternative recorded as rejected. I reproduced the digest computation the
design states: for `R = "wd-gc-sample-2026-10-02"`, `demo_code(R)` is `WDGCB4A4841861208FA8`
(20 chars), `idempotency_key(R)` is `wd-gc-b4a4841861208fa8…311d` (70 chars), `demo_code in key`
and `demo_code.lower() in key` are both `False`, and `_digest_body(demo_code) in
_digest_body(key)` is `True` — so the rewritten assertion is capable of failing and the old one
was not.

---

## Findings

### 1. MEDIUM — "the same, armed twice" is not expressible with `FakeTable.arm_failure`, and caller 5's count of 4 depends on a re-arm the design never specifies

**Where:** §5.5's `_CreditThrottles` rewrite table —

> `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once` | the same, armed
> **twice** | recovery that works once is not recovery

— and the caller-count table's row *caller 5 → **4** (redeem; two armed-and-raising voids; one
succeeding void)*.

Read from the tree, arming is one-shot **per arm**, and the design's own citation points at the
wrong method, which is what hides the problem:

```python
def arm_failure(self, operation: str, exc: Exception) -> None:
    """Make the next `operation` raise, once."""
    self.fail_on[operation] = exc          # tests/coupon_fake_dynamo.py:235-237

def _fail_if_armed(self, operation: str) -> None:
    armed = self.fail_on.pop(operation, None)   # :246  — the consumption lives HERE
```

§5.5 attributes `fail_on.pop` to `arm_failure` *"at `tests/coupon_fake_dynamo.py:246`"*. `:246` is
inside `_fail_if_armed`; `arm_failure` is a plain dict assignment at `:235-237`. The semantic
conclusion ("arms once") is right, but the mis-attribution is why the next question went unasked:
**two arms of the same operation are not two failures unless the second arm happens after the
first has been consumed.** `self.fail_on[operation] = exc` twice in a row is one failure.

The test being rewritten does not arm at all today — it constructs `_CreditThrottles(…,
credit_failures=2)` once and loops twice (`tests/test_gift_card_store.py:712-728`), and the
subclass decrements its own counter. So the literal reading of "the same, armed twice" is *call
`arm_failure` twice up front, as the fake is constructed once today*, which yields **one** failure:
the first `pytest.raises(gc.GiftCardStoreUnavailable)` passes, the second iteration's `void()`
succeeds, the second `pytest.raises` fails, and the recorded transaction count is **3**, not the
**4** §5.5 asserts. §2.6's `arm_failure` paragraph does not close this either — it only adds that
a cancellation carrying `TransactionConflict` may be armed.

This is the family the revision 8 preamble says it is closing, one layer down: a count written
against the intent of a test rather than against what the test will execute. It also fails in the
direction that loses a property — the cheapest repair under time pressure is to drop the second
iteration, and the second iteration *is* the test ("recovery that works once is not recovery").

**Concrete fix.** Pick one and write it down, then derive the count from it:

* **re-arm per attempt**, which keeps `coupon_fake_dynamo.py`'s surface unchanged:

  ```python
  for _ in range(2):
      store.arm_failure("transact_write_items",
                        FakeClientError("ProvisionedThroughputExceededException"))
      with pytest.raises(gc.GiftCardStoreUnavailable):
          gc.void(store, transaction_id=redeemed["transactionId"],
                  clock=clock(), sleep=lambda _s: None)
  ```

  and say in §5.5 that the arm is consumed by `_fail_if_armed`'s `pop`, so it is re-armed before
  each attempt; **or**
* add `arm_failure(self, operation, exc, *, times: int = 1)` to §2.6's addition 2, storing a count
  and decrementing it in `_fail_if_armed`, and state that the default keeps every existing call
  site unchanged (there are existing callers, so the keyword must be defaulted).

Either way, correct the citation to `arm_failure` at `:235-237` consumed by `_fail_if_armed` at
`:246`, since the whole count argument rests on that mechanism.

---

### 2. MEDIUM — `_committer_of` is now the instrument that carries the "neither committer is silently missing" property, and it has no definition, no home and no stated import

**Where:** §5.5's replacement for the per-test literal, §7's access-pattern row (*"Each caller
asserts `seen >= 1` or `seen >= 2` **plus the set of committers exercised**"*), and §5.4's
assertion block.

```python
seen = assert_transaction_items_are_exact_key_updates(store)
assert seen >= 2, "both committers must have been exercised"
assert {_committer_of(kwargs) for name, kwargs in store.calls
        if name == "transact_write_items"} == {"redeem", "void"}
```

Measured: **neither `_committer_of` nor `_is_balance_move` exists anywhere in the tree** (0 matches
across every `.py`). Both are introduced by this design. `_is_balance_move` at least has its
matching rule written out in §5.4 and §5.5 (an `update_item` carrying `ADD balancePaise`, or a
`transact_write_items` whose items carry one). `_committer_of` has one clause — *"discriminates on
the fragment `_is_balance_move` already reads — `ADD balancePaise :neg` is the redeem committer,
`ADD balancePaise :amount` is the void committer"* — and nothing else: no signature, no location,
no behaviour for a transaction that matches neither, and no mention in §8's New row for
`tests/test_gift_card_redeem_concurrency.py`, which lists only
`assert_transaction_items_are_exact_key_updates` as imported from `tests/test_gift_card_store.py`
while §5.4's and caller 6's assertions use both of the others.

That matters because of what just happened to this row: the literal count was deleted **because**
it was the wrong instrument, and this helper is what replaced it. §7 names the committer set as the
proof, and the document's own standard is that the helper carrying a property gets specified where
it lives — which is exactly the treatment `assert_transaction_items_are_exact_key_updates` received
one paragraph earlier, down to naming its neighbours (`table`, `issue`, `clock`, `digest_of`,
`_markers_on` — all four verified present at `:59`, `:63`, `:68`, `:76`, `:423`). Left as it is, an
implementer invents a two-line helper, and the plausible invention returns `None` for a transaction
that matches neither fragment, which turns `== {"redeem", "void"}` into a confusing failure rather
than a named one.

**Concrete fix.** Specify both beside the other helper, and name them in §8:

```python
def _is_balance_move(call) -> bool:
    name, kwargs = call
    if name == "update_item":
        return "ADD balancePaise" in (kwargs.get("UpdateExpression") or "")
    if name == "transact_write_items":
        return any("ADD balancePaise" in (i["Update"].get("UpdateExpression") or "")
                   for i in kwargs["TransactItems"])
    return False

def _committer_of(kwargs) -> str:
    """Which committer opened this transaction, from the card item's own expression."""
    expressions = [i["Update"].get("UpdateExpression") or "" for i in kwargs["TransactItems"]]
    if any("ADD balancePaise :neg" in e for e in expressions):
        return "redeem"
    if any("ADD balancePaise :amount" in e for e in expressions):
        return "void"
    raise AssertionError(f"a transaction that moves no balance: {expressions}")
```

and add to §8's New row for the concurrency test that it imports `_is_balance_move` and
`_committer_of` alongside the shape helper. The raise rather than a sentinel is the point: an
unrecognised transaction should fail as itself, not as a set mismatch.

---

### 3. MEDIUM — §5.5 still states the runtime helper's caller count two ways, in the section that was made the single source for it

**Where:** §5.5, ~40 lines after the numbered six-row caller table:

> **Where the helper itself lives:** `tests/test_gift_card_store.py` … and imported by
> `tests/test_gift_card_redeem_concurrency.py`. **One definition, four callers.**

The table immediately above it enumerates **six** callers and is explicitly nominated as the single
source — §7 defers to it (*"the **six** transaction-driving tests §5.5 enumerates in one place …
this row does not restate the count independently of it"*), §8 says six, and §15's row 1 carries a
superseded annotation saying the list is six and not four. §17 finding 1 states the repair as *"The
caller enumeration is stated **once**, as a numbered six-row table in §5.5"*. The one place it is
still four is inside §5.5 itself, in the sentence a reader goes to when asking *where does this
helper live and who calls it* — which is precisely the sentence an implementer reads when wiring it
up.

The consequence is not cosmetic. Taking "four callers" literally leaves two transaction-driving
tests without the shape check while §7 reports item shape as runtime-covered by six — a weaker
version of the vacuity that revision 6 fixed, and the reason the previous review asked for the list
to be stated once with its count.

**Concrete fix.** Replace the clause with a cross-reference rather than a second number: *"One
definition; its callers are the six enumerated in the table above."* While there: §16's "what is
kept" paragraph still reads *"called from the four transaction-driving tests"* with no superseded
annotation, unlike §14's and §15's corrected rows — NIT 1 below.

---

### 4. NIT — §16's stale "four transaction-driving tests" is the one historical row that did not get the superseded annotation

**Where:** §16, the *"What the review asked to be kept, and is kept"* paragraph.

The convention is established and applied twice (§14 row 1 and §15 row 1 both carry *"corrected in
revision N — see §…"*). This sentence predates revision 8's caller-count correction and carries no
annotation, so a reader who lands in §16 first inherits the number §5.5's table exists to replace.

**Fix:** append *"— the caller list is six, not four; §5.5's numbered table is authoritative (see
§17 finding 1)"*.

---

### 5. NIT — §8's Modified row dates its own previous count to the wrong revision

**Where:** §8, `tests/test_gift_card_store.py` row: *"six updates, two retire-and-replace, three
rewrites, and three re-run without edit — the count moved from seven updates **in revision 8**"*.

Revision 8 is the current revision and holds the six-update count; seven was revision 7's. §17
finding 1 says it correctly (*"§8's count moves from seven updates to six updates plus three
re-runs"*). As written the row reads as though the current revision holds both numbers.

**Fix:** *"the count moved from revision 7's seven updates"*.

---

### 6. NIT — three line citations in §5.5 are off by two or three, including the one the row calls out as newly discovered

**Where:** §5.5's balance-floor row and its IAM paragraph.

Measured at `32b632e3`:

| Design says | Actually |
|---|---|
| `decrements[0]["ExpressionAttributeValues"][":neg"] == -40000` at `:286` | `:289`; `:286` is `assert len(decrements) == 1` |
| the test "inside the test at `:274-290`" | the test spans `:276-294` |
| the SPI `== ["dynamodb:UpdateItem"]` assertion "at `:293`" | `:295`; `:293` is the `PAYMENT_ATTEMPTS_TABLE_ARN` filter comprehension |

The substance of both claims is correct and I verified it: the `:neg` assertion exists and will
break under `_marshal` (it compares a bare `-40000`), and the `== ["dynamodb:UpdateItem"]`
assertion does cover the **PaymentAttemptsTable** statement rather than the ledger, so the design's
correction of its own earlier claim stands. Only the anchors drift — and the `:neg` row is the one
whose whole point is that the enumeration was short by one, so an off-by-three anchor there is
worth one edit.

**Fix:** `:289` and `:276-294` in the balance-floor row; `:295` in the IAM paragraph.

---

### 7. NIT — `_CreditThrottles` loses both its callers and `_MarkerWriteFails` plausibly loses all three, and neither fate is stated

**Where:** §5.5's retire/rewrite set, against the tree.

Measured users: `_CreditThrottles` at `:675` and `:714` — both tests are rewritten to arm the
transaction instead, so the class ends with **zero** callers. `_MarkerWriteFails` at `:440`
(retired test), `:478` (`test_a_stalled_redemption…`, rewritten to be driven by a *settled* claim
and an intervening purchase) and `:745` (retired test) — so on the design's own description it ends
with zero callers too. §5.5 says what happens to every test and nothing about the two fault
injectors the tests existed to use.

This matters only for legibility, but the document already argues the point itself about
`APPLIED_CLAIM_PREFIX`: *"A constant with no caller misleads the next reader into thinking a guard
exists."* A `FakeTable` subclass whose docstring describes a window that no longer exists is the
same hazard in a test file.

**Fix:** one row or one sentence in §5.5 — both subclasses go with the tests that used them, or
whichever survives is named with its surviving caller.

---

## Verified assumptions

Read from the worktree at `32b632e3` and held exactly as the design states. Listed because this is
the fifth pass and the cheapest thing a reviewer can do is re-litigate what is already right.

| Claim | Verified |
|---|---|
| Worktree HEAD is `32b632e3b319b278d76f630f349c9fa96bf3b3bd` | ✅ |
| `money.py` defines `positive_paise` and **no** `value_paise`; `positive_paise` converts an integral `Decimal` (`:34-37`); `value_paise` is `gift_card_store.py:543` | ✅ exact |
| `Money.__post_init__` enforces `type(self.paise) is int`, `0 <= paise <= 9007199254740991` and `currency == "INR"` in one condition (`money.py:16-18`); `from_wix` requires a `str` matching `[0-9]{1,14}(\.[0-9]{1,2})?` (`:22`); `to_wix` emits exactly two places (`:28`) | ✅ exact |
| `gift_card_store.py` is 1,513 lines; `import hmac` `:87`, `import secrets as _secrets` `:89`, `import time` `:90`, `from hashlib import sha256` `:92`, `Callable` in the typing import — so the injected `sleep` default and `_secrets.randbelow` need no new import | ✅ exact |
| `SECRET_ID` `:104`, `PEPPER_FIELD` `:106`, `MAX_VALUE_PAISE = 99_999_999_999`, `APPLIED_CLAIM_PREFIX`/`APPLIED_VOID_PREFIX` `:194-195`, `SecretReader` `:367`, `read_pepper` `:389`, `code_hash` `:442` | ✅ exact |
| `code_hash` is `hmac.new(pepper.encode("utf-8"), normalise_code(code).encode("utf-8"), sha256).hexdigest()` — the construction `card_code` reuses and `CODE_DOMAIN_TAG` separates from | ✅ exact |
| `void()` refuses a duplicate at the **pre-read** with no write: `if original.get("credited") is not False: raise AlreadyVoided` at `:1441`, inside the `if latched:` branch — so §5.3.1's decision is today's behaviour, and `is not False` covers both `True` and absent | ✅ exact |
| `redeem()` short-circuits a settled claim before any money move: `if existing.get("settled"):` at `:1238` returning the replay answer through `:1242`, with `_decrement` never called — so §5.3's symmetric decision is also today's behaviour (the design cites `:1237-1242`, a one-line-wide range) | ✅ |
| `_is_conditional_failure` reads `response["Error"]["Code"]` (`:377-384`) and is consulted by non-transactional callers only, so a separate `_is_transaction_cancellation` is the right call | ✅ |
| The only production callers of `redeem`/`void` are `wix-giftcard-spi/handler.py:310` and `:341`; both emit `{"remainingBalance": int(outcome["remainingBalancePaise"])}` at `:323` and `:361`, so the post-commit figure is customer-visible and §5.3's invariant is the right treatment | ✅ exact |
| `ecommerce/gift-cards/handler.py:143` reads the pepper lazily through an injected reader (`store.read_pepper(_read_secret, secret_id=SPI_SECRET_ID)`) — the pattern §2.5 points the adapter's caller at | ✅ |
| The access-pattern gate's call filter is `if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)): continue` (`tests/test_gift_card_store.py:1106`); its `exact` set is `{get_item, put_item, update_item, delete_item}`, so `transact_write_items` never reaches the `ast.unparse` assertions; the `FunctionDef`-owner walk is at `:1122-1127`-ish and reusable; the whole runtime tail is `store = table()` + `pytest.raises(AssertionError): store.scan()` | ✅ exact — both prior HIGH-2 diagnoses confirmed |
| `test_no_float_is_constructed_anywhere_on_the_store_money_path` is at `:1066`, monkeypatches `builtins.float` and drives a full redeem/void cycle; `test_the_store_holds_no_boto3_client_and_reads_no_secret_itself` is at `:1152`; there is **no** AST float gate over `gift_card_store.py` | ✅ exact |
| The balance-floor test holds all three assertions the design enumerates, including the bare `:neg == -40000` comparison that `_marshal` will break | ✅ (line anchors drift — finding 6) |
| `FakeTable.arm_failure` is a dict assignment at `:235-237`, consumed by `_fail_if_armed`'s `fail_on.pop` at `:246`; `calls.append(...)` precedes `_fail_if_armed(...)` and precedes condition evaluation in every operation (`put_item` `:253/:255`, `get_item` `:267/:268`, `update_item` `:275/:280/:285/:286`) — so `calls` is genuinely an attempt log and §2.6's `applied` outcome log is required | ✅ exact (the design's attribution of the `pop` to `arm_failure` is the mis-citation in finding 1) |
| `FakeClientError.__init__(self, code)` builds only `{"Error": {...}}`, so the `cancellation_reasons` keyword is genuinely required; `FakeTable.__init__` is `(key_attr, indexes)` with no `name` and no `.meta` | ✅ exact |
| The two `_CreditThrottles` tests drive the sequences §5.5 describes (redeem, 1 or 2 failing voids, a succeeding void, and in the first case a refusing fourth call), and `RuntimeError("ProvisionedThroughputExceededException")` is not a cancellation — so the per-attempt recording argument is right and caller 4's count of 3 is correct | ✅ |
| `tests/coupon_fake_dynamo.py` is imported by exactly the seven files §9 names (four gift-card, three coupon) | ✅ exact |
| `_markers_on` `:423`, `table` `:63`, `issue` `:68`, `clock` `:59`, `digest_of` `:76` — the neighbours §5.5 sites the new helper beside | ✅ exact |
| `.github/workflows/` references neither `demo_` nor `scripts/demo`; `route-auth.yml:111` is a bare `python -m pytest -q` full-suite step | ✅ exact — §7's anti-rot claim is backed |
| `coupons/handler.py`: `STAFF_ROLE = "Operator"` `:80`, `_staff` `:138`, `_create` `:204` with `except Exception` at `:229`; it is the only place claim-row → Wix create → `mark_mirrored` is composed | ✅ |
| `tests/test_gift_cards_iam_and_table.py`'s `== ["dynamodb:UpdateItem"]` assertion covers the **PaymentAttemptsTable** statement, not the gift-card ledger — so the design's correction of its own earlier claim is right and the added ledger pin is new coverage | ✅ (anchor drift — finding 6) |
| §2.4 Group C's digest computation: `demo_code(R) = WDGCB4A4841861208FA8` (20 chars), `idempotency_key(R)` 70 chars, `demo_code in key` and `.lower() in key` both `False`, `_digest_body(demo_code) in _digest_body(key)` `True` | ✅ recomputed here |
| §6.2 keeps the credential by reference: `{{resolve:secretsmanager:wecare/wix/headless-api-key:SecretString:apiKey}}` under `asm-exec`, which exists at `~/.local/share/razorpay-mcp-server/asm-exec-env.py` mode `0700`, with "use Option 1 and stop, do not substitute the value" as the fallback | ✅ |
| Prohibitions respected: no live Wix write authored, no deploy, no provisioning, no `get-secret-value` in any spelling, no credential value (the pepper and API key appear only as names), no payment capture/refund/configuration change, no live-send flag, nothing deleted, no guard weakened, and no file in the out-of-bounds list edited (`coupons/handler.py` is driven, not modified) | ✅ |
| Locked decisions intact: coupons **Option B** with our table as the idempotency ledger and Wix doing the arithmetic; gift cards **Wix-native (A)** with retirement source-only and gated on §0.1 condition 3; **Loyalty and Referral** designed nowhere (§1.5) | ✅ — not relitigated here |

## Unverified / wrong assumptions

| # | Assumption in the design | Status |
|---|---|---|
| 1 | Every §3 Wix schema fact — V1-V4, `source` required, `expirationDate`, `codeSuffix`, `balance`/`currency` on the Query response, the two permission scopes, `filter-and-sort.md`'s `specification.code` row, and the markdown rendition rendering no `Errors` section for any method | **UNVERIFIED by this review.** I made no network fetch, and the design states that `docs/execution/wix-contract-verification-20261002.md` does not exist yet. Correctly declared, correctly gated by §3.0's halt rule and by "implementation step 0". **Not a finding** — but §3 remains the only record of these measurements, so step 0 is load-bearing rather than tidy |
| 2 | `FakeTable.arm_failure` can be "armed twice" to produce two failures, and caller 5 therefore records 4 transactions | **WRONG as specified.** Arming is one-shot per arm (`fail_on[op] = exc`, popped by `_fail_if_armed`), so the literal reading yields one failure and 3 transactions, and the second `pytest.raises` fails. Finding 1 |
| 3 | `_committer_of` (and `_is_balance_move`) are available instruments the tests can call | **WRONG — neither exists in the tree** (0 matches), and `_committer_of` has no signature, no home and no stated import despite §7 naming the committer set as the proof. Finding 2 |
| 4 | The runtime helper's caller list is stated once | **CONTRADICTED INSIDE §5.5** — the numbered table says six, the ownership sentence 40 lines later says four. Finding 3 |
| 5 | `FakeTable` models real `TransactWriteItems` semantics for the two-`Update` shape | **UNVERIFIED, and correctly declared** as the largest piece of trust in §5 (§7, §9 assumption 3), with the `RLock`, the strict-refusal posture and `TransactionConflict` arming as the stated mitigations. Not a finding |
| 6 | Wix's `idempotencyKey` is idempotent on this site, and a fractional-INR amount with a custom code is accepted | **UNVERIFIED, and correctly gated** on §0.1 condition 3 / §6.2 steps (a)-(c), owner-run. Not a finding |
| 7 | §0.1's AWS probes (no gift-card function, table, route or secret) | **DATED SNAPSHOT, correctly declared** with instructions to re-derive before the deletion lands. I did not re-run them; nothing in this review depends on them. Not a finding |
| 8 | §5.5's and §5.3's line anchors into `tests/test_gift_card_store.py` and `tests/test_gift_cards_iam_and_table.py` | **THREE ARE WRONG** by two or three lines, while the facts they point at hold. Finding 6 |
| 9 | `_MarkerWriteFails` and `_CreditThrottles` still have callers after §5.5's edits | **NOT STATED, and on the design's own description both end with none.** Finding 7 |

---

## Verdict

0 HIGH + 3 MEDIUM → **CHANGES_REQUESTED**.

Both HIGH mechanisms from the prior review are confirmed closed against the tree and neither
recurs. The gift-card code is HMAC-keyed under the existing `wecare/wix/giftcard-spi:code_pepper`
with a domain tag, an injected required-keyword pepper, a renamed and AST-fenced `demo_code`, and
nothing in the module to log with. The access-pattern property is split so the AST arm asserts
presence and location with the node predicates now spelled out, while a runtime helper over
`table.calls` asserts item shape, refuses an empty recording and is sited on tests that really
drive a transaction. Every MEDIUM the brief listed is resolved: `positive_paise` reconciled with
`Money.__post_init__`, the create body pinned byte-exactly with `source` and `expirationDate`
named, `balancePaise` and `codeLast4` sourced per key with `codeSuffix` and no fallback slice, the
one-create queue typed with the recording count as the named enforcement, §3.0's halt rule in place
and recorded firing on its own author, and §7's CI claim replaced by a test the existing
`pytest -q` step collects.

What remains is the last perimeter of the same family: a fault injector that cannot fire twice
from one arm, the new helper that inherited the property a deleted literal used to carry, and a
count that is still written twice inside the section nominated as its single source. All three are
local edits that change no decision, and the two verdicts, the §0.1 gate and the locked decisions
stand exactly as written.
