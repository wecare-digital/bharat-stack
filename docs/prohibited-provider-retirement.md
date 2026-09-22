# Prohibited-provider retirement manifest

Evidence captured **before** deletion, as the retirement gate requires. Every row
carries the exact identifier, the dependency proof, and the command that puts it
back.

Captured: **2026-09-21** · Account `775261844268` · Region `us-east-1`
Authority: `A4_DESTRUCTIVE` under the standing grant in
`.kiro/steering/01-standing-authorization.md` — "delete an API route or
integration whose target Lambda does not exist", conditional on this export.

## Why these are safe to remove

Both target Lambdas are **absent from the live fleet** (58 functions measured, and
`targetFunctionExists` is `false` for both). An API Gateway route whose
`AWS_PROXY` integration points at a deleted function cannot execute anything — it
can only return an error. So there is no traffic to drain and no behaviour to
preserve; what remains is declarative residue and a recreation path, which the
retirement acceptance criteria explicitly forbid.

Integration reference counts were measured across every route on each API:
`qvupugf` is referenced by exactly the 2 routes below, `cf9a7lp` by exactly the 3
below. Neither is shared with a live route, so both integrations are removed with
their routes rather than left orphaned.

## Surface being removed

### API `79g3bbufdh` (`wecare-api`) — retired Sinch SMS DLR

Sinch is permitted for India RCS only. `wecare-sinch-dlr` was the Sinch **SMS**
delivery-report handler, which the provider matrix prohibits outright.

| Route key | Route ID | Auth | Integration ID | Target |
|---|---|---|---|---|
| `GET /webhook/sinch-dlr` | `iv4u4fs` | `NONE` | `qvupugf` | `wecare-sinch-dlr` (**absent**) |
| `POST /webhook/sinch-dlr` | `nlktsl3` | `NONE` | `qvupugf` | `wecare-sinch-dlr` (**absent**) |

Integration `qvupugf`: `AWS_PROXY`, `POST`, payload format `2.0`, timeout
`30000` ms, URI
`arn:aws:lambda:us-east-1:775261844268:function:wecare-sinch-dlr`.

This API had **never been scanned** by `scripts/audit_route_auth.py`, which
hardcoded `zllr9lrg7j`. That is why these two survived every previous
"331 routes, 0 findings" report.

### API `zllr9lrg7j` (`wecare-digital-api`) — retired Airtel CDR ingester

| Route key | Route ID | Auth | Integration ID | Target |
|---|---|---|---|---|
| `POST /voice-in/cdr` | `569isr0` | `NONE` | `cf9a7lp` | `wecare-voice-in-cdr:live` (**absent**) |
| `GET /voice-in/cdr` | `jeib1ii` | `NONE` | `cf9a7lp` | `wecare-voice-in-cdr:live` (**absent**) |
| `DELETE /voice-in/cdr` | `wdyoeq8` | `NONE` | `cf9a7lp` | `wecare-voice-in-cdr:live` (**absent**) |

Integration `cf9a7lp`: `AWS_PROXY`, `POST`, payload format `2.0`, timeout
`30000` ms, URI
`arn:aws:lambda:us-east-1:775261844268:function:wecare-voice-in-cdr:live`.

The function was removed by commit `91488c94` ("Removed dead Airtel CDR ingester
and columns"); the routes and integration were left behind. Note the shape of
what was public here: an unauthenticated `DELETE` on a CDR surface. The closely
related `/voice-cdr-webhook/clear-logs` hole is what prompted
`scripts/audit_route_auth.py` to be written in the first place.

## What is NOT touched

- `wecare/sinch/rcs` (active secret), `wecare-rcs-send`, `wecare-rcs-dlr` and
  `/webhook/sinch-rcs` — the **allowed** India RCS path.
- Provider-neutral historical CDR data in `stack-wecare-digital-VoiceCDRTable`.
- The Razorpay VPA `wecaredigitalbh511413.rzp@rxairtel`. Its `rxairtel` suffix is
  a payment address, not an Airtel messaging dependency, and must stay
  byte-for-byte.
- The six secrets already scheduled for deletion. Their windows run to term; none
  is cancelled and none is newly scheduled.

## Rollback

Recreate the integration, then the routes pointing at it. The route IDs are
assigned by AWS and will differ; the route keys are what matter.

```bash
# --- API 79g3bbufdh, Sinch SMS DLR ---
aws apigatewayv2 create-integration \
  --api-id 79g3bbufdh \
  --integration-type AWS_PROXY \
  --integration-method POST \
  --payload-format-version 2.0 \
  --timeout-in-millis 30000 \
  --integration-uri arn:aws:lambda:us-east-1:775261844268:function:wecare-sinch-dlr
# then, with the returned <INTEGRATION_ID>:
aws apigatewayv2 create-route --api-id 79g3bbufdh \
  --route-key 'GET /webhook/sinch-dlr'  --target integrations/<INTEGRATION_ID>
aws apigatewayv2 create-route --api-id 79g3bbufdh \
  --route-key 'POST /webhook/sinch-dlr' --target integrations/<INTEGRATION_ID>

# --- API zllr9lrg7j, Airtel CDR ---
aws apigatewayv2 create-integration \
  --api-id zllr9lrg7j \
  --integration-type AWS_PROXY \
  --integration-method POST \
  --payload-format-version 2.0 \
  --timeout-in-millis 30000 \
  --integration-uri arn:aws:lambda:us-east-1:775261844268:function:wecare-voice-in-cdr:live
aws apigatewayv2 create-route --api-id zllr9lrg7j \
  --route-key 'POST /voice-in/cdr'   --target integrations/<INTEGRATION_ID>
aws apigatewayv2 create-route --api-id zllr9lrg7j \
  --route-key 'GET /voice-in/cdr'    --target integrations/<INTEGRATION_ID>
aws apigatewayv2 create-route --api-id zllr9lrg7j \
  --route-key 'DELETE /voice-in/cdr' --target integrations/<INTEGRATION_ID>
```

Restoring a route does **not** restore its handler: both target functions are
gone, so a rollback recreates the same dead surface. Rollback exists to undo a
mistaken deletion of the wrong route, not to bring the providers back — that
would require an explicit, separately authorized decision and would violate the
provider matrix.

Both stages `prod` have `AutoDeploy=true`, so deletions and recreations take
effect immediately without a deploy step.

## Result

| Step | Status |
|---|---|
| Evidence exported | ✅ this document |
| Dependency proof (integration refcounts) | ✅ 2 and 3, matching exactly the routes listed |
| Target functions confirmed absent | ✅ 58-function inventory |
| Routes deleted | ✅ all 5 — `iv4u4fs`, `nlktsl3`, `569isr0`, `jeib1ii`, `wdyoeq8` |
| Integrations deleted | ✅ both — `qvupugf`, `cf9a7lp` |
| Post-deletion verification | ✅ `audit_route_auth.py --strict`: **0 DANGLING**, 0 UNRESOLVED |

Measured immediately after deletion, 2026-09-21:

| Metric | Before | After |
|---|---|---|
| Total HTTP API routes | 332 | **327** |
| `79g3bbufdh` routes / integrations | 3 / 2 | **1 / 1** |
| `zllr9lrg7j` routes / integrations | 329 / 102 | **326 / 101** |
| Dangling routes | 5 | **0** |
| `sinch-dlr` routes remaining | 2 | **0** |
| `/voice-in/cdr` routes remaining | 3 | **0** |

`79g3bbufdh` now carries a single route, `POST /ai/generate` → `wecare-ai-generate-response`.
That integration is **unqualified** — it targets `$LATEST` rather than `:live` —
so it bypasses the version/alias deploy model the other 49 aliased functions use.
Tracked as `DEPLOY-002`; not addressed here because it is a deploy-model question,
not provider retirement.

---

## Addendum, 2026-09-21 — API `79g3bbufdh` (`wecare-api`) deleted entirely

After the two dangling `/webhook/sinch-dlr` routes were removed, this API was left
with a single route. Measuring it rather than assuming:

| Evidence | Value |
|---|---|
| Custom domains mapped to it | **none** — `api.wecare.digital` and `r.wecare.digital` both map to `zllr9lrg7j` |
| Requests, 30 days to 2026-09-21 | **zero** (no `Count` datapoint at all); `zllr9lrg7j` served **84,301** |
| Remaining route | `POST /ai/generate` → `wecare-ai-generate-response`, **unqualified `$LATEST`** |
| Same path on the live API | `POST /ai/generate` → `wecare-ai-generate-response:live` — already correct |
| CORS | `AllowOrigins: ["*"]` |
| `DisableExecuteApiEndpoint` | `false`, so it was publicly reachable at its execute-api URL |
| Created | 2026-03-03 |

So it was a dead duplicate that also defeated the alias deploy model: code reaching
`$LATEST` served traffic without a published version or an alias move, which is
exactly what `lambda-snapstart-deploy` steering exists to prevent. Tracked as
`DEPLOY-002`.

Deleted, in order: route `po5hjn4`, integration `qz7bhz2`, then the API. The stale
Lambda resource-policy statement `apigateway-invoke` granting
`arn:aws:execute-api:us-east-1:775261844268:79g3bbufdh/*/*` was removed too, so the
function's only remaining grant is `zllr9lrg7j/*`.

Source cleanup: `messaging/waba-management/handler.py` defaulted `CORS_API_IDS` to
`zllr9lrg7j,79g3bbufdh`. Left in place, every CORS save from the admin UI would
have failed on a `NotFoundException` for the deleted id.

| Metric | Before | After |
|---|---|---|
| HTTP APIs | 2 | **1** |
| Total routes | 327 | **326** |
| Invoke grants on `wecare-ai-generate-response` | 2 APIs | **1** |

### Rollback

```bash
aws apigatewayv2 create-api --name wecare-api --protocol-type HTTP \
  --route-selection-expression '$request.method $request.path' \
  --cors-configuration 'AllowOrigins=*,AllowMethods=GET,POST,PUT,DELETE,OPTIONS,AllowHeaders=content-type,authorization'
# then, with the returned <API_ID>:
aws apigatewayv2 create-integration --api-id <API_ID> \
  --integration-type AWS_PROXY --integration-method POST \
  --payload-format-version 2.0 --timeout-in-millis 30000 \
  --integration-uri arn:aws:lambda:us-east-1:775261844268:function:wecare-ai-generate-response
aws apigatewayv2 create-route --api-id <API_ID> \
  --route-key 'POST /ai/generate' --target integrations/<INTEGRATION_ID>
aws apigatewayv2 create-stage --api-id <API_ID> --stage-name prod --auto-deploy
aws lambda add-permission --function-name wecare-ai-generate-response \
  --statement-id apigateway-invoke --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn 'arn:aws:execute-api:us-east-1:775261844268:<API_ID>/*/*'
```

A restored API gets a new id, so the rollback recreates the capability, not the
identifier. Nothing referenced the old id except the `CORS_API_IDS` default, and
restoring it should also restore that entry. Note that recreating it reinstates
both defects — a wildcard-CORS public surface and a `$LATEST` integration — so a
rollback should be a deliberate, temporary step rather than the end state.
