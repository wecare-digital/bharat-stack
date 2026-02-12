# Email to AWS — WhatsApp Business Calling via AWS End User Messaging Social

---

**To:** AWS Support / AWS End User Messaging Social Team
**Subject:** WhatsApp Calling API — 403 on pre_accept/accept via Graph API; need guidance on EUM Social calling support

---

Hi AWS Support,

We are using AWS End User Messaging (EUM) Social for WhatsApp Business messaging (account 775261844268, us-east-1). Messaging works perfectly — we send and receive messages via `socialmessaging.send_whatsapp_message()` and receive inbound via SNS.

We are now implementing WhatsApp Business Calling (voice calls via Cloud API) and hitting a 403 permission error when calling Meta's Graph API directly for call signaling (`pre_accept` / `accept` actions on `/{phone_number_id}/calls`).

**Our Architecture:**
- Messaging: AWS EUM Social → SNS → Lambda (works perfectly)
- Calling: Direct Meta Graph API via Lambda (403 error on call control)
- Phone numbers managed via EUM Social (phone-number-id-5e020cecd221429996f6ae721cc42206, phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c)
- System User tokens stored in Secrets Manager

**Questions:**

1. Does AWS EUM Social support WhatsApp Calling API operations (pre_accept, accept, terminate, create calls)? Or must we use the Meta Graph API directly for call signaling?

2. If we must use Meta Graph API directly, is there a known conflict between EUM Social's phone number management and direct Graph API calling? Could EUM Social's ownership of the phone numbers restrict our ability to call the `/{phone_number_id}/calls` endpoint?

3. Is there an EUM Social API equivalent for call control (similar to `send_whatsapp_message` but for calls)?

4. We are using Meta phone number IDs (960395407161423, 997428863451102) for the Graph API calls endpoint. Should we be using the AWS phone number IDs instead?

5. Are there any additional IAM permissions or EUM Social configurations needed to enable calling alongside messaging?

**Error we receive from Meta Graph API:**
```
HTTP 403 — (#200) You do not have the necessary permissions to send messages on behalf of this WhatsApp Business Account
```

**Account Details:**
- AWS Account: 775261844268
- Region: us-east-1
- WABA 1: 1912405516040025 (+919330994400)
- WABA 2: 1633959101297902 (+919903300044)
- EUM Phone ID 1: phone-number-id-5e020cecd221429996f6ae721cc42206
- EUM Phone ID 2: phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c

Any guidance on the correct approach for WhatsApp calling with EUM Social would be appreciated.

Thank you,
WECARE.DIGITAL Team
