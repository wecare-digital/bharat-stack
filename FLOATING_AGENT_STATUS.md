# Floating Agent - Current Status & Troubleshooting

## 🔧 Architecture Change: Using Next.js API Route

To avoid browser CORS and fetch issues, the floating agent now uses a Next.js API route as a proxy:

```
Browser → /api/ai/generate (Next.js) → https://api.wecare.digital/ai/generate (API Gateway)
```

This solves:
- Browser CORS restrictions
- Fetch API issues in some browsers
- Network proxy/firewall issues
- SSL certificate validation issues

The API route is at: `src/app/api/ai/generate/route.ts`

---

## ✅ System Status: OPERATIONAL

### Infrastructure
- **API Gateway**: `https://api.wecare.digital/ai/generate` ✅ Working
- **Lambda Function**: `wecare-ai-generate-response` ✅ Deployed
- **Next.js Dev Server**: `http://localhost:3000` ✅ Running
- **Environment Variables**: ✅ Configured correctly

### API Test Results
```bash
# Direct API test - SUCCESS
curl -X POST "https://api.wecare.digital/ai/generate" \
  -H "Content-Type: application/json" \
  -d '{"messageContent":"test","context":"internal-admin","sessionId":"test-123"}'

# Response: 200 OK
```

### CORS Configuration
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: DELETE,GET,OPTIONS,PATCH,POST,PUT
Access-Control-Allow-Headers: authorization,content-type,x-amz-date,x-amz-security-token,x-api-key
```

---

## 🎯 Current Capabilities (21 Tools)

### 1. Contact Management (4 tools)
- ✅ `search_contacts` - Find contacts by name/phone/email
- ✅ `create_contact` - Create new contact
- ✅ `update_contact` - Update contact details
- ✅ `add_contact_email` - Add/update email address

**Example Queries:**
```
"find contact Jignesh"
"create contact Kumar +919876543210"
"update Jignesh's email to new@email.com"
"add email to Jignesh"
```

### 2. WhatsApp Messaging (3 tools)
- ✅ `send_whatsapp` - Send simple text message
- ✅ `send_whatsapp_buttons` - Send interactive buttons (up to 3)
- ✅ `send_whatsapp_list` - Send interactive list menu

**Example Queries:**
```
"send hi message to Jignesh"
"send message to +919330994400 saying Hello"
"send buttons to Jignesh: Yes, No, Maybe"
"send list menu to Kumar with options: Product A, Product B, Product C"
```

### 3. Multi-Channel Communication (3 tools)
- ✅ `make_voice_call` - Make voice call with TTS or audio
- ✅ `send_sms` - Send SMS message
- ✅ `send_email` - Send email message

**Example Queries:**
```
"call Jignesh and say Your order is ready"
"send SMS to +919876543210 saying Meeting at 3pm"
"email Jignesh about the new product"
```

### 4. Analytics & History (2 tools)
- ✅ `get_messages` - Get message history for contact
- ✅ `get_stats` - Get dashboard statistics

**Example Queries:**
```
"show messages from Jignesh"
"what messages did I send to Kumar"
"show me dashboard stats"
"how many messages sent today"
```

### 5. Scheduling (2 tools)
- ✅ `schedule_message` - Schedule message for future
- ✅ `list_scheduled_messages` - List scheduled messages

**Example Queries:**
```
"schedule message to Jignesh tomorrow 10am saying Reminder"
"show scheduled messages"
"list all scheduled messages"
```

### 6. Templates (2 tools)
- ✅ `list_templates` - List available WhatsApp templates
- ✅ `send_template` - Send template message

**Example Queries:**
```
"show me all templates"
"send template welcome_message to Jignesh"
```

### 7. Data Management (6 tools)
- ✅ `add_contact_email` - Add/update email
- ✅ `delete_contact` - Soft delete contact
- ✅ `delete_messages` - Delete specific/all messages
- ✅ `delete_media_files` - Delete S3 media files
- ✅ `list_media_files` - List media files
- ✅ `clear_all_contact_data` - Clear all data (requires confirmation)

**Example Queries:**
```
"delete contact Jignesh"
"delete all messages from Kumar"
"list media files for Jignesh"
"delete media files older than 30 days"
"clear all data for test contact"
```

---

## 🔧 Troubleshooting

### Issue: "Failed to fetch" Error in Browser

**Root Cause**: Browser cache or dev server not picking up changes

**Solution Steps:**

1. **Restart Next.js Dev Server** (DONE ✅)
   ```bash
   # Server restarted successfully
   # Running at: http://localhost:3000
   ```

2. **Clear Browser Cache**
   - Press `Ctrl + Shift + R` (hard refresh)
   - Or open DevTools → Network tab → Check "Disable cache"
   - Or test in Incognito mode

3. **Verify API in Browser Console**
   ```javascript
   fetch('https://api.wecare.digital/ai/generate', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       messageContent: 'test',
       context: 'internal-admin',
       sessionId: 'test-123'
     })
   }).then(r => r.json()).then(console.log)
   ```

4. **Check Browser Console for Errors**
   - Open DevTools (F12)
   - Check Console tab for errors
   - Check Network tab for failed requests
   - Look for CORS errors or network issues

### Issue: AI Not Understanding Contact Names

**Root Cause**: AI needs to search contacts first

**Solution**: The AI automatically chains tools:
```
User: "send hi to Jignesh"
→ AI calls search_contacts("Jignesh")
→ AI gets phone number
→ AI calls send_whatsapp(phone, "hi")
```

### Issue: Voice Input Not Working

**Root Cause**: Browser doesn't support Web Speech API

**Solution**: Use Chrome, Edge, or Safari (Firefox not supported)

---

## 🚀 Next Steps for Testing

### 1. Test in Browser
1. Open `http://localhost:3000`
2. Click the floating agent button (bottom right)
3. Try these test queries:
   ```
   "help"
   "find contact Jignesh"
   "show me dashboard stats"
   "send test message to +919330994400"
   ```

### 2. Test Voice Input
1. Click the microphone icon
2. Say: "find contact Jignesh"
3. Message should auto-send after speech recognition

### 3. Test Tool Chaining
1. Type: "send hi message to Jignesh"
2. AI should:
   - Search for contact "Jignesh"
   - Get phone number
   - Send WhatsApp message
   - Confirm success

---

## 📈 Future Expansion Phases

### Phase 2: Advanced Messaging (8 tools)
- Media messages (image, video, document, audio)
- Location sharing
- Contact cards
- Stickers and reactions

### Phase 3: Campaign Management (10 tools)
- Create and manage campaigns
- Bulk messaging
- Campaign analytics
- A/B testing

### Phase 4: Payment & Invoicing (8 tools)
- Invoice generation
- Payment links
- Payment tracking
- Receipt generation

### Phase 5: Advanced Analytics (12 tools)
- Contact insights
- Revenue reports
- Sentiment analysis
- Engagement scoring

### Phase 6: Automation & Workflows (10 tools)
- Workflow creation
- Trigger conditions
- Action sequences
- Automation testing

**Total Planned Tools**: 150+ across 16 phases

See `docs/FLOATING_AGENT_VISION.md` for complete roadmap.

---

## 🔐 Security & Best Practices

### Authentication
- Internal agent uses session-based auth
- No user authentication required (admin-only)
- Session timeout: 30 minutes

### Data Management
- Soft deletes for contacts (marked as deleted, not removed)
- Dangerous operations require confirmation
- All operations logged for audit

### Rate Limiting
- API Gateway: 10,000 requests/second
- Lambda: 1000 concurrent executions
- DynamoDB: On-demand capacity

---

## 📞 Support

### Documentation
- `docs/INTERNAL_AGENT.md` - Full technical documentation
- `docs/INTERNAL_AGENT_QUICK_REF.md` - Quick reference
- `docs/DATA_MANAGEMENT_TOOLS.md` - Data cleanup guide
- `docs/FLOATING_AGENT_VISION.md` - Complete vision & roadmap

### Settings Page
- URL: `http://localhost:3000/settings/internal-agent`
- Configure AI model, temperature, tools
- View usage statistics
- Enable/disable specific tools

### API Endpoints
- **Production**: `https://api.wecare.digital/ai/generate`
- **Lambda Direct**: `https://xijlt2fidotq7zbn3s5xlyzup40dxbcm.lambda-url.us-east-1.on.aws`

---

## ✅ Deployment Checklist

- [x] Lambda function deployed with dependencies
- [x] API Gateway configured with custom domain
- [x] CORS headers configured
- [x] Environment variables set
- [x] DynamoDB tables configured
- [x] S3 buckets configured
- [x] Next.js dev server running
- [x] Documentation created
- [x] Settings page created
- [ ] Browser cache cleared (USER ACTION REQUIRED)
- [ ] Test in browser (USER ACTION REQUIRED)

---

**Last Updated**: 2026-03-03  
**Status**: Ready for testing  
**Action Required**: Clear browser cache and test in browser
