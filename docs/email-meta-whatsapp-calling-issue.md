# Email to Meta — WhatsApp Business Calling API: 403 Permission Error on pre_accept/accept

---

**To:** WhatsApp Business API Support / Meta Business Help Center
**Subject:** WhatsApp Calling API — 403 OAuthException (#200) on pre_accept and accept for both WABAs

---

Hi Meta Support,

We are experiencing a persistent 403 error when calling the `/{phone_number_id}/calls` endpoint with `action: pre_accept` and `action: accept` for inbound WhatsApp calls on both our WABAs.

**Error Response:**
```
HTTP 403
{
  "error": {
    "message": "(#200) You do not have the necessary permissions to send messages on behalf of this WhatsApp Business Account",
    "type": "OAuthException",
    "code": 200
  }
}
```

**Our Setup:**

| Item | WABA 1 (WECARE.DIGITAL) | WABA 2 (Manish Agarwal) |
|------|------------------------|------------------------|
| WABA ID | 1912405516040025 | 1633959101297902 |
| App ID | 2238810740192680 | 1224334845952721 |
| Phone Number ID | 960395407161423 | 997428863451102 |
| Display Number | +91 9330994400 | +91 9903300044 |
| Messaging Tier | TIER_2K | TIER_10K |
| Quality Rating | GREEN | GREEN |
| Token Type | System User | System User |
| Token Scopes | whatsapp_business_messaging, whatsapp_business_management, public_profile | Same |
| Calling Enabled | Yes (via POST /{phone_number_id}/settings with calling object) | Yes |
| Webhook Field | `calls` subscribed at both app-level and WABA-level | Same |
| API Version | v20.0 | v20.0 |

**What Works:**
- Webhook verification (GET with hub.challenge) — ✅
- Receiving `connect` webhooks with SDP offer when user calls — ✅
- Receiving `terminate` webhooks when call ends — ✅
- Sending regular messages (text, media, templates) via same tokens — ✅
- Sending `call_permission_request` interactive messages — ✅

**What Fails:**
- `POST /{phone_number_id}/calls` with `action: pre_accept` — ❌ 403
- `POST /{phone_number_id}/calls` with `action: accept` — ❌ 403
- Both WABAs fail with the same error

**API Request (pre_accept):**
```
POST https://graph.facebook.com/v20.0/{phone_number_id}/calls
Authorization: Bearer {system_user_token}
Content-Type: application/json

{
  "messaging_product": "whatsapp",
  "call_id": "wacid.HBgPMjc2NzIxMjM2NDg4Mjg4...",
  "action": "pre_accept"
}
```

**Questions:**
1. Does the Calling API require a separate permission beyond `whatsapp_business_messaging`? If so, what is the exact permission name and how do we enable it?
2. Is there a Calling API enablement step at the WABA level (beyond the phone number settings) that we may be missing?
3. Is there a region restriction? Our numbers are India (+91) and our Cloud API is on us-east-1.
4. Do we need to be on a specific API version (v21.0+, v22.0+) for calling to work?
5. Is there a beta/allowlist requirement for the Calling API that we need to apply for?

**Trace IDs from failed requests:**
- A93wuOuUH8CITf3k08jpuFB (call to +919903300044)
- AiYcAVHBBMtHhQEPFLd4DLZ (call to +919330994400)

Please advise on what permission or configuration change is needed to resolve this.

Thank you,
WECARE.DIGITAL Team
