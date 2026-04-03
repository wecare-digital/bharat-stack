import os
import json
import base64
import uuid
import hashlib
import hmac
import boto3
import urllib.request
import urllib.parse
import urllib.error
from lambda_utils.response import cors_headers, options_response, extract_origin
from lambda_utils.logging import get_logger
from lambda_utils.middleware import require_auth

logger = get_logger(__name__)

origin = ''

s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
TEMPLATE_MEDIA_PREFIX = os.environ.get('TEMPLATE_MEDIA_PREFIX', 'stack/whatsapp-media/template-headers/')
DEFAULT_WABA_ID = 'waba-e47d916f3c7a47e1a34a19653893dd4b'

META_API_VERSION = 'v25.0'
META_GRAPH_URL = f'https://graph.facebook.com/{META_API_VERSION}'
META_APP_ID = '2238810740192680'
DEFAULT_PHONE_ID = '1016149501586345'

AWS_TO_META_WABA = {
    'waba-e47d916f3c7a47e1a34a19653893dd4b': '2094615664435155',   # WABA1
    'waba-dbe343f210204752b74c80a0a59631a6': '2513394156072604',   # WABA2/WABA-T
}
DEFAULT_META_WABA_ID = '2094615664435155'  # WABA1

# Cached token/secret
_meta_creds = {}


def _get_meta_creds():
    """Load Meta access_token and app_secret from Secrets Manager (cached)."""
    if _meta_creds:
        return _meta_creds
    resp = secrets_client.get_secret_value(SecretId='wecare/meta-system-user-token')
    secret = json.loads(resp['SecretString'])
    _meta_creds['access_token'] = secret['access_token']
    _meta_creds['app_secret'] = secret['app_secret']
    return _meta_creds


def _appsecret_proof(access_token: str, app_secret: str) -> str:
    return hmac.new(app_secret.encode(), access_token.encode(), hashlib.sha256).hexdigest()


def _resolve_meta_waba_id(aws_waba_id: str) -> str:
    """Map AWS WABA ID to Meta WABA ID.
    Accepts either AWS format (waba-xxx) or Meta numeric ID directly.
    """
    # If it's already a numeric Meta WABA ID, return as-is
    if aws_waba_id.replace('-', '').isdigit() and not aws_waba_id.startswith('waba-'):
        if aws_waba_id in AWS_TO_META_WABA.values():
            return aws_waba_id
        return aws_waba_id
    if not aws_waba_id.startswith('waba-'):
        aws_waba_id = f'waba-{aws_waba_id}'
    return AWS_TO_META_WABA.get(aws_waba_id, DEFAULT_META_WABA_ID)


def _meta_request(url: str, method: str = 'GET', data: bytes = None, headers: dict = None) -> dict:
    """Make an authenticated request to the Meta Graph API."""
    creds = _get_meta_creds()
    token = creds['access_token']
    proof = _appsecret_proof(token, creds['app_secret'])

    sep = '&' if '?' in url else '?'
    url = f'{url}{sep}access_token={token}&appsecret_proof={proof}'

    req_headers = headers or {}
    if data and 'Content-Type' not in req_headers:
        req_headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        logger.error(json.dumps({'event': 'meta_api_error', 'status': e.code, 'body': error_body}))
        try:
            err = json.loads(error_body)
            msg = err.get('error', {}).get('message', error_body)
        except Exception:
            msg = error_body
        raise RuntimeError(f'Meta API {e.code}: {msg}')


def handler(event, context):
    global origin
    request_id = context.aws_request_id if context else 'local'
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
        # Don't prepend waba- to numeric Meta WABA IDs
        if not waba_id.startswith('waba-') and not waba_id.replace('-', '').isdigit():
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
                return _upload_carousel_media(waba_id, body, query_params)
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
    idx = path.find(prefix)
    if idx == -1:
        return ''
    remainder = path[idx + len(prefix):]
    return remainder.split('/')[0].split('?')[0]


# ── LIST ──

def _list_templates(waba_id, query_params):
    try:
        meta_waba_id = _resolve_meta_waba_id(waba_id)
        url = f'{META_GRAPH_URL}/{meta_waba_id}/message_templates?fields=name,status,category,language,components,id'
        limit = query_params.get('maxResults', '100')
        url += f'&limit={limit}'
        data = _meta_request(url)
        templates = []
        for t in data.get('data', []):
            templates.append({
                'metaTemplateId': t.get('id'),
                'templateName': t.get('name'),
                'templateStatus': t.get('status'),
            })
        return {'statusCode': 200, 'headers': cors_headers(origin), 'body': json.dumps({'templates': templates})}
    except Exception as e:
        return _error_response(500, str(e))


def _list_template_library(waba_id, query_params):
    """AWS-specific list_whatsapp_template_library has no Meta Graph API equivalent."""
    return {
        'statusCode': 200,
        'headers': cors_headers(origin),
        'body': json.dumps({
            'templates': [],
            'note': 'Template library listing is not available via Meta Graph API. Use Meta Business Suite to browse the template library.',
        })
    }


# ── GET SINGLE TEMPLATE ──

def _get_template_details(waba_id, template_id, query_params):
    try:
        url = f'{META_GRAPH_URL}/{template_id}?fields=name,status,category,language,components,id'
        data = _meta_request(url)
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'template': {
                    'metaTemplateId': data.get('id'),
                    'templateName': data.get('name'),
                    'templateStatus': data.get('status'),
                    'components': data.get('components', []),
                    'language': data.get('language', ''),
                    'category': data.get('category', ''),
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
        meta_waba_id = _resolve_meta_waba_id(waba_id)
        url = f'{META_GRAPH_URL}/{meta_waba_id}/message_templates'
        data = _meta_request(url, method='POST', data=json.dumps(template_def).encode())
        return {
            'statusCode': 201,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'metaTemplateId': data.get('id', ''),
                'category': data.get('category', ''),
                'templateStatus': data.get('status', 'PENDING'),
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


def _create_from_library(waba_id, body):
    """AWS create_whatsapp_message_template_from_library has no Meta Graph API equivalent."""
    return _error_response(
        501,
        'Creating templates from the Meta template library is not supported via the Graph API. '
        'Use Meta Business Suite or create the template directly with _create_template.'
    )


# ── UPDATE ──

def _update_template(waba_id, body, query_params, path):
    try:
        template_id = _extract_path_param(path, '/templates/')
        if not template_id:
            template_id = body.get('metaTemplateId', '')
        if not template_id:
            return _error_response(400, 'Template ID required (in path or body)')

        template_def = body.get('templateDefinition')
        if not template_def:
            return _error_response(400, 'templateDefinition required')

        url = f'{META_GRAPH_URL}/{template_id}'
        data = _meta_request(url, method='POST', data=json.dumps(template_def).encode())

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'metaTemplateId': data.get('id', template_id),
            })
        }
    except Exception as e:
        return _error_response(500, str(e))


# ── DELETE ──

def _delete_template(waba_id, template_name, query_params):
    try:
        if not template_name:
            return _error_response(400, 'templateName required')
        meta_waba_id = _resolve_meta_waba_id(waba_id)
        encoded_name = urllib.parse.quote(template_name)
        url = f'{META_GRAPH_URL}/{meta_waba_id}/message_templates?name={encoded_name}'
        _meta_request(url, method='DELETE')
        return {'statusCode': 200, 'headers': cors_headers(origin), 'body': json.dumps({'success': True})}
    except Exception as e:
        return _error_response(500, str(e))


# ── MEDIA UPLOAD ──

def _upload_media_to_meta(file_bytes: bytes, content_type: str, filename: str) -> str:
    """Upload media to Meta via the phone media endpoint. Returns the media ID (header handle)."""
    boundary = uuid.uuid4().hex
    body_parts = []
    body_parts.append(f'--{boundary}\r\n'.encode())
    body_parts.append(f'Content-Disposition: form-data; name="messaging_product"\r\n\r\nwhatsapp\r\n'.encode())
    body_parts.append(f'--{boundary}\r\n'.encode())
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body_parts.append(f'Content-Type: {content_type}\r\n\r\n'.encode())
    body_parts.append(file_bytes)
    body_parts.append(f'\r\n--{boundary}--\r\n'.encode())
    multipart_body = b''.join(body_parts)

    url = f'{META_GRAPH_URL}/{DEFAULT_PHONE_ID}/media'
    headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}
    data = _meta_request(url, method='POST', data=multipart_body, headers=headers)
    return data.get('id', '')


def _upload_template_media(waba_id, body):
    try:
        file_data_b64 = body.get('fileData')
        s3_key = body.get('s3Key')
        content_type = body.get('contentType', 'image/jpeg')
        filename = body.get('filename', 'header.jpg')

        if not file_data_b64 and not s3_key:
            return _error_response(400, 'fileData (base64) or s3Key required')

        if s3_key:
            obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=s3_key)
            file_bytes = obj['Body'].read()
        else:
            file_bytes = base64.b64decode(file_data_b64)

        # Upload to S3 for reference
        upload_key = f'{TEMPLATE_MEDIA_PREFIX}wecare-digital-{uuid.uuid4().hex[:8]}_{filename}'
        s3.put_object(Bucket=MEDIA_BUCKET, Key=upload_key, Body=file_bytes, ContentType=content_type)

        # Upload to Meta
        header_handle = _upload_media_to_meta(file_bytes, content_type, filename)

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

def _upload_carousel_media(waba_id, body, query_params):
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

        upload_key = f'{TEMPLATE_MEDIA_PREFIX}wecare-digital-{uuid.uuid4().hex[:8]}_card{card_index}'
        s3.put_object(Bucket=MEDIA_BUCKET, Key=upload_key, Body=file_bytes, ContentType=content_type)

        header_handle = _upload_media_to_meta(file_bytes, content_type, f'card{card_index}')

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

        components = []
        if body_text:
            components.append({'type': 'BODY', 'text': body_text})

        carousel_cards = []
        for i, card in enumerate(cards):
            card_components = []
            header_type = card.get('headerType', 'image').upper()
            header_handle = card.get('headerHandle', '')
            if header_handle:
                card_components.append({
                    'type': 'HEADER',
                    'format': header_type,
                    'example': {'header_handle': [header_handle]},
                })
            card_body = card.get('bodyText', '')
            if card_body:
                card_components.append({'type': 'BODY', 'text': card_body})
            card_buttons = card.get('buttons', [])
            if card_buttons:
                card_components.append({'type': 'BUTTONS', 'buttons': card_buttons})
            carousel_cards.append({'components': card_components})

        components.append({'type': 'CAROUSEL', 'cards': carousel_cards})

        template_def = {
            'name': name,
            'language': language,
            'category': category,
            'components': components,
        }

        meta_waba_id = _resolve_meta_waba_id(waba_id)
        url = f'{META_GRAPH_URL}/{meta_waba_id}/message_templates'
        data = _meta_request(url, method='POST', data=json.dumps(template_def).encode())

        logger.info(json.dumps({
            'event': 'carousel_template_created',
            'name': name,
            'cardCount': len(cards),
            'metaTemplateId': data.get('id', ''),
        }))

        return {
            'statusCode': 201,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'metaTemplateId': data.get('id', ''),
                'templateStatus': data.get('status', 'PENDING'),
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
