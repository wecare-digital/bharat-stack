"""
AI Query Knowledge Base Lambda Function

Purpose: Query static knowledge base for context (FREE - no OpenSearch!)
Uses static FAQ database instead of Bedrock Knowledge Base

COST SAVINGS: Eliminates $191.60/month OpenSearch Serverless cost
"""

import os
import json
import logging
from typing import Dict, Any

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.logging import get_logger

# Import static knowledge base
import sys
sys.path.append('/opt/python')
from static_knowledge_base import search_knowledge_base as static_kb_search

logger = get_logger(__name__)

# Environment variables
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Query static knowledge base for relevant context."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    
    query = event.get('query', '')
    message_id = event.get('messageId', '')
    kb_type = event.get('kbType', 'external')  # kept for compatibility
    
    logger.info(json.dumps({
        'event': 'static_kb_query_start',
        'kbType': kb_type,
        'queryLength': len(query) if query else 0,
        'messageId': message_id,
        'requestId': request_id
    }))
    
    if SEND_MODE == 'DRY_RUN':
        return {'statusCode': 200, 'body': json.dumps({'context': '', 'mode': 'DRY_RUN'})}
    
    if not query:
        return {'statusCode': 200, 'body': json.dumps({'context': ''})}
    
    try:
        # Query the static knowledge base (FREE!)
        context_text = static_kb_search(query, max_results=3)
        
        logger.info(json.dumps({
            'event': 'static_kb_query_success',
            'contextLength': len(context_text),
            'messageId': message_id,
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'context': context_text,
                'source': 'static_kb'
            })
        }
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'static_kb_query_error',
            'error': str(e),
            'messageId': message_id,
            'requestId': request_id
        }))
        return {
            'statusCode': 200,
            'body': json.dumps({
                'context': '',
                'error': str(e)
            })
        }
