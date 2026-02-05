import os
import json
import logging
import base64
import boto3
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

social_messaging = boto3.client('socialmessaging', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'auth.wecare.digital')
DEFAULT_WABA_ID = 'waba-df9aa4e4946a40b59e269a4f41633ca1'

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}

def handler(event, context):
    request_id = context.aws_request_id if context else 'local'
    request_context = event.get('requestContext', {})
    if 'http' in request_context:
        http_method = request_context.get('http', {}).get('method', 'GET')
        path = request_context.get('http', {}).get('path', '') or event.get('rawPath', '')
    else:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
    
    query_params = event.get('queryStringParameters') or {}
    
    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': ''}
    
    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        waba_id = query_params.get('wabaId', DEFAULT_WABA_ID)
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'
        
        if http_method == 'GET':
            if '/templates/library' in path:
                return _list_template_library(waba_id, query_params)
            return _list_templates(waba_id, query_params)
        elif http_method == 'POST':
            if '/templates/from-library' in path:
                return _create_from_library(waba_id, body)
            return _create_template(waba_id, body)
        elif http_method == 'DELETE':
            return _delete_template(waba_id, query_params.get('templateName', ''), query_params)
        return _error_response(400, 'Invalid request')
    except Exception as e:
        return _error_response(500, str(e))

def _list_templates(waba_id, query_params):
    try:
        response = social_messaging.list_whatsapp_message_templates(id=waba_id, maxResults=100)
        templates = [{'metaTemplateId': t.get('metaTemplateId'), 'templateName': t.get('templateName'),
                      'templateStatus': t.get('templateStatus')} for t in response.get('templates', [])]
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps({'templates': templates})}
    except Exception as e:
        return _error_response(500, str(e))

def _list_template_library(waba_id, query_params):
    try:
        response = social_messaging.list_whatsapp_template_library(id=waba_id, maxResults=50)
        templates = [{'templateId': t.get('templateId'), 'templateName': t.get('templateName'),
                      'templateBody': t.get('templateBody')} for t in response.get('metaLibraryTemplates', [])]
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps({'templates': templates})}
    except Exception as e:
        return _error_response(500, str(e))

def _create_template(waba_id, body):
    try:
        template_def = body.get('templateDefinition')
        if not template_def:
            return _error_response(400, 'templateDefinition required')
        template_blob = json.dumps(template_def).encode('utf-8')
        response = social_messaging.create_whatsapp_message_template(id=waba_id, templateDefinition=template_blob)
        return {'statusCode': 201, 'headers': CORS_HEADERS, 'body': json.dumps({'metaTemplateId': response.get('metaTemplateId')})}
    except Exception as e:
        return _error_response(500, str(e))

def _create_from_library(waba_id, body):
    try:
        meta_lib = body.get('metaLibraryTemplate')
        if not meta_lib:
            return _error_response(400, 'metaLibraryTemplate required')
        response = social_messaging.create_whatsapp_message_template_from_library(id=waba_id, metaLibraryTemplate=meta_lib)
        return {'statusCode': 201, 'headers': CORS_HEADERS, 'body': json.dumps({'metaTemplateId': response.get('metaTemplateId')})}
    except Exception as e:
        return _error_response(500, str(e))

def _delete_template(waba_id, template_name, query_params):
    try:
        if not template_name:
            return _error_response(400, 'templateName required')
        social_messaging.delete_whatsapp_message_template(id=waba_id, templateName=template_name)
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps({'success': True})}
    except Exception as e:
        return _error_response(500, str(e))

def _error_response(status_code, message):
    return {'statusCode': status_code, 'headers': CORS_HEADERS, 'body': json.dumps({'error': message})}
