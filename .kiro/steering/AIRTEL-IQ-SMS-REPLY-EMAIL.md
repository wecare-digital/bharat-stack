---
inclusion: manual
---

# Reply to Airtel IQ — Api Virtual Number (31 March 2026)

Subject: Re: Api Virtual Number

---

Dear Mohit,

Thank you for the follow-up. Please find our responses below with live test evidence from today (31 March 2026).

---

## 1. DLR Callback — Tested & Confirmed Working

We re-tested the DLR callback endpoint today with 3 different payload formats. All returned HTTP 200 successfully.

**Endpoint:**
- URL: https://api.wecare.digital/sms-in/airtel
- Method: POST
- Content-Type: application/json

**Test 1 — DELIVERED:**
```bash
curl --location 'https://api.wecare.digital/sms-in/airtel' \
--header 'Content-Type: application/json' \
--data '{
  "messageId": "dlr-test-001",
  "status": "DELIVERED",
  "statusCode": "000",
  "destination": "9903300044",
  "senderId": "WDBEEP",
  "timestamp": "2026-03-31T11:00:00Z"
}'
```
Response: HTTP 200 — `{"success": true, "message": "DLR received"}`

**Test 2 — FAILED (with error fields):**
```bash
curl --location 'https://api.wecare.digital/sms-in/airtel' \
--header 'Content-Type: application/json' \
--data '{
  "messageId": "dlr-test-002",
  "status": "FAILED",
  "statusCode": "404",
  "destination": "9903300044",
  "senderId": "WDBEEP",
  "errorCode": "DND",
  "errorDescription": "DND subscriber"
}'
```
Response: HTTP 200 — `{"success": true, "message": "DLR received"}`

**Test 3 — SUBMITTED (minimal fields):**
```bash
curl --location 'https://api.wecare.digital/sms-in/airtel' \
--header 'Content-Type: application/json' \
--data '{
  "messageId": "dlr-test-003",
  "status": "SUBMITTED",
  "statusCode": "001",
  "destination": "9903300044",
  "senderId": "WDBEEP"
}'
```
Response: HTTP 200 — `{"success": true, "message": "DLR received"}`

Our endpoint is publicly accessible and accepts any JSON body structure. No IP whitelisting is required on our side. If Airtel's DLR payload format differs, please share a sample and we will adapt.

**Action from Airtel:** Please trigger a test DLR callback to https://api.wecare.digital/sms-in/airtel from your side to confirm connectivity.

---

## 2. SMS API — 403 Forbidden (IP Not Whitelisted)

We tested from our server (IP: 52.3.44.165) and are still receiving **403 Forbidden** on iqmessaging.airtel.in:

```
$ curl -s -o /dev/null -w 'HTTP %{http_code}' 'https://iqmessaging.airtel.in/api/v4/send-sms'
HTTP 403
```

We also tested from a different machine and received HTTP 401 Unauthorized, confirming the API is reachable — the 403 is specifically because our server IP has not been whitelisted.

We were able to send SMS successfully from our local development machine (not IP-restricted), confirming our integration, credentials, and payload format are all correct.

**Pending action from Airtel — Please whitelist IP 52.3.44.165 on:**
- SMS: iqmessaging.airtel.in
- Voice: iqvoice.airtel.in
- OBD: openapi.airtel.in
- Server: AWS Lightsail, us-east-1 (Virginia, US)

**IP Whitelisting on our side — DONE.** Airtel IP 34.111.202.18 is already allowed.

---

## 3. SMS Template — Updated (Registered on DLT)

Please remove the earlier SMS template and update with the below registered template.

- **Template Name:** ivr-default
- **DLT Template ID:** 1007277993798259629
- **Sender ID:** WDBEEP
- **Category:** Service Implicit
- **Registration:** REGISTERED (airtel.com)

**SMS Content (with line breaks):**
```
Thanks for contacting WECARE.DIGITAL!

Submit your request here: https://wecare.digital/selfservice or send us a message / voice note on WhatsApp: https://r.wecare.digital/wa.

We'll review it and follow up if needed.
```

### Important — Line Break Format for SMS API

We tested multiple line break approaches via the Airtel IQ v4 API and found that only `\n\n` (double newline) preserves line breaks in the delivered SMS:

| Format | Result |
|--------|--------|
| `\n` (single newline) | ❌ Stripped |
| `\r\n` (CRLF) | ❌ Stripped |
| `%0a` (URL-encoded) | ❌ Stripped |
| **`\n\n` (double newline)** | ✅ Line breaks preserved |

**Working JSON payload (tested & SMS delivered with line breaks to multiple numbers):**
```json
{
  "customerId": "WECAREDIG_v6J1SyLLI2auy7Lw9JrW",
  "destinationAddress": ["9903300044"],
  "message": "Thanks for contacting WECARE.DIGITAL!\n\nSubmit your request here: https://wecare.digital/selfservice or send us a message / voice note on WhatsApp: https://r.wecare.digital/wa.\n\nWe'll review it and follow up if needed.",
  "sourceAddress": "WDBEEP",
  "messageType": "SERVICE_IMPLICIT",
  "dltTemplateId": "1007277993798259629",
  "entityId": "1201161991108627443"
}
```

**Instruction:** When configuring the default SMS for call connection, please ensure the message content uses `\n\n` (double newline) for line breaks as shown above.

---

## 4. IVR Audio — Already Shared

The IVR audio file was shared as attachment in our previous email (30 March). Please confirm once updated.

---

## Summary — Pending Actions from Airtel

1. **Whitelist IP 52.3.44.165** on iqmessaging.airtel.in, iqvoice.airtel.in, openapi.airtel.in
2. **Trigger a test DLR callback** to https://api.wecare.digital/sms-in/airtel
3. **Update SMS template** to DLT ID 1007277993798259629 — use `\n\n` for line breaks
4. **Update IVR audio** (file shared on 30 March)

Please confirm once completed so we can run end-to-end testing.

Thank you,
Manish Agarwal
WECARE.DIGITAL
