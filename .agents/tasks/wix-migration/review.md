# Wix Cart V2 gate returned to opt-in, and cart identity returned to `customer_cart`

Second review pass. Commit `089ba325` answers the four actionable findings from the pass-1 review of `9bf0b1f2` and `8f2cc092`: the gate is an opt-in again, the owned address is resolved before any call that can write to Wix, the checkout path resolves the customer's existing cart through `customer_cart` instead of minting one per attempt, and `WIX_ECOM_CART` now carries one account of its own `configured` value instead of two contradictory ones. Each fix is pinned by a test that asserts the property rather than the status code — the address test measures `wix.calls == []`, the reuse test counts `POST /ecom/v2/carts` across two attempts, and the gate tests fail the Wix stub if it is ever reached. Three of the four fixes undo something the previous commit had recorded as finished, and the commit message and the `vendorVersions.ts` comment both say so rather than quietly reverting.

**Watch for:** `LOAD_OWNED_ADDRESS` is still `None` in production and assigned only in tests, so an operator who sets `WIX_CART_V2_ENABLED=true` gets a checkout that answers 409 on every request — harmless today because the gate is off and the gap is recorded in three places, but there is no config-time refusal the way `meta_version` refuses an incoherent Graph config (confirmed); the new saved-cart comparison reads `lineItems[].source.catalogReference` and `quantityInfo.requestedQuantity` out of a live cart GET, so a shape mismatch would refuse every returning customer's cart rather than mis-price it, which is the safe direction but belongs in the one authorized live Calculate Cart that is already the deploy gate (likely).

**Verdict**: APPROVED

## High-level view

The gate is opt-in again, and the fix kept what was worth keeping from the inversion. `is_enabled()` returns `True` only when `WIX_CART_V2_ENABLED` is truthy, with `WIX_CART_V2_DISABLED` retained as an override *on top of* the opt-in rather than as a replacement for it, so the one-environment-variable rollback the inversion was reaching for still exists once the opt-in is deployed. Both keys are absent from `config/lambda-env-manifest.json`, so the live answer is `False` on all 65 functions, and the decision stays in one shared function that the cart route and the checkout handler both call.

Ordering in `_v2_snapshot` is now load-bearing and labelled as such. The owned address is read before `CartV2` is even constructed, so a request that cannot be priced is refused before it leaves anything behind. That removes the one-abandoned-cart-per-attempt leak the previous revision would have shipped.

Cart identity moved back to the adapter that owns it. `CustomerCart` gains `resolve()` (read-only, raises `CartBusy` on a locked row, treats an expired row as absent) and `ensure()` returning `(cart_id, created)`, with creation routed through the existing `execute` so the lock protocol, the duplicate-request fingerprint and the persistence stay in one place. A reused cart that does not hold the requested basket is refused rather than priced, and the comparison deliberately uses `requestedQuantity` so an out-of-stock reduction still surfaces as `QUANTITY_REDUCED` instead of "your cart changed". Two concurrent first attempts cannot both create: the conditional put in `execute` precedes the Wix call, so the loser raises `CartBusy` without touching Wix.

The version row is honest again. `configured` reads `V1` because V1 is what serves, `drift` moves to `lag-allowed-with-reason` with an `upgradeBlockedReason` and `lagExpiresOn: 2026-12-31`, and the two open items are named as what they are — six convention-derived request shapes unverified against a live call, and the unwired address read, which the doc calls an owner decision rather than something inventable here.

What remains open is the address seam. It is recorded in the handler docstring, in `upgradeBlockedReason`, and in §10 of the migration doc, but nothing refuses the combination of an enabled gate and an unwired loader, so the failure would be discovered by customers rather than at initialisation.

<details>
<summary>Issues (4)</summary>

1. **Enabled gate plus unwired address loader has no config-time refusal** — `LOAD_OWNED_ADDRESS` is `None` in production and set only by tests, so `WIX_CART_V2_ENABLED=true` yields 409 `DELIVERY_DETAILS_REQUIRED` on every checkout. Non-blocking (the gate is off and the gap is documented in three places), but `is_enabled()` or module init should refuse the incoherent combination the way `meta_version._resolve` refuses a disagreeing version, so the trap cannot be stepped into by an env change alone.
2. **Saved-cart comparison depends on an unverified live response shape** — `_require_same_basket` reads `lineItems[].source.catalogReference` and `quantityInfo.requestedQuantity` from a live cart GET. If the live nesting differs, every key collapses to `("", "")`, every reused cart mismatches, and returning customers get 409 `CART_NOT_PAYABLE` with only the `checkout_cart_basket_mismatch` log to explain it. Add the cart GET line-item shape to the one authorized live Calculate Cart that is already the deploy gate.
3. **Basket mismatch is indistinguishable from other contract violations at the client** — it raises the generic `cart_v2.CartContractError`, so the response is 409 `CART_NOT_PAYABLE` / "Please review your cart and try again", the same answer given for blocking violations and unsupported catalog items. Raise a distinct exception so the client can tell the customer their cart changed rather than that it cannot be priced.
4. **"One purchase, one cart" holds only within `CART_LIFETIME`** — `resolve()` treats an expired row as absent and `execute("create")` drops the old `wixCartId` without carrying it forward, so a checkout after expiry creates a fresh Wix cart and leaves the previous one on the live site. The underlying behaviour predates this commit; what is new is `ensure`'s docstring stating the guarantee without its time bound. Either bound the claim or reconcile the expired cart id.

</details>

<details>
<summary>Details</summary>

### The gate, and what survived the revert

```python
if str(environ.get(DISABLE_KEY, "")).strip().lower() in _TRUTHY:
    return False
return str(environ.get(ENABLE_KEY, "")).strip().lower() in _TRUTHY
```

`grep -o "WIX_CART_V2[A-Z_]*" config/lambda-env-manifest.json` returns nothing, so both keys are absent fleet-wide and the live answer is `False`. The parametrised tests cover `"maybe"` as well as `"false"/"0"/"no"/"off"/""` on the opt-in, and assert the disable key still wins over a deployed `WIX_CART_V2_ENABLED=true`, which is the property that makes the kill switch a real lever rather than a leftover. The revert kept `DISABLE_KEY` rather than deleting it to look clean: the rollback argument behind the inversion was sound on its own terms, and an override preserves it without letting absence mean on.

`test_checkout_handler.py` now clears both keys instead of setting `WIX_CART_V2_DISABLED=true`, so the V1 test file reproduces the deployed configuration rather than pinning a gate — a V1 suite that has to set an env var to see V1 is measuring something other than production.

### Ordering, and the test that measures an absence

```python
loader = LOAD_OWNED_ADDRESS
owned = loader(identity.customer_id) if callable(loader) else None
if not owned:
    raise purchase_intent.DeliveryDetailsRequired("no owned delivery address on file")
adapter = cart_v2.CartV2(_wix_request)
```

The adapter is not constructed until the address is known, so there is no path from a missing address to a Wix write. `assert wix.calls == []` is the assertion that keeps it that way; the previous revision passed a status-code-only version of the same test while leaking a cart per attempt.

The seam itself is unchanged: `grep -rn "LOAD_OWNED_ADDRESS"` finds one assignment at module scope (`None`) and three in `tests/test_checkout_cart_v2_authority.py`. §10 of the migration doc states plainly that wiring it needs a customer-profile source, an IAM grant and an env key, and that the source is a product decision nobody has made — which is the right call rather than inventing one, since the delivery address sets the India place of supply and a fabricated one yields the wrong CGST/SGST-versus-IGST split against GSTIN `19AAFFW7196L1Z8`.

What is missing is a refusal. `is_enabled()` answers `True` on the env var alone, and the 409 then arrives per request. This repo already has the pattern for the opposite behaviour: `meta_version._resolve` raises `MetaVersionError` at import when `META_API_VERSION` and `META_GRAPH_BASE` disagree, deliberately declining to pick a winner, so an incoherent configuration fails at initialisation instead of at the first customer. The gate deserves the same treatment given that enabling it is explicitly an operator action.

### Cart identity: resolve, then generate

`ensure` is the whole fix, and routing creation through `execute` rather than straight at the adapter is what makes it safe:

```python
cart_id = self.resolve(identity)
if cart_id is not None:
    return cart_id, False
self.execute(identity, {"action": "create", "requestId": request_id or str(uuid4()),
                        "items": [dict(item) for item in items]})
```

`execute` claims the row with a conditional put *before* calling Wix, so two concurrent first attempts cannot both create a cart — the loser raises `CartBusy` with no Wix call, and `_create` answers 409 `CART_RECONCILIATION_REQUIRED`, the vocabulary `/wix-store/cart` already uses. `CartMissing` subclasses `ValueError` and lands in the existing `except ValueError` as 409 `AMOUNT_NOT_SETTLED`, a blunt message for "created but not persisted" but one that fails closed.

`_require_same_basket` is the part that needed judgement, and the reasoning is recorded where it will be read:

```python
quantity = quantities.get("requestedQuantity")
if quantity is None:
    quantity = quantities.get("confirmedQuantity")
```

Comparing on `requestedQuantity` is what keeps an out-of-stock reduction reporting as `QUANTITY_REDUCED` rather than as a basket mismatch, since Wix reduces `confirmedQuantity` to available stock and `calculate()` is the thing that refuses that. The fallback to `confirmedQuantity` is a tolerance rather than a hole: it compares the only number present, and `calculate()` still refuses the cart later if the two disagree. The `int()` coercion cannot truncate a float quantity because `wix_ecom.normalized_catalog_items` enforces `type(quantity) is int` and the 1..100000 range upstream of `_v2_catalog_items`.

Both halves of the comparison read the same nesting `cart_v2.calculate` already reads, so no new unverified shape was introduced — but a shape mismatch now has a second consequence it did not have before. `calculate` reading an unexpected nesting raises `CartContractError("unsupported or unavailable catalog item")`; `_require_same_basket` reading it produces `{("", ""): n}` on the saved side, mismatches unconditionally, and refuses every reused cart. Fail-closed in both cases, and the right direction, but it turns one unverified shape into a per-returning-customer refusal, which is worth folding into the live verification already listed as the deploy gate.

The expiry path deserves naming. `resolve()` returns `None` on `expiresAt <= now`, and `execute("create")` only carries `wixCartId` forward `if active`, so the previous Wix cart is dropped rather than reused or completed. That mechanism predates this commit and belongs to the cart route, so it is not a regression; what is new is `ensure`'s "One purchase has one cart" claim, which holds within `CART_LIFETIME` and not across it.

### The version row stopped contradicting itself

The stale `configured: 'V1'` paragraph and its `configured: 'V2'` replacement are now one paragraph reading `V1`, with the inversion recorded as a reverted revision and the reason kept: with neither key set anywhere, "default on" did not mean anyone had chosen V2.

`drift` moving from `must-be-latest` to `lag-allowed-with-reason` is not a quiet relaxation of the version gate. `WIX_ECOM_CART` is a new row split out of the old `WIX_ECOM` entry, which was `configured: 'V1'` against a `verifiedLatest` of V1 and therefore passed `must-be-latest` trivially. The newly discovered fact is that a V2 exists, so with `configured: 'V1'` and `verifiedLatest: 'V2'` the strict setting would fail on code that is in fact migrated. `lag-allowed-with-reason` is the schema's own mechanism for that, it requires `upgradeBlockedReason`, and `lagExpiresOn: 2026-12-31` sits well inside the 2027-02-01 removal of Cart and Checkout V1 so the justification cannot outlive the thing it waits on. `config/vendor-versions.json` and `docs/compatibility.md` were brought back to `V1` with it.

### Gate checks on this commit

No added line matches `get-secret-value`, `get_secret_value`, `batch-get-secret-value`, `batch_get_secret_value`, `secretsmanager`, or any issuer-shaped prefix (`rzp_live`, `AKIA`/`ASIA`, `sk-`, `AIza`, `ghp_`, `xoxb-`, `sk_live_`, PEM headers). The one new log expression emits `savedLines` and `requestedLines` counts only. `_wix_request` still delegates to the existing `wix_ecom` authenticated client, so Cart V2 acquires no second credential path and nothing is read at import.

No added Python line contains `float(`, `round(`, `/ 100.0` or `* 100.0`; the only decimal in the diff is a test duration in a doc table. No raw `'captured'` or `"captured"` literal appears anywhere in the commit.

`wix_ecom.py` is absent from all three commits and still exports `create_checkout`, `get_checkout`, `authoritative_total_paise`, `checkout_currency` and `line_item_summary`, with the V1 branch exercised by a test that clears both gate keys. Nothing matching `/stores/v3`, `/site-media/v1` or `/members/v1` is added or removed. `meta_version.py` and `whatsapp_types.py` are untouched by this commit, and at HEAD `_VERSION_RE` is unchanged, `_BASE_RE` is still anchored at both ends, `_resolve` still raises on a version disagreement, and the two dead `whatsapp_types` constants are still gone.

No deploy, version publish or alias move appears, and nothing Cognito-, WAF-, Route 53- or DNS-related. `config/lambda-env-manifest.json` is correctly left alone: it records live Lambda environment state, and neither gate key is set live. The reflog shows three ordinary `commit:` entries with no amend, rebase, reset or force push. All 12 files in the commit are in scope, and the untracked `ecommerce/finalization.py` and `ecommerce/initiation.py` belonging to another session are still untracked, so no broad stage swept them in.

### Test coverage

The four fixes each gained a test that measures the property: `resolve` finding nothing without calling Wix, `ensure` creating once then reusing, a locked row raising `CartBusy`, an expired row reading as absent, cross-customer refusal, the route returning 503 with both keys cleared and the Wix stub failing the test if reached, the disable key beating a deployed opt-in, a repeated checkout producing exactly one `POST /ecom/v2/carts`, and a mismatched basket answering 409 while reserving no `PAYREF#` row.

Not tested: any live Wix round trip, which remains the deploy gate for the six convention-derived request shapes and now also for the cart GET line-item nesting that `_require_same_basket` depends on; the `LOAD_OWNED_ADDRESS` seam in a wired state, since production never assigns it; reconciliation of a Wix cart abandoned at expiry, which has no implementation. The recorded 6187 passed / 1 skipped, `npm run typecheck` exit 0 and `check-versions.ts` exit 0 were not re-run, per this review's instructions.

</details>

<details>
<summary>File map</summary>

Commit `089ba325`, 12 files, +407/-140. Pass-1 commits `9bf0b1f2` and `8f2cc092` were reviewed previously.

- `amplify/functions/shared/lambda_utils/ecommerce/cart_v2.py` — `is_enabled` back to opt-in, `DISABLE_KEY` retained as an override
- `amplify/functions/shared/lambda_utils/ecommerce/customer_cart.py` — `resolve()` and `ensure()` added; creation routed through `execute`
- `amplify/functions/ecommerce/checkout/handler.py` — address resolved before the adapter is built, cart resolved through `customer_cart`, `_require_same_basket`, `CartBusy` → 409 `CART_RECONCILIATION_REQUIRED`
- `amplify/functions/ecommerce/wix-store/handler.py` — gate comment and route behaviour follow the opt-in
- `packages/config/vendorVersions.ts`, `config/vendor-versions.json`, `docs/compatibility.md` — `WIX_ECOM_CART` back to `configured: 'V1'`, `lag-allowed-with-reason` with `upgradeBlockedReason` and `lagExpiresOn`
- `docs/execution/wix-cart-v2-migration-20261001.md` — §10 records both open items and the measured counts
- `tests/test_cart_v2.py`, `tests/test_checkout_cart_v2_authority.py`, `tests/test_checkout_handler.py`, `tests/test_wix_cart_v2_delivery.py` — gate, ordering and reuse properties

Full diff: `git show 089ba325`

</details>
