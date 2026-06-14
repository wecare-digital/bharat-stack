# Unified Message Table — Design & Decision

Answers: *"create one common table for channel — one constant, one table, channel as the
discriminator (row/heading), so multiple Lambdas read/write per channel."* Plus: where do
**SES/email**, **SMS**, **RCS**, **Voice + WhatsApp Calling** fit.

---

## 1. The key finding (we do NOT need a new table)

The schema **already has** the exact table you're describing. It's the `Message` model in
`amplify/data/resource.ts` → deployed as **`stack-wecare-digital-MessagesTable`**:

```ts
Message: {
  messageId   (PK)
  contactId
  channel     enum [ WHATSAPP, SMS, EMAIL, RCS ]   ← the discriminator you want
  direction   enum [ INBOUND, OUTBOUND ]
  content, status, timestamp, errorDetails
  whatsappMessageId, mediaId, s3Key, mediaUrl
  senderPhone, senderName, senderBsuid, senderUsername, receivingPhone, awsPhoneNumberId
  transcription, detectedLanguage
  expiresAt   (TTL — 30 days)
  GSIs: contactId-index, whatsappMessageId-index
}
```

It is **one table, with `channel` as a first-class field** — exactly the ask. It is already
written to by `outbound-email` (`channel='EMAIL'`). It has TTL, a `contactId` GSI, and every
field the other channels need.

### Why we have a mess today
The system **drifted**. Instead of everyone using `MessagesTable`, each channel grew its own
store:

| Channel | Writes to (today) | Should converge to |
|---|---|---|
| WhatsApp | `WhatsAppInboundTable` + `WhatsAppOutboundTable` (split by direction) | `MessagesTable` |
| Email/SES | `MessagesTable` ✅ already correct | `MessagesTable` |
| SMS (AWS) | `SmsAwsTable` | `MessagesTable` |
| RCS | `RcsMessagesTable` (also points some writes at `WhatsAppOutboundTable`) | `MessagesTable` |
| Voice (AWS) | `VoiceAwsTable` | *(calls — see §4)* |

So the answer to *"can these be shared with the WhatsApp table?"* — **yes**, but the right
canonical target is **`MessagesTable`**, not the WhatsApp split tables. `MessagesTable` is a
single table (your "one table" requirement), already has the `channel` enum, and has TTL.

---

## 2. The canonical write contract (one shared helper for all Lambdas)

Rather than each Lambda hand-rolling its own `put_item`, we add **one shared helper**:
`amplify/functions/shared/lambda_utils/message_store.py`. Every channel Lambda calls the same
`put_message(...)` so rows are always shaped identically. This is the "one constant" you asked
for — the contract lives in exactly one place.

```python
from lambda_utils.message_store import put_message, query_by_contact, scan_channel

put_message(
    channel='sms',            # whatsapp | sms | email | rcs
    direction='outbound',     # inbound | outbound
    contact_id=cid,
    content=text,
    status='sent',            # pending | sent | delivered | read | failed
    message_id=mid,           # optional — auto uuid if omitted
    # channel extras pass straight through and are stored as-is:
    provider_message_id=..., media_url=..., error_code=..., error_details=...,
)
```

Stored shape (normalized — lowercase `channel`/`direction`/`status`, Decimal epoch `timestamp`,
30-day `expiresAt` TTL) matches what `messages-read` already expects, so the Unified Inbox reads
it with no extra mapping.

---

## 3. Rollout — phased, zero-downtime, non-breaking

We do **not** do a big-bang migration. Each channel is converted independently and tested.

**Phase 0 — foundation (no behavior change).** ✅ build `message_store.py`. Nothing wired in
yet, so nothing can break.

**Phase 1 — dual-write, one channel at a time.** Each send + inbound handler ALSO calls
`put_message()` into `MessagesTable`. Its existing table stays untouched, so existing per-channel
pages keep working. Order: SMS → RCS → Voice-as-call-event → (WhatsApp last, highest traffic).
Test each channel end-to-end before the next.

**Phase 2 — unify reads (optional).** Point `messages-read` at `MessagesTable` via a
`channel-index` GSI (see §5), backfill historical rows with a one-off script, then retire the
per-channel scans. Old tables can be left as cold archives or dropped after the TTL window.

Today `messages-read` already does **read-time aggregation** when `channel=ALL` (scans
SMS/RCS/Email stores and tags each row). That gives a working Unified Inbox **now**, while
Phase 1 dual-write makes it efficient and consistent over time.

---

## 4. Voice + WhatsApp Calling — these are NOT messages

A call is an **event** (duration, direction, recording, CDR), not a chat message. Mixing them
into the message inbox makes both worse. Decision:

- **Calls stay in their own tables** (`VoiceAws`, `VoiceCall`, `VoiceCDR`, `WhatsAppCalling`) and
  surface in a separate **Calls view** (call log + recording + transcript).
- **Optional bridge:** a call may write ONE lightweight `messageType:'call'` row to
  `MessagesTable` (e.g. "📞 Missed call · 0:42") so the unified timeline shows that a call
  happened — detail still lives in the Calls view. This is opt-in, not required.
- `messages-read` aggregation is therefore restricted to **message channels only**
  (SMS/RCS/Email) — voice/calls are intentionally excluded. *(Already done + deployed.)*

WhatsApp Calling and the AWS voice recorder are unrelated systems — Calling = WhatsApp Business
Calling API; voice-aws = AWS telephony/OBD. They share the Calls view but not the message table.

---

## 5. The one GSI to add (for Phase 2 scale)

To filter `MessagesTable` by channel efficiently (instead of scan-with-filter), add a
`channel-index` GSI (partition key `channel`, sort key `timestamp`). Until then, Phase 1's
`contactId-index` + per-conversation reads are already efficient; the full-inbox channel filter
uses a bounded scan. Add the GSI via the schema (`resource.ts`) so it's tracked in CI, or via
boto3 `update_table` to match the existing route-patching pattern. Adding a GSI is
non-destructive (no table rebuild).

---

## 6. Decision summary

| Question | Answer |
|---|---|
| One common table with a channel discriminator? | **Yes — `MessagesTable` already is it.** Don't create a new one. |
| One constant / one contract for all Lambdas? | **`message_store.put_message()`** — single shared helper. |
| Can SMS/RCS/Voice share the WhatsApp table? | Share **`MessagesTable`** (better than the WhatsApp split tables). |
| Where does SES/email go? | Already in `MessagesTable` ✅ — it's the reference implementation. |
| Voice + WhatsApp Calling? | **Separate Calls view.** Optional `messageType:'call'` breadcrumb row only. |
| Migration risk? | **None up front** — phased dual-write, one channel at a time, old tables kept. |

**Net infra:** 0 new tables, +1 shared helper module, optional +1 GSI. No deletions.
