---
inclusion: auto
name: sinch-rcs-india-only
description: Sinch RCS configuration and the India-only constraint. Use when touching RCS sending, RCS eligibility, phone-number normalisation for RCS, the wecare/sinch/rcs secret, or anything that might route a non-Indian recipient to Sinch.
---

# Sinch RCS is India only, and its credentials live in one place

Confirmed by the owner on 2026-09-23 and verified against the live account the same day.

## The configuration, as deployed

| Item | Value | Where it lives |
|---|---|---|
| Region | `us-east-1` | — |
| Sender | `wecare-rcs-send:live` | `POST /rcs/send` |
| DLR / inbound | `wecare-rcs-dlr:live` | `POST /webhook/sinch-rcs` |
| Secret | `wecare/sinch/rcs` | `username`, `password`, `project_id`, `app_id`, `bot_id` |
| Username | `wecaretrans` | **secret field, never an env var** |
| Project id | `c8114d03-eeb2-401d-a8f1-abb93594cb33` | `RCS_PROJECT_ID` |
| Conversation App | `01KQSB792X3R148D8ZGHQYW3SP` | `RCS_APP_ID` |
| Bot id | `69e0b2c980cbf50614ffa5fd` | secret field |
| Default template | `rcsmenu` | code default + `NOTIF_RCS_TEMPLATE_NAME` |

Authentication is a Keycloak **password grant** against Sinch India (formerly ACL Mobile):

```
POST https://auth.aclwhatsapp.com/realms/ipmessaging/protocol/openid-connect/token
grant_type=password  client_id=ipmessaging-client  username=<secret>  password=<secret>
```

Sending:

```
POST https://convapi.aclwhatsapp.com/v1/projects/{project_id}/messages:send
Authorization: Bearer <access_token>
```

`SINCH_RCS_ENABLED=true` on `wecare-voice-in-c2c`, `wecare-voice-in-obd` and
`wecare-whatsapp-calling`. It is an **opt-in** and defaults off.

## Do not migrate this to the global Sinch platform

Not `auth.sinch.com`. Not a `KEY_ID`/`KEY_SECRET` pair. Not
`*.conversation.api.sinch.com`. Those are a different account which does not carry this
project, and the symptom of "upgrading" is a blanket 401 on every send.

The current flow is known-good: **730 sends over 30 days with zero authentication
failures**. `tests/test_sinch_rcs_conformance.py` refuses those hostnames and key names, so
a migration fails the suite rather than production. If one is ever actually wanted it is a
separately planned change with its own credentials.

## Credentials come from Secrets Manager only

No username and no password in source, in an environment variable, or on a command line.

The username matters as much as the password, because the password grant authenticates with
the pair. A literal default is half a credential in source control — and it also **hides a
real fault**: a secret missing its username authenticates as the literal with an empty
password and returns a 401 that reads like a provider outage. Five such fallbacks were
removed on 2026-09-23, including the one in the token request itself.

`_load_sinch_credentials` declares every field, requires `username` + `password`, and on a
blank required field logs the missing **field names** and returns `{}` rather than
half-authenticating.

## India only, decided twice

Sinch serves Indian destinations. A non-Indian recipient is **refused, never rewritten**,
and the decision is made at two layers that must agree:

| Layer | Function | What it does |
|---|---|---|
| Eligibility | `notifications.policy.decide_rcs` | picks the provider, creates the delivery row |
| Send | `sinch_rcs._normalize_phone` | builds the identity, or returns `''` |

If they disagree, one of two failures follows: eligibility says Sinch and the sender
refuses, producing a delivery row that no-ops with nothing reporting a fault; or eligibility
says non-India and routes to AWS RCS, which is not provisioned, so a reachable Indian
customer silently loses the channel. `TestEligibilityAndSendingAgree` pins them together.

**Country logic has exactly one authority: `lambda_utils.comms.numbers`.** Do not add a
second normaliser. Two copies is precisely how the defect below survived — I started to add
a third during the 2026-09-23 fix and deleted it before committing.

### The defect this replaced

`_normalize_phone` ended with:

```python
if len(clean) >= 10:
    return '91' + clean[-10:]
```

Several countries are exactly ten digits in full E.164, so:

```
+65 8123 4567   Singapore -> 916581234567    a real, DIFFERENT Indian subscriber
+1 415 555 2671 US        -> 914155552671    a real, DIFFERENT Indian subscriber
```

The provider accepted the send and the message was delivered to a stranger. That is
misdelivery, not misrouting, and nothing reported a fault.

### `0` + ten digits is refused, deliberately

The Indian STD trunk form `09903300044` and the UK national format `07911123456` are
structurally identical, and both have ten digits starting in 6-9. Assuming India would be
the same mistake, just narrower.

Measured before deciding: all 13 `ContactsTable` rows store `+91` E.164 and **zero**
leading-zero forms exist in `ContactsTable` or `CrmLeads`. The special case served no real
input while making the sender disagree with the policy.

If an STD-formatted number ever must be accepted, normalise it **where the country is
known** — at the point of capture — not by guessing at send time.

## Known gaps

- `webhook_secret` is **absent** from `wecare/sinch/rcs`, so `POST /webhook/sinch-rcs`
  cannot verify Sinch's signature. 17 callbacks were refused over 30 days. Adding it is an
  owner action on the Sinch side.
- **559 of 730 sends failed** over 30 days, every one reporting *"Number is RCS disabled or
  Bot is not launched with the number's provider"* — the recipients are not RCS-capable,
  not a defect in this integration. `lambda_utils.rcs_status` classifies it as permanent so
  the failure is legible rather than retried forever.
- The `rcsmenu` template id and version are recorded as `UNVERIFIED` in the policy reason.
