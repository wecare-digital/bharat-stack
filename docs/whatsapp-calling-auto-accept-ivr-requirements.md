# WhatsApp Calling — Auto-Accept + Play IVR: Requirements Breakdown

## What Needs to Happen (A → B → C Flow)

### A. Inbound Call Arrives (Webhook → Lambda)

1. User calls business WhatsApp number
2. Meta sends `connect` webhook with:
   - `call_id` — unique call identifier
   - `from` — caller's phone number
   - `session.sdp` — SDP offer (WebRTC session description)
   - `metadata.phone_number_id` — business phone number Meta ID
3. Lambda stores call log in DynamoDB (status: `ringing`)
4. Lambda checks auto-pickup config from SystemConfig table

**Current Status:** ✅ Working — webhook received, call logged
**Blocker:** None

---

### B. Auto-Accept the Call (Lambda → Meta Graph API)

**Step B1: pre_accept**
- Lambda sends `POST /{phone_number_id}/calls` with `action: pre_accept`
- This tells Meta "we intend to answer" — extends the timeout window
- Caller sees "connecting..." instead of ringing

**Step B2: accept with SDP answer**
- Lambda sends `POST /{phone_number_id}/calls` with `action: accept` + `sdp_answer`
- This establishes the WebRTC media session
- Caller hears audio from this point

**Current Status:** ❌ BLOCKED — 403 permission error on both pre_accept and accept
**Blocker:** Meta token lacks calling permission (see emails above)

**What's Needed to Unblock:**
- Meta must confirm the exact permission/enablement required
- Token may need regeneration with calling scope
- Or WABA may need calling feature enabled by Meta

**Additional Blocker — SDP Answer Generation:**
- `accept` requires a valid SDP answer (WebRTC session description)
- Lambda (server-side Python) cannot generate SDP answers natively
- Options to solve:
  - **Option 1:** Frontend browser WebRTC (current approach — user clicks Answer)
  - **Option 2:** Server-side WebRTC stack (GStreamer, Opal, Opal) on EC2/ECS
  - **Option 3:** SIP integration with FreeSWITCH/Asterisk (if SIP enabled on WABA)
  - **Option 4:** Use a headless browser (Puppeteer) on Lambda/ECS to generate SDP

---

### C. Play IVR Audio to Caller (After Call Connected)

**Option C1: In-call audio via WebRTC (ideal)**
- After accept with SDP answer, WebRTC media session is active
- Send audio stream through the WebRTC peer connection
- Caller hears IVR audio during the call
- Requires server-side WebRTC stack (Option 2 or 3 from above)

**Option C2: WhatsApp audio message (current workaround)**
- After pre_accept, send a WhatsApp audio message to the caller
- Caller receives audio as a chat message, NOT in-call audio
- Call itself has no audio — terminates after timeout
- This is what `_auto_pickup_and_play` currently does

**Option C3: SIP + Media Server (production-grade)**
- Configure SIP on the WABA phone number
- Route calls to FreeSWITCH/Asterisk
- Play IVR audio via SIP media
- Handle DTMF input for IVR menu
- Transfer to agent or AI bot

**Current Status:** ⚠️ Partially working (Option C2 only — audio message, not in-call)
**Blocker:** Cannot play in-call audio without WebRTC/SIP stack + 403 blocks even the workaround

---

## Summary: What's Broken and Why

| Step | What | Status | Blocker |
|------|------|--------|---------|
| A | Receive call webhook | ✅ Works | — |
| B1 | pre_accept | ❌ 403 | Token permission / WABA calling not enabled |
| B2 | accept + SDP answer | ❌ 403 + no SDP | Same + need WebRTC stack for SDP generation |
| C | Play IVR audio in-call | ❌ Not possible | Need B2 working + WebRTC/SIP media stack |
| C (workaround) | Send audio message | ⚠️ Partial | Works only if 24h messaging window is open |

## Immediate Action Items

1. **Send email to Meta** — get 403 resolved (permission/enablement)
2. **Send email to AWS** — confirm EUM Social calling support
3. **Once 403 resolved** — test pre_accept + accept with frontend WebRTC (browser SDP answer)
4. **For production IVR** — evaluate SIP integration vs server-side WebRTC

## Architecture Decision Needed

For true auto-accept + IVR (no human in the loop), choose one:

| Approach | Complexity | Latency | Cost | IVR Quality |
|----------|-----------|---------|------|-------------|
| Frontend WebRTC (browser) | Low | High (needs user) | Free | Good |
| Server WebRTC (GStreamer on ECS) | High | Low | Medium | Good |
| SIP + FreeSWITCH (EC2) | High | Low | Medium | Best (DTMF support) |
| SIP + Amazon Connect | Medium | Low | Per-minute | Best |
