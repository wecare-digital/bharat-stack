# Feature flag register

Seeded 2026-09-21 from source grep at HEAD `4baf4236`. Source default is recorded
here; the **deployed** environment value is a separate measurement and is not yet
taken — a Lambda's `Environment` block can override the source default.

A permanent forgotten flag is a defect. Every row needs a retirement date once
its rollout completes.

| Flag | Owner | Source default | Deployed value | Environments | Prerequisites | Cohort | Telemetry | Rollback trigger | Retire by | State |
|---|---|---|---|---|---|---|---|---|---|---|
| `PSTN_BROWSER_ROUTING_ENABLED` | PSTN | `false` (`messaging/plivo-answer/handler.py:87`) | **NOT MEASURED** | prod | Cognito token route, endpoint/session/presence lifecycle, softphone state machine, `PSTN_AGENT_ENDPOINT` set | none yet | answer rate, hangup cause, browser readiness | any call not reaching an agent | Phase 10 + observation window | held `false` |
| `PSTN_CONNECTED_NOTIFICATIONS_ENABLED` | Notifications | `false` (`shared/lambda_utils/pstn/notifications.py:81`) | **NOT MEASURED** | prod | one canonical dispatch owner (`NOTIF-OWN-001`), delivery store resolved (`NOTIF-STORE-001`), migrated suppression keys | QA recipient only | logical deliveries vs attempts, duplicate count, DLQ age | any duplicate customer message | Phase 10 + observation window | held `false` |
| `WA_LIVE_SMOKE_TEST` | WhatsApp | **not present in source** | n/a | — | required by the brief for any live send, with an explicit `WA_QA_RECIPIENT` | — | — | — | — | `NOT IMPLEMENTED` — gap, see `TEST-001` |
| `WA_QA_RECIPIENT` | WhatsApp | **not present in source** | n/a | — | pairs with the flag above | — | — | — | — | `NOT IMPLEMENTED` — gap |

## Notes

- `plivo-answer` already fails closed in the right direction: if
  `PSTN_BROWSER_ROUTING_ENABLED` is true but `PSTN_AGENT_ENDPOINT` is unset it
  raises rather than silently dropping the call (`handler.py:228`).
- `voice-in/c2c/handler.py:139` references the routing flag in an operator-facing
  message; confirm that path is not a second routing decision point.
- There is currently **no** live-send guard flag for WhatsApp. Until
  `WA_LIVE_SMOKE_TEST` and `WA_QA_RECIPIENT` exist, no automated live WhatsApp
  send may be attempted.

## Phase 1 action

Read the deployed `Environment` block of `wecare-plivo-answer`,
`wecare-whatsapp-calling`, `wecare-voice-in-c2c` and `wecare-voice-in-obd` and
fill the **Deployed value** column. A source default is not a production fact.
