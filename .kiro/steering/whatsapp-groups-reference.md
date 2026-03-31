---
inclusion: manual
---

# WhatsApp Groups API — LLM Reference

## Overview

WhatsApp Cloud API Groups allow businesses to create invite-only group conversations
with up to 512 participants. Groups are managed via the Meta Graph API and are part
of the WhatsApp Cloud API product.

**Main Documentation:** https://developers.facebook.com/docs/whatsapp/cloud-api
(Groups section under "Core APIs and capabilities")

**Extended Reference (360dialog partner docs):**
- https://docs.360dialog.com/docs/messaging/groups
- https://docs.360dialog.com/docs/messaging/groups/group-management

## Key Limits

| Limit | Value |
|-------|-------|
| Max participants per group | 512 (including business number) |
| Max groups per business phone | 10,000 |
| Max Cloud API businesses per group | 1 |
| Participant addition | Invite-only (via invite link) |
| Supported message types | Text, media, text-based templates, media-based templates |
| NOT supported | Calling API, Coexistence users, Multi-solution Conversations |
| Pricing | Per-message (same as Cloud API messages) |

## API Endpoints (Meta Graph API v25.0)

Base: `https://graph.facebook.com/v25.0`

### Group Lifecycle

```
POST /{phone_number_id}/groups
  Body: { messaging_product: "whatsapp", subject: "...", description: "...", join_approval_mode: "auto_approve"|"approval_required" }
  → Returns: { messaging_product: "whatsapp", request_id: "..." }
  → NOTE: Group creation is ASYNC. The group_id arrives via group_lifecycle_update webhook.
  → The group appears in GET /{phone_number_id}/groups after a few seconds.

GET /{phone_number_id}/groups
  → Returns: { data: [{ id, subject, created_at }], paging: {...} }
  → NOTE: Uses phone_number_id NOT waba_id

GET /{group_id}?fields=id,subject,description,creation_timestamp,participants,total_participant_count,join_approval_mode,suspended,messaging_permission,member_visibility
  → Returns group details with all requested fields
  → NOTE: `owner` and `invite_link` are NOT valid fields here. Use /{group_id}/invite_link endpoint instead.
  → NOTE: `messaging_permission` and `member_visibility` may return empty if not yet set.

POST /{group_id}
  Body: { messaging_product: "whatsapp", subject: "...", description: "...", messaging_permission: "all"|"admins", member_visibility: "all"|"admins" }
  → Updates group settings (subject, description confirmed working; privacy fields may require beta access)
  → Image upload: multipart form with file=@image.png (may require specific permissions)

DELETE /{group_id}
  → Deletes group and removes all participants
```

### Invite Link

```
GET /{group_id}/invite_link
  → Returns: { invite_link: "https://chat.whatsapp.com/LINK_ID" }

POST /{group_id}/invite_link
  Body: { messaging_product: "whatsapp" }
  → Resets invite link (previous links become invalid)
```

### Participants

```
DELETE /{group_id}/participants
  Body: { messaging_product: "whatsapp", participants: [{ user: "+1234567890" }] }
  → Removes participants (removed users cannot rejoin via invite link)
```

Note: You CANNOT add participants directly via API. Participants must join via invite link.

### Join Requests (when join_approval_mode = "approval_required")

```
GET /{group_id}/join_requests
  → Returns: { data: [{ join_request_id, wa_id, creation_timestamp }] }

POST /{group_id}/join_requests
  Body: { messaging_product: "whatsapp", join_requests: ["JOIN_REQUEST_ID"] }
  → Approves join requests

DELETE /{group_id}/join_requests
  Body: { messaging_product: "whatsapp", join_requests: ["JOIN_REQUEST_ID"] }
  → Rejects join requests
```

### Group Messaging

```
POST /{phone_number_id}/messages
  Body: {
    messaging_product: "whatsapp",
    recipient_type: "group",
    to: "GROUP_ID",
    type: "text"|"image"|"video"|"document"|"audio"|"template",
    text: { body: "...", preview_url: true },        // for text
    image: { link: "https://..." , caption: "..." },  // for image
    video: { link: "https://..." , caption: "..." },  // for video
    document: { link: "https://...", caption: "...", filename: "..." }, // for document
    audio: { link: "https://..." },                   // for audio
    template: { name: "...", language: { code: "en" }, components: [...] } // for template
  }
  → Supported types: text, image, video, document, audio, template
  → NOT supported in groups: interactive, contacts, location, sticker, reaction
```

### Privacy Settings (via POST /{group_id})

```
messaging_permission: "all" (everyone can post) | "admins" (admin-only posting)
member_visibility: "all" (all members visible) | "admins" (only admins see member list)
join_approval_mode: "auto_approve" | "approval_required"
```
NOTE: Privacy fields may require beta access or specific API version. Subject and description updates confirmed working.

## Webhooks

### group_lifecycle_update
Triggered on: group creation, group deletion
```json
{
  "field": "messages",
  "value": {
    "messaging_product": "whatsapp",
    "metadata": { "display_phone_number": "...", "phone_number_id": "..." },
    "group_lifecycle_updates": [{
      "group_id": "GROUP_ID",
      "type": "CREATION" | "DELETION",
      "invite_link": "https://chat.whatsapp.com/..."
    }]
  }
}
```

### group_participants_update
Triggered on: participant join, participant leave, participant removed
```json
{
  "group_participants_updates": [{
    "group_id": "GROUP_ID",
    "type": "JOIN" | "LEAVE" | "REMOVED",
    "participant": { "wa_id": "..." }
  }]
}
```

### group_settings_update
Triggered on: subject/description/photo change
```json
{
  "group_settings_updates": [{
    "group_id": "GROUP_ID",
    "type": "SUBJECT" | "DESCRIPTION" | "PHOTO",
    "new_value": "..."
  }]
}
```

## WECARE.DIGITAL Implementation

### Backend (Lambda)
- Handler: `amplify/functions/messaging/whatsapp-business-api/handler.py`
- Routes:
  - `GET/POST/PUT/DELETE /wa-business/groups` — CRUD
  - `POST /wa-business/groups/participants` — Remove participants
  - `POST /wa-business/groups/send` — Send group message
  - `GET/POST /wa-business/groups/invite-link` — Get/reset invite link
  - `GET/POST/DELETE /wa-business/groups/join-requests` — Manage join requests

### Frontend
- Page: `src/pages/dm/whatsapp/groups.tsx`
- Embedded in settings page under "Groups" tab
- API client: `src/api/client.ts` (listGroups, createGroup, getGroup, etc.)

### Data Model
- `WhatsAppGroup` table in DynamoDB (amplify/data/resource.ts)
  - Tracks: groupId, wabaId, subject, description, inviteLink, participantCount, joinApprovalMode

### Script
- `scripts/_create_bharat_stack_group.py` — Creates the "Bharat Stack" group on WABA1
- `scripts/_share_bharat_stack_link.py` — Shares the invite link to phone numbers

### Live Group: Bharat Stack
- Group ID: `Y2FwaV9ncm91cDo5MTkzMzA5OTQ0MDA6MTIwMzYzNDI0MzYyMTc4MDYx`
- Invite Link: `https://chat.whatsapp.com/D0j5ozSQnjFAtavhXO09ZR`
- Phone: +919330994400 (WECARE.DIGITAL)
- WABA: 2094615664435155
- Join mode: auto_approve
- Capacity: 512 participants

### Configuration
- WABA1: 2094615664435155 (WECARE.DIGITAL, +919330994400)
- WABA2: 2513394156072604 (Manish Agarwal, +919903300044)
- Phone1 Meta ID: 1016149501586345
- Phone2 Meta ID: 1055232054343117
- Meta API Version: v25.0

## Group Invite Template

To invite users at scale, create a template with `library_template_name: "group_invite_link"`:

```json
{
  "name": "bharat_stack_invite",
  "category": "UTILITY",
  "language": "en",
  "library_template_name": "group_invite_link",
  "components": [
    {
      "type": "BODY",
      "text": "You're invited to join *Bharat Stack* — India's digital infrastructure community by WECARE.DIGITAL. Tap below to join."
    },
    {
      "type": "BUTTONS",
      "buttons": [{ "type": "URL", "text": "Join Group", "url": "{{1}}" }]
    }
  ]
}
```

## Important Limitations (Confirmed via Live API)

1. `join_approval_mode` can ONLY be set at group creation time. It CANNOT be changed after creation.
   - To switch from auto_approve to approval_required, you must create a new group.
2. `messaging_permission` and `member_visibility` settings return error 131009 — may require beta access or newer API version.
3. Group image upload via multipart form returns error 131009 — may require specific permissions.
4. `owner` and `invite_link` are NOT valid fields on GET /{group_id}. Use /{group_id}/invite_link endpoint.
5. Group creation is ASYNC — returns request_id, group_id arrives via webhook.
6. Business phones CANNOT join external/public groups via Cloud API. The API only supports creating and managing your own groups.
7. You cannot add participants directly — they must join via invite link.

## Eligibility Requirements

1. Business must have a verified Meta Business Portfolio
2. Phone number must be registered on Cloud API (not On-Premises)
3. Groups NOT available for Coexistence users
4. Groups NOT available for Multi-solution Conversations phone numbers
