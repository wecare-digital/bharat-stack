# Meta — WhatsApp Business Username API access request

> **CONFIRMED STATUS (probed live against phone `1016149501586345`, Graph v25.0):**
> The username feature is **GATED / not enabled** for this account.
> `GET /{phone}/username_suggestions` → `147000` *"Username feature not available —
> This feature is not yet available for this account"* (error_subcode 2655129).
> The `username` field is not readable (`#100`), and `/set-username` / `/usernames`
> return `2500 Unknown path`. A `POST /{phone}` with a `username` field returns a
> misleading `200 {"success":true}` **no-op** — it does NOT claim a handle.
> **Action: send the request below to have Meta enable the feature**, then re-probe
> to confirm the exact GA edge name.

There are **two different "username" features**. Don't confuse them.

## 1. Business username (vanity handle, e.g. @wecaredigital)
A public handle for the **business**, claimed per phone number.
- API (implemented in `whatsapp-business-api/handler.py`):
  - `GET /<phone_id>/username` — current handle + status
  - `GET /<phone_id>/username_suggestions` — reserved suggestions
  - `POST /<phone_id>/set-username` — claim (`transfer_action`: `none` | `force_transfer`)
  - `POST /<phone_id>/set-username` with `{username:''}` — release
  - Exposed at `/wa-business/username*`. Format: 3–35 chars, `[a-z0-9._]`.
  - Error **147005** = handle is on another phone in your portfolio → retry with
    `transferAction=force_transfer` (or pass `autoForceTransfer=true`).
  - Uses the **Phone Number ID** (not WABA ID); needs `whatsapp_business_management`.
- **Availability:** rolled out by Meta in limited/gated waves. If the GET
  `/username_suggestions` call returns a permission/`#100`-type error for a WABA,
  access is **not yet enabled** for that account → send the email below.
- **How to confirm live status** (authenticated): call
  `GET /wa-business/username/suggestions?phoneId=<metaPhoneId>` with a valid admin
  token, or check WhatsApp Manager → Phone numbers → Username. A normal response =
  live; an error = gated.

### Email draft (send to Meta Direct/Partner support or via Business Help Center)

> **Subject:** Request to enable WhatsApp Business Username API for our WABAs
>
> Hello Meta Partner Support,
>
> We operate WECARE.DIGITAL on the WhatsApp Cloud API (Direct API) and would like to
> request access to the **WhatsApp Business Username** feature/API for the following
> WhatsApp Business Accounts and phone numbers:
>
> - WABA ID `2094615664435155` — WECARE.DIGITAL — phone `+91 93309 94400`
>   (Phone Number ID `1016149501586345`) — desired username: `wecaredigital`
> - WABA ID `2513394156072604` — Manish Agarwal — phone `+91 99033 00044`
>   (Phone Number ID `1055232054343117`) — desired username: `manish`
>
> Our integration already implements the `/<phone_number_id>/username`,
> `/username_suggestions` (GET), claim (POST) and release (DELETE) endpoints and is
> ready to use the feature as soon as it is enabled for our accounts.
>
> Could you please confirm whether the Business Username API is available for these
> WABAs, and if it is gated, enable it or advise the eligibility requirements?
>
> Thank you,
> WECARE.DIGITAL

## 2. End-user usernames + Business-Scoped User ID (BSUID) — privacy rollout (2026)
This is a **separate, mandatory** change, not something to request — it is happening:
- BSUIDs appear in production webhooks from **~March 31, 2026**.
- Businesses can **send using BSUIDs from ~May 2026**.
- End-user usernames roll out to users through **mid/late 2026**; once a user adopts a
  username, **their phone number may stop appearing in webhook payloads** — you must
  identify them by BSUID.
- **Our readiness:** BSUID handling is already implemented across `inbound-whatsapp`,
  `outbound-whatsapp`, `whatsapp-calling`, and `whatsapp-voice` (recipient/BSUID
  extraction + routing). Keep contact records keyed so a BSUID can map to a contact
  even without a phone number.

Sources (industry summaries; verify against Meta's official changelog):
Twilio, Infobip, Gallabox, Vonage, Sinch BSUID guidance (2026).
