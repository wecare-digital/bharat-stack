# Implementation plan — Wix coupon + gift card sample

Turns `design.md` **revision 8** into code. The design is **frozen**: nothing below reopens a
verdict, an architecture or a §1 decision. Where this plan differs from a sentence in the design
it is because the design's own authoritative table says so, or because a review finding asked for
an implementation mechanism the design named but did not define — each such case is flagged inline
with `[REVIEW n]` and nowhere else.

**Worktree (absolute, always):** `/Users/wecaredigital/wecare-store/.worktrees/wix-coupon-giftcard-sample-20261002`
Branch `wix-coupon-giftcard-sample-20261002`, based on `stack` at `32b632e3`. Do not create a
worktree. Every `git` is `git -C <worktree>`. Relative paths from the step cwd land in the main
workspace — use absolute paths or `cwd` the worktree.

**Interpreter.** The worktree has no `.venv`; the one that satisfies `conftest.py` (≥3.12) lives in
the parent checkout:

```
cd /Users/wecaredigital/wecare-store/.worktrees/wix-coupon-giftcard-sample-20261002
/Users/wecaredigital/wecare-store/.venv/bin/python -m pytest <paths> -q
```

Referred to below as `$PY`. A bare `python3` is not a valid baseline.

## Locked decisions carried into every item

* **Coupons = Option B.** `coupon_store` is the issuance ledger kept for idempotency (Wix
  `Create Coupon` has no `idempotencyKey` and no read-by-code); Wix does the discount arithmetic
  only. Resolve-before-generate on the issuance key. Nothing here computes a discount.
* **Gift cards = Wix-native (A).** Build toward Wix's gift-card API as the balance authority.
  `wix_gift_cards.py` ships **unwired** and a Group D guard keeps it that way.
* **Retirement of our gift-card backend is source-only and gated.** It is **not** performed in
  this change — see item 16, which is a decision point with a written STOP rule, not a deletion.
* **The gift-card code stays HMAC-keyed** under the **existing** `wecare/wix/giftcard-spi` field
  `code_pepper`, domain-tagged, 20 characters (Wix's ceiling). The clear bearer code is never
  returned to a caller and never logged. `demo_code` is unkeyed, demo-only, and fenced from
  `amplify/` by an AST guard.
* **Loyalty and Referral are dropped.** No seam, no stub, no mention in code.

## Hard prohibitions, in force for every item

No deploy. No provisioning (`--apply` on nothing). **No live Wix write of any kind.** No
`secretsmanager get-secret-value` in any spelling — the API key and the pepper appear only as
secret **names**. Integer paise, explicit `== "INR"`, `Decimal(str(value))` only where a DynamoDB
number re-enters arithmetic, no float on any **amount** (the one permitted float is a `sleep`
duration — design §5.6). No live sends. Stay inside this worktree: do not touch
`.worktrees/direct-razorpay-20261002`, `ecommerce/checkout/handler.py`, `payment_readiness.py`,
`payments/razorpay-webhook/handler.py`, or anything under `amplify/functions/messaging/`.
`amplify/functions/ecommerce/coupons/handler.py` is **driven, not modified**.

Git: stage by explicit path, prefer `git commit --only <paths> -F <msgfile>`, never `git add .`
/`-A`/`-u`, no bare `stash`, no `clean`, no force push, no history rewrite. Do **not** rebase onto
or fast-forward `stack`; leave the branch for owner review.

## Known-good baseline, measured in this worktree at `32b632e3`

| Measurement | Result |
|---|---|
| `tests/test_gift_card_store.py` + the 7 other gift-card/coupon/vocabulary consumers | **301 passed, 7 xfailed** |
| `tests/test_coupon_store.py` | **70 passed** |
| `tests/test_url_host_routing_rules.py` + `tests/test_legacy_redirect_rollback_snapshot.py` | **5 failed, 6 passed** — pre-existing, **not** regressions |

`wecare/google-maps-server:api_key` is an expired, unrelated secret; ignore it.

No `.ts`/`.tsx`/`.js` file is in this change's footprint, so `npm run build` + `vitest` is a
final whole-repo gate only (item 18) and the build-before-vitest ordering matters there.

---

# Items

- [ ] 1. **Write the Wix contract verification transcript — design §3.0's "implementation step 0", before any code.**
      Create `docs/execution/wix-contract-verification-20261002.md` by re-running the six commands
      in §3.0.1 against `dev.wix.com`'s markdown rendition (`.md` appended). Per fetch record: the
      URL **in the form used**, HTTP status, page byte size, and the **extracted schema fragment** —
      not a summary. V1 and V2 are **absences**, so record the command, its empty/typed output and
      its exit status; a `grep -c` of `0` is the finding, not a silence. Also record §3.0.1's own
      warning: the pre-revision-5 URL set now 404s and returns a ~4 MB schema-free shell, so a
      future re-run against the old form reads *absent* when the fact is *present*.
      **Apply §3.0's HALT rule.** If V1 (`idempotencyKey` absent from `CreateCouponRequest`),
      V2 (`Query Coupons` `filter` typed `string`), V3 (`idempotencyKey` present on
      `CreateGiftCardRequest`) or V4 (the `code` operator map on `Query Gift Cards`) disagrees with
      the design, **stop and report**. Do not edit a row and continue; a verdict-carrying
      disagreement moves §1, §0.1 and the memo with it, and that is a design decision this plan
      may not take. Non-verdict rows (a length, a path, a format, an example) are corrected in
      place in the transcript — the artifact wins.
      Files: `docs/execution/wix-contract-verification-20261002.md`
      Verify: the file exists and contains all four V-rows with status, byte size and fragment;
      `grep -c 'HTTP 200' ` reports one line per fetch; the four verdict rows each state
      *confirmed* explicitly. No code has been written yet, so there is nothing else to run.

- [ ] 2. **`tests/coupon_fake_dynamo.py` — the three additions of design §2.6, plus the injected-failure repair.**
      (a) An `RLock` created in `__init__` and held for the **entire body** of `put_item`,
      `get_item`, `update_item`, `delete_item`, `query` and `transact_write_items`, condition
      evaluation included — this is what models DynamoDB's per-item/per-transaction atomicity and
      is what licenses item 9's interleaving claim. `RLock`, not `Lock`, because subclass overrides
      re-enter through `super()`.
      (b) An `applied` outcome log beside the existing `calls` attempt log, appended **inside** the
      locked body only after every condition passed and the mutation committed, in `put_item`,
      `update_item`, `delete_item` and `transact_write_items`. `calls` keeps its current meaning
      (appended **before** the condition — `:253`, `:267`, `:275`) and no existing assertion
      changes.
      (c) `transact_write_items(TransactItems=[...])` in the real low-level shape: deserialise with
      `from boto3.dynamodb.types import TypeDeserializer` (legal here — `tests/` already depends on
      botocore), convert `{"N": ...}` `Decimal` to `int` and **raise** on a non-integral value,
      evaluate every item's `ConditionExpression` first and apply all or nothing, and raise
      `FakeClientError("TransactionCanceledException", cancellation_reasons=[...])` with
      `{"Code": "ConditionalCheckFailed"}` / `{"Code": "None"}` entries on failure. Support exactly
      the `Update`-with-`ConditionExpression` shape and refuse anything else with a new
      `UnsupportedFakeOperation(BaseException)` — **not** an `AssertionError`, because
      `gift_card_store` wraps the balance move in `except Exception` → `GiftCardStoreUnavailable`
      and would relabel the fake's complaint as a transient outage. Record
      `("transact_write_items", {...})` with the item list **as received**.
      (d) `FakeClientError.__init__(code, *, cancellation_reasons=None)` placing the list at the
      **top level** of the response, a sibling of `"Error"` — the defaulted keyword leaves every
      existing call site untouched.
      (e) `name: str = "stack-wecare-digital-FakeTable"` constructor keyword plus `.name`, and
      `.meta.client` returning the fake itself, so production can use only the real boto3 shape.
      (f) `[REVIEW 1]` **`arm_failure(operation, exc, *, times: int = 1)`** with a decrementing
      counter. The design's `test_a_void_credit_that_fails_twice...` says the fault is "armed
      twice", which today's one-shot `arm_failure` cannot express: `_fail_if_armed` consumes the
      arm with `self.fail_on.pop(operation, None)` at `:246`, so two arms before the calls produce
      **one** failure and the second `pytest.raises` fails against correct code. Of the two repairs
      the design's review offered, `times=` is chosen over re-arming between the two `void()`
      calls: it keeps the arming visible at the arming site instead of hiding a re-arm in the
      middle of a test body, and it makes the test's own narrative literally true. Default `1`, so
      all seven importers are unaffected. Record in the docstring the citation the design got
      wrong: the pop is in **`_fail_if_armed` (:246)**, not in `arm_failure` (`:235-237`).
      Files: `tests/coupon_fake_dynamo.py`
      Verify: `$PY -m pytest tests/test_coupon_store.py tests/test_coupon_reconciliation.py
      tests/test_wix_coupons_contract.py tests/test_gift_card_store.py
      tests/test_gift_card_two_leg_finalization.py tests/test_gift_card_spi_contract.py
      tests/test_gift_card_amounts_and_gst.py -q` — unchanged from baseline (the lock is inert for
      a single-threaded caller, `applied` is additive, `name` and `times` are defaulted). A failure
      in the three coupon files is a **defect in the fake**, not noise.

- [ ] 3. **`tests/wix_transport_stub.py` — the `urlopen` replacement (design §2.3).**
      `UnexpectedWixCall(BaseException)` — deliberately **not** an `Exception`, because
      `wix_ecom._request` ends in `except Exception` → `WixEcomError` (`:109-111`, `try` at `:103`)
      and `coupons/handler._create` catches `Exception` and answers **202** with a
      documented-success body (`:229-233`), so an `AssertionError` here would be laundered into a
      success. A frozen `RecordedRequest` dataclass holding `method`, `url` (absolute),
      `headers` with `Authorization` replaced by `"<redacted>"` **at capture**,
      `authorization_present: bool`, `body_bytes`, `body`. `WixTransport` with
      `expect(*, method, endpoint, status=200, body=None, raw=None)`,
      `expect_http_error(*, method, endpoint, status)` raising a genuine
      `urllib.error.HTTPError(url, status, "", {}, None)`, and `__call__(request, timeout=None)`
      that **compares `(request.get_method(), request.full_url)` against the queued entry before
      popping** and raises `UnexpectedWixCall` naming expected vs actual on a mismatch — this typed
      queue is what makes "one create, not two" enforceable. `endpoint` is a path; the stub
      prepends `wix_ecom.WIX_API_BASE` itself. Refuse loudly: empty queue, wrong call at the head,
      unconsumed entries at teardown, a `request` that is not a `urllib.request.Request`. Serve a
      minimal context manager with `.read() -> bytes` plus inert `.status`/`.headers`. Record
      `timeout` without policing it.
      Files: `tests/wix_transport_stub.py`
      Verify: `$PY -c "import sys; sys.path.insert(0,'tests'); import wix_transport_stub"` imports
      clean; the module is exercised for real by items 6 and 12. (`tests/conftest.py` already puts
      `amplify/functions/shared` on `sys.path`.)

- [ ] 4. **The nine response fixtures (design §8 New).**
      `tests/fixtures/wix_giftcard_create_response.json` (B1 `CreateGiftCardResponse`, full clear
      code, from the documented example), `wix_giftcard_query_by_code_response.json` (obfuscated
      code, with `codeSuffix`, `balance.amount`, `currency`),
      `wix_giftcard_balance_after_redeem.json` (`balance.amount` `"999.75"`),
      `wix_giftcard_query_miss_response.json` (`giftCards: []`) **plus a sibling with the
      `giftCards` key absent**, `wix_giftcard_query_two_matches_response.json` (two entries),
      `wix_giftcard_query_disabled_response.json` (one entry carrying `disabledDate` **and**
      `expirationDate`), `wix_coupon_create_response.json` (`{"id": "..."}`), and
      `wix_coupon_get_response_float_amounts.json` — the existing Get shape with
      `"moneyOffAmount": 10.0` and `"minimumSubtotal": 5000.5`, because the existing
      `wix_coupon_get_response.json` carries only JSON integers and cannot demonstrate the float
      hazard. Leave the existing fixture unchanged and in use for every non-float row.
      Files: the nine paths under `tests/fixtures/`
      Verify: `$PY -c "import json,glob;[json.load(open(p)) for p in
      glob.glob('tests/fixtures/wix_giftcard_*.json')+glob.glob('tests/fixtures/wix_coupon_*.json')]"`
      exits 0, and the float fixture parses with
      `type(...["coupon"]["specification"]["moneyOffAmount"]) is float`.

- [ ] 5. **`lambda_utils/ecommerce/wix_gift_cards.py` — the B1 adapter, pure and unwired (design §2.5).**
      Constants exactly as §2.5 states: `BASE = "/gift-cards/v1/gift-cards"`, `CURRENCY = "INR"`,
      `SOURCE_MANUAL = "MANUAL"`, `MAX_IDEMPOTENCY_KEY = 100`, `MIN/MAX_CODE_LENGTH = 8, 20`,
      `CODE_SUFFIX_LENGTH = 4`, `MIN_INITIAL_VALUE_PAISE = 1`,
      `MAX_INITIAL_VALUE_PAISE = 99_999_999_999` (borrowed from the SPI so legs 2 and 3 are bounded
      identically — §3.3 records **no** Wix maximum), `CODE_DOMAIN_TAG = b"wix-gc-code:"`.
      `WixGiftCardError(RuntimeError)` with `__init__(code, message="")` setting a stable
      enumerable `.code`, plus the closed `REFUSAL_CODES` frozenset — mirroring
      `wix_coupons.WixCouponError`, so a reason is a field and never message text.
      Three derivations: `idempotency_key(*, reference_id)` (unkeyed sha256, `"wd-gc-" + digest`
      truncated to 100 — rotation-invariant, not bearer value); `card_code(*, reference_id, pepper)`
      = `hmac.new(pepper, CODE_DOMAIN_TAG + reference_id, sha256)` → `("WDGC" + hex[:16]).upper()`,
      exactly 20 chars, `pepper` **keyword-only with no default**, refusing `""`/`None` with
      `A_PEPPER_IS_REQUIRED`; `demo_code(*, reference_id)` unkeyed and demo-only, same shape and
      same length, with the docstring stating the true danger — **both it and the idempotency key
      expose the same unkeyed sha256 digest of the same input, so either yields the other.**
      `WixGiftCards(request)` with `create`, `find_by_code`, `get`, `disable` (no `delete` — Wix has
      none). `create` **resolves before it generates**: when a deterministic `code` is supplied it
      calls `find_by_code` first; a hit returns the existing card — including a disabled or expired
      one — and issues **no** create. Only the `{}` miss proceeds to `POST`, carrying
      `idempotencyKey` as the in-Wix backstop for the query→create window.
      `find_by_code`'s three branches: `{}` on a miss (not `None`, no raise); **one** hit → the
      same **seven** keys `create` returns with `resolved: True`; more than one →
      `WixGiftCardError("AMBIGUOUS_CODE")` with no further request. `giftCards[0]` is read only
      after the length check.
      The create body is **exactly** §2.5's dict and nothing else: `initialValue.amount` =
      `Money(paise).to_wix()`, `currency`, `source`, with `code` and `expirationDate`
      conditionally **merged in rather than sent as `null`**. Never send `orderInfo` (a false
      provenance claim) or `notificationInfo` (a live customer email on a premium plan).
      The return dict is the one authoritative seven-key enumeration —
      `{giftCardId, codeLast4, balancePaise, currency, resolved, disabled, expirationDate}` — the
      same on both branches and on both public functions. `codeLast4` is **Wix's `codeSuffix`**,
      never a parse of `code`; absent or not exactly four characters raises
      `CODE_SUFFIX_MISSING` with no fallback to slicing bearer value. `disabled` =
      `bool(... .get("disabledDate"))`; `expirationDate` passes through **unparsed** (this adapter
      makes no expiry decision). Docstring the one key that means two facts: `balancePaise` is
      `initialValue` on a create and the **current** balance on a resolve hit.
      Every validation row in §2.5's table, each refusing **before** any amount is formatted or any
      request composed: `type(initial_value_paise) is not int` (exact type — `bool` is an `int`),
      the min/max, `currency == CURRENCY` compared **explicitly and first**, code length,
      `source in {SOURCE_MANUAL}`, idempotency-key length `1..100`,
      `datetime.datetime.fromisoformat` on `expiration_iso`, non-empty `gift_card_id`.
      Imports: `hashlib`, `hmac`, `from hashlib import sha256`, `datetime`, and the shared money
      types. **No** `boto3`, `botocore`, `urllib`, `os` — that is a **denylist**, and the import
      enumeration in the design is descriptive; do not turn it into an allowlist assertion. The
      module reads **no secret**: the pepper is a required keyword the caller obtains. No `logger`,
      no `logging`, no `print(`.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/wix_gift_cards.py`
      Verify: `$PY -c "import sys;sys.path.insert(0,'amplify/functions/shared');from
      lambda_utils.ecommerce import wix_gift_cards as w;print(w.card_code(reference_id='wd-gc-sample-2026-10-02',pepper='p'),w.demo_code(reference_id='wd-gc-sample-2026-10-02'))"`
      prints two 20-character codes, the second being `WDGCB4A4841861208FA8`. Full coverage lands
      in item 6.

- [ ] 6. **`tests/test_wix_coupon_giftcard_sample.py` — the harness, Groups A–D (design §2.4).**
      Install the §2.2 containment in a fixture: `monkeypatch.setitem(wix_ecom._key_cache, "key",
      PLACEHOLDER_API_KEY)` (a module constant chosen to match none of
      `scripts/block_inline_secrets.py`'s issuer prefixes, never an argv value) and
      `monkeypatch.setitem(sys.modules, "boto3", _ExplodesOnAttributeAccess())` whose
      `__getattr__` raises `_UnexpectedAwsUse(BaseException)`. Assert `wix_ecom._secrets is None`
      after driving. Do **not** assert `"boto3" not in sys.modules` — it is false in this very
      module once the handler is imported, and red in CI regardless of the code under test.
      Patch `urllib.request.urlopen` and nothing else, so all five behaviours of `wix_ecom._request`
      execute for real.
      **Group A** (adapter/wire, `coupon_store.create` then
      `WixCoupons(wix_ecom._request).create`, composed by the test): method + absolute URL
      `POST https://www.wixapis.com/stores/v2/coupons`, `/ecom/` absent, the normalised header-name
      set `{authorization, content-type, accept, wix-site-id}` **and** a separate assertion on the
      exact recorded spelling `{Authorization, Content-type, Accept, Wix-site-id}` — note
      **`Content-type`**, because `Request.add_header` applies `str.capitalize()`; put the reason in
      the assertion message so nobody "fixes" it by loosening it. `Wix-site-id ==
      wix_ecom.WIX_SITE_ID`, `Authorization` present and never recorded, the body compared
      **whole** (an extra key in a coupon specification is a different promise),
      `type(...["moneyOffAmount"]) is int`, `type(...["startTime"]) is str`, no `type` field, and a
      second **percent-off** definition asserting `type(...["percentOffRate"]) is int` and
      `"moneyOffAmount" not in ...` — that is the payload §6.5 hands the owner.
      **Group B** (handler, `handler._create(event, origin=...)`): stub exactly
      `handler._staff → lambda event: None` and `handler._coupons_table → lambda: fake`, and pass
      the full event including `"_auth": {"username": "demo-operator"}` so `created_by` matches
      production. Patch `_staff`, **not** `middleware.require_auth` — `handler.middleware` is the
      shared module object that 58 files reference. Rows per §2.4: create success → `201` and
      `wixMirrorState == MIRRORED`; the float fixture at adapter level asserting the hazard is real
      (`type(...) is float`) **before** asserting containment (no `float` in the view);
      `assert_mirrors` for the foreign-code conflict and the case-only non-conflict (**not** `get`,
      which raises nothing); `expect_http_error` for 400/409/428/500/502 at **both** levels —
      `WixEcomError` escaping at adapter level, **202** with the row left `PENDING_WIX` and
      `evaluate → WIX_MIRROR_INCOMPLETE` at handler level; `deactivate` → `PATCH .../{id}` with
      body exactly `{"specification": {"active": false}}` and no `fieldMask`. The two 409 rows
      together are the §1.3 unrecoverability finding made executable.
      **Group C** (the gift-card adapter): the whole §2.4 Group C table. Order matters — the
      determinism row comes **first**, then the keying rows. For non-recoverability use
      `_digest_body(v) = v.lower().removeprefix("wdgc").removeprefix("wd-gc-")` and assert in
      **both** directions for `card_code`, **plus the positive line**
      `_digest_body(demo_code(R)) in _digest_body(idempotency_key(R))` — that third line is the
      mutation test that makes the first two capable of failing. Domain separation is a
      **recomputation**: `card_code(...) != ("WDGC" + gift_card_store.code_hash(X, pepper=P)[:16]).upper()`,
      which fails iff `CODE_DOMAIN_TAG` is removed; say so in the assertion message rather than
      claiming a black-box check. Assert `demo_code` positively against its formula, both lengths
      `== MAX_CODE_LENGTH == 20`, the pepper refusal with `.code == "A_PEPPER_IS_REQUIRED"` and
      **zero** recorded requests, every §2.5 refusal's `.code in REFUSAL_CODES` with
      `isinstance(exc, RuntimeError)` and zero requests, the byte-exact create body with `source`
      present and the two optional keys **absent rather than null**,
      `type(...["initialValue"]["amount"]) is str`, `currency == "INR"`, resolve-before-create
      enforced **two ways** (the typed queue `query(miss) → create → query(hit)`, **and** a direct
      count of `POST`s to the create endpoint `== 1` — the count is the named enforcement),
      `find_by_code` miss `== {}` exactly, multi-match → `AMBIGUOUS_CODE` with zero further
      requests, the disabled resolve hit reported (not refused) with no create, the expiry returned
      verbatim, the seven-key set asserted on **three** subjects (create, resolve hit, direct
      one-hit `find_by_code`) through one helper whose message names branch-independence, the
      fractional round-trip `Money(250050).to_wix() == "2500.50"` and back with `type(...) is int`,
      and the balance read-back `Money.from_wix("999.75").paise == 99975`.
      No-float is proved three ways and **not** by monkeypatching `float` (the `json` decoder binds
      `parse_float` at construction, so the patch is inert and only risks breaking pytest):
      boundary type assertions, the Group D AST gate, and
      `pytest.raises(ValueError): Money.from_wix(10.0)`.
      **Group D** (structural): no handler imports `wix_gift_cards`; the four-module **denylist**;
      no `get_secret_value`/`batch_get_secret_value`/`client`/`resource`; **no file under
      `amplify/` references `demo_code`** by an AST walk over `ast.Attribute`, `ast.Name` and
      `ast.ImportFrom` **only** — not a text grep and not `FunctionDef.name`, because
      `wix_gift_cards.py` is itself under `amplify/` and defines the function; do not special-case
      the file. `card_code`'s `pepper` in `args.kwonlyargs` with its `kw_defaults` entry `None`; no
      `logger`/`logging`/`print(` in the module; the identifier `float` absent from both
      `wix_gift_cards.py` and the demo script by AST; `handler._staff`'s source calls
      `middleware.require_auth` with `STAFF_ROLE`; and `wix_ecom._secrets is None`.
      Files: `tests/test_wix_coupon_giftcard_sample.py`
      Verify: `$PY -m pytest tests/test_wix_coupon_giftcard_sample.py -q` — all pass, zero
      skips. Then `$PY -m pytest tests/test_wix_coupons_contract.py tests/test_coupon_store.py
      tests/test_coupon_reconciliation.py -q` still matches baseline.

- [ ] 7. **`gift_card_store.py` — the two-item `TransactWriteItems` fix (design §5.3, §5.3.1).**
      Depends on item 2 (the fake must model the transaction before any test can drive it).
      Add `_marshal(value)` hand-written in the module — `BOOL` before `int` because `bool` **is**
      an `int`; `type(value) is int` exactly, so `Decimal` and `float` cannot slip through; `S` for
      `str`; otherwise `GiftCardValidationError("UNMARSHALABLE_VALUE", f"cannot marshal
      {type(value).__name__}")`. **Two arguments, constant code plus prose** — `.code` is the field
      handlers branch on and the SPI maps through `SPI_ERRORS`, so an interpolated code is
      unbranchable. `GiftCardValidationError`, **not** `GiftCardStoreUnavailable`: an unmarshalable
      value recurs identically on every retry, and labelling it retriable turns one defect into a
      retry storm on a money path. Do **not** import `TypeSerializer` — the AST gate at
      `tests/test_gift_card_store.py:1152` forbids `boto3`/`botocore`/`os` anywhere in the module,
      including inside a function body, and weakening a gate to land a change is not available.
      Add `_is_transaction_cancellation(error)` and `_cancellation_reason_codes(error)` reading
      `response["CancellationReasons"]` at the **top level** (a sibling of `"Error"`, not inside
      it — reading it from `response["Error"]` yields `[]` on every real cancellation and converts
      the main path of this fix into a 5xx). Keep `_is_conditional_failure` (`:377`) **exactly as
      it is**: it is consulted by `_put`, `hold`, `credit`, `disable`, `release` and `_delete_hold`,
      none of which opens a transaction.
      Add `_transact_with_retry(table, items, *, sleep=time.sleep)` as the module's **only** caller
      of `transact_write_items`, resolved as `table.meta.client.transact_write_items(...)` with
      `TableName=table.name`. Bounded retry on `TransactionConflict` / `ThrottlingError` /
      `ProvisionedThroughputExceeded`: 2 retries, 3 attempts, delay `0.05 * 2 ** n +
      _secrets.randbelow(25) / 1000` (`secrets`, never `random` — SnapStart freezes a PRNG). A
      cancellation with **empty or unrecognised** reason codes is treated as
      `ConditionalCheckFailed` and decided from the data, **never** as an outage. Re-raise a
      non-retryable cancellation unchanged so the caller's decide-from-data branch is unaffected.
      Rename `_decrement` (`:1277`) → `_commit_redemption(..., *, sleep=time.sleep)` and add its
      twin `_commit_void(table, digest, transaction_key, amount, now, *, sleep=time.sleep)`. Both
      route through `_transact_with_retry` and **neither** calls `transact_write_items` directly —
      that is the structure item 8's AST guard asserts, so the names are load-bearing.
      Redeem items exactly as §5.3 specifies (card: `ADD balancePaise :neg SET updatedAt,
      activeClaimAttemptId, activeHoldAttemptId = if_not_exists(...)` under
      `attribute_exists(key) AND balancePaise >= :amount AND #status = :active`; claim:
      `SET settled = :true, settledAt = :at` under `attribute_exists(key) AND settled = :false`).
      Void items exactly as §5.3.1 (card: `ADD balancePaise :amount SET updatedAt` under
      `attribute_exists(key) AND balancePaise <= :ceiling` with `:ceiling = MAX_VALUE_PAISE -
      amount`; txn: `SET credited = :true, creditedAt = :at` under `attribute_exists(key) AND
      attribute_exists(credited) AND credited = :false`). `attribute_exists(credited)` is written
      explicitly and is **not** redundant: without it *absent* is indistinguishable from *`True`*
      in the branch set and a card whose void predates the flag becomes permanently un-voidable.
      Remove `_mark_settled` (`:1363`), `_mark_credited` (`:1376`) and `_drop_applied_marker`
      (`:1337`) **entirely**, and `APPLIED_CLAIM_PREFIX`/`APPLIED_VOID_PREFIX` (`:194-195`) from
      the module and `__all__`; narrow the `CARD_ATTRIBUTES` docstring note. A settle helper that
      still exists invites a future caller to write `settled` outside the transaction, which is the
      exact defect this closes.
      `credit()` (`:951`) **loses its `once_key` parameter and the whole marker branch**
      (`:951-1015`), keeping only the plain addition — two top-ups of the same size are two events
      and nothing should make them idempotent. `void()` (`:1395`) is its only caller today.
      `redeem()` (`:1172`) and `void()` each gain a **keyword-only** `sleep: Callable[[float],
      None] = time.sleep`, threaded to `_transact_with_retry` through the committer exactly as
      `clock` is threaded. Those two signature moves — the `once_key` removal and the `sleep`
      addition — are the whole of this change's public surface movement, and neither breaks the two
      production callers (`wix-giftcard-spi/handler.py:310` and `:341`), which pass neither.
      `balanceAfterPaise` stays a **best-effort follow-up `UpdateItem`** (TransactWriteItems has no
      `ReturnValues: ALL_NEW`), and `redeem()`'s docstring carries §5.3's invariant verbatim:
      `remainingBalancePaise` and `GCTXN#.balanceAfterPaise` are the balance **as at the read that
      followed the commit** — observations, not the result of this transaction; the exact figure is
      `amountPaise`.
      Both pre-reads stay the **primary** decision and the transaction conditions are the
      **concurrency re-check**: a duplicate `void()` refuses at `:1441` (`if
      original.get("credited") is not False: raise AlreadyVoided`) with **no write**, and a
      duplicate `redeem()` returns the replay answer at `:1237-1242` with no money move. Do not
      open a transaction merely to cancel it on an ordinary duplicate.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py`
      Verify: `$PY -m pytest tests/test_gift_card_store.py -q` will be **red** here and that is
      expected — item 8 is its other half; the gate to pass **now** is
      `$PY -m pytest tests/test_gift_card_store.py -q -k
      "holds_no_boto3 or no_float_is_constructed"`, both of which must stay green (they are
      re-run-without-edit), plus `$PY -m pytest tests/test_gift_card_spi_contract.py
      tests/test_gift_card_amounts_and_gst.py -q` unchanged.

- [ ] 8. **`tests/test_gift_card_store.py` — six updates, two retire-and-replace, three rewrites, three re-runs, plus the new helpers (design §5.5).**
      Depends on item 7. Add three **module-level** helpers beside `table`, `issue`, `clock`,
      `digest_of`, `_markers_on`, all importable by item 9:
      * `assert_transaction_items_are_exact_key_updates(store) -> int` exactly as §5.5 specifies —
        read `calls`, **not** `applied`, so a cancelled attempt is still shape-checked; **refuse an
        empty recording first** with the named message; then for every transaction assert
        `TransactItems` non-empty, each item's key set exactly `{"Update"}` (which is what forbids a
        later `Put`/`Delete`/`ConditionCheck` arriving without a design change), a non-empty
        `TableName`, a non-empty `Key`, and no `IndexName`. Return the count.
      * `_is_balance_move(call)` — matches an `update_item` whose `UpdateExpression` contains
        `ADD balancePaise` **or** a `transact_write_items` whose items do. The fragment is a plain
        string in both forms and is untouched by `_marshal`, so one predicate reads both logs.
      * `[REVIEW 2]` `_committer_of(kwargs) -> str` — **defined here, because the design names it
        and the tree has no such symbol.** Signature: takes the recorded
        `transact_write_items` kwargs and returns `"redeem"` when any item's `UpdateExpression`
        contains `ADD balancePaise :neg`, `"void"` when it contains `ADD balancePaise :amount`, and
        **raises `AssertionError`** for a transaction that moves no balance — not a sentinel, so a
        transaction that is neither cannot be silently absorbed into a set comparison. Home:
        `tests/test_gift_card_store.py`, beside the helper above; imported by name in item 9.
      `[REVIEW 3]` **Follow §5.5's numbered six-row caller table, not its "One definition, four
      callers" sentence** — §7, §8 and §15 all defer to the table, and the sentence is a surviving
      stale count. Taking it literally leaves two transaction-driving tests unchecked.
      The six callers, each asserting `seen >= 1` or `seen >= 2` **plus a committer set** and **no
      literal transaction total**: `..._does_not_move_the_balance` (`seen >= 1`, `{"redeem"}`);
      `test_the_settle_and_the_balance_move_are_one_commit` (`>= 1`, `{"redeem"}`);
      `test_the_credit_and_the_credited_flag_are_one_commit` (`>= 2`, `{"redeem","void"}`);
      `test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` (`>= 2`,
      `{"redeem","void"}`); `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once`
      (`>= 2`, `{"redeem","void"}`); and item 9's concurrency test (`>= 2`, `{"redeem"}`).
      Per-test edits:
      * `test_the_balance_floor_is_a_condition_expression_not_a_read_then_write` (`:276-294`) —
        **three** assertions move, not two: find the floor inside the `transact_write_items` card
        item; re-index the read-ordering assertion onto the transaction (the surviving `update_item`
        is now the `balanceAfterPaise` follow-up, so indexing on it asserts the wrong thing about
        the wrong write); and compare `:neg` in its **AttributeValue** form `{"N": "-40000"}` at
        **`:289`** `[NIT 6 — the design says :286, which is `assert len(decrements) == 1`; the
        test spans :276-294, not :274-290]`. That third assertion is checking the marshalling; the
        `^-?[0-9]+$` rule owns the money property.
      * `test_a_second_redeem_..._does_not_move_the_balance` — assert no balance move in **either**
        representation.
      * `test_the_claim_is_written_before_the_balance_moves` — compare the claim `put_item` index
        against the `transact_write_items` index.
      * `test_an_applied_move_marker_does_not_outlive_the_move_it_guards` (`:499`, assertions at
        `:513`/`:519`) — assert the stronger fact: **no** `appliedClaim#`/`appliedVoid#` attribute
        is ever written, so item-size growth is bounded by construction rather than by a cleanup
        step.
      * `test_a_redemption_whose_settle_write_failed_debits_the_balance_exactly_once` (`:428`) —
        **retire and replace** with `test_the_settle_and_the_balance_move_are_one_commit`, which
        asserts **unreachability**: there is no interleaving in which the balance has moved and the
        claim is unsettled. Retiring a test is the step most likely to be mistaken for making the
        build green, so the replacement must assert the stronger property, not nothing.
      * `test_a_void_whose_credited_write_failed_returns_the_balance_exactly_once` (`:731`) —
        **retire and replace** with `test_the_credit_and_the_credited_flag_are_one_commit`, which
        must **additionally** assert that a second `void()` of the same transaction credits
        nothing — that is the rehoused property from the plain-credit test below.
      * `test_a_stalled_redemption_still_debits_once_when_another_purchase_lands_between` (`:470`)
        — **rewrite, same name**, driven by a *settled* claim plus an intervening different
        purchase, which is the post-fix route to that state.
      * `test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` (`:657`) and
        `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once` (`:712`) —
        **rewrite, same names**, aiming the fault at the transaction via
        `arm_failure("transact_write_items", FakeClientError("ProvisionedThroughputExceededException"))`
        and, for the second, `times=2` from item 2(f). A bare throughput `FakeClientError` is **not**
        a cancellation, so `_is_transaction_cancellation` is `False`, `_transact_with_retry`
        re-raises without looping, and the test's own second/third `void()` call **is** the retry.
        Keep each answer identical to today's — that is the check that the rewrite preserved the
        property rather than replacing it.
      * `test_a_plain_credit_is_not_made_idempotent_because_two_top_ups_are_two_events` (`:781`) —
        **loses half its body**: the marker assertion at `:793` **and** the whole five-line
        `once_key="void-abc"` half, which would be a `TypeError` after item 7. Name unchanged. The
        homeless property (*the same logical credit replayed moves the balance once*) is rehoused
        on the void side, as stated above.
      * `test_a_void_latched_before_the_credited_flag_existed_is_never_re_credited` — **re-run
        without edit**; §5.3.1's pre-read decision means both its `AlreadyVoided` and its balance
        assertion hold unchanged.
      * `test_the_store_holds_no_boto3_client_and_reads_no_secret_itself` (`:1152`) and
        `test_no_float_is_constructed_anywhere_on_the_store_money_path` (`:1066`) — **re-run
        without edit and they must stay green.** The second is *affected* (it drives a full
        redeem/void cycle through the new path) and an affected test nobody ran is
        indistinguishable from an unaffected one; it stays green mechanically because neither a
        float **literal** nor `int.__truediv__` calls `builtins.float`.
      * `test_every_dynamodb_access_is_an_exact_key_operation_or_the_status_index_query` (`:1094`)
        — **presence and location only.** Three facts, two predicates, one shared walk: fact one
        (exactly one `transact_write_items` call in the module) uses the gate's existing
        `ast.Attribute` filter at `:1106`; facts two and three (its owning `FunctionDef` is
        `_transact_with_retry`, and `_transact_with_retry` is called from exactly
        `_commit_redemption` and `_commit_void`) need their own predicate
        `isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id ==
        "_transact_with_retry"`, because the existing filter finds only attribute calls; the
        `FunctionDef`-owner walk at `:1119-1124` is shared by all three. Do **not** `ast.unparse`
        the call and look for `TableName`/`Key` — §5.3 assembles the items in separate assignments,
        so that assertion fails against correct code. Leave the gate's runtime tail
        (`store.scan()` raising) exactly as it is; do **not** call the new helper from here —
        that gate drives no transaction and the helper would pass vacuously.
      * **Add one test:** `_marshal` is byte-identical to
        `boto3.dynamodb.types.TypeSerializer().serialize` over the exact value set these
        transactions carry — every amount sign, `0`, `MAX_VALUE_PAISE`, `-MAX_VALUE_PAISE`, both
        booleans, the key and status strings. It lives in `tests/`, where botocore is already a
        dependency, so the module keeps its import-free guarantee and the equivalence is still
        measured.
      * **Add one assertion:** no branch reads `balanceAfterPaise`, so the observation can never
        become an input to a decision (measured: all three sites `:1259`, `:1367`, `:1478` are
        writes).
      `[NIT 7]` **Both fault injectors go with their callers, and that is stated rather than left
      to be discovered.** `_CreditThrottles` (`:631`) is used only at `:675` and `:714`, both
      rewritten to arm the transaction, so it loses **both** callers; `_MarkerWriteFails` (`:394`)
      is used at `:440` and `:745` (both retired) and `:478` (rewritten to be driven by a settled
      claim), so it loses **all three**. Delete both classes. A fault injector with no caller
      misleads the next reader exactly as a constant with no caller does.
      Files: `tests/test_gift_card_store.py`
      Verify: `$PY -m pytest tests/test_gift_card_store.py -q` — all pass. Then confirm no
      literal transaction total survived: `grep -nE 'seen == [0-9]' tests/test_gift_card_store.py`
      is empty, and `grep -c 'assert_transaction_items_are_exact_key_updates'` reports the five
      in-file callers plus the definition.

- [ ] 9. **`tests/test_gift_card_redeem_concurrency.py` — the four concurrent tests (design §5.4).**
      Depends on items 2, 7 and 8. Import `assert_transaction_items_are_exact_key_updates`,
      `_committer_of` and `_is_balance_move` from `tests/test_gift_card_store.py`.
      `_InterleaveAtBalanceMove(FakeTable)` overrides **both** `update_item` **and**
      `transact_write_items` — one per representation — awaiting its latch **before** delegating to
      `super()` in each, so the table lock is never held across a wait. Overriding only
      `update_item` (the pattern the suite's two now-deleted subclasses showed) latches the pre-fix
      representation and silently stops latching anything the moment the fix lands, degrading the
      test into the unsynchronised race it exists to avoid.
      Three `threading.Event`s, no `sleep` anywhere: `claim_written` (set by the fake after A's
      `put_item` on the `GCORDER#` key applies; the **main thread** waits on it and only then
      starts B, so A always wins the claim and the roles are not raced for), `claim_read` (set
      after B's `get_item` returns; A's **first** balance move waits on it — t3 before t4), and
      `a_returned` (set by the **main thread** after `A.join(5)`; B's balance move waits on it —
      t7 after t6, which is what makes the pre-fix double debit certain rather than likely). Main
      sequence exactly: start A → wait `claim_written` → start B → `A.join(5)` → set `a_returned`
      → `B.join(5)` → assert. Assert `not thread.is_alive()` after each join so a deadlock fails as
      a deadlock. Threads named `A`/`B`; the fake picks its latch from
      `threading.current_thread().name`, so the subclass is identical across the fix.
      Test 1, `test_two_concurrent_redeems_for_one_payment_attempt_debit_once`: value **500000**,
      both threads redeem **150000** under one attempt — the face value must exceed twice the
      redemption or the balance floor masks the bug with an unrelated guard. Assert
      `balancePaise == 350000` (not 200000), **two** balance-move entries in `calls` (both tried)
      and **one** in `applied` (one landed), one shared `transactionId`, exactly one `committed`
      and one not, `settled is True`, and no `appliedClaim#` attribute. Both counts are required:
      `calls == 1` would report `2` post-fix and go red on correct code, and "B tried and was
      refused" is a stronger statement than "B did not try".
      Test 2: two concurrent `void()`s of one transaction credit **once**, both counts asserted the
      same way. Test 3: two **different** `paymentAttemptId`s still debit **twice** — the property
      that must not regress. Test 4: §5.3.1's three-valued `credited` — a transaction row with
      **no** `credited` attribute is refused with `AlreadyVoided` and the balance does not move.
      Call the shape helper from test 1 over a recording that includes the **cancelled** attempt —
      the one caller that exercises the attempt-log-not-outcome-log choice.
      Files: `tests/test_gift_card_redeem_concurrency.py`
      Verify: `$PY -m pytest tests/test_gift_card_redeem_concurrency.py -q` — all pass, no test
      exceeding its 5 s joins. Then run it five times in a row
      (`for i in 1 2 3 4 5; do $PY -m pytest tests/test_gift_card_redeem_concurrency.py -q || break; done`)
      to confirm the schedule is forced rather than timed.

- [ ] 10. **`tests/test_gift_cards_iam_and_table.py` — one added assertion.**
      Pin the `GiftCardLedger` (own role, `scripts/provision_gift_cards_roles.py:238`) and
      `GiftCardLedgerNoDelete` (SPI, `:284`) statements' **action sets** to exactly what the store
      needs, so a future widening has to be deliberate. **No provisioner is edited and no IAM
      change is needed**: `TransactWriteItems` is authorized through its items' actions, so two
      `Update` items need `dynamodb:UpdateItem`, which both roles already grant;
      `dynamodb:ConditionCheckItem` is required only for a `ConditionCheck` item and this
      transaction has none. `[NIT 6]` The existing exact-action assertion the design once cited as
      the guard is at **`:295`** (not `:293`) and covers
      `AdvanceGiftCardStageOnAPaymentAttempt` on **PaymentAttemptsTable**, not the ledger — the
      ledger was pinned by nothing, which is why this assertion is being added.
      Files: `tests/test_gift_cards_iam_and_table.py`
      Verify: `$PY -m pytest tests/test_gift_cards_iam_and_table.py -q` — all pass;
      `git -C <worktree> status --short scripts/` shows no provisioner modified.

- [ ] 11. **Triage the affected consumers — re-run, do not pre-edit (design §5.5).**
      Run every file that consumes `gift_card_store` **or** `coupon_fake_dynamo` and apply the
      rule: an assertion about **behaviour** must pass unchanged, and a failure there is a defect
      in the fix rather than a test to update; only an assertion naming the **mechanism** (a
      specific `update_item`, a specific expression fragment) may be rewritten, and each rewrite
      must preserve the property in the same breath. Expected: `test_gift_card_two_leg_finalization.py`
      is the heaviest consumer (52 matching lines) and most of it is behavioural;
      `test_gift_card_spi_contract.py`, `test_gift_card_amounts_and_gst.py` and the three coupon
      files need **no** change — and a surprise in the coupon three is a **defect in the fake**,
      which is the only reason they are listed.
      Files: `tests/test_gift_card_two_leg_finalization.py` (triage only; expect few or no edits)
      Verify: `$PY -m pytest tests/test_gift_card_two_leg_finalization.py
      tests/test_gift_card_spi_contract.py tests/test_gift_card_amounts_and_gst.py
      tests/test_coupon_store.py tests/test_coupon_reconciliation.py
      tests/test_wix_coupons_contract.py tests/test_payment_vocabulary_at_decision_points.py -q` —
      green, and the passed/xfailed counts reconcile against the 301/7 baseline plus whatever this
      change added.

- [ ] 12. **`scripts/demo_coupon_giftcard_sample.py` — the runnable three-leg demonstration (design §4).**
      Depends on items 2, 3, 5, 7. `sys.path` gains `amplify/functions/shared` and `tests`, then
      it imports `WixTransport` from `tests/wix_transport_stub.py` and `FakeTable` from
      `tests/coupon_fake_dynamo.py` — **one stub, two callers**; a private copy inside `scripts/`
      is the drift this task exists to prevent, and nothing in `tests/` ships in a Lambda package.
      `argparse` exactly as §4.2: `--leg`, `--json`, `--no-colour`, `--value-paise` (default
      250050), `--redeem-paise` (150075), `--coupon-money-off-paise` (12345600), `--coupon-code`
      (`WDSAMPLE10`), `--reference-id` (`wd-gc-sample-2026-10-02`). **No `--pepper` flag** — that
      would put a pepper-shaped value on a command line, which `secret-handling.md` forbids and
      `.kiro/hooks/block-inline-secrets.json` refuses. `main(argv)` **returns** its exit code with
      `if __name__ == "__main__": sys.exit(main())` at the bottom, so item 13 can run it in-process.
      Exit `0` all legs matched, `1` a contract assertion failed, `2` a usage error.
      Leg 1 drives `coupons/handler._create` with the same single `_staff` stub and
      `_coupons_table` pointer the harness uses, and passes the `_auth` event so `created_by` is
      `"demo-operator"`. Leg 2 derives its code with `wix_gift_cards.demo_code(reference_id=...)`
      — unkeyed, demo-only — and prints the two-line disclosure from §4.2 so the production
      derivation (`card_code`, keyed, pepper by reference) is named beside it; the replay
      **re-derives** both identifiers rather than reusing them, and the transcript reports **one**
      create call counted off `transport.requests`. Leg 3 runs `gift_card_store` issue → balance →
      redeem → balance in integer paise with the code masked throughout.
      Validation per §4.5, each failure exiting `2`: `--coupon-money-off-paise` must be a multiple
      of 100 (the whole-rupee rule belongs **here and only here** —
      `wix_coupons._rupees` at `:107-117` refuses the rest); `--value-paise` and `--redeem-paise`
      take **any** paise, because the fractional default is exactly what makes leg 2 cross the Wix
      decimal boundary the design calls the strongest argument for the Wix-native model;
      `--coupon-code` goes through `coupon_store.normalise_code` and the demo defines no second
      code rule. `type=int` everywhere; no `float(` in the file (item 6's Group D asserts it by
      AST).
      The renderer omits `Authorization` (already `<redacted>` at capture) and prints
      `Authorization: <redacted — wecare/wix/headless-api-key>`; masks any gift-card code to
      `****` + last four **in both directions**, labelled in a comment as a habit for the day the
      adapter is wired rather than as what makes the demo safe offline; and **refuses to render a
      body it cannot classify** rather than printing it. A **coupon** code prints in full,
      deliberately — it is broadcast marketing material.
      The two final lines are facts that are **enforced**, not observed: `wix_ecom._secrets is
      None` under the §2.2 `boto3` sabotage installed before the first leg, and zero AWS API calls
      via a `before-send` hook on every client that exists in the process
      (`middleware.cognito.meta.events`, `rate_limit.dynamodb.meta.client.meta.events`) raising
      `UnexpectedAwsCall(BaseException)` — **not** an `Exception`, or leg 1's handler would answer
      202 and the demo would print `0` while a call had been attempted and swallowed. Do **not**
      print `boto3 imported = NO`: it is false once the handler is imported, and a false structural
      claim in the one artifact whose purpose is to be trusted is worse than no claim. The demo
      makes **no** payment-state decision and imports no payment vocabulary.
      Files: `scripts/demo_coupon_giftcard_sample.py`
      Verify: `$PY scripts/demo_coupon_giftcard_sample.py --json > /dev/null; echo $?` prints `0`;
      `$PY scripts/demo_coupon_giftcard_sample.py --no-colour` renders the §4.4 shape with
      `3 legs, 0 contract mismatches`; `$PY scripts/demo_coupon_giftcard_sample.py
      --value-paise 100 --redeem-paise 200; echo $?` prints `2`.

- [ ] 13. **`tests/test_demo_coupon_giftcard_sample.py` — the demo's anti-rot enforcer (design §7).**
      Depends on item 12. Load the demo with `importlib.util.spec_from_file_location` — this
      repository's existing pattern for a script under test — install the §2.2 `boto3` sabotage and
      the `_key_cache` seed, call `main(["--json", "--no-colour"])` **in-process**, and assert the
      return value is `0`, that captured stdout parses as JSON and **nothing else was printed**
      (that is `--json`'s contract), that the transcript reports **three legs** and **zero**
      contract mismatches, and that `wix_ecom._secrets is None` **after** the run — so the demo's
      own no-AWS line is corroborated from outside the demo rather than by the demo agreeing with
      itself. A test rather than a new CI step, because the existing `python -m pytest -q` at
      `.github/workflows/route-auth.yml:111` already collects it, it inherits the harness's
      containment, and a failure is a named assertion instead of a scrollback. **No workflow file
      is modified.**
      Files: `tests/test_demo_coupon_giftcard_sample.py`
      Verify: `$PY -m pytest tests/test_demo_coupon_giftcard_sample.py -q` — passes;
      `git -C <worktree> status --short .github/` is empty.

- [ ] 14. **The owner memo — `wix-native-decision-memo.md` (design §6.1).**
      One page, no new analysis, for a reader who will not open the design: coupons are **(B)** and
      why (no idempotency key, no read-by-code, so a lost create response leaves a live Wix coupon
      whose id we cannot recover — our table supplies that recovery, and Wix already does all the
      arithmetic); gift cards are **(A)** and why (server-side `idempotencyKey`, queryable by full
      code, exact decimal-string amounts, `balance` `readOnly`), with the blocker cleared by the
      owner's 2026-10-02 confirmation; **what still has to be true before we delete our backend** —
      the three-condition §0.1 gate, stated in the design's own honest sentence: *a dashboard
      glance proves the product exists; it does not prove the API accepts our key, our shape and
      our fractional-INR amounts on this site, and that is one owner-run call away*; what
      retirement removes (§6.4), including that **nothing exists in AWS to delete**; what is
      already true in both branches (Wix does the arithmetic, we never return a discount figure to
      a browser); and that **Loyalty and Referral are noted and out of scope**, so the memo answers
      that before it is asked.
      Also carry §6.2's owner procedure **by reference only**: the `count` read and the
      create → replay-same-key → query-by-full-code sequence, with the `asm-exec` by-reference
      invocation form. **No credential value, in any field, anywhere.**
      Files: `.agents/tasks/wix-coupon-giftcard-sample-20261002/wix-native-decision-memo.md`
      Verify: `$PY scripts/block_inline_secrets.py` is not applicable to a file, so check by
      inspection plus `grep -nE 'rzp_live_|sk-|AIza|ghp_|xoxb-|AKIA|ASIA|sk_live_|ksk_|BEGIN
      [A-Z ]*PRIVATE KEY' <memo>` returning nothing, and confirm the only credential mentions are
      the **names** `wecare/wix/headless-api-key` and `wecare/wix/giftcard-spi`.

- [ ] 15. **Record the §5 defect's two halves in the same breath, wherever it is reported.**
      Any report of the concurrent double-debit must carry both sentences: it is **HIGH as a source
      defect** — it would silently debit stored value twice and leave a self-consistent ledger —
      **and it never reached a customer**, because no `wecare-gift-cards`, no
      `wecare-wix-giftcard-spi`, no `GiftCardsTable` and no matching route exists in account
      `775261844268` (re-derived 2026-10-02; re-derive again rather than quoting that snapshot).
      Dropping the first understates the defect; dropping the second overstates the incident.
      Files: `.agents/tasks/wix-coupon-giftcard-sample-20261002/wix-native-decision-memo.md` (the
      §5 paragraph), and the final report text
      Verify: by inspection — both halves present in one paragraph, neither separable from the
      other.

- [ ] 16. **The retirement gate — evaluate, then STOP and report. Do not delete.**
      This is the one item whose output is a decision, and it is written as a rule so it cannot be
      resolved by enthusiasm. The owner's locked instruction is to retire our gift-card backend in
      source **only after the demo proves the Wix-native path works against Wix's real API
      contract**, and to **stop and report** if a gap appears. Design §0.1 measures what a stubbed
      demo can and cannot prove, and the answer is decisive:
      | §0.1 condition | Who satisfies it | State after items 1-13 |
      |---|---|---|
      | 1 — the Wix Gift Card app is installed | owner, dashboard | ✅ answered YES 2026-10-02 |
      | 2 — harness and demo green: our shapes match the documented contract, integer paise survive the decimal-string boundary, resolve-before-create consumes one create | this change | ✅ by items 6, 9, 12, 13 |
      | 3 — **one owner-run live verification on the real site** (the `count` read, then create → replay-same-key → query-by-full-code) | **owner only; a live Wix write is a standing refusal here** | ⏳ **OPEN** |
      Condition 2 is what this change can deliver and it is delivered. Condition 3 is the only one
      that can fail for a reason this design cannot anticipate — a missing scope
      (`SCOPE.DC-ECOM-MEGA.MANAGE-ECOM` is broad), a region or plan constraint, a response that
      differs from the published schema — and it is unreachable from here. **So the deletion does
      not happen in this change.** Delete nothing: `gift_card_store.py`, `GiftCardsTable`'s
      provisioners, the two handlers, the deploy-registry entries, the routes and their tests all
      stay. The §5 fix therefore **lands** (items 7-9), which is exactly §5.0's "gate open today"
      row, and it is the defensible state: shipping a known concurrent double-debit on the strength
      of an intention to delete the code later is not available.
      Deliverable instead: a `## Retirement gate — evaluated, NOT cleared` section in the memo
      listing §6.4's inventory verbatim (so the owner can size the decision), the two line items
      the later wiring change **inherits** — (a) the recording rule must be re-derived against a
      **real** clear code before the first live call, because offline every code is a fixture
      placeholder; (b) `card_code`'s return value lives entirely in code this design does not
      author, so the wiring change must state and test that it never reaches a log line, an
      exception message, a staff/admin/reconciliation surface, or clear-text storage — and the
      order of operations: **wire the Wix-native adapter in before deleting our store, never
      after**, so a failed first real call does not leave the product with no gift cards at all.
      Name the exact unblock action in one line: *owner runs §6.2's `count` read and the
      three-step sample-card sequence; a `403`-class refusal is a scope grant, not a negative
      answer.*
      Files: `.agents/tasks/wix-coupon-giftcard-sample-20261002/wix-native-decision-memo.md`
      Verify: `git -C <worktree> status --short` shows **no deletion** of
      `amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py`,
      `amplify/functions/ecommerce/gift-cards/handler.py`,
      `amplify/functions/ecommerce/wix-giftcard-spi/handler.py`, the three gift-card provisioners
      or `tests/test_gift_card_store.py`; and `$PY -m pytest tests/test_gift_card_store.py -q`
      still passes, which is what proves the backend is intact rather than half-removed.

- [ ] 17. **Dispose of the four NITs explicitly, in one place.**
      The design is frozen at revision 8, so a NIT that asks for a design-document edit is
      **dropped with a one-line note** rather than applied to a frozen artifact; a NIT that
      corrects a fact an implementer will act on is **applied in code**, and all four are already
      threaded into the items above. Record the disposition in a short
      `## Review NIT disposition` section so no later reader thinks they were ignored:
      * **NIT 4** (§16's stale "four transaction-driving tests" lacks a superseded annotation) —
        **dropped**, design frozen. Superseded in effect by item 8, which follows §5.5's numbered
        six-row table.
      * **NIT 5** (§8's Modified row dates its own previous count to the wrong revision) —
        **dropped**, design frozen; a dating error in a changelog row changes no code.
      * **NIT 6** (three line citations off by two or three) — **applied**: items 8 and 10 use
        `:289`, `:276-294` and `:295`, all three re-measured in this worktree at `32b632e3`. Both
        substantive claims underneath them were correct.
      * **NIT 7** (`_CreditThrottles` loses both callers, `_MarkerWriteFails` all three, and
        neither fate was stated) — **applied**: item 8 deletes both classes and says so, with the
        call sites mapped to their owning tests.
      Files: `.agents/tasks/wix-coupon-giftcard-sample-20261002/wix-native-decision-memo.md`
      Verify: by inspection — four entries, each marked applied or dropped with its reason.

- [ ] 18. **Final gates, then one commit by explicit path.**
      Run, in this order:
      (a) the design §7 focused set —
      `$PY -m pytest tests/test_wix_coupon_giftcard_sample.py
      tests/test_demo_coupon_giftcard_sample.py tests/test_gift_card_redeem_concurrency.py
      tests/test_gift_card_store.py tests/test_gift_card_two_leg_finalization.py
      tests/test_gift_card_spi_contract.py tests/test_gift_card_amounts_and_gst.py
      tests/test_gift_cards_iam_and_table.py tests/test_wix_coupons_contract.py
      tests/test_coupon_store.py tests/test_coupon_reconciliation.py
      tests/test_payment_vocabulary_at_decision_points.py -q`;
      (b) the demo — `$PY scripts/demo_coupon_giftcard_sample.py --json > /dev/null`;
      (c) the whole suite — `$PY -m pytest -q`, expecting **exactly** the five known baseline
      failures in `tests/test_url_host_routing_rules.py` (4) and
      `tests/test_legacy_redirect_rollback_snapshot.py` (1) and nothing else. Any sixth failure is
      this change's;
      (d) only if any `src/**` file changed — which it should not, since no `.ts`/`.tsx` is in this
      footprint — `npm run build` **before** `npx vitest run`, because vitest depends on the `out/`
      artifact.
      Then commit. The index is shared across sessions, so stage and commit in **one** step and
      bound what the commit can contain:
      `git -C <worktree> status --short` → read it → `git -C <worktree> add <the new files>` →
      `git -C <worktree> commit --only <every path> -F <message file>`. `--only` is not optional:
      it commits exactly the named paths and ignores a pre-dirty index no matter who staged it.
      New files need the `add` first (`--only` rejects an untracked pathspec), and `--only` then
      bounds the commit regardless of what arrives during that window. Do **not** push, rebase onto
      `stack`, or fast-forward anything — the branch is left for owner review.
      Files: none new; the commit message states what landed, that the gift-card backend is
      **intact and not retired**, and that the §5 defect is fixed in source and was never deployed.
      Verify: `git -C <worktree> show --stat HEAD` lists only this change's paths;
      `git -C <worktree> log --oneline -1 stack` is unchanged at `32b632e3`;
      `git -C <worktree> status --short` holds nothing of this change.

---

## Gaps and assumptions, stated rather than left implicit

1. **Condition 3 of the retirement gate is unreachable from here**, so the retirement is prepared
   and not performed (item 16). That is the design's own sequence — demonstrate, then verify live,
   then wire and retire — and it is also the only reading compatible with "no live Wix write".
2. **`FakeTable` is a model of `TransactWriteItems`, and the model is the thing being trusted.**
   The two places it needs care are explicit: the `RLock` supplies the atomicity (without it the
   fake can invent a race the real database does not have, in either direction), and
   `TransactionConflict` must be producible or the retry branch is untested. Keep the fake strict —
   it raises on any item shape or expression form it does not implement — and note that the first
   real exercise of this path is whenever `wecare-gift-cards` is deployed, which has not happened.
3. **`wix_ecom.py` stays read-only.** Every conversion decision rests on its bare `json.dumps`
   (no encoder, so a `Decimal` raises before the request leaves) and `json.loads` (no
   `parse_float`, so a Wix number arrives as a `float`). If it ever gains either, the
   no-numeric-read rule in `wix_coupons.py` becomes removable and item 6's Group B assertions get
   weaker than they should be.
4. **The pepper is the existing `wecare/wix/giftcard-spi:code_pepper`, by reference, never read by
   this module.** One key, two purposes, domain-separated by `CODE_DOMAIN_TAG` on the **message**.
   If the retirement ever deletes that secret, `card_code` loses its pepper — a line item for the
   wiring change, not an afterthought: deleting it breaks every future derivation while leaving
   already-issued cards findable by `codeSuffix`/`id`.
5. **Rotating the pepper changes every derived code.** `idempotency_key` is unkeyed and therefore
   rotation-invariant, which is what stops a post-rotation replay minting a second card. That
   asymmetry is why the two derivations do not share a construction.
6. **`tests/coupon_fake_dynamo.py` is shared by seven test files** (four gift-card, three coupon).
   Item 2 changes it, and item 11 re-runs all seven. A surprise in the coupon three is a defect in
   the fake.
7. **Item 1 can halt the whole plan.** If a verdict-carrying fact has moved, stop at item 1 and
   report; §1's verdict, the §0.1 gate and the memo all move together, and that is a design
   decision outside this plan's authority.
