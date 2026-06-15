# Unified Inbox — Final Architecture, Retirement Plan & 360° Review

Status as of this session: **single canonical message table is LIVE and tested.**
Contacts were already a single shared table. Reads now use GSIs (no scans), TTL bounds size.

---

## 1. Backend architecture (final)

```
                         WRITES (each channel)                         READS
  ┌────────────────────┐                                   ┌──────────────────────────┐
  │ inbound-whatsapp    │──put_message(whatsapp,inbound)─┐  │ messages-read  /messages │
  │ outbound-whatsapp   │──put_message(whatsapp,outbound)┤  │  • contactId  → contactId-index (conversation)
  │ sms-aws             │──put_message(sms)──────────────┤  │  • channel    → channel-index   (filter)
  │ rcs-send            │──put_message(rcs)──────────────┤  │  • ALL        → channel-index ×4 + merge
  │ outbound-email      │──put_message(email)────────────┤  │  → bounded Query, never Scan
  └────────────────────┘                                 │  └──────────────────────────┘
                                                          ▼               ▲
                              ┌───────────────────────────────────────────────────┐
                              │   stack-wecare-digital-MessagesTable  (CANONICAL)  │
                              │   PK id · channel · direction · content · status   │
                              │   timestamp · mediaUrl · s3Key · errorCode …       │
                              │   GSIs: contactId-index, channel-index             │
                              │   TTL: expiresAt (30d) → self-cleaning, bounded    │
                              └───────────────────────────────────────────────────┘
            shared contract: lambda_utils/message_store.py  (one put_message for all)

  Contacts: ONE stack-wecare-digital-ContactsTable (GSIs: bsuid, email, phone) — all channels.
  Calls (NOT messages): VoiceAws · VoiceCDR · VoiceCall · WhatsAppCalling → separate Calls view.
```

### What changed this session
- `message_store.py` — single write contract; lowercase channel; **sparse contactId** (omits empty so the GSI key never errors).
- Dual-write added to: inbound-whatsapp, outbound-whatsapp, sms-aws, rcs-send. Email already native.
- `MessagesTable`: added `contactId-index` + `channel-index` GSIs; **enabled TTL** on `expiresAt`.
- `messages-read`: rewritten to read **only** `MessagesTable` via GSIs; removed 221 lines of legacy multi-table scan code.
- Backfilled 433 historical rows (WhatsApp + RCS) into `MessagesTable`.

### Verified (live invoke)
`ALL`=432 (RCS 416 / WhatsApp 10 / SMS 6), **0 duplicate messageIds**, channel filters return correct
counts, and a cross-channel conversation (contact 918609804665) correctly merges WhatsApp 6 + SMS 6.

---

## 2. Frontend architecture (final)

```
  ★ WhatsApp Inbox  /dm/whatsapp        → WhatsApp-only (send box, WABA, templates) — unchanged
  📥 Messages (unified) /dm/logs        → cross-channel view
        • channel filter: All · WhatsApp · SMS · Email · Voice · RCS
        • per-row channel badge (distinct themed colors) + status badge (design-token palette)
        • reads api.listMessages() → messages-read (single table)
  Channel tools  /dm/sms · /dm/rcs · /dm/ses · /dm/whatsapp/* → keep send/campaign/config per channel
```

Channel + status badges now use distinct, on-brand colors (mirrors `src/lib/design-tokens.ts`):
WhatsApp green · SMS blue · Email amber · RCS teal · Voice violet.

---

## 3. Table retirement plan (the "no duplicate tables" answer)

**Why duplication exists right now:** dual-write is a *transition bridge*, not the end state.
Each channel still writes its own legacy table AND `MessagesTable`. That is intentional and
temporary — it let us converge reads with zero downtime. The end state is **write once** to
`MessagesTable` and drop the legacy message tables.

### KEEP forever (not messages)
| Table | Why |
|---|---|
| `ContactsTable` | the single canonical contacts table (already unified) |
| `VoiceAwsTable`, `VoiceCDRTable`, `VoiceCalls`, `WhatsAppCallingTable` | **calls**, not messages |
| `DLTTemplates`, `WhatsAppVoiceTable` (TTS log), `AirtelSMSTable` (provider-specific) | not part of the unified message store |
| `MessagesTable` | the canonical target |

### RETIRE after repoint + soak (message logs, now duplicated)
`WhatsAppInboundTable` · `WhatsAppOutboundTable` · `SmsAwsTable` · `RcsMessagesTable`

**These cannot be deleted yet** — deleting now WOULD break code. They still have live readers
beyond `messages-read`:

| Legacy table | Still read by | Repoint needed before delete |
|---|---|---|
| WhatsAppOutbound | delivery-status updates (`whatsappMessageId-index`), payment lookup (`paymentReferenceId-index`), `template-analytics`, `bulk-worker` | add `whatsappMessageId-index` + `paymentReferenceId-index` to MessagesTable; repoint these |
| WhatsAppInbound | `invoice-engine` payment scan, status updates, ad-attribution | repoint to MessagesTable |
| SmsAwsTable | `sms-aws` GET/list/delete/clear (SMS logs page) | repoint sms-aws reads to MessagesTable (channel=sms) |
| RcsMessagesTable | `rcs-send` list, `rcs-dlr` status updates | repoint rcs reads/DLR to MessagesTable |

### Phase 3 — COMPLETE ✅ (deployed + verified)
1. ✅ GSIs on `MessagesTable`: `contactId-index`, `channel-index`, `whatsappMessageId-index`, `paymentReferenceId-index` + TTL on `expiresAt`.
2. ✅ WhatsApp delivery-status updates mirror onto canonical (same `id`); Airtel + RCS DLR mirror status too.
3. ✅ `sms-aws` (verified 12) and `rcs-send` (verified 50) list/get/delete read canonical (filter by channel).
4. ✅ `messages-read ?stats=count` counts canonical across all channels (verified 445).
5. ✅ Payment `payment_request` + `payment` records dual-write to canonical (dashboard payments read canonical).
6. ✅ Fixed: `message_store` uses dedicated `UNIFIED_MESSAGES_TABLE` env (was hijacked by handlers reusing `MESSAGES_TABLE`).

### Phase 4 — IN PROGRESS (dual-write stopped; soak before delete)

**Done ✅ (Phase 4a):** `sms-aws`, `rcs-send`, `rcs-dlr` now write **only** to the canonical
table. `SmsAwsTable` + `RcsMessagesTable` are **write-free** (no new data), retained read-only
as a safety reference during the soak. All their readers already query canonical.

**Soak (now):** monitor the canonical table for parity/health while the legacy SMS/RCS tables
sit idle. No code reads or writes them.

**Final step (pending — irreversible):** after the soak, delete `SmsAwsTable` +
`RcsMessagesTable` (+ remove their now-dead env vars). A ready-to-run delete script can be added
when you decide to pull the trigger.

**`WhatsAppInbound/Outbound` — KEEP** as WhatsApp's specialized operational store (template
analytics, invoicing, bulk, ad-attribution). The unified inbox already reads WhatsApp from
canonical via dual-write. Not deleted.

### Phase 5 — conversation-grouped unified inbox UI (independent, non-destructive)
Build `/dm/inbox` grouped-by-contact threaded view over the canonical table (channel badges per
bubble, "reply via {channel}" deep-links). Can be built anytime; doesn't depend on Phase 4.

---

## 4. 360° review — improvements, gaps, best practices

### Performance / overload (addressed)
- ✅ Reads are bounded **Query** calls on GSIs, never full-table scans.
- ✅ **TTL (30d)** on `expiresAt` keeps the table small automatically.
- ✅ On-demand billing → no throughput to provision; adaptive capacity absorbs bursts.
- ⚠️ `channel-index` PK has only 4 values (hot-partition risk at very high scale). Fine at current
  volume on-demand; if traffic grows, shard the PK as `channel#YYYYMMDD` and query the needed days.
- ⚠️ The `ALL` view issues 4 channel queries then merges client-side in the Lambda — bounded by
  `limit` per channel. Good enough; for huge volumes add cursor pagination.

### Data integrity (addressed + watch)
- ✅ messageId dedup guarantees no double rows during the dual-write window.
- ✅ Sparse `contactId` (empty omitted) prevents GSI key errors for unmatched messages.
- ⚠️ `expiresAt` is copied from source on backfill — old rows past expiry are TTL-deleted (correct,
  but means >30-day history won't appear in the unified view; export first if you need it).

### Best-practice gaps to close (recommended next)
- **Status/DLR/payments still target legacy tables** — Phase 3 above. Until then, delivery-status
  on the unified view reflects the dual-written copy's status at send time, not later DLR updates.
  (Fix: repoint status updates to also update `MessagesTable`, or add `whatsappMessageId-index`.)
- **`?stats=count`** still counts WhatsApp tables only — update to `MessagesTable` for true totals.
- **IaC drift**: GSIs/TTL were added via boto3 (consistent with the route-patching pattern) but the
  `stack-wecare-digital-*` tables aren't in CDK. Recommend codifying them in a CDK/custom-resource
  stack so infra is reproducible.
- **Security**: `messages-read` is authenticated (Cognito). Keep PII (phones/content) out of logs —
  `mask_phone`/`redact_pii` already exist; ensure new code paths use them.

### UX / UI
- ✅ Distinct channel + status badges (design-token palette) on the unified view.
- 🔜 Optional: upgrade `/dm/logs` from a table into a conversation-style unified inbox (grouped by
  contact, channel badge per bubble, "reply via {channel}" deep-links to the channel tool).
- 🔜 Cross-channel search (Ctrl-K) over `MessagesTable` once `whatsappMessageId`/content indexing exists.

### AI (existing system — reuse, don't rebuild)
One `/ai/assist` gateway over `ai-generate-response` (Bedrock) with a `task` discriminator powers
per-page features (reply suggestions, summarize, classify, analyze failures) — all logged to
`AIInteraction`. The unified table makes cross-channel summaries/insights trivial.

### Cost
- Single table + TTL → lower storage and fewer scans than 5 growing tables.
- Dual-write doubles writes *temporarily* (Phase 1–2); ends after Phase 3 step 5.

---

## 5. Net infra delta this session
- **+2 GSIs** + **TTL** on `MessagesTable`. **0 tables created, 0 deleted.**
- Dual-write wired into 4 Lambdas; `messages-read` simplified to one table; email + helper consistent.
- Frontend: themed badges on the unified view.
