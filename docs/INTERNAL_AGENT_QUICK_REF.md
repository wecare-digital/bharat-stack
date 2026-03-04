# Internal Agent - Quick Reference

## 🚀 Quick Start

Just type naturally! The AI understands context and executes tasks automatically.

## 📝 Example Queries

### Contact Management
```
"find contact Jignesh"
"search for contacts with 9330994400"
"create contact named John with phone +919876543210"
"update Jignesh's email to new@email.com"
```

### Send Messages
```
"send hi message to Jignesh"
"send hello to all contacts named Kumar"
"send WhatsApp to +919330994400 saying test message"
```

### Interactive Messages
```
"send buttons to Jignesh with options Yes, No, Maybe"
"send list menu to Jignesh with products: Product A, Product B"
"create interactive message for Jignesh asking for feedback"
```

### Voice & SMS
```
"make voice call to Jignesh saying hello"
"call Jignesh with pre-recorded message"
"send SMS to Jignesh: your order is ready"
"email Jignesh about the meeting"
```

### Message History
```
"show messages from Jignesh"
"what did Jignesh say last"
"get last 20 messages with Jignesh"
"show me all conversations today"
```

### Analytics
```
"what are today's stats"
"show dashboard statistics"
"how many messages sent today"
"total contacts count"
```

### Scheduling
```
"schedule message to Jignesh for tomorrow 10am"
"remind Jignesh about meeting at 3pm"
"list all scheduled messages"
```

### Templates
```
"list available templates"
"send template welcome_message to Jignesh"
"use template order_confirmation for Jignesh"
```

## 🎯 Pro Tips

1. **Be Natural**: No need for exact syntax - AI understands context
2. **Multi-Step**: AI can chain actions (search → send → confirm)
3. **Context Aware**: Remembers previous conversation
4. **Smart Search**: Mentions name? AI searches automatically
5. **Error Recovery**: If something fails, AI suggests alternatives

## ⚙️ Settings

Access: `/settings/internal-agent`

**Quick Toggles:**
- Enable/Disable agent
- Auto-search contacts
- Conversation history
- Default channel

**Advanced:**
- AI model selection
- Temperature (creativity)
- Session timeout
- Tool permissions

## 🔧 Capabilities Matrix

| Feature | WhatsApp | SMS | Email | Voice |
|---------|----------|-----|-------|-------|
| Simple Text | ✅ | ✅ | ✅ | ✅ (TTS) |
| Interactive Buttons | ✅ | ❌ | ❌ | ❌ |
| Interactive Lists | ✅ | ❌ | ❌ | ❌ |
| Scheduling | ✅ | ✅ | ✅ | ✅ |
| Templates | ✅ | ❌ | ❌ | ❌ |
| Media | 🚧 | ❌ | ✅ | ❌ |

✅ Available | ❌ Not Available | 🚧 Coming Soon

## 🆘 Troubleshooting

**Agent not responding?**
- Check if enabled in settings
- Verify API connection
- Try "help" command

**Wrong contact found?**
- Be more specific with name/phone
- Use full phone number with country code
- Check contact exists in CRM

**Message not sent?**
- Verify contact has valid phone/email
- Check channel is enabled
- Review error message from AI

## 📊 Current Limits

- Max message length: 2000 characters
- Session timeout: 15 minutes (configurable)
- Max conversation history: 20 messages
- Tool execution timeout: 120 seconds

## 🔮 Coming Soon

- Bulk messaging
- Campaign management
- Payment links
- Media messages
- Custom workflows
- Team collaboration
- Advanced analytics
- CRM integrations

## 💡 Best Practices

1. **Use Names**: "send to Jignesh" vs "send to +919876543210"
2. **Be Specific**: "send WhatsApp" vs just "send"
3. **Check Results**: AI confirms actions taken
4. **Use History**: Reference previous messages
5. **Try Help**: Type "help" for capabilities

## 🎓 Learning Examples

### Beginner
```
"help"
"find Jignesh"
"send hi to Jignesh"
```

### Intermediate
```
"send interactive buttons to Jignesh asking if he wants to proceed"
"show me all messages from Jignesh today"
"schedule reminder to Jignesh for tomorrow"
```

### Advanced
```
"find all contacts named Kumar and send them a welcome message"
"create voice call campaign for product launch"
"analyze message patterns for Jignesh"
```

---

**Need Help?** Type "help" in the agent or visit `/settings/internal-agent`
