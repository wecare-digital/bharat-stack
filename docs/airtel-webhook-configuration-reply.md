# WeCare Digital — Webhook Configuration Details for Airtel

**Date:** 12 Feb 2026
**From:** WeCare Digital (voice@wecare.digital)
**To:** Airtel IQ Integration Team
**Subject:** Webhook URLs, Request Body Formats & Working Curl Examples for Voice-In + SMS-In

---

Hi Airtel Team,

Please find below the complete webhook configuration details with request body formats and working curl examples for all 6 endpoints. All endpoints are live and returning 200.

---

## 1. CDR WEBHOOK (Inbound + All Outbound CDR Callbacks)

| Field | Value |
|---|---|
| URL | `POST https://api.wecare.digital/voice-cdr-webhook` |
| Method | POST |
| Content-Type | application/json |
| Auth | None (open webhook) |
| Customer ID | WECAREDIG_v6J1SyLLI2auy7Lw9JrW |
| Inbound Number | +91 9319767034 |
| Contact Email | voice@wecare.digital |

### callBackURLs config for Airtel call flows:

```json
{
  "callBackURLs": [
    {
      "eventType": "CDR",
      "notifyURL": "https://api.wecare.digital/voice-cdr-webhook",
      "method": "POST",
      "headers": {}
    },
    {
      "eventType": "ALL",
      "notifyURL": "https://api.wecare.digital/voice-cdr-webhook",
      "method": "POST",
      "headers": {}
    }
  ]
}
```

### Accepted Request Body — Format A (camelCase, Inbound/C2C):

```json
{
  "vmSessionId": "abc123-session-id",
  "clientCorrelationId": "Xchange123863",
  "callType": "INBOUND",
  "overallCallStatus": "Answered",
  "callerNumber": "9876543210",
  "destinationNumber": "9319767034",
  "callerId": "9876543210",
  "customerId": "WECAREDIG_v6J1SyLLI2auy7Lw9JrW",
  "duration": 45000,
  "conversationDuration": 40000,
  "fromWaitingTime": 5000,
  "billableDuration": 40000,
  "startTime": 1707700000000,
  "endTime": 1707700045000,
  "callAnswerTime": 1707700005000,
  "timestamp": "2026-02-12 14:30:00",
  "hangUpStatus": "NORMAL_CLEARING",
  "hangupCause": "NORMAL_CLEARING",
  "callerNumberStatus": "Answer",
  "callerNumberStatusDetails": "",
  "destinationNumberStatus": "Answered",
  "destinationNumberStatusDetails": "",
  "circleNameCaller": "Delhi",
  "circleNameDestination": "Delhi",
  "operatorNameCaller": "Bharti Airtel (GSM)",
  "operatorNameDestination": "Bharti Airtel (GSM)",
  "recordingURL": "https://recording-url-if-available.wav",
  "retryCountCaller": 0,
  "retryCountDestination": 0,
  "participants": [
    {
      "participantType": "From",
      "participantName": "Caller",
      "status": "Answer",
      "retryCount": 0
    },
    {
      "participantType": "To",
      "participantName": "Destination",
      "status": "Answered",
      "retryCount": 0
    }
  ],
  "events": []
}
```

### Accepted Request Body — Format B (Display/Underscore, OBD Campaigns):

```json
{
  "Session_ID": "obd-session-456",
  "Client_Correlation_Id": "corr-789",
  "Call_Type": "OUTBOUND",
  "Overall_Call_Status": "Answered",
  "Caller_Number": "8130078559",
  "Destination_Number": "9876543210",
  "Caller_ID": "8040761117",
  "Customer_Name": "WECAREDIG_v6J1SyLLI2auy7Lw9JrW",
  "duration": 31556,
  "conversationDuration": 24189,
  "Campaign_Id": "698af5ddb799f448d9d091c0",
  "Campaign_Name": "Test Campaign",
  "Date": "12/02/2026",
  "Time": "14:40:07",
  "Caller_Status": "Disconnected",
  "Destination_Status": "Disconnected",
  "Caller_Circle_Name": "Delhi",
  "Caller_Operator_Name": "Bharti Airtel (GSM)",
  "Caller_Duration": "00:31",
  "Conversation_Duration": "00:00:24",
  "Caller_Waiting_Time": "00:00:07",
  "Billable_Duration": "00:24",
  "Hangup_Cause": "NORMAL_CLEARING",
  "Recording": "",
  "participants": [
    {
      "participantType": "From",
      "participantName": "",
      "status": "Disconnected"
    },
    {
      "participantType": "To",
      "participantName": "",
      "status": "Disconnected"
    }
  ]
}
```

### Working Curl — Format A (camelCase):

```bash
curl -X POST https://api.wecare.digital/voice-cdr-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "vmSessionId": "test-session-001",
    "clientCorrelationId": "Xchange999",
    "callType": "INBOUND",
    "overallCallStatus": "Answered",
    "callerNumber": "9876543210",
    "destinationNumber": "9319767034",
    "callerId": "9876543210",
    "customerId": "WECAREDIG_v6J1SyLLI2auy7Lw9JrW",
    "duration": 30000,
    "conversationDuration": 25000,
    "fromWaitingTime": 5000,
    "timestamp": "2026-02-12 14:30:00",
    "callerNumberStatus": "Answer",
    "destinationNumberStatus": "Answered",
    "participants": [
      {"participantType": "From", "status": "Answer"},
      {"participantType": "To", "status": "Answered"}
    ]
  }'
```

### Working Curl — Format B (Display/OBD):

```bash
curl -X POST https://api.wecare.digital/voice-cdr-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "Session_ID": "obd-test-001",
    "Client_Correlation_Id": "corr-test-001",
    "Call_Type": "OUTBOUND",
    "Overall_Call_Status": "Answered",
    "Caller_Number": "8130078559",
    "Destination_Number": "9876543210",
    "Campaign_Id": "698af5ddb799f448d9d091c0",
    "Campaign_Name": "Test",
    "duration": 31556,
    "conversationDuration": 24189,
    "Caller_Status": "Disconnected",
    "Destination_Status": "Disconnected",
    "participants": [
      {"participantType": "From", "status": "Disconnected"},
      {"participantType": "To", "status": "Disconnected"}
    ]
  }'
```

### Expected 200 Response:

```json
{
  "status": "ok",
  "vmSessionId": "test-session-001",
  "clientCorrelationId": "Xchange999",
  "message": "CDR received and stored successfully"
}
```

---

## 2. CLICK-TO-CALL (C2C)

| Field | Value |
|---|---|
| URL | `POST https://api.wecare.digital/voice-in/c2c` |
| Method | POST (initiate call), GET (list calls), DELETE (clear logs) |
| Content-Type | application/json |
| Auth | HMAC-SHA256 (Kong gateway) |
| App ID | WECAREDIG_fD4BKqUbC8k90jNrPR0n |
| Caller ID | 8047311032 |
| Airtel API | https://iqvoice.airtel.in/gateway/airtel-xchange/v2/click-to-call |

### Our API Request Body (to initiate a C2C call):

```json
{
  "fromNumber": "9876543210",
  "toNumber": "9123456789",
  "enableRecording": true,
  "contactId": "optional-contact-ref",
  "retryCount": 1,
  "enableEarlyMedia": true
}
```

### Airtel C2C Payload (what we send to Airtel Kong API):

```json
{
  "from": "9876543210",
  "to": "9123456789",
  "caller_id": "8047311032",
  "to_caller_id": "8047311032",
  "record": true,
  "early_media": true,
  "retry": {"count": 1}
}
```

### CDR Callback on this endpoint:

This endpoint also accepts Airtel CDR callbacks. If Airtel sends C2C CDR callbacks here instead of `/voice-cdr-webhook`, they will be detected automatically and stored correctly in the VoiceCDR table.

CDR detection fields: `vmSessionId`, `clientCorrelationId`, `Session_ID`, `Client_Correlation_Id`, `overallCallStatus`, `Overall_Call_Status`, or `participants` array with `participantType`.

### Working Curl — Initiate C2C Call:

```bash
curl -X POST https://api.wecare.digital/voice-in/c2c \
  -H "Content-Type: application/json" \
  -d '{
    "fromNumber": "9876543210",
    "toNumber": "9123456789",
    "enableRecording": true,
    "retryCount": 1
  }'
```

### Working Curl — CDR Callback to C2C endpoint:

```bash
curl -X POST https://api.wecare.digital/voice-in/c2c \
  -H "Content-Type: application/json" \
  -d '{
    "vmSessionId": "c2c-session-001",
    "clientCorrelationId": "Xchange456",
    "callType": "OUTBOUND",
    "overallCallStatus": "Answered",
    "callerNumber": "9876543210",
    "destinationNumber": "9123456789",
    "duration": 20000,
    "conversationDuration": 15000,
    "participants": [
      {"participantType": "From", "status": "Answer"},
      {"participantType": "To", "status": "Answered"}
    ]
  }'
```

### Expected 200 Response (CDR callback):

```json
{
  "status": "ok",
  "vmSessionId": "c2c-session-001",
  "clientCorrelationId": "Xchange456",
  "message": "C2C CDR callback received and stored"
}
```

---

## 3. OBD (Outbound Dialer)

| Field | Value |
|---|---|
| URL | `POST https://api.wecare.digital/voice-in/obd` |
| Method | POST (create campaign / upload), GET (list), DELETE (clear) |
| Content-Type | application/json |
| Customer ID | WECAREDIG_v6J1SyLLI2auy7Lw9JrW |
| App ID | IRONMAN |
| Caller ID | 8040761117 |
| Call Flow ID | dfbeda76-f641-420f-95e7-b78d562a941f |
| Template ID | 69818654d9e8e260e60b16a7 |

### Airtel APIs used:

| Purpose | URL |
|---|---|
| Upload Audio | `POST https://openapi.airtel.in/gateway/airtel-xchange/uploadPrompts?customerId={customerId}` |
| Upload CSV | `POST https://openapi.airtel.in/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload?customerId={customerId}&campaignType=OBD_CALL` |
| Create Campaign | `POST https://iqtelephony.airtel.in/gateway/airtel-xchange/campaign-manager/v2/createCampaign` |

### Our API Request Body (create OBD campaign):

```json
{
  "campaignName": "My OBD Campaign",
  "contacts": ["9876543210", "9123456789"],
  "callerId": "8040761117",
  "audioUrl": "https://openapi.airtel.in/gateway/airtel-xchange/assets/audios/global/Default_Airtel_Jingle.wav",
  "retryCount": 2,
  "sheetFileNames": []
}
```

### CDR Callback on this endpoint:

This endpoint also accepts Airtel CDR callbacks. The previous 400 error (`"contacts or sheetFileNames is required"`) is now fixed. OBD CDR callbacks sent here will be detected automatically and stored correctly.

CDR detection fields: Same as CDR webhook — `vmSessionId`, `Session_ID`, `overallCallStatus`, `Overall_Call_Status`, `participants` array.

### Working Curl — OBD CDR Callback (Format B / Display):

```bash
curl -X POST https://api.wecare.digital/voice-in/obd \
  -H "Content-Type: application/json" \
  -d '{
    "Session_ID": "obd-campaign-session-001",
    "Client_Correlation_Id": "obd-corr-001",
    "Call_Type": "OUTBOUND",
    "Overall_Call_Status": "Answered",
    "Caller_Number": "8040761117",
    "Destination_Number": "9876543210",
    "Customer_Name": "WECAREDIG_v6J1SyLLI2auy7Lw9JrW",
    "Campaign_Id": "698af5ddb799f448d9d091c0",
    "Campaign_Name": "Test Campaign",
    "duration": 25000,
    "conversationDuration": 20000,
    "Caller_Status": "Disconnected",
    "Destination_Status": "Disconnected",
    "Date": "12/02/2026",
    "Time": "14:40:07",
    "participants": [
      {"participantType": "From", "status": "Disconnected"},
      {"participantType": "To", "status": "Disconnected"}
    ]
  }'
```

### Expected 200 Response:

```json
{
  "status": "ok",
  "vmSessionId": "obd-campaign-session-001",
  "clientCorrelationId": "obd-corr-001",
  "message": "OBD CDR callback received and stored"
}
```

---

## 4. SMS ENDPOINT (Airtel IQ SMS)

| Field | Value |
|---|---|
| URL | `POST https://api.wecare.digital/sms-in/airtel` |
| Method | POST (send SMS), GET (list), DELETE (clear) |
| Content-Type | application/json |
| Auth | Basic `V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy` |
| Customer ID | WECAREDIG_v6J1SyLLI2auy7Lw9JrW |
| Sender ID | WDBEEP |
| Entity ID (PE ID) | 1201161991108627443 |
| Default DLT Template | 1007974344269130859 |

### Airtel SMS APIs supported:

| Version | URL | Notes |
|---|---|---|
| v4 (default) | `POST https://iqmessaging.airtel.in/api/v4/send-sms` | Single/Multiple recipients |
| v5 | `POST https://iqmessaging.airtel.in/api/v5/send-sms-cm` | Content Moderation (auto DLT) |
| v6 | `POST https://iqmessaging.airtel.in/api/v6/send-sms` | Enhanced response with echo-back |
| Bulk (Conduit) | `POST https://iqmessaging.airtel.in/conduit/api/v1/send-sms-bulk` | Different format per recipient |

### Our API Request Body — Single/Multiple SMS (v4/v5/v6):

```json
{
  "phoneNumber": "9876543210",
  "content": "Your OTP is 123456. Valid for 5 minutes.",
  "messageType": "SERVICE_EXPLICIT",
  "dltTemplateId": "1007974344269130859",
  "apiVersion": "v4"
}
```

Or with multiple recipients:

```json
{
  "phoneNumbers": ["9876543210", "9123456789"],
  "content": "Your appointment is confirmed for tomorrow.",
  "messageType": "SERVICE_EXPLICIT",
  "dltTemplateId": "1007974344269130859",
  "apiVersion": "v4"
}
```

### What we send to Airtel (v4 payload):

```json
{
  "customerId": "WECAREDIG_v6J1SyLLI2auy7Lw9JrW",
  "destinationAddress": ["9876543210"],
  "message": "Your OTP is 123456. Valid for 5 minutes.",
  "sourceAddress": "WDBEEP",
  "messageType": "SERVICE_EXPLICIT",
  "dltTemplateId": "1007974344269130859",
  "entityId": "1201161991108627443"
}
```

### Headers sent to Airtel:

```
Content-Type: application/json
Authorization: Basic V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy
customerId: WECAREDIG_v6J1SyLLI2auy7Lw9JrW
```

### Our API Request Body — Bulk (Conduit):

```json
{
  "bulk": true,
  "phoneNumbers": ["9876543210", "9123456789"],
  "content": "Bulk message content here",
  "messageType": "SERVICE_EXPLICIT",
  "dltTemplateId": "1007974344269130859"
}
```

### What we send to Airtel Conduit (bulk payload):

```json
[
  {
    "msisdn": "9876543210",
    "content": "Bulk message content here",
    "header": "WDBEEP",
    "messageType": "SERVICE_EXPLICIT",
    "templateId": "1007974344269130859",
    "peId": "1201161991108627443",
    "category": "SMS_NCM"
  },
  {
    "msisdn": "9123456789",
    "content": "Bulk message content here",
    "header": "WDBEEP",
    "messageType": "SERVICE_EXPLICIT",
    "templateId": "1007974344269130859",
    "peId": "1201161991108627443",
    "category": "SMS_NCM"
  }
]
```

### Working Curl — Send SMS (v4):

```bash
curl -X POST https://api.wecare.digital/sms-in/airtel \
  -H "Content-Type: application/json" \
  -d '{
    "phoneNumber": "9876543210",
    "content": "Your OTP is 123456. Valid for 5 minutes.",
    "messageType": "SERVICE_EXPLICIT",
    "dltTemplateId": "1007974344269130859",
    "apiVersion": "v4"
  }'
```

### Expected 200 Response:

```json
{
  "success": true,
  "messageId": "uuid-here",
  "providerMessageId": "airtel-msg-id",
  "recipientCount": 1,
  "status": "sent",
  "apiVersion": "v4"
}
```

---

## Summary — All 6 Webhook URLs

| # | Service | URL | Method |
|---|---|---|---|
| 1 | CDR Webhook (All CDR) | `https://api.wecare.digital/voice-cdr-webhook` | POST |
| 2 | Click-to-Call (C2C) | `https://api.wecare.digital/voice-in/c2c` | POST/GET/DELETE |
| 3 | OBD (Outbound Dialer) | `https://api.wecare.digital/voice-in/obd` | POST/GET/DELETE |
| 4 | SMS (Airtel IQ) | `https://api.wecare.digital/sms-in/airtel` | POST/GET/DELETE |
| 5 | Voice CDR Read | `https://api.wecare.digital/voice-cdr-webhook` | GET |
| 6 | Dashboard Webhook Tab | All URLs listed in copyable reference text | — |

### Key Notes for Airtel Configuration:

1. **CDR Webhook** accepts BOTH Format A (camelCase) and Format B (Display_Format with underscores). No changes needed on Airtel side — send either format.

2. **C2C and OBD endpoints** also accept CDR callbacks. If Airtel sends CDR callbacks to `/voice-in/c2c` or `/voice-in/obd` instead of `/voice-cdr-webhook`, they will be auto-detected and stored correctly.

3. **OBD 400 error is fixed.** The previous error `"contacts or sheetFileNames is required"` was caused by CDR callbacks being treated as campaign creation requests. CDR payloads are now detected before campaign logic runs.

4. **SMS endpoint** supports v4, v5, v6, and Conduit bulk — all via the same URL `https://api.wecare.digital/sms-in/airtel`.

5. **No IP whitelisting required on our side.** Our endpoints are open. Airtel IPs (125.19.17.212, 125.17.6.54, 122.187.47.153) only need whitelisting if we get 403 errors calling Airtel APIs.

6. **No auth required for CDR callbacks.** The CDR webhook, C2C CDR callback, and OBD CDR callback endpoints do not require authentication headers. Just POST the JSON body.

---

Please configure the callbacks accordingly. Let us know if you need any changes or have questions.

Best regards,
WeCare Digital
voice@wecare.digital
