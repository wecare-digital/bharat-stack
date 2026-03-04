# Internal Agent - AI-Powered Admin Assistant

## Overview

The Internal Agent is an AI-powered assistant built with Amazon Bedrock that helps admin users perform tasks through natural language. It uses tool calling (function calling) to execute actions dynamically.

## Architecture

```
FloatingAgent (Frontend)
    ↓
AI Generate Response Lambda
    ↓
Amazon Bedrock Converse API (Nova Lite)
    ↓
Tool Execution (15+ capabilities)
    ↓
Various Lambda Functions & DynamoDB
```

## Current Capabilities (15 Tools)

### 1. Contact Management
- **search_contacts**: Find contacts by name, phone, or email
- **create_contact**: Add new contacts to CRM
- **update_contact**: Modify existing contact details

### 2. WhatsApp Messaging
- **send_whatsapp**: Send simple text messages
- **send_whatsapp_buttons**: Send interactive button messages (up to 3 buttons)
- **send_whatsapp_list**: Send interactive list menus with sections

### 3. Multi-Channel Communication
- **make_voice_call**: Initiate voice calls with TTS or pre-recorded audio
- **send_sms**: Send SMS messages
- **send_email**: Send email messages

### 4. Analytics & History
- **get_messages**: Retrieve message history for contacts
- **get_stats**: Get dashboard statistics (contacts, messages, activity)

### 5. Advanced Features
- **schedule_message**: Schedule messages for future delivery
- **list_scheduled_messages**: View pending scheduled messages
- **list_templates**: List available WhatsApp templates
- **send_template**: Send WhatsApp template messages

## Usage Examples

### Natural Language Queries

```
"send a hi message to Jignesh"
→ AI searches for Jignesh → Sends WhatsApp message

"show me messages from Jignesh"
→ AI finds Jignesh → Retrieves message history

"make a voice call to Jignesh saying hello"
→ AI finds Jignesh → Initiates TTS voice call

"send interactive buttons to Jignesh with options Yes and No"
→ AI creates button message → Sends to Jignesh

"what are today's stats"
→ AI retrieves dashboard statistics

"schedule a reminder to Jignesh for tomorrow at 10am"
→ AI schedules message for specified time
```

## How It Works

### 1. User Input
User types natural language query in FloatingAgent

### 2. AI Processing
- Query sent to Lambda with context: 'internal-admin'
- Bedrock Converse API analyzes intent
- AI decides which tools to use

### 3. Tool Execution
- AI calls appropriate tools (e.g., search_contacts, send_whatsapp)
- Tools execute via Lambda invocations or DynamoDB queries
- Results returned to AI

### 4. Response Generation
- AI synthesizes tool results into natural language
- Response sent back to user
- Conversation history maintained

## Configuration

### Settings Page
Access at: `/settings/internal-agent`

**General Settings:**
- Enable/Disable agent
- AI Model selection (Nova Lite, Nova Pro, Claude, etc.)
- Temperature (creativity level)
- Max tokens (response length)
- Session timeout
- Default channel (WhatsApp/SMS/Email)
- Auto-search contacts
- Conversation history

**Tool Capabilities:**
- Enable/disable specific tools
- Organized by category
- Bulk enable/disable by category

## Expanding Capabilities

### Adding New Tools

#### 1. Define Tool Schema (handler.py)

```python
{
    'toolSpec': {
        'name': 'your_tool_name',
        'description': 'What this tool does - be specific for AI understanding',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'param1': {
                        'type': 'string',
                        'description': 'Parameter description'
                    }
                },
                'required': ['param1']
            }
        }
    }
}
```

#### 2. Add Tool Router (handler.py)

```python
def _execute_internal_tool(tool_name: str, tool_input: Dict, request_id: str) -> Dict:
    # ... existing tools ...
    elif tool_name == 'your_tool_name':
        return _tool_your_tool_name(tool_input, request_id)
```

#### 3. Implement Tool Function (handler.py)

```python
def _tool_your_tool_name(params: Dict, request_id: str) -> Dict:
    """Your tool implementation."""
    try:
        # Your logic here
        result = do_something(params)
        
        return {
            'success': True,
            'data': result,
            'message': 'Operation completed'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

#### 4. Deploy

```powershell
.\deploy-lambda.ps1
```

### Example: Adding Bulk Message Tool

```python
# 1. Tool Schema
{
    'toolSpec': {
        'name': 'send_bulk_message',
        'description': 'Send same message to multiple contacts at once',
        'inputSchema': {
            'json': {
                'type': 'object',
                'properties': {
                    'contactIds': {
                        'type': 'array',
                        'description': 'Array of contact IDs',
                        'items': {'type': 'string'}
                    },
                    'message': {
                        'type': 'string',
                        'description': 'Message to send'
                    },
                    'channel': {
                        'type': 'string',
                        'description': 'Channel: whatsapp, sms, email'
                    }
                },
                'required': ['contactIds', 'message', 'channel']
            }
        }
    }
}

# 2. Implementation
def _tool_send_bulk_message(params: Dict, request_id: str) -> Dict:
    """Send bulk messages."""
    contact_ids = params.get('contactIds', [])
    message = params.get('message')
    channel = params.get('channel', 'whatsapp')
    
    if not contact_ids or not message:
        return {'success': False, 'error': 'contactIds and message required'}
    
    results = []
    for contact_id in contact_ids:
        # Send message to each contact
        result = send_message(contact_id, message, channel)
        results.append(result)
    
    return {
        'success': True,
        'sent': len([r for r in results if r.get('success')]),
        'failed': len([r for r in results if not r.get('success')]),
        'message': f'Sent to {len(results)} contacts'
    }
```

## Future Expansion Ideas

### 1. Campaign Management
- Create campaigns
- Add contacts to campaigns
- Track campaign performance
- Schedule campaign messages

### 2. Payment & Invoicing
- Generate invoices
- Send payment links
- Track payment status
- Send payment reminders

### 3. Analytics & Reports
- Generate custom reports
- Export data (CSV, PDF)
- Visualize trends
- Predictive analytics

### 4. Automation Workflows
- Create automated sequences
- Trigger-based actions
- Conditional logic
- Multi-step workflows

### 5. Integration Tools
- Wix store integration
- CRM sync
- Calendar integration
- Third-party APIs

### 6. Advanced Messaging
- Send media (images, videos, documents)
- Send location messages
- Send contact cards
- Message reactions

### 7. Team Collaboration
- Assign conversations
- Internal notes
- Team chat
- Task management

### 8. Customer Insights
- Sentiment analysis
- Intent classification
- Customer segmentation
- Behavior tracking

## Best Practices

### Tool Design
1. **Clear Descriptions**: AI relies on descriptions to choose tools
2. **Specific Parameters**: Define exact parameter types and requirements
3. **Error Handling**: Always return success/error status
4. **Logging**: Log tool usage for debugging and analytics

### AI Prompting
1. **System Prompt**: Keep it focused on task execution
2. **Tool Descriptions**: Be specific about when to use each tool
3. **Examples**: Provide usage examples in descriptions
4. **Constraints**: Mention limitations clearly

### Performance
1. **Tool Chaining**: AI can call multiple tools in sequence
2. **Caching**: Cache frequently accessed data
3. **Timeouts**: Set appropriate Lambda timeouts
4. **Retries**: Implement retry logic for failures

### Security
1. **Validation**: Validate all tool inputs
2. **Authorization**: Check user permissions
3. **Rate Limiting**: Prevent abuse
4. **Audit Logging**: Track all tool executions

## Troubleshooting

### AI Not Using Tools
- Check tool descriptions are clear
- Verify tool schema is valid JSON
- Review system prompt for clarity
- Check CloudWatch logs for errors

### Tool Execution Failures
- Verify Lambda permissions
- Check DynamoDB table access
- Review error logs
- Test tool functions independently

### Slow Responses
- Reduce max_tokens if too high
- Optimize tool implementations
- Check Lambda cold starts
- Review conversation history size

## Monitoring

### CloudWatch Logs
- `/aws/lambda/wecare-ai-generate-response`
- Search for: `internal_agent_called`, `internal_tool_use`, `internal_converse_iteration`

### Metrics to Track
- Tool usage frequency
- Response times
- Error rates
- Token consumption
- User satisfaction

## API Endpoints

### Get Internal Agent Config
```
GET /ai/internal/config
```

### Update Internal Agent Config
```
PUT /ai/internal/config
Body: { enabled, modelId, temperature, ... }
```

### Generate Response
```
POST /ai/generate
Body: {
  messageContent: "user query",
  context: "internal-admin",
  sessionId: "session-id"
}
```

## Cost Optimization

### Model Selection
- **Nova Lite**: ~$0.06/1M tokens (recommended for most tasks)
- **Nova Pro**: ~$0.80/1M tokens (complex reasoning)
- **Claude 3.5**: ~$3.00/1M tokens (premium quality)

### Token Management
- Keep system prompts concise
- Limit conversation history (default: 20 messages)
- Use session timeouts (default: 15 min)
- Truncate long inputs (default: 2000 chars)

### Tool Efficiency
- Batch operations when possible
- Cache frequently accessed data
- Use DynamoDB efficiently
- Minimize Lambda cold starts

## Support

For issues or questions:
1. Check CloudWatch logs
2. Review this documentation
3. Test tools independently
4. Contact development team

---

**Version**: 1.0.0  
**Last Updated**: March 3, 2026  
**Maintained By**: WECARE.DIGITAL Development Team
