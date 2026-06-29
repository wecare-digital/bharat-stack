# Meta Business Agent (MBA) — readiness & implementation plan

Meta Business Agent is a **Meta-hosted AI agent** that answers WhatsApp chats
directly (Meta runs the model, knowledge, and tools). It is an alternative to our
self-hosted Bedrock AI (`ai-generate-response`). Docs:
https://developers.facebook.com/documentation/meta-business-agent/get-started

## Eligibility
- **Countries:** Brazil, India, Mexico, Saudi Arabia, UK, US → **India ✅ (we qualify)**.
- **Verticals:** Automotive, CPG, **Professional Services ✅ (ours)**, Retail/Ecommerce, Travel.

## Readiness — verified live (Jun 2026)
| Prerequisite | Status |
|---|---|
| WABA ID | ✅ `2094615664435155` (WABA1), `2513394156072604` (WABA2) |
| App ID | ✅ `2238810740192680` |
| Token type | ✅ SYSTEM_USER (non-expiring) |
| `whatsapp_business_messaging` scope | ✅ granted (debug_token) |
| `whatsapp_business_management` scope | ✅ granted |
| App subscribed to WABA (Step 6) | ✅ verified via `GET /{WABA}/subscribed_apps` |
| Webhook field `messages` (Step 7) | ✅ already subscribed |
| Webhook fields `message_echoes`, `messaging_handovers` (Step 7) | ✅ added to Webhooks UI to subscribe |

## Manual / Meta-gated steps (cannot be automated)
1. **Step 1 — Enable MBA in WhatsApp Manager** → Meta Business Agent tab → enable for an
   eligible phone number. Gated by country/vertical approval. **Required before the
   agent APIs work** (same gating pattern as usernames).
2. **Step 8 — Send test consumer numbers to your Meta contact** to enable the `reset`
   command for testing.

## Endpoints to implement (from get-started "Next steps")
Backend target: `/wa-business/agent/*` proxied to the Meta Graph endpoints, with a
frontend "Business Agent" admin page. Exact Graph paths/schemas are required first
(reference pages are login-gated; not publicly fetchable):

| Endpoint | Purpose |
|---|---|
| Settings | Agent behavior, persona, language |
| Skills | System instructions |
| Business info | Business details the agent can reference |
| FAQs | Q&A knowledge pairs |
| Websites | Reference URLs |
| Catalog | Connect a product catalog |
| Files | Upload knowledge files |
| Connectors | External APIs the agent can call |
| Connector tools | Operations on a connector |
| Thread control | Agent ↔ human handoff |
| Agent eval | Performance evaluation |
| Agent test | Simulated conversation tests |

## Blocker to build
The per-endpoint API reference (paths, methods, request/response JSON) is **not
publicly fetchable** — it renders behind the Meta developer-portal login. To build
the module accurately I need, for each endpoint above:
- the Graph path (e.g. `POST /{WABA_ID}/<edge>` or `/{phone_id}/<edge>`),
- request body fields, and
- response shape.

Paste the reference pages (as done for the BSUID doc) or export them, and the module
will be built precisely (backend routes + tests + frontend page) — same pattern as
flows/templates.

## Note: MBA vs our Bedrock AI
MBA moves inference + knowledge to Meta. We already run `ai-generate-response`
(Bedrock, self-hosted, with our own KB/guardrails). Decide whether MBA replaces or
complements it before going live, to avoid two agents answering the same chats
(`messaging_handovers` / Thread control governs who responds).
