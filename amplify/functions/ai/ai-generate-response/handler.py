"""
AI Generate Response Lambda Function

Purpose: Generate AI response using Bedrock Agent with Knowledge Base
Language detection ensures responses match user's language

Model: Amazon Nova Lite (~$0.06/1M input tokens)

Architecture:
- INTERNAL Agent/KB: For FloatingAgent (admin tasks)
  - Agent ID: QIEEHEBTZO
  - Agent Alias: ASCBD7YPUT
  - KB ID: D0JU8Q7IQS
- EXTERNAL Agent/KB: For WhatsApp auto-reply (customer-facing)
  - Agent ID: Z4YAK0ZLBO
  - Agent Alias: WANPKHQGIB
  - KB ID: LYMQLKZNY7
"""

import os
import json
import logging
import boto3
import uuid
import re
from typing import Dict, Any, Tuple

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')

# Internal Agent (FloatingAgent - admin tasks)
INTERNAL_AGENT_ID = os.environ.get('INTERNAL_AGENT_ID', 'QIEEHEBTZO')
INTERNAL_AGENT_ALIAS = os.environ.get('INTERNAL_AGENT_ALIAS', 'ASCBD7YPUT')
INTERNAL_KB_ID = os.environ.get('INTERNAL_KB_ID', 'D0JU8Q7IQS')

# External Agent (WhatsApp auto-reply - customer facing)
EXTERNAL_AGENT_ID = os.environ.get('EXTERNAL_AGENT_ID', 'Z4YAK0ZLBO')
EXTERNAL_AGENT_ALIAS = os.environ.get('EXTERNAL_AGENT_ALIAS', 'WANPKHQGIB')
EXTERNAL_KB_ID = os.environ.get('EXTERNAL_KB_ID', 'LYMQLKZNY7')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Generate AI response using Bedrock Agent."""
    request_id = context.aws_request_id if context else 'local'
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }
    
    # Handle OPTIONS preflight
    if event.get('httpMethod') == 'OPTIONS' or event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}
    
    # Parse body from API Gateway event
    body = event
    if 'body' in event:
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except (json.JSONDecodeError, TypeError):
            body = event
    
    # Determine which agent to use based on context
    agent_context = body.get('context', 'external')  # default to external (WhatsApp)
    
    if agent_context == 'internal-admin':
        agent_id = INTERNAL_AGENT_ID
        agent_alias = INTERNAL_AGENT_ALIAS
        kb_id = INTERNAL_KB_ID
    else:
        agent_id = EXTERNAL_AGENT_ID
        agent_alias = EXTERNAL_AGENT_ALIAS
        kb_id = EXTERNAL_KB_ID
    
    logger.info(json.dumps({
        'event': 'ai_generate_start',
        'sendMode': SEND_MODE,
        'agentContext': agent_context,
        'agentId': agent_id,
        'kbId': kb_id,
        'requestId': request_id
    }))
    
    # Check if agents are configured
    if not agent_id and not kb_id:
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'suggestedResponse': _get_fallback_response(),
                'error': 'AI agents not configured yet'
            })
        }
    
    if SEND_MODE == 'DRY_RUN':
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'suggestedResponse': '', 'mode': 'DRY_RUN'})}
    
    try:
        message_content = body.get('messageContent', '')
        message_id = body.get('messageId', '')
        contact_id = body.get('contactId', '')
        
        logger.info(json.dumps({
            'event': 'ai_generate_processing',
            'messageContent': message_content[:100] if message_content else '',
            'requestId': request_id
        }))
        
        if not message_content:
            return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'suggestedResponse': _get_fallback_response()})}
        
        # Generate response using Bedrock Agent or KB
        if agent_id and agent_alias:
            suggestion = _invoke_bedrock_agent(message_content, agent_id, agent_alias, kb_id, request_id)
        elif kb_id:
            detected_lang, lang_name = _detect_language(message_content)
            suggestion = _query_knowledge_base(message_content, kb_id, detected_lang, lang_name, request_id)
        else:
            suggestion = _get_fallback_response()
        
        logger.info(json.dumps({
            'event': 'ai_generate_complete',
            'messageId': message_id,
            'suggestionLength': len(suggestion) if suggestion else 0,
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'suggestedResponse': suggestion,
                'messageId': message_id,
                'contactId': contact_id
            })
        }
        
    except Exception as e:
        logger.error(json.dumps({'event': 'ai_generate_error', 'error': str(e), 'requestId': request_id}))
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'suggestedResponse': _get_fallback_response(), 'error': str(e)})}


def _invoke_bedrock_agent(user_message: str, agent_id: str, agent_alias: str, kb_id: str, request_id: str) -> str:
    """Invoke Bedrock Agent for response generation."""
    try:
        session_id = str(uuid.uuid4())
        detected_lang, lang_name = _detect_language(user_message)
        
        language_instruction = f"[RESPOND IN {lang_name.upper()} ONLY] "
        enhanced_message = language_instruction + user_message
        
        logger.info(json.dumps({
            'event': 'bedrock_agent_invoke',
            'agentId': agent_id,
            'sessionId': session_id,
            'messageLength': len(user_message),
            'detectedLanguage': lang_name,
            'requestId': request_id
        }))
        
        response = bedrock_agent_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias,
            sessionId=session_id,
            inputText=enhanced_message,
            enableTrace=False
        )
        
        completion = ""
        for event in response.get('completion', []):
            if 'chunk' in event:
                chunk_data = event['chunk']
                if 'bytes' in chunk_data:
                    completion += chunk_data['bytes'].decode('utf-8')
        
        if completion:
            logger.info(json.dumps({
                'event': 'bedrock_agent_success',
                'responseLength': len(completion),
                'detectedLanguage': lang_name,
                'requestId': request_id
            }))
            return completion.strip()
        
        # Fallback to KB if agent returns empty
        if kb_id:
            return _query_knowledge_base(user_message, kb_id, detected_lang, lang_name, request_id)
        
        return _get_fallback_response(lang_name)
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'bedrock_agent_error',
            'error': str(e),
            'requestId': request_id
        }))
        if kb_id:
            detected_lang, lang_name = _detect_language(user_message)
            return _query_knowledge_base(user_message, kb_id, detected_lang, lang_name, request_id)
        return _get_fallback_response()


def _detect_language(text: str) -> Tuple[str, str]:
    """Detect language from text using character patterns."""
    if not text:
        return ('en', 'English')
    
    # Hindi/Devanagari
    if re.search(r'[\u0900-\u097F]', text):
        marathi_words = ['आहे', 'काय', 'मला', 'तुम्ही', 'आम्ही']
        if any(word in text for word in marathi_words):
            return ('mr', 'Marathi')
        return ('hi', 'Hindi')
    
    # Bengali
    if re.search(r'[\u0980-\u09FF]', text):
        return ('bn', 'Bengali')
    
    # Tamil
    if re.search(r'[\u0B80-\u0BFF]', text):
        return ('ta', 'Tamil')
    
    # Telugu
    if re.search(r'[\u0C00-\u0C7F]', text):
        return ('te', 'Telugu')
    
    # Gujarati
    if re.search(r'[\u0A80-\u0AFF]', text):
        return ('gu', 'Gujarati')
    
    # Hinglish
    hinglish_words = ['kya', 'hai', 'kaise', 'mujhe', 'aap', 'hum', 'tum', 'kab', 'kahan', 'kyun', 'nahi', 'haan', 'theek', 'accha', 'bahut']
    if sum(1 for word in hinglish_words if word in text.lower()) >= 2:
        return ('hi-Latn', 'Hinglish')
    
    return ('en', 'English')


def _query_knowledge_base(user_message: str, kb_id: str, detected_lang: str, lang_name: str, request_id: str) -> str:
    """Direct Knowledge Base query with Nova Lite."""
    try:
        logger.info(json.dumps({
            'event': 'kb_query_start',
            'kbId': kb_id,
            'model': 'amazon.nova-lite-v1:0',
            'detectedLanguage': lang_name,
            'requestId': request_id
        }))
        
        prompt_template = f"""You are WECARE.DIGITAL's friendly AI assistant.

CRITICAL: You MUST respond ONLY in {lang_name}. Do not mix languages.

INSTRUCTIONS:
- Respond ONLY in {lang_name} language
- Keep responses SHORT (2-3 sentences max)
- Use 1-2 emojis for warmth
- Always mention the specific brand name
- End with a clear action (website, phone, or next step)

BRANDS:
- Travel/Hotels/Visa → BNB Club (bnbclub.in)
- Documents/Registration/GST → Legal Champ (legalchamp.in)
- Disputes/Complaints → No Fault (nofault.in)
- Puja/Rituals → Ritual Guru (ritualguru.in)
- Self-inquiry/Reflection → Swdhya (swdhya.in)

CONTACT: +91 9330994400 | one@wecare.digital

CONTEXT FROM KNOWLEDGE BASE:
$search_results$

USER QUESTION ({lang_name}): $query$

Respond helpfully in {lang_name} and end with a specific action."""
        
        response = bedrock_agent_runtime.retrieve_and_generate(
            input={'text': user_message},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': kb_id,
                    'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0',
                    'generationConfiguration': {
                        'promptTemplate': {
                            'textPromptTemplate': prompt_template
                        }
                    }
                }
            }
        )
        
        output = response.get('output', {}).get('text', '')
        
        if output:
            logger.info(json.dumps({
                'event': 'kb_query_success',
                'responseLength': len(output),
                'detectedLanguage': lang_name,
                'requestId': request_id
            }))
            return output.strip()
        
        return _get_fallback_response(lang_name)
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'kb_query_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _get_fallback_response(lang_name)


def _get_fallback_response(lang_name: str = 'English') -> str:
    """Return a friendly fallback response in the detected language."""
    fallback_responses = {
        'Hindi': "नमस्ते! 👋 WECARE.DIGITAL से संपर्क करने के लिए धन्यवाद। त्वरित सहायता के लिए +91 9330994400 पर कॉल करें या one@wecare.digital पर ईमेल करें। 😊",
        'Bengali': "নমস্কার! 👋 WECARE.DIGITAL-এ যোগাযোগ করার জন্য ধন্যবাদ। দ্রুত সাহায্যের জন্য +91 9330994400-এ কল করুন বা one@wecare.digital-এ ইমেল করুন। 😊",
        'Hinglish': "Hi! 👋 WECARE.DIGITAL se contact karne ke liye thanks. Quick help ke liye +91 9330994400 pe call karein ya one@wecare.digital pe email karein. 😊",
        'Tamil': "வணக்கம்! 👋 WECARE.DIGITAL-ஐ தொடர்பு கொண்டதற்கு நன்றி। விரைவான உதவிக்கு +91 9330994400 அழைக்கவும் அல்லது one@wecare.digital மின்னஞ்சல் அனுப்பவும். 😊",
        'Telugu': "నమస్కారం! 👋 WECARE.DIGITAL ని సంప్రదించినందుకు ధన్యవాదాలు। త్వరిత సహాయం కోసం +91 9330994400 కు కాల్ చేయండి లేదా one@wecare.digital కు ఇమెయిల్ చేయండి. 😊",
        'Gujarati': "નમસ્તે! 👋 WECARE.DIGITAL નો સંપર્ક કરવા બદલ આભાર. ઝડપી મદદ માટે +91 9330994400 પર કૉલ કરો અથવા one@wecare.digital પર ઇમેઇલ કરો. 😊",
        'Marathi': "नमस्कार! 👋 WECARE.DIGITAL शी संपर्क साधल्याबद्दल धन्यवाद। जलद मदतीसाठी +91 9330994400 वर कॉल करा किंवा one@wecare.digital वर ईमेल करा. 😊",
    }
    
    return fallback_responses.get(lang_name, "Hi! 👋 Thanks for reaching out to WECARE.DIGITAL. For quick help, call us at +91 9330994400 or email one@wecare.digital. We're here to help! 😊")
