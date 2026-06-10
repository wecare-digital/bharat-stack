# Live Smoke Test Plan (gated)

**Guard:** No live send runs unless BOTH are set:
```
WA_LIVE_SMOKE_TEST=true
WA_QA_RECIPIENT=91XXXXXXXXXX   # masked in all logs as +91******XXXX
```
Only send to the QA recipient. Never a real customer number.

## Battery
| # | Test | How | Pass criteria |
|---|------|-----|---------------|
| 1 | Template list (read-only) | `GET /whatsapp/templates?wabaId=2094615664435155` | Returns templates with `components` + `language` |
| 2 | Text send | `POST /whatsapp/send` text to QA | `messages[0].id` returned; row in `WhatsAppOutboundTable` |
| 3 | Media: image/doc/audio/video | upload → `POST /whatsapp/send` mediaFile | delivered; media id stored |
| 4 | Template (body-only) WABA 1 | `wecare_otp`-style | accepted; status webhook → delivered |
| 5 | Template w/ DOCUMENT header | `wecare_pdf` + uploaded PDF | header renders; delivered |
| 6 | Template → NEW number | "New template message" → QA number (not saved) | contact auto-created; delivered; appears in inbox |
| 7 | Template WABA 2 | switch WABA selector | delivered from WABA 2 |
| 8 | Typing indicator | `sendTypingIndicator(waba, inboundWamid)` | 200; bubble shown |
| 9 | Mark read | inbound context | read receipt accepted |
| 10 | Webhook inbound | reply from QA phone | row in `WhatsAppInboundTable` |
| 11 | Status webhook | observe sent→delivered→read | `WhatsAppOutboundTable` status updates |
| 12 | Flow (if `WA_FLOWS_ENABLED`) | `POST /wa-business/flows` test send | response webhook → `FlowSubmissionTable` |

## Result template
For each: payload (redacted), API response code, message id, DynamoDB evidence, Live verified Yes/No.

**Current run:** NOT EXECUTED — `WA_QA_RECIPIENT` missing → status `MOCKED_ONLY_WAITING_FOR_CREDENTIALS` for all send tests. Test 1 (list) verified via direct Lambda invoke.
