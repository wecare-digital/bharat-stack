# Order-Centric Architecture — Implementation Plan

## Audit Summary

| Module | Status | Flow ID | Handler | Needs Rebuild |
|--------|--------|---------|---------|---------------|
| Submit Request | ✅ Working | 1469093721293830 | submit_request.py | Fix dropdown + screen mapping |
| Subscribe | ✅ Working | 1262971692700761 | subscribe.py | No |
| Track Request | ❌ Broken | 973888792200167 (DEPRECATED) | generic.py | Full rebuild |
| Amend Request | ❌ Broken | 1533536534833353 (DEPRECATED) | generic.py | Full rebuild |
| Appointment | ❌ Broken | 1475722977488573 (DEPRECATED) | generic.py | Full rebuild |
| RX Slot | ❌ Broken | 1892784521355352 (DEPRECATED) | generic.py | Full rebuild |
| Drop Docs | ❌ Broken | 1737801600902350 (DEPRECATED) | generic.py | Full rebuild |
| Enterprise Assist | ❌ Broken | 2132515287534606 (DEPRECATED) | generic.py | Full rebuild |
| Leave Review | ❌ Broken | 963443293213262 (DEPRECATED) | generic.py | Full rebuild |
| FAQ | ⚠️ Partial | N/A | faq-handler | Needs flow or page |

## Root Causes of Broken Flows

1. **All 7 deprecated flows** point to old Meta flow IDs that are DEPRECATED on WABA 1
2. **No dedicated handlers** — all 7 use generic.py which just saves form data
3. **No flow JSONs** — only Submit Request and Track Request have JSON files
4. **No order-centric design** — everything is request-centric
5. **Submit Request THANK_YOU screen** — returns screen:'THANK_YOU' but terminal response uses screen:'SUCCESS' (Meta special keyword, should work but needs testing)

## New Tables Needed

### OrdersTable (new central table)
```
orderId (PK): "WD-ORD-A1B2C3D4"
shortId: "A1B2C3D4"
orderDate: "2026-02-22"
orderTime: "18:00:00"
source: "wix" | "manual" | "shopify"
sourceOrderId: "wix-native-12345"
customerPhone: "+919330994400"
customerName: "Manish Agarwal"
totalAmount: 499 (rupees)
currency: "INR"
itemsSummary: "Black Tee × 1, White Cap × 2"
orderStatus: "active" | "fulfilled" | "cancelled"
paymentStatus: "paid" | "not_paid" | "pending"
createdAt, updatedAt
GSIs: customerPhone, source, orderStatus
```

### RequestStatusHistoryTable (new)
```
historyId (PK)
submissionId
orderId
oldStatus, newStatus
changedBy: "admin" | "system" | "webhook"
notes
changedAt
```

## Dropdown Format Change

Old: `WD-ORD - A1B2C3D4 - 22-02-2026 - 18:00:00 - IST`
New: `A1B2C3D4 — 22 Feb 2026, 6:00 PM`

The full canonical ID stays in the system as `orderId` field.
The dropdown shows `shortId — formatted date` for readability.

## Implementation Phases

### Phase 1: Core + Submit Request Fix + Track Request
- [ ] Add OrdersTable to Amplify data model
- [ ] Fix _fetch_orders_for_flow to return short format
- [ ] Rebuild Submit Request flow JSON with short dropdown
- [ ] Build Track Request flow JSON (ORDER_SELECT → STATUS)
- [ ] Build track_request.py handler
- [ ] Add admin status update to flow-responses.tsx
- [ ] Create new flows on WABA 1 as DRAFT
- [ ] Deploy and test

### Phase 2: Amend Request + Order Management Dashboard
- [ ] Build Amend Request flow JSON
- [ ] Build amend_request.py handler
- [ ] Build /dm/orders admin page
- [ ] Add order detail panel with request list
- [ ] Add status update controls

### Phase 3: Appointment + RX Slot
- [ ] Build Appointment flow JSON + handler
- [ ] Build RX Slot flow JSON + handler
- [ ] Add AppointmentsTable
- [ ] Add admin appointment management

### Phase 4: Drop Docs (Document Management)
- [ ] Build Drop Docs flow JSON + handler
- [ ] Add DocumentsTable
- [ ] WhatsApp media ingestion pipeline
- [ ] Admin document review UI

### Phase 5: Enterprise Assist + Leave Review + FAQ
- [ ] Build Enterprise Assist flow JSON + handler
- [ ] Build Leave Review flow JSON + handler
- [ ] Build FAQ as searchable WhatsApp Flow or page
- [ ] Add ReviewsTable, EnterpriseAssistTable, FaqTable
