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
| `WA_LIVE_SMOKE_TEST` | WhatsApp | `false` — absent means off (`shared/lambda_utils/live_smoke.py:FLAG_ENV`) | **absent** on `wecare-outbound-whatsapp:19`, measured 2026-09-21 | dev / QA only — **never** prod | `WA_QA_RECIPIENT` must be set, or the mode blocks every send | QA recipient only | `smoke_mode_request_blocked` / `smoke_mode_send_blocked` log events | any outbound send refused while the flag was believed off | end of Phase 2 handset QA | implemented, held **off** |
| `WA_QA_RECIPIENT` | WhatsApp | unset (`shared/lambda_utils/live_smoke.py:RECIPIENT_ENV`) | **absent** on `wecare-outbound-whatsapp:19`, measured 2026-09-21 | dev / QA only | owner must nominate the number; `WAITING_FOR_OWNER` | — | suffix only, never the number | — | with the flag above | implemented, unset |

## Notes

- `plivo-answer` already fails closed in the right direction: if
  `PSTN_BROWSER_ROUTING_ENABLED` is true but `PSTN_AGENT_ENDPOINT` is unset it
  raises rather than silently dropping the call (`handler.py:228`).
- `voice-in/c2c/handler.py:139` references the routing flag in an operator-facing
  message; confirm that path is not a second routing decision point.
- `WA_LIVE_SMOKE_TEST` is a **lockdown, not a permission**, and the direction is
  the whole point. Off (the production state) changes nothing. On, the sender
  refuses every recipient except `WA_QA_RECIPIENT`. Read the other way round —
  flag enables sending — the guard's failure mode would be "send to anyone" and
  the flag would have to be on in production for normal traffic, making it
  useless as a test switch.
- The consequence to keep in mind: turning it on in production **halts customer
  messaging**. That is the correct direction for a safety switch to fail, but it
  is why the row above says dev/QA only and why the deployed value is measured,
  not assumed. Verified absent on `:19`.
- Smoke mode with no `WA_QA_RECIPIENT` blocks **everything**, including the QA
  number. An operator who enables the mode and forgets the recipient sees zero
  sends immediately, rather than an unrestricted send window.
- Enforced in two places on purpose: `outbound-whatsapp/handler.py` returns a
  clean `403` right after recipient resolution (before the typing indicator, the
  `block_users` branch and every send branch), and `_send_direct_api` repeats the
  check at the wire. The second is the guarantee — a branch added later that
  forgets the first still cannot reach a customer. `tests/test_live_smoke_lockdown.py`
  pins both, and a RED proof confirmed that with the guard neutralised the same
  call reaches the Graph request.

## Phase 1 action

Read the deployed `Environment` block of `wecare-plivo-answer`,
`wecare-whatsapp-calling`, `wecare-voice-in-c2c` and `wecare-voice-in-obd` and
fill the **Deployed value** column. A source default is not a production fact.
