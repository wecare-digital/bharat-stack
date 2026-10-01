# Checkout verification re-scoped to the deployed bytes — fourth pass

The third-iteration response (`8a48e5f9`) answers all nine findings from the previous pass at the source rather than in prose. The change that matters: `--verify` now downloads the artifact off the `live` alias and scopes the import validation, the reachability closure and the IAM grant report to those bytes, so the two withheld grants (`dynamodb:ConditionCheckItem`, `secretsmanager:GetSecretValue` on `wecare/razorpay/api`) are confirmed unnecessary against production instead of inferred from a local export nobody deployed. Six of the nine prior findings described a check that could not fail; each is now driven against a deliberately broken input, and the source-text assertions that stood in for behaviour were replaced with a `verify()` harness running the real function against stubbed AWS. Nothing was deployed, no IAM changed, and `CHECKOUT_INITIATION_ENABLED` is still absent from the live environment rather than set to `"false"`.

Watch for: the verifier hardening is unpushed, so the branch of record still exits 0 on gate-off-with-readiness-set (confirmed); the live alias runs v2, published by another session from a revision nobody here can identify (confirmed); the new gate-contract tests read the handler from the shared working tree with a skip-on-absence, the pattern this same commit removed from the no-float test (confirmed).

**Verdict**: APPROVED

## High-level view

Scope held. Six commits, nineteen owned paths, zero entries from the DO-NOT-TOUCH list, and `deploy_all_lambdas.py` untouched in all six. One function was created; the only alias this task has ever moved is `wecare-checkout:live`.

The gate is off and nothing became payable, and that now rests on a measurement of production rather than of an export. `CHECKOUT_INITIATION_ENABLED` is absent, both `EXPECTED_*` readiness inputs are empty so `payment_readiness` refuses independently of the flag, `PaymentAttemptsTable` holds 0 items, and the live artifact's 20-module reachable closure contains neither `razorpay_orders` nor any transaction call. Exactly one secret-reading module is reachable — `wix_ecom.py` — and `CheckoutLeastPrivilege` grants exactly that one secret.

The brief's literal deliverable was not observed and cannot be. `require_customer` runs before the body is parsed, and inside `_create` the readiness evaluation precedes the gate, so an external probe gets 401 and an authenticated one would get 409. Satisfying the literal string means weakening authentication or minting a customer token; neither is authorised. The substitution is now evidenced in an artifact outside the reporting document, which states `ownerAcceptance: NOT EVIDENCED` itself — the honest answer to the previous pass's complaint about provenance, and not a manufactured sign-off. Accepting it remains an owner decision.

Two facts about production moved underneath this work. `wecare-checkout:live` is v2, published by a concurrent session from an unidentified revision, and `wecare-razorpay-webhook` is v46 where the brief named v45. Both are attributed with CloudTrail timings and with the structural argument that the provisioner holds zero references to the other function and only ran `--verify`. Rolling the webhook alias back would revert another session's deployed payment fix, so recording the drift is the correct action.

What is not of record is the verifier hardening itself. `origin/stack` carries the IAM narrowing that blocked the previous pass, verified by reading the branch — but not the live-artifact scoping, the derived environment key list, or the failure on gate-off-with-readiness-set. A `--verify` run from the remote today reports success in the one state the evidence singles out as dangerous.

Two low-severity leftovers in the new code: `_package_of` has an `if/else` whose branches are identical, and the guard keeping the presigned artifact URL out of the output inspects `print` calls only while its docstring claims arguments and logging expressions too.

<details>
<summary>Issues (7)</summary>

1. **Verifier hardening unpushed** — `8a48e5f9` is local-only; `origin/stack`'s `--verify` omits `WIX_SITE_ID`, exits 0 on readiness-set-with-gate-off, and scopes the grant report to a local export. Push it so the gate an operator runs before enabling initiation is the hardened one.
2. **Gate-contract tests read the shared working tree** — `tests/test_checkout_gate_contract.py` parses the handler from `ROOT` and `pytest.skip`s when the file is absent. Parametrise over the `committed` fixture this commit added elsewhere, and assert presence instead of skipping.
3. **Live v2 provenance unknown** — the alias runs a 113-file package whose `CodeSha256` matches nothing reproducible here. The safety verdicts were re-derived against those bytes, but the source revision is unrecorded. The publishing session should record it; re-verify immediately before the gate is enabled.
4. **`wecare-razorpay-webhook` is v46, not v45** — the brief's literal condition is no longer satisfiable and must not be re-satisfied by rolling back another session's payment fix. No action for this task.
5. **`PAYMENT_INITIATION_DISABLED` never observed live** — owner acceptance of the test-plus-structural-pinning substitution is `NOT EVIDENCED`. Owner to accept explicitly, or authorise a customer token plus readiness values for a live observation.
6. **`_package_of` no-op ternary** — `parts[:-1] if parts[-1] != "__init__.py" else parts[:-1]`. Collapse to `parts[:-1]` and keep the docstring, before someone "fixes" the dead branch.
7. **Presigned-URL guard narrower than its claim** — `test_the_presigned_download_url_is_never_printed_or_stored` inspects `print` calls and the `except Exception` return only; and `live_members` does not check that the location is `https://` before `urlopen`. Widen the walk, and add the scheme check the `# noqa: S310` suppression acknowledges.

</details>

<details>
<summary>Details</summary>

## The grant report describes what is running

```python
described = lam().get_function(FunctionName=FUNCTION_NAME, Qualifier=qualifier)
sha = described.get("Configuration", {}).get("CodeSha256", "")
location = (described.get("Code") or {}).get("Location")
...
fetched = package_sha(payload)
if sha and fetched != sha:
    return None, sha, f"live code NOT MEASURED: downloaded bytes hash to {fetched}, ..."
```

The seam that makes this possible is that `deploy_all_lambdas.validate` reasons purely over a `members` dict and never reads the `Spec` it is handed, so the checker that gates a build can be pointed at bytes retrieved from production. `validate_members` passes `frozenset()` for layer-provided modules, which errs strict: a module resolvable only via a layer reports as an error, never as a false pass.

`report_required_grants(deployed)` is the only grant report now, and `deployed is None` stays distinct from "measured, needs nothing" — an unreadable artifact appends a problem and reaches the report as `None`, which answers `NOT JUDGED`. The local build survives as a comparison only, printed as a member-set difference and never allowed to carry a verdict.

## The closure can see its own relative edges

`import_closure` did `if node.level or not node.module: continue`, discarding every `from .x import y` — 35 edges in `lambda_utils`, one of them inside this closure (`template_ttl.py` → `whatsapp_types.py`), so the measured set was 19 where 20 are reachable. The verdict was unchanged because the missed module opens no transaction, but the failure direction is a false "grant not required" with a green verifier.

The replacement arithmetic is correct, including the `__init__.py` case. `_package_of` expresses it as a ternary whose two branches are the same expression:

```python
parts = arcname.split("/")
return parts[:-1] if parts[-1] != "__init__.py" else parts[:-1]
```

Both arms are right, because a package's `__init__.py` has that package as its containing directory. The hazard is a future reader seeing an `if/else` that must mean something and "correcting" the dead branch to `parts[:-2]`. `test_relative_import_resolution_cases` pins the `__init__.py` result, so such an edit fails rather than shipping, which bounds this to readability.

## The new test file does not follow the discipline the same commit established

Three prior findings were one defect in three costumes: the lazy-secret walk saw three node types in two files, the no-float test skipped modules absent from the package, and both property tests ran against the working-tree build alone. All three were fixed by widening the walk, asserting presence before parsing, and parametrising over a `committed` fixture built from `git archive HEAD`.

The file added in this commit does neither of the last two. `tests/test_checkout_gate_contract.py` resolves the handler as `ROOT / "amplify" / "functions" / "ecommerce" / "checkout" / "handler.py"` and skips when it is absent:

```python
if not HANDLER.is_file():
    pytest.skip("checkout handler not present in this checkout")
```

That is the shape the no-float fix explicitly rejected — "a money module that is not in the package is the more serious defect, not the excuse to skip the check" — applied to a more load-bearing file. The handler is not on this task's owned paths, so it is the file most likely to be changed by another session, and these five assertions are the pinning mechanism for the substituted deliverable.

Today the risk is nil and corroborated: the handler is clean, identical at HEAD and `origin/stack`, and its line numbers match the live-measured snapshot exactly (`require_customer` 229, `_body` 233, `create_checkout` 259, `allocate_payment_reference` 290, `put_item` 312, gate 323). Ran the file as a spot-check — 5 passed.

## Where "the gate is off" stops meaning "nothing happens"

The gate is the last check in `_create`, and the recorded 0-before / 0-after on `PaymentAttemptsTable` holds because `require_customer` refuses at the door, not because the gate short-circuits:

```
229  require_customer          <- refuses every probe today
259  wix_ecom.create_checkout  <- a LIVE Wix write
277  payment_readiness         <- refuses behind it today, both EXPECTED_* empty
290  allocate_payment_reference   reserves PAYREF#
312  put_item on PaymentAttemptsTable
323  if not INITIATION_ENABLED <- the gate, last
```

So the moment an owner supplies both readiness values with the flag still off, every authenticated `action=create` performs a live Wix write and writes an attempt row before refusing. `--verify` now exits 1 on that combination instead of printing it, and `test_readiness_set_with_the_gate_on_is_still_a_problem` confirms neither condition masks the other.

Handler ordering is pre-existing code this task does not own, so it was measured and pinned rather than changed. `test_no_new_side_effect_creeps_in_before_the_gate` is a subset assertion deliberately: moving the gate earlier stays green, a new outbound call appearing ahead of it fails.

## The verifier that catches that is not on the remote

`origin/stack`'s `scripts/provision_checkout.py` carries `route_statement_id`, a per-route `source_arn` and `live_policy_statements` in `verify()` — read off the branch, which closes the previous pass's blocking finding. Three hardenings from this commit are not there: the live-artifact scoping, the environment key list derived from `expected_environment()`, and the failure on gate-off-with-readiness-set.

This differs materially from the previous pass, where the branch of record would have *re-widened* an IAM grant and reported success. Nothing on the remote mutates anything wrongly; it verifies less. But `--verify` is what an operator runs before enabling initiation, so the remote copy would pass the state where inertness ends, and would accept a wrong `WIX_SITE_ID`.

## Production moved, and both moves are attributed rather than claimed

The live alias is v2, `CodeSha256 1Ho3NbcbR3mlX8n3UBVth0wSSnBqh5OXPb1r1XETMHM=`, matching none of the three packages reproducible from here. Every safety property was re-measured against it by qualifier — flag absent, both `EXPECTED_*` empty, role unchanged, python3.12, both per-route invoke statements with exact ARNs, both routes answering the handler's 401, table at 0 items — and this iteration added the package-derived half. The load-bearing probe is the handler's own 401 JSON rather than API Gateway's `500 {"message":"Internal Server Error"}`, which is what proves the alias-level resource policy survived the version move.

What stays unknown is which revision v2 is. For a payment-path function that is a real chain-of-custody gap; it is also not this coder's to close, and the closure measurement means the IAM verdicts describe production regardless.

`wecare-razorpay-webhook` is v46 against the brief's v45, evidenced three ways: CloudTrail shows five functions' code replaced in the window and none is `wecare-checkout`; the provisioner contains zero occurrences of `razorpay-webhook` and exactly one `publish_version`, keyed on `FUNCTION_NAME`; and the only invocation this iteration was `--verify`, which returns before reaching any `ensure_*`. The shared IAM user cannot discriminate sessions and the document says so. The condition's purpose — that this task moves no existing alias — holds.

## Secrets, money and IAM

Checked and clean: no `get_secret_value` or `batch_get_secret_value` call in the provisioner, the three test files or the IaC, the only occurrences being inside the detector that forbids them; no `float(` call or float literal in `money.py`, `checkout_pricing.py`, `wix_ecom.py` or the handler; no raw `'captured'` literal in the handler, `website_checkout.py` or `razorpay_orders.py`; `CheckoutLeastPrivilege` carrying three Sids with explicit resource ARNs and no `Resource: "*"`; `wecare-digital-lambda-role` appearing in the provisioner exactly once, in a comment explaining why it is not touched; and the IaC declaring two per-route `AWS::Lambda::Permission` resources, with `/*/*` surviving only in a comment recording what it replaced.

One handling gap in the new network code. `get_function` returns a presigned URL carrying an `X-Amz-Signature`, which is credential-shaped material. It is fetched in-process, never printed, and kept out of the failure message, which uses `type(exc).__name__`; the module has zero logger references, so there is no logging expression to leak through today. The guard test, though, inspects `print` calls and the `except Exception` return region while its docstring claims "a log line, an argument or any logging expression" — so adding a logger would not be caught. And `live_members` calls `urllib.request.urlopen(location)` with `# noqa: S310` suppressing the lint that exists for exactly this, without checking the scheme first. Both are cheap to close and neither is exploitable from outside the account.

</details>

<details>
<summary>Files changed in this pass (8a48e5f9)</summary>

| Path | Change |
|---|---|
| `scripts/provision_checkout.py` | `live_members` + `validate_members` so verdicts describe deployed bytes; `resolve_relative_import`; env key list derived from `expected_environment()`; readiness-set-with-gate-off now fails |
| `tests/test_provision_checkout_contract.py` | +16 — relative-import closure, live-artifact scoping, presigned URL never printed, and a `verify()` harness driving the real function against stubbed AWS |
| `tests/test_checkout_package_completeness.py` | two property tests parametrised over `committed`; lazy-secret walk widened to every import-time statement in every module; no-float asserts presence first |
| `tests/test_checkout_gate_contract.py` | new — 5 assertions pinning why the literal probe is unreachable and failing on a new side effect ahead of the gate |
| `docs/execution/snapshots/checkout-live-closure-20261001.json` | the deployed artifact measured: 113 files, 0 errors, 20-module closure, IAM verdict re-derived |
| `docs/execution/snapshots/checkout-gate-ordering-20261001.json` | the substitution evidenced outside the reporting document, with `ownerAcceptance: NOT EVIDENCED` |
| `docs/execution/checkout-deployment-20261001.md` | third-iteration response; v45→v46 and v1→v2 drift recorded |

Full work spans `13c9f7a2`, `4d1b396f`, `ad3bf0a0`, `643a86e0`, `23f6ebae`, `8a48e5f9` — 19 paths, none from the DO-NOT-TOUCH list.

</details>
