---
inclusion: always
---

# Owner-nominated QA recipient

    +918100640044

Nominated by the owner on 2026-09-22 for **RCS, SMS and WhatsApp** test sends.
Referred to as the "wecare test number".

This resolves the `WAITING_FOR_OWNER` block that was holding the Phase 2 WhatsApp
handset round trip, every live-send check in Phase 3, and the Android/iPhone
rendering QA in the Sinch RCS audit.

## Verified properties

Measured against the repo's own helpers, not assumed:

| Property | Value |
|---|---|
| E.164 | `+918100640044` |
| Country | India (`IN`), so India DLT and India RCS rules apply |
| Collides with a business number | **No** |
| SMS routing | AWS End User Messaging `ap-south-1`, DLT key `ivr-default` |
| RCS routing | Sinch India — currently `INELIGIBLE_UNSUPPORTED` only because `SINCH_RCS_ENABLED` is off |
| `live_smoke` behaviour as `WA_QA_RECIPIENT` | QA number allowed; a customer number and all three business numbers refused |

The business-number check matters: the registry in
`lambda_utils/notifications/events.py` holds `918031830030`, `919330994400` and
`919903300044`, and this number is none of them. So it passes the backstop that
exists to stop us messaging ourselves, rather than being silently refused by it.

## Recording is not enabling

Writing this number down does **not** switch anything on. A live send still
requires a deliberate, separately-authorized step:

| To send | What must change | Current state |
|---|---|---|
| WhatsApp smoke test | `WA_LIVE_SMOKE_TEST=true` **and** `WA_QA_RECIPIENT=+918100640044` on `wecare-outbound-whatsapp` | both **absent** |
| Connected-call notification | `PSTN_CONNECTED_NOTIFICATIONS_ENABLED=true` **and** `NOTIF_CUTOVER_WATERMARK` set | both **absent** |
| India RCS | `SINCH_RCS_ENABLED=true` | absent |

`WA_LIVE_SMOKE_TEST` is a **lockdown, not a permission**: switching it on narrows
sending to this number only and halts customer messaging. That is the correct
direction for a safety switch, and it is why it must not be left on.

## The masked-log ambiguity

Its last four digits are `0044` — **the same as `+919903300044`**, the secondary
WhatsApp Calling number (WABA2, Meta phone id `1055232054343117`).

Every log site in this codebase masks phone numbers to the last four, so a line
reading `...0044` is ambiguous between the QA recipient and a business number.
When reading logs during QA, disambiguate on `direction`, `channel` or the
delivery id rather than on the masked suffix. Do not widen the masking to resolve
it — a full number in a log is a disclosure, and the ambiguity is cheaper than
that.

## Use it only as a recipient

It is a destination for test messages. It is **not**:

- a business sender or caller ID
- a Sinch RCS *test number* in the provisioning sense (those are registered
  against the RCS Sender and reported by `testNumberStates[]`; this number has not
  been shown to be one)
- a substitute for the per-number connected-call matrix, which is keyed on the
  business number that carried the call

Device QA metadata — handset make, OS version, carrier, whether RCS is actually
enabled on it — is tracked separately in `docs/rcs-ios-android-testing.md`. A
capability list is not proof of which OS answered.
