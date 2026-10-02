# Retire one Razorpay merchant account from current source, keep the other

Iteration 2 of the stale-account purge. Iteration 1 was rejected because the purge was absent from the reviewed tree — `57f5b505` and its full revert `e61a49c4` cancelled exactly — so local `stack` still carried `[retired Razorpay account]` in deployed Lambda source, both webhook fixtures, the readiness module, the spec, the dashboard component, and `docs/compatibility.md`, where the retired account was still described as *"strong — this is the account that talks to us"*. Commit `6e1a4178` lands the purge by adopting `origin/stack`'s byte-identical content for nine authorized paths rather than merging, because a plain merge is blocked by a cross-session dirty file. All eight blocking checks pass: every non-Class-C occurrence of both retired identifiers is gone except one declined cross-session seam, Class C immutable history is byte-unchanged in this commit, the money-safety mismatch test was kept with a synthetic fixture, the deep link was correctly left alone, the partner-onboarding fallback was removed with a proving test, and no credential value appears anywhere.

Watch for: (1) `.kiro/steering/META-BETA-REQUEST-EMAIL.md:49,51` still names the retired merchant account in a draft email to Meta — **confirmed**, and declining to fix it is correct under the multi-session rule, but the hazard is real and the unblock is a merge, not an edit. (2) `origin/stack` — the tree the orchestrator is told to merge — **rewrites six Class C immutable-history files**, including a measured dedup key in `phase-04d-payment-audit.md`; **confirmed**, and nobody has flagged it. (3) The live Lambda environment half remains unverified from source. (4) Two fixtures and one test comment now overclaim provenance after the mechanical substitution.

**Verdict**: APPROVED

## High-level view

The landing method is the interesting design decision. `git merge origin/stack` fails because `origin/stack` rewrites `.kiro/steering/META-BETA-REQUEST-EMAIL.md` while another session holds that file modified-unstaged, and every way around it (stash, reset, committing another session's work) is prohibited here. So the coder used `git checkout origin/stack -- <9 paths>` to adopt byte-identical content. Byte-identity is load-bearing rather than incidental: it is what made iteration 1's revert necessary (two independent rewrites of the same prose turned the merge into eight manual conflict resolutions) and what guarantees the orchestrator's eventual merge auto-resolves. Verified independently — `git diff origin/stack HEAD` over the nine paths is empty, and `git merge-tree --write-tree origin/stack HEAD` returns a bare tree oid with no conflict section.

The surviving seam is the one incomplete target. `META-BETA-REQUEST-EMAIL.md` is a record of emails sent to Meta, and lines 49 and 51 list the retired account as the Razorpay merchant for two payment configurations. An owner reusing that steering file would name a retired merchant account to Meta. The dirty hunk belongs to a different region of the file (an editor's note at lines 6-23 about MCC and PayU), so the merge resolves both edits without conflict once the other session commits — confirmed by reading both diffs. Declining is correct: committing the working-tree version of that path would sweep eighteen lines of another session's work, which is exactly the failure rule 3b exists to prevent.

The Class C immutability check passes for this commit and fails for the tree it is told to merge with. `origin/stack` substitutes the placeholder into `phase-04d-payment-audit.md`, `checkout-consolidation-findings-20261001.md`, `deep-audit-20261001b.md`, `phase-a-plan.md` and `section68-current-state-audit-20261001.md`. One of those replaces the literal measured dedup key `[retired Razorpay account]:payment.downtime.started:1790100905`, so an audit record of a measurement no longer contains the thing measured. The same repository already applies the correct principle in the seam file itself — *"rewriting a sent email would falsify the record"*. This is a decision for the orchestrator before merging, not a defect in `6e1a4178`.

Class B behaviour is untouched: only the `payment_readiness.py` module docstring changed, the authoritative constant is still `acc_TTFSyolquKEZEy`, and the RETIRED / AUTHORITATIVE distinction plus the past-tense correction narrative both survive. The brief asked for the literal retired id to survive as the thing-being-corrected and it does not; that deviation was accepted in iteration 1 on the strength of the owner's verbatim *"remove old from everywhere"*, and the coder recorded it explicitly rather than letting a later reader read the brief as unmet.

The partner-onboarding fallback removal is sound from source alone, and I checked the function rather than taking the argument on trust. `wecare/razorpay-webhook` holds exactly one field, the loop returns only when `key_id` and `key_secret` are both non-empty, so the second iteration could never satisfy the return and always fell through to the same empty tuple. Behaviour is unchanged and the new test pins it on both the success and the failure path.

Three provenance claims are now slightly false after the mechanical substitution. `tests/test_payment_status.py` still labels its fixtures *"The real live payload, copied from a RazorpayWebhookLogTable row"* while `account_id` is synthetic; `tests/test_payment_readiness.py:23` reads *"the previously-assumed `acc_RETIRED_FIXTURE` was the stale env value"*, which attributes a historical role to a string that never existed; and `docs/compatibility.md:87` plus `payment_readiness.py:47` still say live env *"says"* the retired VPA in present framing, which is stale if live v60 carries the retained pair. The coder recorded the third deliberately and deferred it to avoid diverging from `origin/stack`. None affects an assertion or a routing decision.

<details>
<summary>Issues (9)</summary>

1. **Retired MID survives in the Meta beta-request steering file** (confirmed, non-blocking) — `.kiro/steering/META-BETA-REQUEST-EMAIL.md:49,51` still names `[retired Razorpay account]` as the Razorpay merchant for two payment configurations in a draft email to Meta. Declining is correct (another session holds the file dirty); unblock by merging `origin/stack` after that session commits, and do not let the two surviving hits read as a missed target.
2. **`origin/stack` rewrites six Class C immutable-history files** (confirmed, non-blocking here, decide before merging) — the prescribed merge imports placeholder substitutions into `phase-04d-payment-audit.md`, `checkout-consolidation-findings-20261001.md`, `deep-audit-20261001b.md`, `phase-a-plan.md` and `section68-current-state-audit-20261001.md`, including a measured dedup key. Decide explicitly whether audit-trail rewriting is accepted, rather than inheriting it silently.
3. **Live Lambda environment unverified** (confirmed, carried from iteration 1) — `origin/stack`'s doc claims `wecare-whatsapp-business-api:live` is at v60 with both retained values, but this is a source-only change and nothing here measured AWS. Confirm with `get-alias` and `get-function-configuration` on the alias before treating the live surface as clean.
4. **`test_payment_status.py` fixtures overclaim provenance** (confirmed, cosmetic) — both still carry *"The real live payload, copied from a RazorpayWebhookLogTable row on 2026-09-23"* while `account_id` is now `acc_RETIRED_FIXTURE`. Qualify the comment so the fixture is not read as verbatim.
5. **`test_payment_readiness.py:23` attributes history to a synthetic string** (confirmed, cosmetic) — *"The previously-assumed `acc_RETIRED_FIXTURE` was the stale env value"* describes a value that never existed. Reword to name no id.
6. **Residual present-tense VPA prose** (confirmed, deferred by the coder) — `docs/compatibility.md:87` and `payment_readiness.py:47` still say live env *"says"* / *"was"* the retired VPA. Correct post-merge in one place.
7. **`whatsapp-business-api` comment is stale about which pair disagrees with live** (confirmed, pre-existing) — the comment at ~3162 states the removed fallbacks `acc_TTFSyolquKEZEy` / `rxairtel` disagreed with the live environment, which is no longer true after the live correction. Not introduced by this diff; fold into the post-merge prose pass.
8. **Hit counts in the handoff doc are off by one** (confirmed, cosmetic) — it records 7 files for the MID and 5 for the VPA; actual tracked counts are 8 and 6, because the handoff doc itself quotes both identifiers. Harmless, but a reviewer re-measuring will see a mismatch.
9. **Brief's `plan.md` does not exist** (confirmed, non-blocking) — `.agents/tasks/razorpay-account-purge-20261002/plan.md` was destroyed by the revert and not restored; only `review.md` / `review.json` are present. All verification evidence lives in `docs/execution/razorpay-account-purge-20261002.md`, so nothing is missing, but the task record has no plan.

</details>

<details>
<summary>Details</summary>

### Adoption instead of merge, and why byte-identity is the mechanism

The nine authorized paths were taken from `origin/stack` wholesale. Two preconditions were verified before adopting, and I re-ran both:

```
git diff --stat origin/stack HEAD -- <9 paths>        → empty
git merge-tree --write-tree origin/stack HEAD         → bare tree oid, no conflict section
```

The first proves the adopted content is byte-identical to the remote, which is what makes the orchestrator's merge auto-resolve regardless of base — the precise failure mode that forced iteration 1's revert. The second proves no conflict exists today.

The coder's pre-adoption check `git diff --stat c6fd53dc HEAD -- <9 paths>` being empty is the one that matters for safety: local was identical to the merge base for every target, so no local work from another session was clobbered by the checkout.

### The declined seam, and why the dirty hunk does not overlap

```
local working tree (another session, uncommitted):  lines 6-23, +18
    an editor's note about MCC 4722 vs live 7392, and PayU retirement

origin/stack (committed):                           lines 49, 51
    [retired Razorpay account] → [retired Razorpay account]
```

Non-overlapping, so the merge resolves both. `git grep -c [retired Razorpay account] origin/stack` returns nothing, confirming the remote tree is clean of the id.

What makes this more than prose: those lines sit in a table of payment configurations inside an email template addressed to Meta, so the retired merchant account is the value an owner would transcribe into a live beta request. The purge exists to prevent exactly that. The brief's check 1 counts this as blocking, but `01-standing-authorization` A1_LOCAL and the multi-session rules both require preserving a file another session owns, and steering outranks the brief — committing the working-tree version of that path would sweep eighteen lines of unrelated work under this commit's message, which is the failure rule 3b was written for. Recording it with a named unblock is the correct outcome, not an edit.

### Class C: clean here, rewritten on the merge target

Byte-unchanged in `6e1a4178`, verified against the merge base:

```
git diff --stat c6fd53dc HEAD -- change-authority-matrix.md phase-04d-payment-audit.md \
                                  checkout-consolidation-findings-20261001.md    → empty
```

`origin/stack` is a different story — 6 files, +69/-22. The substitution in the payment audit is the one worth seeing, because it removes a literal that was a measurement:

```diff
-discriminator. One key — `[retired Razorpay account]:payment.downtime.started:1790100905` — was
+discriminator. One key — `[retired Razorpay account]:payment.downtime.started:1790100905` — was
 delivered 6 times with two distinct body sizes while our endpoint returned 200 each time.
```

And in the checkout findings, a column headed *"Live value"* no longer holds the value that was live:

```diff
-| `wecare-whatsapp-business-api` | `RAZORPAY_MID` | `[retired Razorpay account]` | `acc_TTFSyolquKEZEy` — **stale on live** |
+| `wecare-whatsapp-business-api` | `RAZORPAY_MID` | `[retired Razorpay account]` | `acc_TTFSyolquKEZEy` — **stale on live** |
```

This is a tension the owner instruction creates rather than a mistake — *"remove old from everywhere"* and immutable audit history genuinely conflict — but it should be resolved deliberately. The repository already states the opposing principle in the seam file: *"rewriting a sent email would falsify the record."*

### Class B — module behaviour untouched

Only the `payment_readiness.py` docstring changed; no executable line is in the diff. `MID = 'acc_TTFSyolquKEZEy'` remains the authoritative constant in the test module, the RETIRED / AUTHORITATIVE table structure survives, and the lesson the module keeps — *"a webhook `account_id` is evidence of which account sent an event, not proof of which account the Meta configuration settles into"* — is intact.

The deviation from the brief's check 2 stands: the literal id does not survive as the thing being corrected. Accepted in iteration 1, re-accepted here, and recorded in handoff note 4 so it is not mistaken for an unmet requirement later.

### Class D — the guard was kept, and the loss is recorded twice

Preferred option taken. `test_a_mid_mismatch_blocks_payment` still asserts `RAZORPAY_MID_MISMATCH` fires and still asserts `verdict.provider_mid`; only the wrong-account fixture string moved to `acc_RETIRED_FIXTURE`. The property under test is inequality against the expected MID, which does not special-case any value.

What is lost, and stated in both the commit message and the handoff doc without softening: the mismatch guard no longer proves that *this specific* retired account would be refused if Razorpay ever reported it again.

The two `test_payment_status.py` fixtures lose nothing measurable — no assertion in that file reads `account_id`, the dedup keys are entity-id scoped, and the Defect-2 regression proof asserts on key composition. But the comment above them still reads *"The real live payload, copied from a RazorpayWebhookLogTable row on 2026-09-23"*, which is now false about one field. A future reader diffing the fixture against a real webhook log will find a discrepancy the comment denies.

### Partner-onboarding: the dead-code argument holds

Checked against the function, not just the argument:

```python
for secret_id in ('wecare/razorpay/api',):
    ...
    if key_id and key_secret:
        return key_id, key_secret
return '', ''
```

`wecare/razorpay-webhook` holds exactly one field, `webhook_secret` — stated in this function's own docstring from a 2026-09-19 verification and corroborated by `whatsapp-payments-india-reference.md`. The return requires both `key_id` and `key_secret` non-empty, so the second iteration could never satisfy it and always fell through to the same `return '', ''` the function now reaches directly. Behaviour is unchanged, and this needed no credential read to establish.

`tests/test_partner_razorpay_canonical_secret.py` proves the property rather than restating the code: `get_secret_value` must be called **exactly once** with `SecretId='wecare/razorpay/api'`, asserted on both the success path and a raising-client failure path. Re-adding the webhook secret to that tuple fails the second assertion. The webhook secret is retained, correctly — it is the signing credential for signature verification, not an API credential, so its survival is not a missed purge target.

### Deep link and secret hygiene

`src/config/constants.ts` is absent from the commit and already held `wecaredigitalbh511413.rzp@rxairtel`, which `payment_readiness.py` records as AUTHORITATIVE. There was no `@icici` reference to remove in `constants.ts` or `src/pages/workspace/pay/link/`, so check 5 passes by non-action. `rxairtel` is preserved byte-for-byte as a Razorpay payment-address suffix, not an Airtel messaging dependency.

No credential value appears in any edit, command or log. The new test's `'fixture-id'` / `'fixture-secret'` literals are synthetic and not issuer-shaped. No `get-secret-value` or `batch-get-secret-value` call was made by the coder or by this review. The merchant id and UPI VPA are non-secret identifiers — they appear in every deep link and QR — and the key pair they sit beside was never read or named.

### Commit discipline

Ten explicit paths, all Razorpay content plus the handoff doc. The working tree holds another session's dirty steering file and seven untracked items (`AGENTS.md`, three `ecommerce/*.py` modules, a Cognito MFA snapshot, `scripts/retired_url_equity.py`, a coupons task directory) — none swept in. The coupons work sits in its own prior commit `7a0c122c`.

The `payment_readiness.py` edit matches the `amplify/functions/shared/lambda_utils/**` push trigger on `.github/workflows/seo-tools-deploy.yml`, so the eventual push fires a `seo-tools` CI deploy. The coder flagged this; it is expected rather than incidental.

### Untracked scratch copies

`.scratch/deploy-checkout/`, `.scratch/checkout-completion-review/` and `.scratch/dirty-backup-20261001-183507/` still contain both retired identifiers in copies of `payment_readiness.py`, `compatibility.md`, the handlers and the tests. `.scratch/` is gitignored (`.gitignore:133`), so this is not a repository leak. It matters only if a file is ever copied back out of a scratch tree, which would reintroduce the identifiers silently.

### Verification evidence, as recorded

Read from the handoff doc, not re-run:

```
.venv/bin/python -m pytest tests/ -q      6501 passed, 1 skipped, 5 xfailed, exit 0
npm run typecheck (tsc --noEmit)          exit 0, no output
payment_readiness + payment_status + partner_razorpay_canonical_secret    113 passed
test_a_mid_mismatch_blocks_payment        1 passed
```

Zero failures, and the doc explains why the single pre-existing failure from iteration 1's withdrawn evidence is gone: the `_variables` manifest self-count assertion was fixed by `0bec35da`. That accounting is more useful than a bare pass count, because it closes out an attribution that would otherwise have been inherited.

</details>

<details>
<summary>Files changed (10)</summary>

| Path | Change |
|---|---|
| `amplify/functions/shared/lambda_utils/payment_readiness.py` | Docstring only: `STALE` → `RETIRED`, past tense, placeholder for the id. No executable change |
| `amplify/functions/messaging/partner-onboarding/handler.py` | Webhook-secret fallback removed from the credential loop |
| `amplify/functions/messaging/whatsapp-business-api/handler.py` | Comment at ~3162, placeholders for the retired pair |
| `tests/test_partner_razorpay_canonical_secret.py` | New. Pins exactly-one canonical secret read on success and failure paths |
| `tests/test_payment_readiness.py` | Mismatch fixture → `acc_RETIRED_FIXTURE`; test kept |
| `tests/test_payment_status.py` | Both webhook fixtures → `acc_RETIRED_FIXTURE` |
| `docs/compatibility.md` | Retired row no longer claims authority; `acc_TTFSyolquKEZEy` row is the authoritative one |
| `src/pages/workspace/dashboard/system-architecture.tsx` | Retired-comment id replaced; displayed values unchanged |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md` | Past tense, placeholders |
| `docs/execution/razorpay-account-purge-20261002.md` | New. The handoff and evidence record |

Full diff: `git show 6e1a4178`
</details>
