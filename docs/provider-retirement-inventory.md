# Provider retirement inventory

Exact, classified inventory of every Airtel, Sinch SMS, Plivo SMS, legacy AWS SMS
and old voice-route reference in runtime-relevant code. Baseline commit
`6680a9fa`, measured 2026-09-19.

This is the authority for what may be deleted and what must be retained. It is
generated from reading the tree, not from prior documents — two earlier documents
(`docs/provider-inventory.md`, `docs/migration-plan.md`) contained stale claims
that are corrected at the bottom of this file.

## Classification vocabulary

| Class | Meaning | Deletable? |
|---|---|---|
| `ACTIVE_RUNTIME` | executes in a deployed Lambda or the shipped frontend bundle | yes, after replacement is tested |
| `INFRASTRUCTURE` | `resource.ts`, `backend*.ts`, `iam-policies.ts`, deploy maps, alarms, log retention, env vars, API routes | yes, after the runtime is gone |
| `UI` | a page or component an operator sees | yes |
| `TEST` | test code | replace, do not simply delete |
| `DOCUMENTATION` | prose, comments, docstrings | rewrite to match reality |
| `MIGRATION_COMPAT` | required to read or export legacy records | **retain** until export is signed off |
| `HISTORICAL_DATA` | model names and stored provider literals describing traffic that really was sent that way | **retain permanently** |

## Measured baseline

```
.venv/bin/python -m pytest -q      883 passed
npm test -- --run                   29 passed (7 files)
npm run typecheck                   clean
scripts/check-provider-policy.sh   160 findings / 6 failing rules / exit 1
./scripts/plivo-reconcile --json    all invariants PASS (see below)
```

Provider-policy findings by rule at baseline:

| Rule | Findings | Files |
|---|---|---|
| `airtel-runtime` | 111 | 14 |
| `airtel-sms-proxy` | 11 | 5 |
| `sinch-sms-sender` | 17 | 3 |
| `sinch-outside-rcs` | 3 | 3 |
| `legacy-aws-sms` | 9 | 4 |
| `sms-provider-literal` | 9 | 5 |
| `sinch-voice-whatsapp` | 0 | — already compliant |
| `plivo-sms` | 0 | — already compliant |

## Live Plivo state, read-only

`./scripts/plivo-reconcile --json` at `6680a9fa`. Every documented invariant holds:

| Invariant | Live value | Status |
|---|---|---|
| Application ID | `12775976954213184` | PASS |
| Application name | `WECARE-WHATSAPP-IVR` | PASS |
| Application SIP URI | `sip:12775976954213184@app.plivo.com` | PASS |
| `default_endpoint_app` | `true` | PASS — protected |
| Number | `918031830030` | PASS |
| Number → application | `/Application/12775976954213184/` | PASS — do not move |
| Endpoint alias | `WECARE-WhatsApp-IVR-SIP` | PASS |
| Endpoint username | `wecarewaivr203331794466262` | PASS |
| Endpoint SIP URI | `sip:wecarewaivr203331794466262@phone.plivo.com` | PASS |
| answer / fallback / hangup method | `POST` / `POST` / `POST` | PASS |
| `sip_auth_type` | `credential` | PASS |
| `number.sms_enabled` | **`false`** | Plivo SMS is structurally impossible on this number |

Answer, fallback and hangup URL tokens are all the same secret
(`sha256:9e60f6b94841`); the value is never printed.

## 1. Airtel — SMS

### 1.1 `amplify/functions/messaging/sms-in/airtel/` — whole function retires

`wecare-sms-in-airtel`. Misleadingly named: despite `sms-in` it is the **primary
outbound India sender**, the Airtel DLR receiver, and the DLT template registry.

| Lines | Symbol | Class |
|---|---|---|
| 19-21 | **live-looking Airtel Kong credentials in the module docstring** | `DOCUMENTATION` + **P0 exposure** |
| 97 | `AIRTEL_SMS_SECRET_NAME = 'wecare/airtel/sms'` | `INFRASTRUCTURE` |
| 98 | `AIRTEL_SMS_HOST = 'iqmessaging.airtel.in'` | `ACTIVE_RUNTIME` |
| 99 | `SMS_PROXY_URL = 'http://52.3.44.165:8899'` | `ACTIVE_RUNTIME` |
| 120-176 | `_call_airtel_via_proxy()` | `ACTIVE_RUNTIME` |
| 316-418 | `_send_sms()` — Airtel v5 `send-sms-cm` | `ACTIVE_RUNTIME` |
| 420-502 | `_send_bulk_sms()` — Conduit bulk | `ACTIVE_RUNTIME` |
| 504-642 | template CRUD against `DLTTemplates` | `ACTIVE_RUNTIME` → moves to `sms-aws` |
| 666-700 | `DEFAULT_DLT_TEMPLATES` | `HISTORICAL_DATA` — regulatory ids, reused by `comms/dlt.py` |
| 732-842 | `_list_messages` / `_get_message` / `_delete_message` / `_clear_logs` | `MIGRATION_COMPAT` — only read path for `AirtelSMSTable` |
| `resource.ts:11-25` | `wecare-sms-in-airtel` + 5 Airtel env vars | `INFRASTRUCTURE` |

**P0, independent of this migration:** the docstring credentials are in git
history. Rotate at the provider before treating file deletion as remediation.
Recorded as `WAITING_FOR_PROVIDER` — see the final report.

### 1.2 `amplify/functions/messaging/outbound-sms/handler.py` — densest target

Holds three prohibited senders and the fallback chain. Fallback chain verbatim,
`:157-194`:

```
provider=='sinch' explicit  -> _send_sinch_sms
+91 and 12 digits           -> _send_airtel_iq_sms
  on ANY Airtel failure     -> _send_sinch_sms, relabelled provider='sinch'
everything else             -> _send_aws_sms  (classic Pinpoint, then SNS)
```

| Lines | Symbol | Class |
|---|---|---|
| 38 | `boto3.client('sns')` | `ACTIVE_RUNTIME` — prohibited |
| 39 | `boto3.client('pinpoint')` — classic | `ACTIVE_RUNTIME` — prohibited |
| 44 | `PINPOINT_APP_ID` | `INFRASTRUCTURE` |
| 50-52 | `AIRTEL_IQ_HOST`, `SMS_PROXY_URL` | `ACTIVE_RUNTIME` |
| 54-55 | `AIRTEL_IQ_ENTITY_ID`, `AIRTEL_IQ_SOURCE_ADDRESS` | `HISTORICAL_DATA` — regulatory, now owned by `comms/dlt.py` |
| 66-96 | `_load_airtel_iq_creds()` | `ACTIVE_RUNTIME` |
| 266-297 | `_load_sinch_sms_creds()`, secret `wecare/sinch/sms` | `ACTIVE_RUNTIME` |
| 299-386 | `_send_sinch_sms()`, `jumbo.aclgateway.com` | `ACTIVE_RUNTIME` — already non-functional, `:316` hard-fails with no `oauth_token` |
| 387-433 | `_send_aws_sms()` — classic `pinpoint.send_messages`, `sns.publish` | `ACTIVE_RUNTIME` — prohibited |
| 435-613 | `_send_airtel_iq_sms()` — v4/v5/v6 via the proxy | `ACTIVE_RUNTIME` |
| 638-653 | `_send_airtel_sms()` — dead, no callers | `ACTIVE_RUNTIME` (dead) |
| `resource.ts:14` | `PINPOINT_APP_ID` literal | `INFRASTRUCTURE` |
| `resource.ts:17-24` | 6 Airtel env vars | `INFRASTRUCTURE` |

### 1.3 Cross-Lambda callers that must be rewired before deletion

| Caller | Target | Location |
|---|---|---|
| `wecare-whatsapp-calling` | `wecare-sms-in-airtel`, **synchronous** | `whatsapp-calling/handler.py:1415-1472` via `:1352`, `:1521` |
| `wecare-wix-store` | `wecare-sms-in-airtel` | `ecommerce/wix-store/handler.py:1585,1589` |
| `wecare-voice-in-c2c` | `/sms-in/airtel` or `/sms-aws/send` | `voice-in/c2c/handler.py:1001` |
| `wecare-voice-in-obd` | `/sms-in/airtel` or `/sms-aws/send` | `voice-in/obd/handler.py:1680,1690` |
| frontend | `POST /sms/send` with `provider:'airtel'` | `src/pages/dm/whatsapp/calling.tsx:619-637`, `src/pages/dm/sms/index.tsx:280+` |
| frontend | `sendSinchSms()` | `src/api/client.ts:1260-1266` |
| `wecare-plivo-answer` | `wecare-sms-aws:live` | `plivo-answer/handler.py:71` — **already correct** |

## 2. Airtel — voice

| Function | Airtel surface | Class |
|---|---|---|
| `voice-in/c2c` | `iqvoice.airtel.in/.../v2/click-to-call`, secret `wecare/airtel/c2c`, `AIRTEL_C2C_TABLE`, `AIRTEL_KONG_HOST` | `ACTIVE_RUNTIME` + `INFRASTRUCTURE` |
| `voice-in/obd` | `openapi.airtel.in`, `iqtelephony.airtel.in`, secret `wecare/airtel/obd`, audio-spec conversion, campaign upload | `ACTIVE_RUNTIME` + `INFRASTRUCTURE` |
| `voice-in/cdr` | Airtel CDR webhook receiver; also the **only** `sinch-outside-rcs` Lambda hit at `:1306-1321` | `ACTIVE_RUNTIME` + `MIGRATION_COMPAT` |
| `outbound-voice` | Airtel C2C + OBD backing, secret `wecare/airtel/c2c` | `ACTIVE_RUNTIME` |
| `whatsapp-calling` | `_try_airtel_sms`, `SMS_LAMBDA_AIRTEL` | `ACTIVE_RUNTIME` |
| `ai-generate-response:1018` | advertises an "Airtel C2C" tool to the model | `ACTIVE_RUNTIME` — agent offers a retired capability |

`voice-in/cdr` is **not** purely Airtel: `plivo-answer` writes into the same
`VoiceCDRTable` with `id='plivo#<uuid>'`, `source='plivo'`. The table is shared
and must not be dropped.

## 3. Sinch

| Item | Location | Disposition |
|---|---|---|
| Sinch SMS sender + creds | `outbound-sms/handler.py:266-386` | **delete** |
| Sinch DLR Lambda | `messaging/sms-in/sinch/handler.py`, `wecare-sinch-dlr` | **delete** |
| `sendSinchSms()` | `src/api/client.ts:1260-1266` | **delete** |
| Sinch send tab | `src/pages/dm/sms/index.tsx:50` | **delete** |
| deploy map entry | `scripts/deploy_all_lambdas.py:160` | **delete** |
| IAM | `amplify/iam-policies.ts:434` | **delete** |
| India RCS helper | `lambda_utils/sinch_rcs.py` | **KEEP** — approved |
| `rcs-send`, `rcs-dlr` | `messaging/rcs-{send,dlr}/` | **KEEP** |
| `RcsMessages` model | `amplify/data/resource.ts:361-389` | **KEEP** |
| dead `send_rcs_order_notification` | `sinch_rcs.py:399-431` | delete — no callers |
| dead `send_rcs_wa_alert` | `sinch_rcs.py:434-452` | delete — no callers |
| duplicate `_is_rcs_enabled()` + inline secret read | `voice-in/cdr/handler.py:1306-1321` | **collapse into the shared helper** — this is the `sinch-outside-rcs` violation |
| `wecare/sinch/sms` secret | Secrets Manager | delete **after** rollback window, separately approved |
| `wecare/sinch/rcs` secret | Secrets Manager | **KEEP** |

Sinch SMS rows live in `AirtelSMSTable` with `provider='sinch'`, so the Sinch tab
is also the only read path for that legacy traffic. It is replaced by one
read-only legacy-history view, not simply removed.

## 4. Plivo SMS

Zero references. `number.sms_enabled=false` live. Already compliant; the CI gate
keeps it that way.

## 5. Legacy AWS SMS

| Item | Location | Class |
|---|---|---|
| `sns.publish` for SMS | `outbound-sms/handler.py:414-428` | `ACTIVE_RUNTIME` — prohibited |
| classic `pinpoint.send_messages` | `outbound-sms/handler.py:391-393` | `ACTIVE_RUNTIME` — prohibited |
| classic Pinpoint client | `sms-aws/handler.py:40-41` | `ACTIVE_RUNTIME` — prohibited |
| `INDIA_PINPOINT_APP_ID` | `sms-aws/handler.py:62`, `resource.ts:21` | `INFRASTRUCTURE` — empty |
| classic template CRUD | `sms-aws/handler.py:584-731` + routes `:135-147` | `ACTIVE_RUNTIME` — explicitly not DLT-capable |
| "Pinpoint Templates" tab | `src/pages/dm/sms/index.tsx:53` | `UI` |
| EUM v2 sender | `sms-aws/handler.py:39`, `:391-472` | **KEEP** — the approved path |

`amplify/iam-policies.ts:93-141` already grants `sms-voice:*` only — no
`sns:Publish` for SMS, no classic Pinpoint. The IAM side is already compliant;
only code is not. `iam-policies.ts:185-195` grants `sns:Publish` scoped to the
alarm topic, which is not SMS.

## 6. Data models — retain

| Model | Lines | Disposition |
|---|---|---|
| `AirtelSMS` | `data/resource.ts:316-343` | `HISTORICAL_DATA` — retain, expose read-only |
| `DLTTemplates` | `:344-360` | **KEEP live** — regulatory registry, read by `comms/dlt.py` |
| `RcsMessages` | `:361-389` | **KEEP live** — India RCS |
| `AirtelC2C` | `:390-419` | `HISTORICAL_DATA` — retain |
| `VoiceCDR` | `:420-529` | **KEEP live** — shared with Plivo |
| `OBDCampaign` | `:530-548` | `HISTORICAL_DATA` — retain |
| `VoiceCall` | `:239-262` | `HISTORICAL_DATA` — `provider` spans airtel + aws |

Stored provider literals that describe real past traffic and must **not** be
relabelled: `voice-in/c2c:1029`, `voice-in/obd:1708`, `whatsapp-calling:1355`,
`outbound-sms:164,166,191`, `data/resource.ts:373,516`.

## 7. Existing infrastructure this migration builds on

Already present and correct, discovered during inventory:

| Component | Location | Note |
|---|---|---|
| `lambda_utils/comms/` | `shared/lambda_utils/comms/` | AWS-only SMS seam: `get_sms_service`, `AwsSmsProvider`, `SmsRegionResolver`, `dlt` single-source-of-truth. **No messaging Lambda imports it yet** — that is the Phase 2 rewire. |
| `webhook_dedup.claim_event` | `shared/lambda_utils/webhook_dedup.py:39` | atomic `attribute_not_exists` claim, **fails OPEN** |
| `idempotency.claim_admin_action` | `shared/lambda_utils/idempotency.py:52` | same primitive, **fails CLOSED** — the shape connected notifications need |
| `plivo_signature.py` | `shared/lambda_utils/` | V3 verification, cross-checked against the official SDK in `tests/test_plivo_signature.py` |
| `plivo_control_plane.py` + `plivo-reconcile` | `scripts/` | snapshot / plan / dry-run / protected fields / readback; number routing already separated |

## 8. Test coverage — and the gap

Relevant suites: `test_plivo_routes.py`, `test_plivo_answer.py`,
`test_plivo_signature.py`, `test_plivo_control_plane.py`, `test_comms_sms.py`,
`test_sms_aws_dlt.py`, `test_idempotency.py`, `test_webhook_dedup.py`.

**A case-insensitive grep for `airtel|sinch` across `tests/` returns zero
matches.** Deleting the Airtel and Sinch SMS code therefore breaks no test — but
there is equally no regression net proving the AWS replacement preserves
behaviour for the India call-notification path. Phase 2 adds that coverage
*before* removing `_try_airtel_sms`.

## 9. Corrections to existing documents

| Document | Stale claim | Reality |
|---|---|---|
| `docs/provider-inventory.md` §6 | `plivo-answer` is answer-only; fallback/hangup/events are `NEW`; V3 signature is `NEW` | all four routes and V3 verification are implemented (464 lines) |
| `docs/provider-inventory.md` §6 | post-call SMS at `:145-192` calls a provider | it invokes `wecare-sms-aws:live`; already compliant |
| `docs/provider-inventory.md` §11 | `check-provider-policy.sh` is `NEW` | exists and runs in CI with `--expect-fail` |
| `docs/provider-inventory.md` §2 | `comms/` abstraction count is 0 | `lambda_utils/comms/` exists with 4 modules and a test suite |
| `.kiro/steering/lambda-snapstart-deploy.md` | — | correct as written: SnapStart is OFF on 62/62; the `live` alias is what makes publish mandatory |

`outbound-sms/handler.py:66-96` carries a docstring claiming
`SnapStart.ApplyOn=PublishedVersions`. Measured live: SnapStart is `None`/`Off`
on all 65 functions (re-measured 2026-09-26). The lazy-load behaviour it describes is still correct and
still required — for warm-sandbox caching rather than snapshotting — so the code
stays and the comment is corrected where the file survives.
