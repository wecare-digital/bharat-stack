"""
Bedrock Agent Action Group Handler

Purpose: Handle action group requests from Bedrock Agent (internal admin tasks)
Agent ID: QIEEHEBTZO
Agent Alias: ASCBD7YPUT
KB ID: D0JU8Q7IQS

Actions:
- send_whatsapp_message: Send WhatsApp message to contact
- send_sms_message: Send SMS to contact
- send_email: Send email to contact
- create_contact: Create new contact
- update_contact: Update existing contact
- delete_contact: Delete contact
- search_contacts: Search contacts by name/phone/email
- get_contact: Get contact details
- delete_message: Delete a message
- get_messages: Get messages for a contact
- create_invoice: Create invoice (placeholder)
- get_stats: Get dashboard statistics
"""

import os
import json
import logging
import boto3
import uuid
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
MESSAGES_INBOUND_TABLE = os.environ.get('MESSAGES_INBOUND_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
MESSAGES_OUTBOUND_TABLE = os.environ.get('MESSAGES_OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
OUTBOUND_WHATSAPP_FUNCTION = os.environ.get('OUTBOUND_WHATSAPP_FUNCTION', 'wecare-outbound-whatsapp')
OUTBOUND_SMS_FUNCTION = os.environ.get('OUTBOUND_SMS_FUNCTION', 'wecare-outbound-sms')
OUTBOUND_EMAIL_FUNCTION = os.environ.get('OUTBOUND_EMAIL_FUNCTION', 'wecare-outbound-email')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle Bedrock Agent action group requests.
    
    Event format from Bedrock Agent (function-based):
    {
        "actionGroup": "wecare-actions",
        "function": "sendWhatsApp",
        "parameters": [{"name": "phone", "value": "+91..."}, ...]
    }
    
    Or API-based:
    {
        "actionGroup": "wecare-actions",
        "apiPath": "/send-whatsapp",
        "httpMethod": "POST",
        "parameters": [...],
        "requestBody": {...}
    }
    """
    request_id = context.aws_request_id if context else 'local'
    
    # Get function name or API path
    function_name = event.get('function', '')
    api_path = event.get('apiPath', '')
    
    logger.info(json.dumps({
        'event': 'agent_action_received',
        'actionGroup': event.get('actionGroup'),
        'function': function_name,
        'apiPath': api_path,
        'requestId': request_id
    }))
    
    try:
        parameters = _extract_parameters(event)
        
        # Route based on function name (preferred) or API path
        if function_name:
            result = _route_function(function_name, parameters, request_id)
        else:
            http_method = event.get('httpMethod', 'POST')
            request_body = event.get('requestBody', {})
            result = _route_action(api_path, http_method, parameters, request_body, request_id)
        
        return _build_response(result, function_name or api_path)
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'agent_action_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _build_response({
            'success': False,
            'error': str(e)
        }, function_name or api_path)


def _extract_parameters(event: Dict) -> Dict[str, str]:
    """Extract parameters from Bedrock Agent event."""
    params = {}
    for param in event.get('parameters', []):
        params[param.get('name')] = param.get('value')
    
    # Also check requestBody content
    request_body = event.get('requestBody', {})
    if request_body:
        content = request_body.get('content', {})
        app_json = content.get('application/json', {})
        properties = app_json.get('properties', [])
        for prop in properties:
            params[prop.get('name')] = prop.get('value')
    
    return params


def _route_function(function_name: str, params: Dict, request_id: str) -> Dict:
    """Route function-based action to appropriate handler."""
    
    if function_name == 'sendWhatsApp':
        return _send_whatsapp(params, request_id)
    elif function_name == 'searchContacts':
        return _search_contacts(params, request_id)
    elif function_name == 'createContact':
        return _create_contact(params, request_id)
    elif function_name == 'getStats':
        return _get_stats(request_id)
    elif function_name == 'sendSms':
        return _send_sms(params, request_id)
    elif function_name == 'sendEmail':
        return _send_email(params, request_id)
    elif function_name == 'updateContact':
        return _update_contact(params, request_id)
    elif function_name == 'deleteContact':
        return _delete_contact(params, request_id)
    elif function_name == 'getContact':
        return _get_contact(params, request_id)
    elif function_name == 'deleteMessage':
        return _delete_message(params, request_id)
    elif function_name == 'getMessages':
        return _get_messages(params, request_id)
    elif function_name == 'createInvoice':
        return _create_invoice(params, request_id)
    else:
        return {'success': False, 'error': f'Unknown function: {function_name}'}


def _route_action(api_path: str, method: str, params: Dict, body: Dict, request_id: str) -> Dict:
    """Route action to appropriate handler."""
    
    # Messaging actions
    if api_path == '/send-whatsapp':
        return _send_whatsapp(params, request_id)
    elif api_path == '/send-sms':
        return _send_sms(params, request_id)
    elif api_path == '/send-email':
        return _send_email(params, request_id)
    
    # Contact actions
    elif api_path == '/create-contact':
        return _create_contact(params, request_id)
    elif api_path == '/update-contact':
        return _update_contact(params, request_id)
    elif api_path == '/delete-contact':
        return _delete_contact(params, request_id)
    elif api_path == '/search-contacts':
        return _search_contacts(params, request_id)
    elif api_path == '/get-contact':
        return _get_contact(params, request_id)
    
    # Message actions
    elif api_path == '/delete-message':
        return _delete_message(params, request_id)
    elif api_path == '/get-messages':
        return _get_messages(params, request_id)
    
    # Invoice actions
    elif api_path == '/create-invoice':
        return _create_invoice(params, request_id)
    
    # Stats actions
    elif api_path == '/get-stats':
        return _get_stats(request_id)
    
    else:
        return {'success': False, 'error': f'Unknown action: {api_path}'}


# ============== MESSAGING ACTIONS ==============

def _send_whatsapp(params: Dict, request_id: str) -> Dict:
    """Send WhatsApp message to contact."""
    contact_id = params.get('contactId') or params.get('contact_id')
    phone = params.get('phone')
    message = params.get('message') or params.get('content')
    
    if not message:
        return {'success': False, 'error': 'Message content is required'}
    
    # Get contact if only phone provided
    if not contact_id and phone:
        contact = _find_contact_by_phone(phone)
        if contact:
            contact_id = contact.get('id')
    
    if not contact_id:
        return {'success': False, 'error': 'Contact ID or phone number is required'}
    
    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'content': message
            })
        }
        
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        logger.info(json.dumps({
            'event': 'whatsapp_sent_via_agent',
            'contactId': contact_id,
            'messageId': result_body.get('messageId'),
            'requestId': request_id
        }))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'status': result_body.get('status', 'sent'),
            'message': f'WhatsApp message sent successfully to contact {contact_id}'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to send WhatsApp: {str(e)}'}


def _send_sms(params: Dict, request_id: str) -> Dict:
    """Send SMS to contact."""
    contact_id = params.get('contactId') or params.get('contact_id')
    phone = params.get('phone')
    message = params.get('message') or params.get('content')
    
    if not message:
        return {'success': False, 'error': 'Message content is required'}
    
    if not contact_id and phone:
        contact = _find_contact_by_phone(phone)
        if contact:
            contact_id = contact.get('id')
    
    if not contact_id:
        return {'success': False, 'error': 'Contact ID or phone number is required'}
    
    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'content': message
            })
        }
        
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_SMS_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'status': result_body.get('status', 'sent'),
            'message': f'SMS sent successfully to contact {contact_id}'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to send SMS: {str(e)}'}


def _send_email(params: Dict, request_id: str) -> Dict:
    """Send email to contact."""
    contact_id = params.get('contactId') or params.get('contact_id')
    email = params.get('email')
    subject = params.get('subject', 'Message from WECARE.DIGITAL')
    message = params.get('message') or params.get('content')
    
    if not message:
        return {'success': False, 'error': 'Message content is required'}
    
    if not contact_id and email:
        contact = _find_contact_by_email(email)
        if contact:
            contact_id = contact.get('id')
    
    if not contact_id:
        return {'success': False, 'error': 'Contact ID or email is required'}
    
    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'subject': subject,
                'content': message
            })
        }
        
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_EMAIL_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'status': result_body.get('status', 'sent'),
            'message': f'Email sent successfully to contact {contact_id}'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to send email: {str(e)}'}


# ============== CONTACT ACTIONS ==============

def _create_contact(params: Dict, request_id: str) -> Dict:
    """Create new contact."""
    name = params.get('name')
    phone = params.get('phone')
    email = params.get('email')
    
    if not name and not phone and not email:
        return {'success': False, 'error': 'At least name, phone, or email is required'}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        contact_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        contact = {
            'id': contact_id,
            'name': name or '',
            'phone': phone or '',
            'email': email or '',
            'optInWhatsApp': True,
            'optInSms': True,
            'optInEmail': True,
            'allowlistWhatsApp': True,
            'allowlistSms': True,
            'allowlistEmail': True,
            'createdAt': now,
            'updatedAt': now
        }
        
        contacts_table.put_item(Item=contact)
        
        logger.info(json.dumps({
            'event': 'contact_created_via_agent',
            'contactId': contact_id,
            'name': name,
            'requestId': request_id
        }))
        
        return {
            'success': True,
            'contactId': contact_id,
            'message': f'Contact "{name or phone or email}" created successfully'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to create contact: {str(e)}'}


def _update_contact(params: Dict, request_id: str) -> Dict:
    """Update existing contact."""
    contact_id = params.get('contactId') or params.get('contact_id')
    
    if not contact_id:
        return {'success': False, 'error': 'Contact ID is required'}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        update_expr_parts = ['updatedAt = :now']
        expr_values = {':now': datetime.utcnow().isoformat()}
        
        if params.get('name'):
            update_expr_parts.append('#n = :name')
            expr_values[':name'] = params['name']
        if params.get('phone'):
            update_expr_parts.append('phone = :phone')
            expr_values[':phone'] = params['phone']
        if params.get('email'):
            update_expr_parts.append('email = :email')
            expr_values[':email'] = params['email']
        
        expr_names = {'#n': 'name'} if params.get('name') else {}
        
        contacts_table.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET ' + ', '.join(update_expr_parts),
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names if expr_names else None
        )
        
        return {
            'success': True,
            'contactId': contact_id,
            'message': f'Contact {contact_id} updated successfully'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to update contact: {str(e)}'}


def _delete_contact(params: Dict, request_id: str) -> Dict:
    """Delete contact (soft delete)."""
    contact_id = params.get('contactId') or params.get('contact_id')
    
    if not contact_id:
        return {'success': False, 'error': 'Contact ID is required'}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        contacts_table.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET deletedAt = :now',
            ExpressionAttributeValues={':now': datetime.utcnow().isoformat()}
        )
        
        logger.info(json.dumps({
            'event': 'contact_deleted_via_agent',
            'contactId': contact_id,
            'requestId': request_id
        }))
        
        return {
            'success': True,
            'contactId': contact_id,
            'message': f'Contact {contact_id} deleted successfully'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to delete contact: {str(e)}'}


def _search_contacts(params: Dict, request_id: str) -> Dict:
    """Search contacts by name, phone, or email."""
    query = params.get('query', '').lower()
    
    if not query:
        return {'success': False, 'error': 'Search query is required'}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        response = contacts_table.scan(
            FilterExpression='(attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={':null': None}
        )
        
        contacts = []
        for item in response.get('Items', []):
            name = (item.get('name') or '').lower()
            phone = (item.get('phone') or '').lower()
            email = (item.get('email') or '').lower()
            
            if query in name or query in phone or query in email:
                contacts.append({
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'phone': item.get('phone'),
                    'email': item.get('email')
                })
        
        return {
            'success': True,
            'count': len(contacts),
            'contacts': contacts[:10],  # Limit to 10 results
            'message': f'Found {len(contacts)} contacts matching "{query}"'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to search contacts: {str(e)}'}


def _get_contact(params: Dict, request_id: str) -> Dict:
    """Get contact details by ID or phone."""
    contact_id = params.get('contactId') or params.get('contact_id')
    phone = params.get('phone')
    
    try:
        if contact_id:
            contacts_table = dynamodb.Table(CONTACTS_TABLE)
            response = contacts_table.get_item(Key={'id': contact_id})
            contact = response.get('Item')
        elif phone:
            contact = _find_contact_by_phone(phone)
        else:
            return {'success': False, 'error': 'Contact ID or phone is required'}
        
        if not contact:
            return {'success': False, 'error': 'Contact not found'}
        
        return {
            'success': True,
            'contact': {
                'id': contact.get('id'),
                'name': contact.get('name'),
                'phone': contact.get('phone'),
                'email': contact.get('email'),
                'createdAt': contact.get('createdAt')
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to get contact: {str(e)}'}


# ============== MESSAGE ACTIONS ==============

def _delete_message(params: Dict, request_id: str) -> Dict:
    """Delete a message."""
    message_id = params.get('messageId') or params.get('message_id')
    
    if not message_id:
        return {'success': False, 'error': 'Message ID is required'}
    
    try:
        # Try inbound table first
        inbound_table = dynamodb.Table(MESSAGES_INBOUND_TABLE)
        try:
            inbound_table.delete_item(Key={'id': message_id})
            return {
                'success': True,
                'messageId': message_id,
                'message': f'Message {message_id} deleted successfully'
            }
        except Exception:
            pass
        
        # Try outbound table
        outbound_table = dynamodb.Table(MESSAGES_OUTBOUND_TABLE)
        outbound_table.delete_item(Key={'id': message_id})
        
        return {
            'success': True,
            'messageId': message_id,
            'message': f'Message {message_id} deleted successfully'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to delete message: {str(e)}'}


def _get_messages(params: Dict, request_id: str) -> Dict:
    """Get messages for a contact."""
    contact_id = params.get('contactId') or params.get('contact_id')
    limit = int(params.get('limit', 10))
    
    if not contact_id:
        return {'success': False, 'error': 'Contact ID is required'}
    
    try:
        messages = []
        
        # Get inbound messages
        inbound_table = dynamodb.Table(MESSAGES_INBOUND_TABLE)
        inbound_response = inbound_table.scan(
            FilterExpression='contactId = :cid',
            ExpressionAttributeValues={':cid': contact_id},
            Limit=limit
        )
        
        for item in inbound_response.get('Items', []):
            messages.append({
                'id': item.get('id'),
                'direction': 'inbound',
                'content': item.get('content'),
                'timestamp': str(item.get('timestamp')),
                'status': item.get('status')
            })
        
        # Get outbound messages
        outbound_table = dynamodb.Table(MESSAGES_OUTBOUND_TABLE)
        outbound_response = outbound_table.scan(
            FilterExpression='contactId = :cid',
            ExpressionAttributeValues={':cid': contact_id},
            Limit=limit
        )
        
        for item in outbound_response.get('Items', []):
            messages.append({
                'id': item.get('id'),
                'direction': 'outbound',
                'content': item.get('content'),
                'timestamp': str(item.get('timestamp')),
                'status': item.get('status')
            })
        
        # Sort by timestamp
        messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {
            'success': True,
            'count': len(messages),
            'messages': messages[:limit],
            'message': f'Found {len(messages)} messages for contact {contact_id}'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to get messages: {str(e)}'}


# ============== INVOICE ACTIONS ==============

def _create_invoice(params: Dict, request_id: str) -> Dict:
    """Create invoice (placeholder - to be implemented)."""
    contact_id = params.get('contactId') or params.get('contact_id')
    amount = params.get('amount')
    description = params.get('description', 'Invoice')
    
    if not contact_id or not amount:
        return {'success': False, 'error': 'Contact ID and amount are required'}
    
    # Placeholder - invoice creation logic would go here
    invoice_id = str(uuid.uuid4())[:8].upper()
    
    return {
        'success': True,
        'invoiceId': f'INV-{invoice_id}',
        'amount': amount,
        'contactId': contact_id,
        'message': f'Invoice INV-{invoice_id} created for amount {amount}'
    }


# ============== STATS ACTIONS ==============

def _get_stats(request_id: str) -> Dict:
    """Get dashboard statistics."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        inbound_table = dynamodb.Table(MESSAGES_INBOUND_TABLE)
        outbound_table = dynamodb.Table(MESSAGES_OUTBOUND_TABLE)
        
        # Count contacts
        contacts_response = contacts_table.scan(
            FilterExpression='attribute_not_exists(deletedAt) OR deletedAt = :null',
            ExpressionAttributeValues={':null': None},
            Select='COUNT'
        )
        total_contacts = contacts_response.get('Count', 0)
        
        # Count messages
        inbound_count = inbound_table.scan(Select='COUNT').get('Count', 0)
        outbound_count = outbound_table.scan(Select='COUNT').get('Count', 0)
        
        return {
            'success': True,
            'stats': {
                'totalContacts': total_contacts,
                'totalInboundMessages': inbound_count,
                'totalOutboundMessages': outbound_count,
                'totalMessages': inbound_count + outbound_count
            },
            'message': f'Stats: {total_contacts} contacts, {inbound_count + outbound_count} total messages'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Failed to get stats: {str(e)}'}


# ============== HELPER FUNCTIONS ==============

def _find_contact_by_phone(phone: str) -> Optional[Dict]:
    """Find contact by phone number."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        
        response = contacts_table.scan(
            FilterExpression='contains(phone, :phone) AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={':phone': clean_phone[-10:], ':null': None},
            Limit=1
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception:
        return None


def _find_contact_by_email(email: str) -> Optional[Dict]:
    """Find contact by email."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        response = contacts_table.scan(
            FilterExpression='email = :email AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={':email': email.lower(), ':null': None},
            Limit=1
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception:
        return None


def _build_response(result: Dict, function_or_path: str = '') -> Dict:
    """Build Bedrock Agent response format for function-based or API-based actions."""
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'wecare-actions',
            'function': function_or_path if not function_or_path.startswith('/') else '',
            'functionResponse': {
                'responseBody': {
                    'TEXT': {
                        'body': json.dumps(result)
                    }
                }
            }
        }
    }
