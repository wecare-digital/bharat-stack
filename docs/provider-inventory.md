# Provider inventory and disposition

Every provider touchpoint in the repository, with the action the Unified
Communications Platform spec requires. Baseline commit `41dc41c2`, 2026-09-19.

Disposition vocabulary:

| | meaning |
|---|---|
| **KEEP** | stays as-is, possibly moved behind an abstraction |
| **REWIRE** | keeps working but must route through the orchestrator |
| **DELETE** | removed from runtime; historical records may retain the name |
| **NEW** | does not exist yet, must be built |
| **SCRUB** | contains credential material that must be removed regardless |

---

## 1. Target provider matrix (§54)

| Provider | Messaging | SMS | Voice | RCS |
|---|---|---|---|---|
| **Meta** | WhatsApp ✅ | — | WhatsApp Calling ✅ | — |
| **AWS** | — | **ALL SMS ✅** | — | international ✅ |
| **Sinch** | ❌ | ❌ | ❌ | **India only ✅** |
| **Plivo** | ❌ | ❌ | PSTN/SIP/IVR ✅ | — |
| **Airtel** | ❌ | ❌ | ❌ | ❌ |

The single most important rule: **AWS End User Messaging is the normal SMS
provider**, for India (`ap-south-1`) and international (`us-east-1` default),
including as the fallback for both RCS paths.

---

## 2. AWS — End User Messaging SMS

| Item | Location | Disposition |
|---|---|---|
| EUM v2 sender, two-region, DLT-aware | `messaging/sms-aws/handler.py` | **KEEP** — becomes `AwsSmsProvider` |
| `us-east-1` client | `sms-aws/handler.py:39` | KEEP |
| `ap-south-1` per-request client | `sms-aws/handler.py:407` | KEEP → move behind `SmsRegionResolver` |
| DLT country params | `sms-aws/handler.py:417-424` | KEEP |
| Hard DLT gate + 422 | `sms-aws/handler.py:92-110,316-334` | KEEP — required by §6 "fail safely" |
| `DryRun` | `sms-aws/handler.py:426-428` | KEEP — use for §49 acceptance |
| Origination identity pinned `+18444891209` | `sms-aws/handler.py:48-59` | KEEP |
| `_format_e164` country-code correctness | `sms-aws/handler.py:479-505` | KEEP |
| Classic Pinpoint template CRUD | `sms-aws/handler.py:41` + `/templates` | **DELETE** — explicitly not DLT (`:66-73`); the DynamoDB registry is authoritative |
| Optimistic `status:'SENT'`, never updated | `sms-aws/handler.py:357-375` | **NEW** — needs a delivery-receipt consumer |
| Region-pinned IAM `sms-voice` ARN | `amplify/iam-policies.ts:94-105` | **REWIRE** — must cover `ap-south-1` |
| Voice via EUM v2 | `messaging/voice-aws/handler.py:34,258-270` | KEEP (out of SMS scope) |

**Gap with no current owner:** no delivery-receipt ingestion exists anywhere for
AWS SMS. Until it is built, "delivered" is unknowable and §42's *delivery rate*
dashboard cannot be honest.

---

## 3. AWS — RCS (international)

| Item | Disposition |
|---|---|
| `AwsRcsProvider` | **NEW** (§14) |
| `AwsRcsTemplateRenderer` | **NEW** (§15) |
| `RcsCapabilityResolver` | **NEW** (§17) — must **not** branch on Android vs iPhone |
| RCS → AWS SMS fallback + channel-state tracking | **NEW** (§16) |
| Agent/pool registration in `us-east-1` | **NEW** — provider-approval gated |

Nothing exists today. There is no `social-messaging` client anywhere in the repo.

---

## 4. Sinch — DELETE all SMS, KEEP India RCS

### 4.1 Sinch SMS — DELETE (§9)

| Item | Location |
|---|---|
| Credential loader | `outbound-sms/handler.py:270-297` (secret `wecare/sinch/sms`) |
| Sender | `outbound-sms/handler.py:299-385` → `jumbo.aclgateway.com/v12/.../messages.json` |
| **SMS fallback from Airtel** | `outbound-sms/handler.py:185-194` |
| DLR receiver (whole Lambda) | `messaging/sms-in/sinch/handler.py`, `wecare-sinch-dlr` |
| Frontend forcing the Sinch branch | `src/api/client.ts:1248-1266` `sendSinchSms()` |
| Route `POST /webhook/sinch-dlr` | `docs/WEBHOOK-INVENTORY.md:20` |
| IAM | `amplify/iam-policies.ts:395` |
| Deploy map entry | `scripts/deploy_all_lambdas.py:160` |
| Secret definition | `scripts/store_provider_secret.py:174-185` |
| UI send tab | `src/pages/dm/sms/index.tsx` |

Historical rows may keep `provider = 'sinch'`. **New** SMS must never use Sinch.

Note: `wecare/sinch/sms` currently has **no `oauth_token`**, so Sinch SMS cannot
send at all right now (`outbound-sms/handler.py:315` hard-fails). Deleting this
path removes a already-broken dependency rather than a working one.

### 4.2 Sinch India RCS — KEEP (§10-§13)

| Item | Location | Disposition |
|---|---|---|
| RCS helper | `lambda_utils/sinch_rcs.py` | **KEEP** → `providers/sinch/rcs/` per §10 |
| Send Lambda | `messaging/rcs-send/handler.py` | KEEP |
| DLR Lambda | `messaging/rcs-dlr/handler.py` | KEEP |
| Enable flag `SINCH_RCS_ENABLED` | `voice-in/{cdr,c2c,obd}/resource.ts` | KEEP |
| Data model `RcsMessages` | `amplify/data/resource.ts:361-389` | KEEP |
| Approved templates `rcsmenu`/`rcsorder`/`waalert` | `sinch_rcs.py:22-25` | KEEP |
| `send_rcs_order_notification` | `sinch_rcs.py:399-431` | **DELETE** — no callers |
| `send_rcs_wa_alert` | `sinch_rcs.py:434-452` | **DELETE** — no callers |
| Duplicate local `_is_rcs_enabled()` | `voice-in/cdr/handler.py:1307` | **DELETE** — use the shared helper |
| `SinchRcsTemplateImporter` | — | **NEW** (§12), read-only |
| Internal `RcsTemplate` model | — | **NEW** (§13) |

**RCS fallback must become AWS SMS `ap-south-1`** (§11). It must never fall back
to Sinch SMS.

---

## 5. Airtel — DELETE everything (§2)

### 5.1 Airtel SMS

| Item | Location |
|---|---|
| Primary India sender (whole Lambda) | `messaging/sms-in/airtel/handler.py`, `wecare-sms-in-airtel` |
| Static-IP proxy `52.3.44.165:8899` | `sms-in/airtel/handler.py:99,120-176` · `outbound-sms/handler.py:52,538` |
| Second Airtel sender + v4/v5/v6 | `outbound-sms/handler.py:435-636` |
| Dead legacy wrapper | `outbound-sms/handler.py:638-651` |
| Sync Airtel call from calling | `whatsapp-calling/handler.py:1324,1412-1474` |
| Order SMS target | `ecommerce/wix-store/handler.py:1589` |
| Voice-path SMS routing | `voice-in/c2c/handler.py:1001` · `voice-in/obd/handler.py:1680` |
| Secrets | `wecare/airtel-iq`, `wecare/airtel/sms` |
| IAM | `amplify/iam-policies.ts:336` |
| Alarms + log retention | `amplify/backend-resources.ts:182-190` |
| Data models `AirtelSMS`, TTL config | `amplify/data/resource.ts:317-343` · `amplify/backend.ts:53-57` |
| Deploy map | `scripts/deploy_all_lambdas.py:159` · `scripts/deploy_all.ps1:112,191` |
| Dashboard send tab | `src/pages/dm/sms/index.tsx:288-291,688-691` |
| Steering doc | `.kiro/steering/AIRTEL-IQ-SMS-REPLY-EMAIL.md` |
| **Plaintext credentials in a docstring** | `sms-in/airtel/handler.py:20-23,49-55` — **SCRUB** |

### 5.2 Airtel voice — out of SMS scope, still prohibited

`voice-in/c2c` (`wecare/airtel/c2c`, `iqvoice.airtel.in`), `voice-in/obd`
(`wecare/airtel/obd`), `voice-in/cdr` (`wecare/airtel/sms` + Sinch whitelist note
at `:1301-1308`), plus models `AirtelC2C`/`VoiceCDR`/`OBDCampaign` in
`data/resource.ts:390-530`.

§2 says Airtel is prohibited as an active provider, which includes voice. §1
assigns PSTN voice to Plivo. **Airtel voice removal is larger than Airtel SMS
removal** and is sequenced separately in the migration plan — the C2C/OBD/CDR
subsystems have their own dashboards, tables and webhook endpoints.

### 5.3 What Airtel removal unlocks

The Airtel SMS proxy is **one of only two jobs** the Lightsail box does. Removing
Airtel SMS deletes the `:8899` dependency entirely, leaving only the SIP media
leg — which is what the Plivo cutover replaces. **Lightsail retirement is an
outcome of this migration.**

---

## 6. Plivo — KEEP voice, never SMS

| Item | Location | Disposition |
|---|---|---|
| Answer URL handler | `messaging/plivo-answer/handler.py` | **KEEP** |
| Application `12775976954213184` `WECARE-WHATSAPP-IVR` | live console | **KEEP** — do not recreate (§20) |
| App SIP URI `sip:12775976954213184@app.plivo.com` | — | **NEW** — must be verified (§24) |
| Endpoint SIP `sip:wecarewaivr203331794466262@phone.plivo.com` | live console | **KEEP** — do not recreate (§23) |
| `sip_auth_type='credential'` | live console | KEEP — inbound SIP already authenticated |
| `?token=` gate on all three URLs | live console + `wecare/plivo-answer` | KEEP |
| `POST /plivo/fallback` | — | **NEW** (§22, §26) |
| `POST /plivo/hangup` | — | **NEW** (§22, §26) |
| `POST /plivo/events` | — | **NEW** (§26) |
| **V3 signature validation** | — | **NEW** (§27) — none exists anywhere |
| Post-call SMS side effect | `plivo-answer/handler.py:145-192` | **REWIRE** through the orchestrator |
| `plivo==4.62.0` | `requirements-dev.txt:73` | dev-only, not bundled — leave |
| Plivo SMS | — | **must never exist** |

No Plivo SMS code exists today, which makes §54's "Plivo SMS = NO" already true.
The CI gate must keep it true.

---

## 7. Meta — KEEP

| Item | Location | Disposition |
|---|---|---|
| WhatsApp Cloud API messaging | ~20 handlers, Graph `v25.0` | **KEEP** (§19) |
| Calling settings read/write incl. SIP | `whatsapp-business-api/handler.py:2530-2751` | **KEEP** — the repoint tool |
| SIP password redaction | `:2556-2585` | KEEP |
| Webhook signature + replay guard | `whatsapp-calling/handler.py:285-397` | KEEP |
| `appsecret_proof` helper | `lambda_utils/appsecret.py` | **REWIRE** — 4 inline re-implementations should use it |
| Unreachable `token2` branch | `whatsapp-calling/handler.py:91,108-127` | **DELETE** — `WABA2_IDS = set()` |
| Post-call SMS/RCS fan-out | `whatsapp-calling/handler.py:1333-1585` | **REWIRE** through the orchestrator |

---

## 8. Google — all NEW

| Item | Disposition |
|---|---|
| `GoogleAuthService`, incremental OAuth | **NEW** (§31) |
| `GoogleContactsService` / People API | **NEW** (§32) |
| `GoogleAdsService`, read-only in V1 | **NEW** (§33) |
| Caller-lookup chain | **NEW** (§32) |

Existing Google-adjacent code is **not** reusable for this: `marketing-ads`
handles Meta CTWA ads, and `scripts/google-*.sh` are one-off shell utilities.

Credentials already in Secrets Manager: `wecare/google/cloud` (unified API key,
verified live against PageSpeed/Places/Geocoding), `wecare/seo/google-oauth`
(client id + secret), `wecare/google/ads` (customer id `836-758-9699`, manager
`427-041-2231`).

**Blocked:** `GOOGLE_ADS_DEVELOPER_TOKEN` is **not** present in
`wecare/google/ads`. Google Ads API cannot authenticate without it.

---

## 9. Truecaller — all NEW

| Item | Disposition |
|---|---|
| `POST /auth/truecaller/callback` | **NEW** (§35) — nonce, replay protection, SSRF guard, no token logging |
| Verification flow | **NEW** (§34) — reuse existing app, do not create another |
| Truecaller for Business caller branding | **NEW** (§36) — stays `false` until KYC approval |

Only the secret definition exists (`scripts/store_provider_secret.py:107-116`).
`wecare/truecaller` now holds `app_key`, `app_name`, `app_domain`,
`callback_url`. Nothing reads it.

---

## 10. TTS — consolidate 4 implementations

| Existing | Location | Disposition |
|---|---|---|
| `/whatsapp-voice/tts` | `whatsapp-voice/handler.py:282-464` | **REWIRE** behind `TextToSpeechService` |
| `/site-language/tts` | `core/site-language/handler.py:332-341` | REWIRE — best pattern: discovers voices via `describe_voices` |
| `/voice-in/obd/tts` | `voice-in/obd/handler.py:555-562` | REWIRE |
| `_generate_ivr_tts_audio` | `whatsapp-calling/handler.py:2115-2174` | REWIRE |
| `TextToSpeechService` abstraction | — | **NEW** (§30) |
| `VoiceScriptComposer` + approval flow | — | **NEW** (§28, §29) |

`plivo-answer` deliberately uses **no** TTS (pre-recorded audio only) and its
tests enforce that. Do not add TTS to it.

---

## 11. Tooling and governance — NEW

| Item | Disposition |
|---|---|
| `scripts/check-provider-policy.sh` | **NEW** (§44) — land before the migration |
| `.env.example` | **NEW** (§45) — only `.env.local.example` exists |
| `scripts/test-aws-sms.sh`, `test-india-aws-sms.sh` | NEW (§46) |
| `scripts/sync-sinch-rcs-templates` | NEW (§12) |
| `scripts/test-aws-rcs`, `test-rcs-{ios,android,fallback}` | NEW (§46) |
| `scripts/test-plivo-{webhook,application-sip}`, `test-whatsapp-sip`, `check-sip-tls` | NEW (§46) |
| `scripts/test-google-{oauth,contacts,ads}`, `test-truecaller-callback` | NEW (§46) |
| `scripts/test_call_paths.py` | **KEEP** — already the authoritative call-leg verifier |

---

## 12. Secrets — current state (31 in account `775261844268`)

| Secret | Provider | Disposition |
|---|---|---|
| `wecare/airtel-iq`, `wecare/airtel/sms` | Airtel SMS | DELETE after cutover |
| `wecare/airtel/c2c`, `wecare/airtel/obd`, `wecare/airtel-iq` | Airtel voice | DELETE in the voice phase |
| `wecare/sinch/sms` | Sinch SMS | DELETE (already unusable — no `oauth_token`) |
| `wecare/sinch/rcs` | Sinch RCS | KEEP |
| `wecare/meta-system-user-token` | Meta | KEEP |
| `wecare/plivo/api`, `wecare/plivo`, `wecare/plivo-answer` | Plivo | KEEP |
| `wecare/google/cloud`, `wecare/google-api-key`, `wecare/google-maps` | Google | KEEP — all three hold the same unified key `sha256:0bd4beb6496a` |
| `wecare/seo/google-oauth` | Google OAuth | KEEP |
| `wecare/google/ads` | Google Ads | KEEP — **missing `developer_token`** |
| `wecare/truecaller` | Truecaller | KEEP — no consumer yet |
| `wecare/elevenlabs` | ElevenLabs | KEEP — webhook live, no agent yet |

Deleting a secret requires pointwise confirmation
(`.kiro/steering/maintenance-reporting.md`). No secret is deleted during the code
migration; removal is a separate, later step once nothing reads it.

---

## 13. Counts to drive §49 acceptance

Measured at baseline `41dc41c2`:

```
SMS senders                         3   -> target 1 (AwsSmsProvider)
distinct SMS providers in runtime   4   -> target 1 (AWS)
   Airtel IQ, Sinch, classic Pinpoint, EUM v2
Airtel runtime references          14 files
Sinch SMS runtime references        5 files
Plivo SMS references                0   (already compliant)
AWS RCS implementations             0   -> target 1
provider abstractions               0   -> target: SmsService + 2 RCS providers + orchestrator
AWS SMS delivery-receipt consumers  0   -> target 1
```

Acceptance is met when the first two rows read `1` and `1`, Airtel and Sinch SMS
read `0`, and `scripts/check-provider-policy.sh` exits `0` in CI.
