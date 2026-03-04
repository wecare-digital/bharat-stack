# 🚀 Floating Agent - Quick Start Guide

## ✅ System is Ready!

Your AI-powered internal agent is deployed and operational. The API is working correctly.

---

## 🎯 What You Can Do Right Now

The floating agent can handle 21 different types of tasks across 7 categories:

### 1. Contact Management
```
"find contact Jignesh"
"create contact Kumar +919876543210"
"update Jignesh's email to new@email.com"
```

### 2. Send Messages
```
"send hi message to Jignesh"
"send message to +919330994400 saying Hello"
"send buttons to Jignesh: Yes, No, Maybe"
```

### 3. Make Calls & Send SMS
```
"call Jignesh and say Your order is ready"
"send SMS to +919876543210 saying Meeting at 3pm"
```

### 4. View Analytics
```
"show messages from Jignesh"
"show me dashboard stats"
"how many messages sent today"
```

### 5. Schedule Messages
```
"schedule message to Jignesh tomorrow 10am saying Reminder"
"show scheduled messages"
```

### 6. Manage Templates
```
"show me all templates"
"send template welcome_message to Jignesh"
```

### 7. Data Management
```
"delete contact Jignesh"
"delete all messages from Kumar"
"list media files for Jignesh"
```

---

## 🧪 Testing Options

### Option 1: Test with Standalone HTML (Recommended First)

1. Open `test-floating-agent.html` in your browser
2. It will auto-test the API connection
3. Try the quick test buttons or type your own queries
4. This bypasses any browser cache issues

### Option 2: Test in Your App

1. Open `http://localhost:3000` in your browser
2. **Clear browser cache**: Press `Ctrl + Shift + R` (hard refresh)
3. Click the floating agent button (bottom right corner)
4. Try these test queries:
   ```
   help
   find contact Jignesh
   show me dashboard stats
   ```

### Option 3: Test with Browser Console

1. Open your app at `http://localhost:3000`
2. Press `F12` to open DevTools
3. Go to Console tab
4. Paste this code:
   ```javascript
   fetch('https://api.wecare.digital/ai/generate', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       messageContent: 'help',
       context: 'internal-admin',
       sessionId: 'test-123'
     })
   }).then(r => r.json()).then(console.log)
   ```

---

## 🔧 If You Still See "Failed to fetch"

### Step 1: Clear Browser Cache
- Press `Ctrl + Shift + R` (Windows/Linux)
- Or `Cmd + Shift + R` (Mac)
- Or open in Incognito/Private mode

### Step 2: Check Browser Console
1. Press `F12` to open DevTools
2. Go to Console tab
3. Look for any error messages
4. Go to Network tab
5. Try sending a message
6. Check if the request appears and what the error is

### Step 3: Verify Environment
1. Check `.env.local` has:
   ```
   NEXT_PUBLIC_API_BASE=https://api.wecare.digital
   ```
2. Restart dev server if you changed it:
   ```bash
   # Stop current server (Ctrl+C)
   npm run dev
   ```

---

## 🎤 Voice Input

The floating agent supports voice input!

1. Click the microphone icon in the chat
2. Speak your command (e.g., "find contact Jignesh")
3. The message will auto-send after recognition
4. Works in Chrome, Edge, and Safari (not Firefox)

---

## ⚙️ Settings Page

Configure the agent at: `http://localhost:3000/settings/internal-agent`

You can:
- Enable/disable the agent
- Change AI model (Nova Lite, Nova Pro, Claude)
- Adjust temperature and max tokens
- Enable/disable specific tools
- View usage statistics

---

## 📚 Documentation

- **FLOATING_AGENT_STATUS.md** - Current status and troubleshooting
- **docs/INTERNAL_AGENT.md** - Full technical documentation
- **docs/INTERNAL_AGENT_QUICK_REF.md** - Quick reference guide
- **docs/DATA_MANAGEMENT_TOOLS.md** - Data cleanup tools guide
- **docs/FLOATING_AGENT_VISION.md** - Complete roadmap (150+ tools planned)

---

## 🚀 Future Capabilities

The agent is designed to expand to 150+ tools across 16 phases:

- **Phase 2**: Media messaging (images, videos, documents)
- **Phase 3**: Campaign management (bulk messaging, A/B testing)
- **Phase 4**: Payment & invoicing (payment links, receipts)
- **Phase 5**: Advanced analytics (sentiment analysis, engagement scoring)
- **Phase 6**: Automation & workflows (trigger-based actions)
- And 10 more phases...

See `docs/FLOATING_AGENT_VISION.md` for the complete roadmap.

---

## 🎯 Next Steps

1. **Test the API** using `test-floating-agent.html`
2. **Clear browser cache** and test in your app
3. **Try voice input** with the microphone button
4. **Explore capabilities** by asking "help" or trying different queries
5. **Check settings page** to configure the agent

---

## 📞 Quick Reference

- **API Endpoint**: `https://api.wecare.digital/ai/generate`
- **Dev Server**: `http://localhost:3000`
- **Settings**: `http://localhost:3000/settings/internal-agent`
- **Test File**: `test-floating-agent.html`
- **Lambda Function**: `wecare-ai-generate-response`
- **Session Timeout**: 30 minutes

---

## ✅ System Status

- [x] Lambda deployed with all dependencies
- [x] API Gateway configured with custom domain
- [x] CORS headers configured correctly
- [x] Environment variables set
- [x] Next.js dev server running
- [x] Documentation created
- [x] Test file created
- [ ] **Browser cache cleared** ← YOU ARE HERE
- [ ] **Test in browser** ← NEXT STEP

---

**Ready to test!** Open `test-floating-agent.html` or clear your browser cache and try the app.
