# Meta Business Agent — setup status & checklist

Backend: `wecare-meta-business-agent` (deployed). Actions: `readiness`, `eligibility`,
`onboard`, `settings`/`settings_update`/`enable`/`disable`, `allowlist*`, `entities`.
Auth: Bearer + `appsecret_proof` from `wecare/meta-system-user-token`. Verified reaching Meta.

## Verified status (checked via API 2026-07-03)
| Step | Status | Notes |
|---|---|---|
| 6. App subscribed to WABA | ✅ done | WECARE.DIGITAL (app 2238810740192680) on both WABAs (2094615664435155, 2513394156072604) |
| 2–5. System user token | ✅ works | `wecare/meta-system-user-token` authenticates (appsecret_proof required) |
| 7. `messages` webhook field | ✅ | existing integration receives messages |
| 7. `standby` + `messaging_handovers` | ⚠️ manual | App Dashboard → WhatsApp → Configuration (required for agent standby routing) |
| 1. Meta Business AI ToS | ❌ BLOCKER | WhatsApp Manager → Meta Business Agent tab, per number. All agent endpoints 403 until accepted. |

## Remaining manual actions (no code left)
1. WhatsApp Manager → **Meta Business Agent** tab → accept ToS + set up for +91 93309 94400 and +91 99033 00044.
2. App Dashboard → WhatsApp → Configuration → subscribe **`standby`** and **`messaging_handovers`** webhook fields.

## After ToS accepted — go-live flow (via the Lambda)
1. `eligibility` → expect `{is_eligible: true}`.
2. `onboard` (channel=whatsapp) → returns `agent_id`; schedules data-prep jobs.
3. Configure knowledge/skills (configure group — add from OpenAPI specs when needed).
4. `enable` (settings rollout.enabled=true) → agent starts responding to NEW conversations.
5. Handle standby routing: inbound arrives on `standby` when agent has control; take control by
   sending a message; hand back via Thread Control (`pass`).

## Not yet wired
- API route `POST /meta-agent` — blocked by the 300-route cap on API `zllr9lrg7j`
  (raise the "Routes per API" quota, or reclaim slots by consolidating redundant routes).
- Configure/Operate endpoints (skills, knowledge, connectors, eval, test, thread-control) —
  add the same way from their per-endpoint OpenAPI specs.
