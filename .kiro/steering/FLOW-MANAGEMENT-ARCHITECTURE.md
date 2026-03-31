---
inclusion: manual
---

# WhatsApp Flows Management Architecture

## Problem
We're scaling from 1 flow to 25+ flows. Current approach has hardcoded screen handlers in the Lambda.
Need: generic flow engine, flow registry, unified data storage, payment tracking.

## Naming Convention
All flows follow: `{NN}.{CODE}` e.g. `01.WD_SR`, `02.WD_ADDR`, `03.WD_KYC`

## Architecture Overview

### 1. Flow Registry Table (`FlowRegistryTable`)

Stores config for every flow. The endpoint handler reads this to know how to process each flow.

```
PK: flowId (Meta flow ID, e.g. "1484164182716509")

Fields:
  flowId          - string (Meta flow ID)
  flowCode        - string ("01.WD_SR", "02.WD_ADDR", etc.)
  flowName        - string (human readable: "Submit Request")
  flowVersion     - string ("7.3")
  dataApiVersion  - string ("4.0")
  wabaId          - string (which WABA this flow belongs to)
  status          - string (DRAFT / PUBLISHED / DEPRECATED)
  category        - string (service_request / address / kyc / feedback / payment / booking / other)
  
  # Payment config
  requiresPayment - boolean
  paymentAmount   - integer (paise, e.g. 4900 = ₹49)
  paymentDescription - string ("Processing fee")
  
  # Screen routing config (JSON)
  # Maps screen_id → action type so the handler knows what to do
  screenConfig    - string (JSON)
    Example: {
      "ORDER_SELECT": {"action": "data_exchange", "nextScreen": "REQUEST_FORM", "fetchData": "orders"},
      "REQUEST_FORM": {"action": "navigate", "nextScreen": "REVIEW"},
      "REVIEW": {"action": "submit", "nextScreen": "SUCCESS", "triggerPayment": true},
      "SUCCESS": {"action": "terminal", "success": true}
    }
  
  # Contact enrichment config — which flow fields map to contact fields
  contactMapping  - string (JSON)
    Example: {
      "address_line1": "addressLine1",
      "city": "city",
      "pincode": "pincode",
      "email": "email"
    }
  
  # Metadata
  createdAt       - integer (epoch)
  updatedAt       - integer (epoch)
  publishedAt     - integer (epoch)

GSIs:
  flowCode-index  (PK: flowCode)
  wabaId-index    (PK: wabaId)
  category-index  (PK: category)
```

### 2. Flow Submissions Table (`FlowSubmissionsTable`)

Generic table for ALL flow submissions. Replaces the current SubmitRequestsTable approach.

```
PK: submissionId (UUID)

Fields:
  submissionId     - string (UUID)
  flowId           - string (Meta flow ID)
  flowCode         - string ("01.WD_SR")
  flowVersion      - string ("7.3")
  
  # Who
  phone            - string
  contactId        - string
  senderName       - string
  
  # What (generic key-value from flow)
  formData         - string (JSON — full form data from the flow)
  
  # Extracted common fields (for querying)
  orderId          - string (if applicable)
  requestType      - string (if applicable)
  subject          - string (if applicable)
  
  # Reference numbers
  submissionNumber - string ("WD-SR-XXXXXXXX", "WD-ADDR-XXXXXXXX", etc.)
  
  # Payment tracking
  paymentRequired  - boolean
  paymentAmount    - integer (paise)
  paymentStatus    - string (none / pending / captured / failed / refunded)
  paymentRefId     - string ("WD-PAY-XXXXXXXX")
  invoiceId        - string (linked invoice)
  transactionId    - string (payment gateway txn ID)
  paidAt           - integer (epoch)
  
  # Lifecycle
  status           - string (open / in_progress / resolved / closed / cancelled)
  assignedTo       - string (agent ID)
  notes            - string (agent notes)
  resolvedAt       - integer (epoch)
  
  # Timestamps
  createdAt        - integer (epoch)
  updatedAt        - integer (epoch)

GSIs:
  phone-index          (PK: phone, SK: createdAt)
  flowCode-index       (PK: flowCode, SK: createdAt)
  paymentStatus-index  (PK: paymentStatus, SK: createdAt)
  paymentRefId-index   (PK: paymentRefId)
  submissionNumber-index (PK: submissionNumber)
  status-index         (PK: status, SK: createdAt)
  orderId-index        (PK: orderId)
```

### 3. Flow Logs Table (`FlowLogsTable`)

Separate from submissions. Every screen interaction logged here for audit.

```
PK: logId (UUID)

Fields:
  logId        - string
  flowId       - string
  flowCode     - string
  flowToken    - string
  phone        - string
  action       - string (INIT / data_exchange / navigate / complete / ping)
  screen       - string (screen ID)
  dataSnapshot - string (JSON of data exchanged)
  requestId    - string (Lambda request ID)
  createdAt    - integer (epoch)
  
  # Error tracking
  isError      - boolean
  errorType    - string
  errorMessage - string

GSIs:
  phone-index    (PK: phone, SK: createdAt)
  flowId-index   (PK: flowId, SK: createdAt)
```

### 4. How the Generic Flow Handler Works

```
_handle_flow_data(body):
  1. Decrypt request
  2. Extract flow_token → parse flowId from token format: "{flowCode}-{uuid}-ph-{phone}"
  3. Look up FlowRegistry by flowId (cache in Lambda memory for 5 min)
  4. Read screenConfig for current screen
  5. Based on action type:
     - "data_exchange" + "fetchData": call the appropriate data fetcher
     - "navigate": pass through data to next screen
     - "submit": 
        a. Save to FlowSubmissionsTable (generic)
        b. If requiresPayment: trigger async payment
        c. If contactMapping: enrich contact record
        d. Return terminal screen data
     - "terminal": close flow
  6. Log to FlowLogsTable
  7. Encrypt and return
```

### 5. Payment Tracking Flow

```
Flow Submit (screen=REVIEW, action=submit)
  │
  ├─ Save FlowSubmission (paymentStatus=pending, paymentAmount from registry)
  │
  ├─ Async Lambda invoke: _handle_flow_payment
  │   ├─ Create invoice via invoice-engine
  │   ├─ Update FlowSubmission.invoiceId
  │   ├─ Send payment link via WhatsApp
  │   └─ Send confirmation message
  │
  └─ Return SUCCESS screen to user

Payment Webhook (from PayU/Razorpay):
  ├─ Look up FlowSubmission by paymentRefId
  ├─ Update paymentStatus = captured, transactionId, paidAt
  └─ Send payment confirmation via WhatsApp
```

### 6. Contact Enrichment

When a flow has `contactMapping` in its registry config, the handler automatically
updates the Contact record with data collected from the flow.

Example: Address collection flow (02.WD_ADDR) has:
```json
{
  "address_line1": "addressLine1",
  "address_line2": "addressLine2", 
  "city": "city",
  "state": "state",
  "pincode": "pincode"
}
```

After submission, the handler runs:
```python
for flow_field, contact_field in contact_mapping.items():
    if form_data.get(flow_field):
        update contact[contact_field] = form_data[flow_field]
```

### 7. Flow Catalog — Full Numbering Plan

Flows are grouped by category. Each flow has a `flowType` that tells the handler
what kind of processing it needs (form_submit, order_management, interactive, data_collection, payment).

#### Category A: Service Requests (form_submit + payment)
User fills a form, submits, pays a fee. Creates a ticket/request.

| Code | Name | flowType | Payment | Description |
|------|------|----------|---------|-------------|
| 01.WD_SR | Submit Request | form_submit | ₹49 | Generic service request for any order |
| 02.WD_RET | Return Request | form_submit | ₹49 | Return an item — collects reason, photos |
| 03.WD_EXC | Exchange Request | form_submit | ₹49 | Exchange — collects preferred replacement |
| 04.WD_REF | Refund Request | form_submit | ₹49 | Refund — collects bank/UPI details |
| 05.WD_COMP | Complaint | form_submit | No | File a complaint — no fee |
| 06.WD_ESC | Escalation | form_submit | No | Escalate existing request |

#### Category B: Order Management (order_management)
User interacts with their orders — track, modify, cancel. Reads/writes order data.

| Code | Name | flowType | Payment | Description |
|------|------|----------|---------|-------------|
| 10.WD_OTRK | Order Tracking | order_management | No | Track order status + delivery ETA |
| 11.WD_OMOD | Order Modify | order_management | No | Change size/color/quantity before shipping |
| 12.WD_OCAN | Order Cancel | order_management | No | Cancel order — shows refund estimate |
| 13.WD_OADD | Order Address Change | order_management | No | Update delivery address before dispatch |
| 14.WD_OINV | Order Invoice | order_management | No | Download/view invoice for an order |
| 15.WD_OREORD | Reorder | order_management | Variable | Reorder a previous order — triggers payment |

#### Category C: Interactive / Conversational (interactive)
Multi-step flows with branching logic, conditional screens, dynamic data.

| Code | Name | flowType | Payment | Description |
|------|------|----------|---------|-------------|
| 20.WD_QUIZ | Product Quiz | interactive | No | Quiz to recommend products |
| 21.WD_CALC | Price Calculator | interactive | No | Calculate price based on selections |
| 22.WD_CONF | Product Configurator | interactive | No | Configure custom product (size, material, etc.) |
| 23.WD_SURV | Customer Survey | interactive | No | NPS/CSAT survey with branching |
| 24.WD_POLL | Quick Poll | interactive | No | Single-question poll |

#### Category D: Data Collection (data_collection)
Collect info from user and enrich their Contact record.

| Code | Name | flowType | Payment | contactMapping |
|------|------|----------|---------|----------------|
| 30.WD_ADDR | Address Collection | data_collection | No | address_line1→addressLine1, city→city, state→state, pincode→pincode |
| 31.WD_KYC | KYC Verification | data_collection | No | name→name, email→email, gstNumber→gstNumber |
| 32.WD_PROF | Profile Update | data_collection | No | name→name, email→email, preferredLanguage→preferredLanguage |
| 33.WD_PREF | Preferences | data_collection | No | optInWhatsApp→optInWhatsApp, optInEmail→optInEmail |
| 34.WD_BCARD | Business Card | data_collection | No | companyName→companyName, designation→designation |

#### Category E: Payments & Billing (payment)
Direct payment collection, invoice payment, subscription. Uses WhatsApp Native Payments (PayU/Razorpay).

| Code | Name | flowType | Payment | Description |
|------|------|----------|---------|-------------|
| 40.WD_PAY | Direct Payment | payment | Variable | Pay any amount — user enters or pre-filled |
| 41.WD_INVPAY | Invoice Payment | payment | Variable | Pay a specific invoice |
| 42.WD_SUB | Subscription Renewal | payment | Variable | Renew subscription plan — select plan, pay |
| 43.WD_TIP | Tip / Donation | payment | Variable | Optional tip or donation |
| 44.WD_EMI | EMI / Premium Payment | payment | Variable | Loan EMI or insurance premium — select, pay |
| 45.WD_CART | Cart Checkout | payment | Variable | Abandoned cart recovery — confirm items, address, pay |
| 46.WD_PREAUTH | Pre-Authorization | payment | Variable | Appointment pre-pay / deposit to reduce no-shows |

#### Native Payments Integration Pattern

All payment flows follow this pattern:
1. Flow collects order/product/service details via screens
2. REVIEW screen shows summary + amount
3. On submit → Flow handler creates invoice via invoice-engine
4. Invoice-engine sends WhatsApp Native Payment message (order_details)
5. User pays via UPI/Card/NetBanking inside WhatsApp
6. Payment webhook → updates FlowSubmission + Invoice + sends confirmation

```
FLOW (Screens)          →  SUBMIT  →  Invoice Engine  →  Native Payment Message
[Browse] [Select] [Review]    ↓           ↓                    ↓
                         FlowSubmission  Invoice           PayU/Razorpay
                         (pending)       (created)         (UPI/Card/NB)
                              ↓               ↓                 ↓
                         Payment Webhook ← Meta Webhook ← Payment Gateway
                              ↓
                         FlowSubmission.paymentStatus = captured
                         Invoice.status = paid
                         Send confirmation + receipt
```

#### Use Cases from Karix/Meta Best Practices

1. **Product Purchase Journey** (45.WD_CART)
   - Customer browses catalog via carousel/list
   - Adds to cart → Flow collects address, delivery preference
   - Checkout screen shows order summary + total
   - Native Payment triggers in-chat UPI/Card payment
   - Order confirmation + tracking in same chat

2. **Appointment Booking + Pre-Pay** (46.WD_PREAUTH + 50.WD_BOOK)
   - CalendarPicker selects date/time slot
   - Service selection via ChipsSelector
   - Pre-payment to reduce no-shows
   - Confirmation with calendar details

3. **Subscription Renewal** (42.WD_SUB)
   - Reminder message before expiry
   - Flow shows current plan + renewal options
   - One-tap payment for renewal
   - Confirmation with new expiry date

4. **Abandoned Cart Recovery** (45.WD_CART)
   - Automated WhatsApp reminder with cart items
   - Flow confirms items, address, delivery time
   - One-tap payment button
   - Order placed without leaving chat

5. **EMI / Premium Collection** (44.WD_EMI)
   - Automated reminder before due date
   - Flow shows loan/policy details + amount due
   - Quick reply to select payment method
   - Native Payment for instant collection

6. **Digital Storefront** (Full journey)
   - CTWA Ad → WhatsApp chat
   - AI agent greets, gathers preferences
   - Catalog/carousel showcases products
   - Flow: product config → address → checkout
   - Native Payment → order confirmation → tracking

#### Category F: Booking & Scheduling (booking)
Appointment, slot booking, reservations.

| Code | Name | flowType | Payment | Description |
|------|------|----------|---------|-------------|
| 50.WD_BOOK | Appointment Booking | booking | No | Book a time slot (uses CalendarPicker v6.1+) |
| 51.WD_RESV | Reservation | booking | Variable | Reserve with deposit |
| 52.WD_CALL | Callback Request | booking | No | Request a callback at preferred time |

#### Category G: Feedback & Reviews (feedback)
Post-purchase feedback, product reviews, testimonials.

| Code | Name | flowType | Payment | Description |
|------|------|----------|---------|-------------|
| 60.WD_FB | Feedback | feedback | No | General feedback form |
| 61.WD_REV | Product Review | feedback | No | Rate + review a product |
| 62.WD_TEST | Testimonial | feedback | No | Collect testimonial with consent |

### 8. Flow Type Processing Logic

The `flowType` in the registry determines how the handler processes the submission:

```python
FLOW_TYPE_HANDLERS = {
    'form_submit': {
        # Save to FlowSubmissions, optionally trigger payment, send confirmation
        'on_submit': ['save_submission', 'trigger_payment_if_required', 'send_confirmation', 'enrich_contact'],
        'generates_number': True,  # WD-SR-XXXXXXXX
    },
    'order_management': {
        # Read order data, perform action (cancel/modify), update order, notify
        'on_submit': ['save_submission', 'execute_order_action', 'send_confirmation'],
        'generates_number': False,  # Uses existing order ID
        'requires_order_lookup': True,
    },
    'interactive': {
        # Save responses, may trigger follow-up actions
        'on_submit': ['save_submission', 'process_responses', 'enrich_contact'],
        'generates_number': False,
    },
    'data_collection': {
        # Primary purpose: enrich contact record
        'on_submit': ['save_submission', 'enrich_contact', 'send_confirmation'],
        'generates_number': False,
    },
    'payment': {
        # Create invoice, send payment link, track
        'on_submit': ['save_submission', 'create_invoice', 'send_payment_link'],
        'generates_number': True,  # WD-PAY-XXXXXXXX
    },
    'booking': {
        # Create booking record, send confirmation with calendar details
        'on_submit': ['save_submission', 'create_booking', 'trigger_payment_if_required', 'send_booking_confirmation'],
        'generates_number': True,  # WD-BK-XXXXXXXX
    },
    'feedback': {
        # Save feedback, update contact satisfaction score
        'on_submit': ['save_submission', 'update_satisfaction_score', 'send_thank_you'],
        'generates_number': False,
    },
}
```

### 9. How ₹49 (or any payment) is Tracked

```
FLOW SUBMIT
  │
  ├─ Handler reads FlowRegistry: requiresPayment=true, paymentAmount=4900
  │
  ├─ Save FlowSubmission:
  │   paymentRequired: true
  │   paymentAmount: 4900
  │   paymentStatus: "pending"
  │   paymentRefId: "WD-PAY-A1B2C3D4"
  │
  ├─ Async: Create Invoice (invoice-engine Lambda)
  │   ├─ invoiceId saved back to FlowSubmission
  │   ├─ Send payment link via WhatsApp template
  │   └─ Payment link → PayU/Razorpay checkout
  │
  └─ Return SUCCESS screen to user

PAYMENT WEBHOOK (PayU/Razorpay callback)
  │
  ├─ Look up FlowSubmission by paymentRefId
  ├─ Update:
  │   paymentStatus: "captured"
  │   transactionId: "payu_txn_123456"
  │   paidAt: 1711900800
  │
  └─ Send payment confirmation WhatsApp message

DASHBOARD QUERIES:
  - Pending payments: query paymentStatus-index WHERE paymentStatus = "pending"
  - Revenue today: query paymentStatus-index WHERE paymentStatus = "captured" AND paidAt > today_start
  - By flow: query flowCode-index WHERE flowCode = "01.WD_SR" → sum paymentAmount where captured
  - Overdue: pending + createdAt > 7 days ago → flag for follow-up
```

### 10. Frontend: Flow Management Dashboard

New section in admin dashboard: "Flows Hub"

**Tab 1: Flow Registry**
- List all registered flows: code, name, type, status, version, payment config
- Add/edit flow config (register new Meta flow ID with its config)
- Quick actions: publish, deprecate, clone config

**Tab 2: Submissions**
- All submissions across all flows, filterable by:
  - Flow code (dropdown: 01.WD_SR, 02.WD_ADDR, etc.)
  - Status (open / in_progress / resolved / closed)
  - Payment status (pending / captured / failed)
  - Date range
  - Phone number
- Click submission → detail view with full form data, payment history, agent notes
- Bulk actions: assign, close, export CSV

**Tab 3: Payments**
- Payment reconciliation dashboard
- Cards: Total pending, Total captured today/week/month, Failed count
- Table: all payment submissions with amount, status, txn ID, paid date
- Filter by flow code to see revenue per flow type
- Export for accounting

**Tab 4: Analytics**
- Per-flow metrics: completion rate, drop-off screen, avg completion time
- Payment conversion: sent vs paid percentage
- Contact enrichment: how many contacts updated via flows
- Volume trends: submissions per day/week by flow type

### 11. Migration Path

1. Add new tables (FlowRegistry, FlowSubmissions, FlowLogs) to Amplify data model
2. Add address/profile fields to Contact model
3. Seed FlowRegistry with 01.WD_SR_v73 config
4. Refactor _handle_flow_data to use registry-based routing
5. Keep old SubmitRequestsTable read-only for historical data
6. New submissions go to FlowSubmissionsTable
7. Frontend reads from both tables during transition
8. After 30 days, archive old table data and switch fully
