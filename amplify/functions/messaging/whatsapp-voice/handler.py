"""
WhatsApp Voice Lambda Function

Purpose: Generate TTS audio via Amazon Polly and send as WhatsApp audio messages
Uses: Amazon Polly (TTS) + AWS EUM Social (WhatsApp) + S3 (storage)

Endpoints:
  POST /whatsapp-voice/tts     - Generate TTS and send as WhatsApp audio
  POST /whatsapp-voice/send    - Send existing audio file as WhatsApp message
  GET  /whatsapp-voice/voices  - List available Polly voices
  GET  /whatsapp-voice/logs    - List sent voice messages
  DELETE /whatsapp-voice/clear-logs - Clear all logs
"""

import os
import json
import uuid
import time
import logging
import base64
import boto3
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)
polly = boto3.client('polly', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
social_messaging = boto3.client('socialmessaging', region_name=REGION)

# Environment
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
VOICE_LOG_TABLE = os.environ.get('VOICE_LOG_TABLE', 'base-wecare-digital-WhatsAppVoiceTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'auth.wecare.digital')
MEDIA_PREFIX = os.environ.get('MEDIA_PREFIX', 'whatsapp-media/whatsapp-voice/')

# WhatsApp Phone Number IDs
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1',
    'phone-number-id-2ff05755631b41f29151c0573b7a4e2a')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2',
    'phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6')

META_API_VERSION = 'v20.0'
TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days


# Polly voices grouped by language
POLLY_VOICES = {
    'en-IN': [
        {'id': 'Kajal', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Raveena', 'gender': 'Female', 'engine': 'standard'},
    ],
    'en-US': [
        {'id': 'Joanna', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Matthew', 'gender': 'Male', 'engine': 'neural'},
        {'id': 'Ivy', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Kendra', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Salli', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Joey', 'gender': 'Male', 'engine': 'neural'},
        {'id': 'Ruth', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Stephen', 'gender': 'Male', 'engine': 'neural'},
    ],
    'en-GB': [
        {'id': 'Amy', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Emma', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Brian', 'gender': 'Male', 'engine': 'neural'},
        {'id': 'Arthur', 'gender': 'Male', 'engine': 'neural'},
    ],
    'hi-IN': [
        {'id': 'Kajal', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Aditi', 'gender': 'Female', 'engine': 'standard'},
    ],
    'arb': [
        {'id': 'Zeina', 'gender': 'Female', 'engine': 'standard'},
        {'id': 'Hala', 'gender': 'Female', 'engine': 'neural'},
    ],
    'es-US': [
        {'id': 'Lupe', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Pedro', 'gender': 'Male', 'engine': 'neural'},
    ],
    'fr-FR': [
        {'id': 'Lea', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Remi', 'gender': 'Male', 'engine': 'neural'},
    ],
    'de-DE': [
        {'id': 'Vicki', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Daniel', 'gender': 'Male', 'engine': 'neural'},
    ],
    'ja-JP': [
        {'id': 'Kazuha', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Takumi', 'gender': 'Male', 'engine': 'neural'},
    ],
    'ko-KR': [
        {'id': 'Seoyeon', 'gender': 'Female', 'engine': 'neural'},
    ],
    'pt-BR': [
        {'id': 'Camila', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Thiago', 'gender': 'Male', 'engine': 'neural'},
    ],
    'cmn-CN': [
        {'id': 'Zhiyu', 'gender': 'Female', 'engine': 'neural'},
    ],
    'it-IT': [
        {'id': 'Bianca', 'gender': 'Female', 'engine': 'neural'},
        {'id': 'Adriano', 'gender': 'Male', 'engine': 'neural'},
    ],
    'tr-TR': [
        {'id': 'Burcu', 'gender': 'Female', 'engine': 'neural'},
    ],
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle WhatsApp voice/TTS operations."""
    request_id = context.aws_request_id if context else 'local'
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('rawPath', event.get('path', ''))
    query_params = event.get('queryStringParameters') or {}

    logger.info(json.dumps({
        'event': 'whatsapp_voice_handler',
        'method': http_method, 'path': path, 'requestId': request_id
    }))

    try:
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})

        # DELETE /whatsapp-voice/clear-logs
        if http_method == 'DELETE' and 'clear-logs' in path:
            return _clear_logs(request_id)

        # GET /whatsapp-voice/voices
        if http_method == 'GET' and 'voices' in path:
            return _list_voices()

        # GET /whatsapp-voice/logs
        if http_method == 'GET':
            return _list_logs(query_params, request_id)

        # POST /whatsapp-voice/tts
        if http_method == 'POST' and 'tts' in path:
            body = json.loads(event.get('body', '{}'))
            return _handle_tts(body, request_id)

        # POST /whatsapp-voice/send (send existing audio)
        if http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return _handle_send_audio(body, request_id)

        return _response(405, {'error': 'Method not allowed'})

    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"WhatsApp voice error: {str(e)}", exc_info=True)
        return _response(500, {'error': 'Internal server error'})


def _handle_tts(body: Dict, request_id: str) -> Dict[str, Any]:
    """Generate TTS via Polly and send as WhatsApp audio message."""
    contact_id = body.get('contactId', '')
    phone_number = body.get('phoneNumber')
    message_text = body.get('messageText', '')
    voice_id = body.get('voiceId', 'Kajal')
    language_code = body.get('languageCode', 'en-IN')
    engine = body.get('engine', 'neural')
    phone_number_id = body.get('phoneNumberId', PHONE_NUMBER_ID_1)

    if not message_text:
        return _response(400, {'error': 'messageText is required'})

    # Resolve phone number from contact if needed
    if not phone_number and contact_id:
        contact = _get_contact(contact_id)
        phone_number = contact.get('phone') if contact else None

    if not phone_number:
        return _response(400, {'error': 'phoneNumber or contactId required'})

    phone_e164 = _format_phone(phone_number)
    if not phone_e164:
        return _response(400, {'error': 'Invalid phone number'})

    msg_id = str(uuid.uuid4())

    try:
        # Step 1: Generate TTS audio via Polly (OGG Vorbis for WhatsApp)
        logger.info(json.dumps({
            'event': 'polly_synthesize',
            'voiceId': voice_id, 'language': language_code,
            'engine': engine, 'textLength': len(message_text)
        }))

        # Use SSML for better control
        ssml_text = f'<speak><prosody rate="medium">{message_text}</prosody></speak>'

        polly_response = polly.synthesize_speech(
            Text=ssml_text,
            TextType='ssml',
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine=engine,
            LanguageCode=language_code,
        )

        audio_stream = polly_response['AudioStream'].read()
        audio_size = len(audio_stream)

        logger.info(json.dumps({
            'event': 'polly_success',
            'audioSize': audio_size,
            'contentType': polly_response.get('ContentType', '')
        }))

        # Step 2: Upload to S3
        s3_key = f"{MEDIA_PREFIX}{msg_id}.mp3"
        s3.put_object(
            Bucket=MEDIA_BUCKET,
            Key=s3_key,
            Body=audio_stream,
            ContentType='audio/mpeg',
            Metadata={
                'voiceId': voice_id,
                'language': language_code,
                'messageText': message_text[:200],
                'contactId': contact_id,
            }
        )

        logger.info(json.dumps({
            'event': 's3_upload_success',
            'bucket': MEDIA_BUCKET, 's3Key': s3_key
        }))

        # Step 3: Upload to WhatsApp via EUM Social PostWhatsAppMessageMedia
        media_id = _upload_to_whatsapp(s3_key, phone_number_id, request_id)

        if not media_id:
            return _response(500, {
                'error': 'Failed to upload audio to WhatsApp',
                'messageId': msg_id, 's3Key': s3_key
            })

        # Step 4: Send WhatsApp audio message
        wa_message_id = _send_whatsapp_audio(
            phone_e164, media_id, phone_number_id, request_id
        )

        # Step 5: Store log
        now = int(time.time())
        _store_log({
            'messageId': msg_id,
            'contactId': contact_id,
            'phoneNumber': phone_e164,
            'messageText': message_text[:500],
            'voiceId': voice_id,
            'languageCode': language_code,
            'engine': engine,
            'audioSize': audio_size,
            's3Key': s3_key,
            'whatsappMediaId': media_id,
            'whatsappMessageId': wa_message_id or '',
            'phoneNumberId': phone_number_id,
            'status': 'sent' if wa_message_id else 'failed',
            'type': 'tts',
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })

        # Step 6: Also store in messages table for inbox display
        _store_message_record(
            msg_id, contact_id, f'[Voice Note] {message_text[:100]}',
            'sent' if wa_message_id else 'failed',
            phone_number_id, phone_e164, s3_key, wa_message_id
        )

        return _response(200, {
            'success': True,
            'messageId': msg_id,
            'whatsappMessageId': wa_message_id,
            's3Key': s3_key,
            'audioSize': audio_size,
            'voiceId': voice_id,
            'status': 'sent' if wa_message_id else 'upload_only'
        })

    except polly.exceptions.InvalidSsmlException as e:
        # Retry without SSML
        logger.warning(f"SSML failed, retrying plain text: {str(e)}")
        try:
            polly_response = polly.synthesize_speech(
                Text=message_text,
                TextType='text',
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine=engine,
                LanguageCode=language_code,
            )
            audio_stream = polly_response['AudioStream'].read()
            s3_key = f"{MEDIA_PREFIX}{msg_id}.mp3"
            s3.put_object(
                Bucket=MEDIA_BUCKET, Key=s3_key,
                Body=audio_stream, ContentType='audio/mpeg'
            )
            media_id = _upload_to_whatsapp(s3_key, phone_number_id, request_id)
            wa_message_id = _send_whatsapp_audio(
                phone_e164, media_id, phone_number_id, request_id
            ) if media_id else None

            now = int(time.time())
            _store_log({
                'messageId': msg_id, 'contactId': contact_id,
                'phoneNumber': phone_e164, 'messageText': message_text[:500],
                'voiceId': voice_id, 'languageCode': language_code,
                's3Key': s3_key, 'whatsappMediaId': media_id or '',
                'whatsappMessageId': wa_message_id or '',
                'status': 'sent' if wa_message_id else 'failed',
                'type': 'tts', 'createdAt': Decimal(str(now)),
                'ttl': Decimal(str(now + TTL_SECONDS)),
            })
            return _response(200, {
                'success': True, 'messageId': msg_id,
                'whatsappMessageId': wa_message_id, 's3Key': s3_key
            })
        except Exception as e2:
            logger.error(f"Polly plain text also failed: {str(e2)}")
            return _response(500, {'error': f'TTS failed: {str(e2)}'})

    except Exception as e:
        logger.error(f"TTS error: {str(e)}", exc_info=True)
        return _response(500, {'error': str(e)})


def _handle_send_audio(body: Dict, request_id: str) -> Dict[str, Any]:
    """Send an existing audio file (from S3 or base64) as WhatsApp audio message."""
    contact_id = body.get('contactId', '')
    phone_number = body.get('phoneNumber')
    phone_number_id = body.get('phoneNumberId', PHONE_NUMBER_ID_1)
    s3_key = body.get('s3Key')
    audio_base64 = body.get('audioBase64')
    content_type = body.get('contentType', 'audio/ogg')

    if not phone_number and contact_id:
        contact = _get_contact(contact_id)
        phone_number = contact.get('phone') if contact else None

    if not phone_number:
        return _response(400, {'error': 'phoneNumber or contactId required'})

    phone_e164 = _format_phone(phone_number)
    msg_id = str(uuid.uuid4())

    try:
        # If base64 audio provided, upload to S3 first
        if audio_base64 and not s3_key:
            ext = 'ogg' if 'ogg' in content_type else 'mp3'
            s3_key = f"{MEDIA_PREFIX}{msg_id}.{ext}"
            audio_bytes = base64.b64decode(audio_base64)
            s3.put_object(
                Bucket=MEDIA_BUCKET, Key=s3_key,
                Body=audio_bytes, ContentType=content_type,
                Metadata={'contactId': contact_id, 'type': 'recording'}
            )

        if not s3_key:
            return _response(400, {'error': 's3Key or audioBase64 required'})

        # Upload to WhatsApp
        media_id = _upload_to_whatsapp(s3_key, phone_number_id, request_id)
        if not media_id:
            return _response(500, {'error': 'Failed to upload to WhatsApp'})

        # Send audio message
        wa_message_id = _send_whatsapp_audio(
            phone_e164, media_id, phone_number_id, request_id
        )

        now = int(time.time())
        _store_log({
            'messageId': msg_id, 'contactId': contact_id,
            'phoneNumber': phone_e164, 's3Key': s3_key,
            'whatsappMediaId': media_id,
            'whatsappMessageId': wa_message_id or '',
            'phoneNumberId': phone_number_id,
            'status': 'sent' if wa_message_id else 'failed',
            'type': 'recording',
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })

        _store_message_record(
            msg_id, contact_id, '[Voice Recording]',
            'sent' if wa_message_id else 'failed',
            phone_number_id, phone_e164, s3_key, wa_message_id
        )

        return _response(200, {
            'success': True, 'messageId': msg_id,
            'whatsappMessageId': wa_message_id, 's3Key': s3_key
        })

    except Exception as e:
        logger.error(f"Send audio error: {str(e)}", exc_info=True)
        return _response(500, {'error': str(e)})


def _upload_to_whatsapp(s3_key: str, phone_number_id: str,
                        request_id: str) -> Optional[str]:
    """Upload media from S3 to WhatsApp via EUM Social PostWhatsAppMessageMedia."""
    try:
        response = social_messaging.post_whatsapp_message_media(
            originationPhoneNumberId=phone_number_id,
            sourceS3File={
                'bucketName': MEDIA_BUCKET,
                'key': s3_key,
            },
        )
        media_id = response.get('mediaId', '')
        logger.info(json.dumps({
            'event': 'whatsapp_media_upload_success',
            'mediaId': media_id, 's3Key': s3_key
        }))
        return media_id
    except Exception as e:
        logger.error(f"WhatsApp media upload error: {str(e)}")
        return None


def _send_whatsapp_audio(phone: str, media_id: str,
                         phone_number_id: str,
                         request_id: str) -> Optional[str]:
    """Send audio message via EUM Social SendWhatsAppMessage."""
    try:
        # WhatsApp Cloud API audio message payload
        digits = ''.join(c for c in phone if c.isdigit())
        wa_payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': f'+{digits}',
            'type': 'audio',
            'audio': {'id': media_id}
        }

        message_bytes = json.dumps(wa_payload).encode('utf-8')

        response = social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_number_id,
            message=message_bytes,
            metaApiVersion=META_API_VERSION,
        )

        wa_msg_id = response.get('messageId', '')
        logger.info(json.dumps({
            'event': 'whatsapp_audio_sent',
            'messageId': wa_msg_id, 'to': phone
        }))
        return wa_msg_id

    except Exception as e:
        logger.error(f"WhatsApp send error: {str(e)}")
        return None


def _list_voices() -> Dict[str, Any]:
    """Return available Polly voices grouped by language."""
    return _response(200, {'voices': POLLY_VOICES})


def _list_logs(params: Dict, request_id: str) -> Dict[str, Any]:
    """List WhatsApp voice message logs."""
    try:
        table = dynamodb.Table(VOICE_LOG_TABLE)
        result = table.scan(Limit=int(params.get('limit', 100)))
        items = result.get('Items', [])
        items.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        return _response(200, {
            'logs': [_normalize_log(i) for i in items],
            'count': len(items)
        })
    except Exception as e:
        logger.error(f"List logs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _clear_logs(request_id: str) -> Dict[str, Any]:
    """Clear all voice message logs."""
    try:
        table = dynamodb.Table(VOICE_LOG_TABLE)
        result = table.scan(ProjectionExpression='messageId')
        items = result.get('Items', [])
        deleted = 0
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={'messageId': item['messageId']})
                deleted += 1
        return _response(200, {'success': True, 'deletedCount': deleted})
    except Exception as e:
        logger.error(f"Clear logs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _store_log(item: Dict) -> None:
    """Store voice message log."""
    try:
        table = dynamodb.Table(VOICE_LOG_TABLE)
        clean = {k: v for k, v in item.items() if v is not None and v != ''}
        table.put_item(Item=clean)
    except Exception as e:
        logger.error(f"Store log error: {str(e)}")


def _store_message_record(msg_id: str, contact_id: str, content: str,
                          status: str, phone_number_id: str,
                          recipient_phone: str, s3_key: str,
                          wa_message_id: Optional[str]) -> None:
    """Store in messages table so it shows in WhatsApp inbox."""
    try:
        table = dynamodb.Table(MESSAGES_TABLE)
        now = int(time.time())
        table.put_item(Item={
            'id': msg_id,
            'messageId': msg_id,
            'contactId': contact_id,
            'content': content,
            'direction': 'OUTBOUND',
            'channel': 'whatsapp',
            'status': status,
            'messageType': 'audio',
            'mediaUrl': f"https://{MEDIA_BUCKET}.s3.amazonaws.com/{s3_key}",
            's3Key': s3_key,
            'whatsappMessageId': wa_message_id or '',
            'awsPhoneNumberId': phone_number_id,
            'recipientPhone': recipient_phone,
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
            'ttl': Decimal(str(now + 30 * 24 * 60 * 60)),
        })
    except Exception as e:
        logger.error(f"Store message error: {str(e)}")


def _normalize_log(item: Dict) -> Dict:
    """Normalize log record."""
    return {
        'messageId': item.get('messageId', ''),
        'contactId': item.get('contactId', ''),
        'phoneNumber': item.get('phoneNumber', ''),
        'messageText': item.get('messageText', ''),
        'voiceId': item.get('voiceId', ''),
        'languageCode': item.get('languageCode', ''),
        'audioSize': int(item.get('audioSize', 0)),
        's3Key': item.get('s3Key', ''),
        'whatsappMediaId': item.get('whatsappMediaId', ''),
        'whatsappMessageId': item.get('whatsappMessageId', ''),
        'status': item.get('status', ''),
        'type': item.get('type', 'tts'),
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _get_contact(contact_id: str) -> Dict:
    """Get contact from DynamoDB."""
    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        # Table key is 'id', not 'contactId'
        result = table.get_item(Key={'id': contact_id})
        return result.get('Item', {})
    except Exception as e:
        logger.error(f"Get contact error: {str(e)}")
        return {}


def _format_phone(phone: str) -> str:
    """Format phone to E.164."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if len(digits) == 10:
        return f'+91{digits}'
    if phone.startswith('+'):
        return phone
    return f'+{digits}' if digits else ''


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """HTTP response with CORS."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
