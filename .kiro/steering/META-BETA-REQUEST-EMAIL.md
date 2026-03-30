---
inclusion: manual
---

# Email to Meta: WhatsApp Payments Beta Access Request

**To:** whatsappindia-bizpayments-support@meta.com
**CC:** (your Meta representative if you have one)
**Subject:** WhatsApp Payments Beta Access Request — WECARE.DIGITAL (WABA: 2094615664435155 + 2513394156072604)

---

Dear WhatsApp India Business Payments Team,

We are writing to request beta access for the following WhatsApp Payments features for our business, WECARE.DIGITAL. We have completed a full production-grade integration with PayU and Razorpay payment gateways and are actively processing payments via WhatsApp.

## Business Details

| Field | Value |
|---|---|
| Business Name | WECARE.DIGITAL |
| Business Portfolio | Meta Business Manager |
| GSTIN | 19AADFW7431N1ZK |
| PAN | AADFW7431N |
| MCC | 4722 (Travel Agencies and Tour Operators) |
| Purpose Code | 03 (Travel) |
| Business Address | The W.B.S.I.D.C. Building, Unit 1/20, 81/2/7, Phears Ln, Kolkata, WB 700012 |
| Website | https://wecare.digital |
| Support Email | one@wecare.digital |
| Support Phone | +91 93309 94400 |

## WABA Details

| WABA | ID | Phone | Status |
|---|---|---|---|
| WABA 1 (WECARE.DIGITAL) | 2094615664435155 | +91 93309 94400 | Active, Direct API |
| WABA 2 (Manish Agarwal) | 2513394156072604 | +91 99033 00044 | Active, Direct API |

## Payment Gateway Configurations

| Config Name | WABA | Gateway | MID | Status |
|---|---|---|---|---|
| WECARE-RAZOR-PAY | WABA 1 | Razorpay | acc_HDfub6wOfQybuH | Active |
| WECARE-PAYU | WABA 1 | PayU | 8629516 | Active |
| Razorpay_ManishAgarwal | WABA 2 | Razorpay | acc_HDfub6wOfQybuH | Active |
| PayU_ManishAgarwal | WABA 2 | PayU | 8629516 | Active |

## What We Have Built (Production-Ready)

Our integration covers the complete WhatsApp Payments-In specification:

### Core Payment Flow
- PG Deep Integration with both Razorpay and PayU
- order_details interactive messages with full payload compliance (v25.0)
- order_status messages for payment confirmation (completed, canceled)
- Payment Lookup API verification (security compliance — not relying solely on webhooks)
- Meta Refund API integration (POST /payments_refund)
- Dual webhook processing: Meta payment webhooks (primary) + direct PG webhooks (backup)
- HMAC-SHA256 signature verification (Razorpay) + SHA-512 reverse hash (PayU)
- Idempotent webhook processing with DynamoDB audit trail

### Invoice & Billing
- GST-compliant invoice generation with sequential numbering (WD/FY/NNNNN)
- POS receipt-style PNG generation (thermal receipt layout with PAID stamp)
- PDF generation
- Auto-send invoice image on WhatsApp after payment capture
- Configurable convenience fee (rate + GST rate + skip flag)

### Payment Routing
- Per-WABA payment configuration isolation (cross-WABA safety net)
- Strict 10-digit phone matching for customer invoice isolation
- Invoice stores preferred gateway + configuration for keyword-triggered payments
- Sequential payment flow (auto-sends next pending invoice after capture)

### Customer Experience
- 65+ payment trigger keywords (English, Hindi, Hinglish, Devanagari)
- Physical-goods support with structured address fields
- Native WhatsApp address collection (empty addresses[] for customer input)
- Order expiration (configurable, default 24h, Meta minimum 300s enforced)
- UPI limit auto-switch to web checkout above Rs 5,00,000
- Preferred UPI app support (gpay, phonepe, paytm, etc.)

### Advanced Features (Ready for Beta)
- Enhanced Payment Links support (payment_link type with Razorpay/PayU URLs)
- UPI Intent mode (upi_intent_link type)
- quick_pay mode (hides "Review and Pay", shows only "Pay Now")
- Third Party Validation (TPV) support for Razorpay and PayU
- enabled_payment_options (restrict to UPI or web)

## Beta Features We Are Requesting Access To

### 1. Enhanced Payment Links
We have implemented the template-based Enhanced Payment Links flow and are ready to test with production Razorpay and PayU payment links.

**Sample Razorpay payment link:** (will provide upon request)
**Sample PayU payment link:** (will provide upon request)
**Preferred Payment Gateways:** Razorpay, PayU

### 2. Checkout Button Templates with Coupons, Real-time Inventory, and Shipping
We are ready to implement the checkout endpoint for data_exchange (get_coupons, apply_coupon, remove_coupon, apply_shipping). We have existing WhatsApp Flows encryption/decryption infrastructure that can be reused for the checkout endpoint.

### 3. WhatsApp Business Calling + SIP
All 3 phone numbers have calling enabled with SIP integration:

| Phone | Meta ID | SIP Hostname | Port | Encryption | Status |
|---|---|---|---|---|---|
| +91 93309 94400 | 1016149501586345 | sip.wecare.digital | 5061 | SDES | ENABLED |
| +91 99033 00044 | 1055232054343117 | sip.wecare.digital | 5061 | SDES | ENABLED |

Asterisk PBX (22.8.2) on Lightsail instance at 52.3.44.165 with IVR (Polly TTS, multi-language).

## Technical Stack

- AWS Lambda (Python 3.12) — 44 serverless functions
- DynamoDB — 8 tables with GSIs
- Meta WhatsApp Cloud API v25.0 (Direct API)
- Next.js admin dashboard on AWS Amplify
- S3 + CloudFront for invoice storage/delivery

## Contact

| Role | Name | Contact |
|---|---|---|
| Technical Lead | Manish Agarwal | one@wecare.digital |
| Business | WECARE.DIGITAL | +91 93309 94400 |

We are happy to provide any additional information, sample payloads, or schedule a technical walkthrough at your convenience.

Thank you for your support.

Best regards,
WECARE.DIGITAL Team
