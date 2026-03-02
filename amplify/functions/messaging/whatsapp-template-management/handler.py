"""
WhatsApp Template Management Lambda Function

Full template lifecycle management via AWS EUM Social API:
- ListWhatsAppMessageTemplates
- GetWhatsAppMessageTemplate
- CreateWhatsAppMessageTemplate
- CreateWhatsAppMessageTemplateFromLibrary
- CreateWhatsAppMessageTemplateMedia
- UpdateWhatsAppMessageTemplate
- DeleteWhatsAppMessageTemplate
- ListWhatsAppTemplateLibrary
- Carousel template creation
"""

import os
import json
import logging
import base64
import uuid
import boto3
from typing import Dict, Any

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.logging import get_logger
from lambda_utils.middleware import require_auth

logger = get_logger(__name__)

social_messaging = boto3.client('socialmessaging', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
TEMPLATE_MEDIA_PREFIX = os.environ.get('TEMPLATE_MEDIA_PREFIX', 'whatsapp-media/template-headers/')
DEFAULT_WABA_ID = 'waba-e47d916f3c7a47e1a34a19653893dd4b'

# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event, context):
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)
    request_context = event.get('requestContext', {})
    if 'http' in request_context:
        http_method = request_context.get('http', {}).get('method', 'GET')
        path = request_context.get('http', {}).get('path', '') or event.get('rawPath', '')
    else:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')

    query_params = event.get('queryStringParameters') or {}

    if http_method == 'OPTIONS':
        return options_response(origin)

    # Enforce auth
    auth_result = require_auth(event)
    if auth_result is not None:
        return auth_result

    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        waba_id = query_params.get('wabaId', DEFAULT_WABA_ID)
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'

        # Route requests
        if http_method == 'GET':
            if '/templates/library' in path:
                return _list_template_library(waba_id, query_params)
            template_id = _extract_path_param(path, '/templates/')
            if template_id and template_id not in ('library', 'analytics', 'carousel', 'carousel-media', 'media', 'from-library'):
                return _get_template_details(waba_id, template_id, query_params)
            return _list_templates(waba_id, query_params)

        elif http_method == 'POST':
            if '/templates/from-library' in path:
                return _create_from_library(waba_id, body)
            if '/templates/carousel-media' in path:
                return _upload_carousel_media(waba_id, body)
            if '/templates/carousel' in path:
                return _create_carousel_template(waba_id, body)
            if '/templates/media' in path:
                return _upload_template_media(waba_id, body)
            return _create_template(waba_id, body)

        elif http_method == 'PUT':
            return _update_template(waba_id, body, query_params, path)

        elif http_method == 'DELETE':
            return _delete_template(waba_id, query_params.get('templateName', ''), query_params)

        return _error_response(400, 'Invalid request')
    except Exception as e:
        logger.error(json.dumps({'event': 'template_handler_error', 'error': str(e), 'requestId': request_id}))
        return _error_response(500, str(e))


def _extract_path_param(path: str, prefix: str) -> str:
    """Extract path parameter after a prefix."""
    idx = path.find(prefix)
    if idx == -1:
        return ''
    remainder = path[idx + len(prefix):]
    return remainder.split('/')[0].split('?')[0]


def _list_templates(waba_id, query_params):
    try:
        response = social_messaging.list_whatsapp_message_templates(
            id=waba_id, maxResults=int(query_params.get('maxResults', 100))
        )
        templates = [{'metaTemplateId': t.get('metaTemplateId'), 'templateName': t.get('templateName'),
                      'templateStatus': t.get('templateStatus')} for t in response.get('templates', [])]
        return {'statusCode': 200, 'headers': cors_headers(origin), 'body': json.dumps({'templates': templates})}
    except Exception as e:
        return _error_response(500, str(e))


def _list_template_library(waba_id, query_params):
    try:
        response = social_messaging.list_whatsapp_template_library(
            id=waba_id, maxResults=int(query_params.get('maxResults', 50))
        )
        templates = [{'templateId': t.get('templateId'), 'templateName': t.get('templateName'),
                      'templateBody': t.get('templateBody')} for t in response.get('metaLibraryTemplates', [])]
        return {'statusCode': 200, 'headers': cors_headers(origin), 'body': json.dumps({'templates': templates})}
    except Exception as e:
        return _error_response(500, str(e))


def _get_template_details(waba_id, template_id, query_params):
    """Get a single template's full details including components."""
    try:
        response = social_messaging.get_whatsapp_message_template(
            id=waba_id, metaTemplateId=template_id
        )
        template = response.get('template', {})
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'template': {
                    'metaTemplateId': template.get('metaTemplateId'),
                    'templateName': template.get('templateName'),
                    'templateStatus': template.get('templateStatus'),
                    'templateBody': template.get('templateBody'),
                    'components': template.get('components', []),
                    'language': template.get('language', ''),
                    'category': template.get('category', ''),
                }
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


# ── CREATE ──

def _create_template(waba_id, body):
    try:
        template_def = body.get('templateDefinition')
        if not template_def:
            return _error_response(400, 'templateDefinition required')
        template_blob = json.dumps(template_def).encode('utf-8')
        response = social_messaging.create_whatsapp_message_template(
            id=waba_id, templateDefinition=template_blob
        )
        return {
            'statusCode': 201,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'metaTemplateId': response.get('metaTemplateId'),
                'category': response.get('category', ''),
                'templateStatus': response.get('templateStatus', 'PENDING'),
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


def _create_from_library(waba_id, body):
    try:
        meta_lib = body.get('metaLibraryTemplate')
        if not meta_lib:
            return _error_response(400, 'metaLibraryTemplate required')
        response = social_messaging.create_whatsapp_message_template_from_library(
            id=waba_id, metaLibraryTemplate=meta_lib
        )
        return {
            'statusCode': 201,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'metaTemplateId': response.get('metaTemplateId'),
                'category': response.get('category', ''),
                'templateStatus': response.get('templateStatus', 'PENDING'),
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


# ── UPDATE ──

def _update_template(waba_id, body, query_params, path):
    """Update an existing WhatsApp message template."""
    try:
        template_id = _extract_path_param(path, '/templates/')
        if not template_id:
            template_id = body.get('metaTemplateId', '')
        if not template_id:
            return _error_response(400, 'Template ID required (in path or body)')

        template_def = body.get('templateDefinition')
        if not template_def:
            return _error_response(400, 'templateDefinition required')

        template_blob = json.dumps(template_def).encode('utf-8')
        response = social_messaging.update_whatsapp_message_template(
            id=waba_id,
            metaTemplateId=template_id,
            templateDefinition=template_blob
        )

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'metaTemplateId': response.get('metaTemplateId', template_id),
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


# ── DELETE ──

def _delete_template(waba_id, template_name, query_params):
    try:
        if not template_name:
            return _error_response(400, 'templateName required')
        social_messaging.delete_whatsapp_message_template(
            id=waba_id, templateName=template_name
        )
        return {'statusCode': 200, 'headers': cors_headers(origin), 'body': json.dumps({'success': True})}
    except Exception as e:
        return _error_response(500, str(e))


# ── MEDIA UPLOAD ──

def _upload_template_media(waba_id, body):
    """Upload header media (image/video/document) for a template.
    Uses CreateWhatsAppMessageTemplateMedia API.
    Accepts base64-encoded file or S3 key reference.
    """
    try:
        file_data_b64 = body.get('fileData')  # base64 encoded
        s3_key = body.get('s3Key')
        content_type = body.get('contentType', 'image/jpeg')
        filename = body.get('filename', 'header.jpg')

        if not file_data_b64 and not s3_key:
            return _error_response(400, 'fileData (base64) or s3Key required')

        # Get file bytes
        if s3_key:
            obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=s3_key)
            file_bytes = obj['Body'].read()
        else:
            file_bytes = base64.b64decode(file_data_b64)

        # Upload to S3 first (for reference)
        upload_key = f'{TEMPLATE_MEDIA_PREFIX}{uuid.uuid4().hex[:12]}_{filename}'
        s3.put_object(
            Bucket=MEDIA_BUCKET,
            Key=upload_key,
            Body=file_bytes,
            ContentType=content_type,
        )

        # Call CreateWhatsAppMessageTemplateMedia
        response = social_messaging.create_whatsapp_message_template_media(
            id=waba_id,
            sourceS3File={
                'bucketName': MEDIA_BUCKET,
                'key': upload_key,
            }
        )

        header_handle = response.get('id', '')

        logger.info(json.dumps({
            'event': 'template_media_uploaded',
            'headerHandle': header_handle,
            's3Key': upload_key,
            'contentType': content_type,
        }))

        return {
            'statusCode': 201,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'metaHeaderHandle': header_handle,
                's3Key': upload_key,
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


# ── CAROUSEL TEMPLATE ──

def _upload_carousel_media(waba_id, body):
    """Upload media for a carousel card header (image or video).
    Returns the header handle needed for carousel template creation.
    """
    try:
        file_data_b64 = body.get('fileData')
        s3_key = body.get('s3Key')
        content_type = body.get('contentType', 'image/jpeg')
        card_index = int(body.get('cardIndex', 0))

        if not file_data_b64 and not s3_key:
            return _error_response(400, 'fileData (base64) or s3Key required')

        if s3_key:
            obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=s3_key)
            file_bytes = obj['Body'].read()
        else:
            file_bytes = base64.b64decode(file_data_b64)

        upload_key = f'{TEMPLATE_MEDIA_PREFIX}carousel/{uuid.uuid4().hex[:12]}_card{card_index}'
        s3.put_object(
            Bucket=MEDIA_BUCKET,
            Key=upload_key,
            Body=file_bytes,
            ContentType=content_type,
        )

        response = social_messaging.create_whatsapp_message_template_media(
            id=waba_id,
            sourceS3File={
                'bucketName': MEDIA_BUCKET,
                'key': upload_key,
            }
        )

        header_handle = response.get('id', '')

        return {
            'statusCode': 201,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'headerHandle': header_handle,
                's3Key': upload_key,
                'cardIndex': card_index,
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


def _create_carousel_template(waba_id, body):
    """Create a carousel template with multiple cards.
    Each card has a header (image/video), body text, and optional buttons.
    """
    try:
        name = body.get('name')
        language = body.get('language', 'en_US')
        category = body.get('category', 'MARKETING')
        body_text = body.get('bodyText', '')
        cards = body.get('cards', [])

        if not name:
            return _error_response(400, 'name required')
        if not cards or len(cards) < 2:
            return _error_response(400, 'At least 2 cards required for carousel')
        if len(cards) > 10:
            return _error_response(400, 'Maximum 10 cards allowed')

        # Build carousel template definition per Meta's format
        components = []

        # Body component (text above the carousel)
        if body_text:
            components.append({
                'type': 'BODY',
                'text': body_text,
            })

        # Carousel component
        carousel_cards = []
        for i, card in enumerate(cards):
            card_components = []

            # Card header (image or video)
            header_type = card.get('headerType', 'image').upper()
            header_handle = card.get('headerHandle', '')
            if header_handle:
                card_components.append({
                    'type': 'HEADER',
                    'format': header_type,
                    'example': {'header_handle': [header_handle]},
                })

            # Card body
            card_body = card.get('bodyText', '')
            if card_body:
                card_components.append({
                    'type': 'BODY',
                    'text': card_body,
                })

            # Card buttons
            card_buttons = card.get('buttons', [])
            if card_buttons:
                card_components.append({
                    'type': 'BUTTONS',
                    'buttons': card_buttons,
                })

            carousel_cards.append({'components': card_components})

        components.append({
            'type': 'CAROUSEL',
            'cards': carousel_cards,
        })

        template_def = {
            'name': name,
            'language': language,
            'category': category,
            'components': components,
        }

        template_blob = json.dumps(template_def).encode('utf-8')
        response = social_messaging.create_whatsapp_message_template(
            id=waba_id, templateDefinition=template_blob
        )

        logger.info(json.dumps({
            'event': 'carousel_template_created',
            'name': name,
            'cardCount': len(cards),
            'metaTemplateId': response.get('metaTemplateId', ''),
        }))

        return {
            'statusCode': 201,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'metaTemplateId': response.get('metaTemplateId', ''),
                'templateStatus': response.get('templateStatus', 'PENDING'),
                'templateType': 'CAROUSEL',
                'cardCount': len(cards),
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


# ── ERROR HELPER ──

def _error_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps({'error': message})
    }
