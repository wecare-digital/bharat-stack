# WABA Phone Number Migration Process

## Official Meta Documentation
Source: [Migrating phone numbers among solution partners programmatically](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/support/migrating-phone-numbers-among-solution-partners-programmatically/)

Content was rephrased for compliance with licensing restrictions.

## What Gets Migrated
- Display name, quality rating, messaging limits, Official Business Account status
- High quality approved message templates (duplicated to destination WABA)

## What Does NOT Migrate
- Low quality, rejected, or pending templates
- Template quality ratings (reset to UNKNOWN for 24h)

## Prerequisites
- Both WABAs must belong to the same verified Business
- Phone must be currently registered on source WABA (status: CONNECTED)
- 2FA must be disabled on the phone number
- Destination WABA must have payment method set up
- Destination WABA must have webhook subscription (for Cloud API)
- App must have `whatsapp_business_management` permission
- Phone must have approved display name (name_status: APPROVED)

### Step 1: Verify phone is on Direct API WABA
Ensure the phone number is registered on a Direct API WABA:
```
Meta Graph API: GET /{phone_id}?fields=id,display_phone_number,platform_type
```

### Step 2: Migrate phone to target WABA
```
POST https://graph.facebook.com/v25.0/{TARGET_WABA_ID}/phone_numbers
Headers: Authorization: Bearer {token}
Query: appsecret_proof={proof}
Body: { "cc": "91", "phone_number": "9330994400", "migrate_phone_number": true }
```
Response: `{ "id": "1016149501586345" }` — the phone ID on the target WABA

### Step 3: Request OTP (voice call recommended — SMS may not arrive)
```
POST https://graph.facebook.com/v25.0/{PHONE_ID}/request_code
Body: { "code_method": "VOICE", "language": "en" }
```

### Step 4: Verify OTP
```
POST https://graph.facebook.com/v25.0/{PHONE_ID}/verify_code
Body: { "code": "569778" }
```

### Step 5: Register
```
POST https://graph.facebook.com/v25.0/{PHONE_ID}/register
Body: { "messaging_product": "whatsapp", "pin": "123456" }
```

### Step 6: Verify status
```
GET https://graph.facebook.com/v25.0/{PHONE_ID}?fields=display_phone_number,status,code_verification_status
```
Expected: `status: CONNECTED`, `code_verification_status: VERIFIED`

## IDs Reference
- WABA1: 2094615664435155 (WECARE.DIGITAL — Direct API)
- WABA2: 2513394156072604 (Manish Agarwal — legacy)
- WABA-T: 2513394156072604 (Manish Agarwal — Direct API)
- WABA1: 2094615664435155 (WECARE.DIGITAL — Direct API)
- Business: 382642103987922
- App: 2238810740192680
- Secret: wecare/meta-system-user-token
