# ⚡ Floating Agent - Immediate Action Plan

## 🎯 Goal: Make Production-Ready in 2 Weeks

---

## 📅 Week 1: Critical Infrastructure

### Day 1-2: Audit Logging
**File**: `amplify/functions/ai/ai-generate-response/handler.py`

```python
# Add after line 3500 (tool implementations)

def log_tool_execution(tool_name, params, result, duration, session_id, status='success'):
    """Log every tool execution for audit trail"""
    try:
        audit_table = dynamodb.Table('base-wecare-digital-AuditLog')
        audit_table.put_item(Item={
            'id': str(uuid.uuid4()),
            'timestamp': Decimal(str(int(time.time()))),
            'toolName': tool_name,
            'parameters': json.dumps(params, default=str),
            'result': json.dumps(result, default=str)[:1000],  # Truncate large results
            'duration': Decimal(str(duration)),
            'sessionId': session_id,
            'status': status,
            'context': 'internal-admin'
        })
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")

# Wrap every tool execution:
start_time = time.time()
try:
    result = execute_tool(tool_name, params)
    log_tool_execution(tool_name, params, result, time.time() - start_time, session_id, 'success')
except Exception as e:
    log_tool_execution(tool_name, params, str(e), time.time() - start_time, session_id, 'error')
    raise
```

**Test**: Execute a tool and verify entry in AuditLog table

---

### Day 3: Error Recovery & Retry Logic

```python
# Add retry decorator
from functools import wraps
import time

def retry_on_error(max_retries=3, backoff_factor=2):
    """Retry decorator with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ClientError, ConnectionError, Timeout) as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator

# Apply to all DynamoDB/API calls:
@retry_on_error(max_retries=3)
def search_contacts_impl(query):
    # ... existing code
```

**Test**: Simulate DynamoDB throttling and verify retries

---

### Day 4: Parameter Validation

```python
# Add validation functions
import re

def validate_phone(phone: str) -> tuple[bool, str]:
    """Validate phone number (E.164 format)"""
    if not phone:
        return False, "Phone number is required"
    
    # Remove spaces and dashes
    clean = phone.replace(' ', '').replace('-', '')
    
    # Check E.164 format: +[country code][number]
    pattern = r'^\+[1-9]\d{1,14}$'
    if not re.match(pattern, clean):
        return False, "Invalid phone format. Use: +[country code][number] (e.g., +919876543210)"
    
    return True, clean

def validate_email(email: str) -> tuple[bool, str]:
    """Validate email address"""
    if not email:
        return False, "Email is required"
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    return True, email.lower()

def validate_contact_id(contact_id: str) -> tuple[bool, str]:
    """Validate contact ID (UUID format)"""
    if not contact_id:
        return False, "Contact ID is required"
    
    try:
        uuid.UUID(contact_id)
        return True, contact_id
    except ValueError:
        return False, "Invalid contact ID format"

# Apply to all tool inputs:
def send_whatsapp_impl(contact_id, message):
    # Validate inputs
    valid, result = validate_contact_id(contact_id)
    if not valid:
        return {'error': result}
    
    if not message or len(message) > 4096:
        return {'error': 'Message must be 1-4096 characters'}
    
    # ... existing code
```

**Test**: Try invalid inputs and verify error messages

---

### Day 5: Rate Limiting

```python
# Add rate limiting using DynamoDB
def check_rate_limit(session_id: str, tool_name: str, limit: int = 10, window: int = 60) -> tuple[bool, str]:
    """Check if rate limit exceeded (10 requests per minute per tool)"""
    try:
        table = dynamodb.Table('base-wecare-digital-RateLimitTracker')
        key = f"{session_id}:{tool_name}"
        now = int(time.time())
        window_start = now - window
        
        # Get current count
        response = table.get_item(Key={'id': key})
        item = response.get('Item', {})
        
        # Clean old timestamps
        timestamps = [ts for ts in item.get('timestamps', []) if ts > window_start]
        
        # Check limit
        if len(timestamps) >= limit:
            return False, f"Rate limit exceeded. Max {limit} requests per {window} seconds."
        
        # Add new timestamp
        timestamps.append(now)
        table.put_item(Item={
            'id': key,
            'timestamps': timestamps,
            'expiresAt': now + window
        })
        
        return True, ""
    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")
        return True, ""  # Fail open

# Apply before tool execution:
allowed, error_msg = check_rate_limit(session_id, tool_name)
if not allowed:
    return {'error': error_msg}
```

**Test**: Make 11 rapid requests and verify rate limit

---

## 📅 Week 2: User Experience & Monitoring

### Day 6-7: Conversation Persistence

**File**: `amplify/functions/ai/ai-generate-response/handler.py`

```python
# Update conversation history handling for internal agent
def save_internal_conversation(session_id: str, messages: List[Dict]):
    """Save internal agent conversation history"""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        phone_hash = f"internal-{session_id}"
        now = int(time.time())
        ttl = now + (30 * 60)  # 30 minute TTL
        
        table.put_item(Item={
            'phoneHash': phone_hash,
            'timestamp': Decimal(str(now)),
            'messages': json.dumps(messages[-20:], default=str),  # Keep last 20 messages
            'messageCount': len(messages),
            'context': 'internal-admin',
            'expiresAt': Decimal(str(ttl))
        })
    except Exception as e:
        logger.warning(f"Failed to save conversation: {e}")

def load_internal_conversation(session_id: str) -> List[Dict]:
    """Load internal agent conversation history"""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        phone_hash = f"internal-{session_id}"
        
        response = table.query(
            KeyConditionExpression='phoneHash = :ph',
            ExpressionAttributeValues={':ph': phone_hash},
            Limit=1,
            ScanIndexForward=False
        )
        
        items = response.get('Items', [])
        if items:
            messages_json = items[0].get('messages', '[]')
            return json.loads(messages_json) if isinstance(messages_json, str) else messages_json
    except Exception as e:
        logger.warning(f"Failed to load conversation: {e}")
    
    return []
```

**File**: `src/components/FloatingAgent.tsx`

```typescript
// Load conversation history on mount
useEffect(() => {
  const loadHistory = async () => {
    try {
      const response = await fetch(`/api/ai/history?sessionId=${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
          setMessages(prev => [...data.messages, ...prev]);
        }
      }
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  };
  
  if (isOpen) {
    loadHistory();
  }
}, [isOpen, sessionId]);
```

**Test**: Refresh page and verify conversation persists

---

### Day 8: Better Error Messages

```python
# Define user-friendly error messages
ERROR_MESSAGES = {
    'contact_not_found': {
        'message': 'Contact not found',
        'suggestion': 'Try searching by phone number or create a new contact first.',
        'example': 'Example: "find contact +919876543210" or "create contact John +919876543210"'
    },
    'invalid_phone': {
        'message': 'Invalid phone number format',
        'suggestion': 'Use international format with country code.',
        'example': 'Example: +919876543210 (India), +14155552671 (USA)'
    },
    'rate_limit_exceeded': {
        'message': 'Too many requests',
        'suggestion': 'Please wait a moment before trying again.',
        'example': 'Rate limit: 10 requests per minute per action'
    },
    'service_unavailable': {
        'message': 'Service temporarily unavailable',
        'suggestion': 'Please try again in a few moments.',
        'example': 'If the issue persists, contact support.'
    },
    'invalid_parameters': {
        'message': 'Invalid parameters provided',
        'suggestion': 'Check your input and try again.',
        'example': 'Type "help" to see available commands and examples.'
    }
}

def format_error_response(error_type: str, details: str = '') -> str:
    """Format user-friendly error message"""
    error_info = ERROR_MESSAGES.get(error_type, {
        'message': 'An error occurred',
        'suggestion': 'Please try again or type "help" for assistance.',
        'example': ''
    })
    
    response = f"❌ {error_info['message']}"
    if details:
        response += f"\n\nDetails: {details}"
    response += f"\n\n💡 {error_info['suggestion']}"
    if error_info['example']:
        response += f"\n\n{error_info['example']}"
    
    return response
```

**Test**: Trigger various errors and verify messages

---

### Day 9: Typing Indicators & Progress

**File**: `src/components/FloatingAgent.tsx`

```typescript
const [statusMessage, setStatusMessage] = useState('');

// Show status during processing
const processCommand = async (text: string): Promise<string> => {
  try {
    setStatusMessage('🤔 Understanding your request...');
    
    const aiRes = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messageContent: text,
        context: 'internal-admin',
        sessionId: sessionId,
      }),
    });
    
    setStatusMessage('⚙️ Processing...');
    
    if (aiRes.ok) {
      const aiData = await aiRes.json();
      setStatusMessage('');
      // ... handle response
    }
  } catch (error) {
    setStatusMessage('');
    // ... handle error
  }
};

// Add status indicator to UI
{statusMessage && (
  <div className="agent-status">
    {statusMessage}
  </div>
)}
```

**Test**: Send message and verify status updates

---

### Day 10: CloudWatch Monitoring

**File**: `amplify/functions/ai/ai-generate-response/handler.py`

```python
import boto3
cloudwatch = boto3.client('cloudwatch')

def send_metric(metric_name: str, value: float, unit: str = 'None', dimensions: Dict = None):
    """Send custom metric to CloudWatch"""
    try:
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': datetime.utcnow()
        }
        
        if dimensions:
            metric_data['Dimensions'] = [
                {'Name': k, 'Value': v} for k, v in dimensions.items()
            ]
        
        cloudwatch.put_metric_data(
            Namespace='FloatingAgent',
            MetricData=[metric_data]
        )
    except Exception as e:
        logger.warning(f"Failed to send metric: {e}")

# Add metrics to tool executions:
send_metric('ToolExecutionTime', duration * 1000, 'Milliseconds', {'ToolName': tool_name})
send_metric('ToolExecutionCount', 1, 'Count', {'ToolName': tool_name, 'Status': status})
send_metric('ErrorRate', 1 if status == 'error' else 0, 'Count')
```

**Create CloudWatch Dashboard**:
```bash
aws cloudwatch put-dashboard --dashboard-name FloatingAgent --dashboard-body file://dashboard.json
```

**dashboard.json**:
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["FloatingAgent", "ToolExecutionTime", {"stat": "Average"}],
          ["...", {"stat": "p95"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Tool Execution Time"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["FloatingAgent", "ErrorRate", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Error Rate"
      }
    }
  ]
}
```

**Test**: Execute tools and verify metrics in CloudWatch

---

## ✅ Completion Checklist

### Week 1
- [ ] Day 1-2: Audit logging implemented and tested
- [ ] Day 3: Retry logic implemented and tested
- [ ] Day 4: Parameter validation implemented and tested
- [ ] Day 5: Rate limiting implemented and tested

### Week 2
- [ ] Day 6-7: Conversation persistence implemented and tested
- [ ] Day 8: Better error messages implemented and tested
- [ ] Day 9: Typing indicators implemented and tested
- [ ] Day 10: CloudWatch monitoring set up and tested

### Final Testing
- [ ] End-to-end testing with all features
- [ ] Load testing (10+ concurrent users)
- [ ] Error scenario testing
- [ ] User acceptance testing
- [ ] Documentation updated

---

## 🎯 Success Criteria

After 2 weeks, the floating agent should have:

1. ✅ **Audit Trail**: Every action logged to DynamoDB
2. ✅ **Reliability**: Automatic retry on transient failures
3. ✅ **Security**: Input validation prevents invalid data
4. ✅ **Stability**: Rate limiting prevents abuse
5. ✅ **Persistence**: Conversations saved and restored
6. ✅ **Usability**: Clear error messages with suggestions
7. ✅ **Feedback**: Typing indicators show progress
8. ✅ **Monitoring**: CloudWatch dashboards track performance

---

## 📊 Metrics to Track

### Before (Current)
- Error rate: Unknown
- Response time: ~2-3s
- Uptime: Unknown
- User satisfaction: Unknown

### After (Target)
- Error rate: < 1%
- Response time: < 2s (p95)
- Uptime: > 99.9%
- User satisfaction: > 80%

---

## 🚀 Quick Start

```bash
# 1. Pull latest code
git pull origin main

# 2. Install dependencies
npm install

# 3. Deploy Lambda function
./deploy-lambda.ps1

# 4. Start dev server
npm run dev

# 5. Test the agent
# Open http://localhost:3000
# Click floating agent button
# Try: "help", "find contact Jignesh", "show stats"
```

---

**Start Date**: Today  
**End Date**: +2 weeks  
**Effort**: 1 developer, full-time  
**Cost**: $0 (using existing infrastructure)  
**Impact**: HIGH - Makes agent production-ready
