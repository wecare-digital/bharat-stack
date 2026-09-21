# Kiro handoff

Updated: **2026-09-21**

## Position

| Field | Value |
|---|---|
| Active phase | **Phase 0 complete.** Phase 1 not started — gated on the confirmation queue below |
| Branch | `stack` |
| Exact HEAD | `4baf4236dbf78a784ec84f238e091b699f7f8cd4` (local == `origin/stack`) |
| Deployed this session | **NOTHING.** No AWS write, no push, no commit, no credential change |
| Authority used | `A0_READ` for all discovery, `A1_LOCAL` for 8 documentation files |
| AWS | account `775261844268`, `us-east-1`, 58 Lambdas, 2 HTTP APIs, 332 routes, 66 tables, 31 secrets |
| Precedence | `.kiro/steering/00-current-owner-overrides.md` outranks `bw-crm.md` |

## Artifacts written

`docs/protected-resource-register.md` · `docs/kiro-handoff.md` ·
`docs/execution/{phase-00-status,requirement-registry,dependency-graph,change-authority-matrix,feature-flag-register,evidence-index}.md` ·
`docs/execution/route-auth-audit-20260921.txt`

Nothing is staged. Nothing is committed. Two pre-existing working-tree changes
belong to another session and were left untouched:
`.kiro/specs/plivo-api-control-plane-fix/{bugfix,design}.md` show as deleted.

## The three findings that matter

1. **`/webhook/sinch-rcs` (GET + POST) is unauthenticated end to end.**
   `AuthorizationType=NONE` and `rcs-dlr/handler.py` has no signature, HMAC,
   token or `require_auth`. It writes to the canonical `MessagesTable` and, via
   `evaluate_rules`, invokes `wecare-rcs-send` using a phone number taken from
   the unauthenticated body. Forged inbound traffic and attacker-triggered
   outbound RCS at our cost. Severity **HIGH**.
2. **`POST /whatsapp/inbound` is unauthenticated.** Handler consumes the legacy
   SNS envelope with no signature check, and honours `action=create_invoice`
   before any authorization. Severity **HIGH**.
3. **A whole HTTP API was never audited.** `79g3bbufdh` holds 3 routes,
   including two dangling public routes to the retired `wecare-sinch-dlr`.
   `scripts/audit_route_auth.py` only ever scanned `zllr9lrg7j`, so every
   "0 findings across 331 routes" claim excluded them. It also false-negatived
   `/whatsapp/inbound` through a directory-vs-function name mismatch.

Live exploitability was deliberately **not** tested — that means sending unsigned
requests at a production ingress.

## Confirmation queue

Reply `YES 1`, `YES 1,3`, `NO 2`, `SKIP 4`, or `YES ALL SAFE ITEMS`.

### 1. Extend `scripts/audit_route_auth.py` and re-baseline — recommended YES
Why: the current gate cannot see API `79g3bbufdh` and mis-maps handler
directories, so its "0 findings" is not trustworthy.
Effect: local code + a regenerated report. Scans both APIs, resolves
`inbound-whatsapp-handler` → `wecare-inbound-whatsapp`, keeps the existing
signature/`require_auth` marker logic.
Resources: none. Git: one commit on `stack`. Rollback: revert the commit.
Risk: **low**, read-only tooling. Class `A1_LOCAL` + `A2_REMOTE_CODE`.

### 2. Fix the two unauthenticated ingresses behind failing tests first — recommended YES
Why: findings 1 and 2 above.
Effect: add failing tests, then Sinch signature verification on `rcs-dlr`
(fail closed when the signing secret is absent), and for `/whatsapp/inbound`
either remove the public route or require raw-body Meta signature verification
plus moving `create_invoice` to an internal-only typed contract. Code only in
this item — **no deployment**, so production behaviour does not change yet.
Resources: none until item 4. Git: separate commits. Rollback: revert.
Risk: **low** while undeployed. Class `A1_LOCAL` + `A2_REMOTE_CODE`.

### 3. Live reachability probe of the two ingresses — recommended NO for now
Why: it would upgrade "config and source say open" to measured fact.
Effect: one unsigned request per route against production. For
`/whatsapp/inbound` a `{}` body yields `Records: []` and no writes; for
`/webhook/sinch-rcs` any body risks a `MessagesTable` write and, if an
automation rule matches, a real outbound RCS message.
Resources: production Lambda invocations and CloudWatch entries.
Rollback: none — a send cannot be recalled.
Risk: **medium**. Class `A3_PRODUCTION`. Recommendation: fix first, then verify
the fix, rather than proving the hole exists.

### 4. Deploy the auth fixes to `live` — recommended, but only after item 2 is tested
Why: code fixes do not protect anything until the alias moves.
Effect: `update-function-code` on `wecare-rcs-dlr` (and `wecare-inbound-whatsapp`
if changed), publish a version, move `live`. Rollback versions captured first.
Resources: 1–2 Lambda aliases. Rollback: move `live` back to `rcs-dlr:6` /
`inbound-whatsapp:37`.
Risk: **medium** — a signature check that is wrong will reject genuine Sinch
callbacks. Mitigation: verify against a captured real payload shape before
enabling fail-closed. Class `A3_PRODUCTION`.

### 5. Delete the 5 dangling routes — recommended YES, after items 1–2
Why: retirement acceptance forbids leftover declarative surface, and they are a
recreation path.
Effect: delete `GET`+`POST /webhook/sinch-dlr` and their integration on
`79g3bbufdh`; delete `POST`+`GET`+`DELETE /voice-in/cdr` and their integrations
on `zllr9lrg7j`. All five target functions that **no longer exist**, so nothing
executable is removed.
Evidence first: route/integration JSON exported to
`docs/prohibited-provider-retirement.md` with exact IDs before deletion.
Rollback: recreate route + integration from the exported JSON.
Risk: **low**, but irreversible without the export. Class `A4_DESTRUCTIVE`.

### 6. Proceed with Phase 1 discovery in parallel — recommended YES
Why: it is entirely read-only and unblocks every later phase.
Effect: per-function and per-route machine-readable inventory joined to IaC,
permissions, tables, traffic and frontend callers; deployed environment values
for the flag register; Plivo/Meta/Razorpay/Google/Bing/Wix documentation queues;
SDK and packaged-runtime matrix; cleanup dry-run.
Resources: read-only AWS and documentation fetches. Git: docs commits.
Risk: **low**. Class `A0_READ` + `A1_LOCAL`.

## Waiting on the owner

| Item | Unblock action |
|---|---|
| `SEC-CRED-001` exposed credential families | Owner replaces Razorpay / Google Ads / Google OAuth / Google API key / Bing credentials manually. Kiro will not touch them |
| `MCP-META-001` both Meta MCP servers | Add exact redirect URIs to app `2238810740192680`: `http://localhost:7778/oauth/callback` (DevTools), `http://localhost:7779/oauth/callback` (WhatsApp Business Tools, only when enabling it) |
| `MCP-RZP-001` Razorpay MCP | Blocked on the provider: its token endpoint advertises only `client_secret_post`. Stays disabled |
| Live QA calls and messages | Approved QA recipient required before any connected-call or template test |

## Next command

Nothing runs until the queue above is answered. On `YES 1,2,6` the first step is:

```
python scripts/audit_route_auth.py        # after extending it to both APIs
```

## Rollback state

No change to roll back. Captured rollback targets for the aliases most likely to
move next: `wecare-rcs-dlr:live → 6`, `wecare-inbound-whatsapp:live → 37`,
`wecare-whatsapp-calling:live → 12`, `wecare-outbound-whatsapp:live → 17`.
