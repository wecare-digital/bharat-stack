"""
AI Query Knowledge Base Lambda Function

Purpose: Query Bedrock Knowledge Base for context
Uses External KB for WhatsApp auto-reply

KB IDs:
- Internal KB: D0JU8Q7IQS
- External KB: LYMQLKZNY7
"""

import os
import json
import logging
import boto3
from typing import Dict, Any, Optional

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

# Configure logging
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

# AWS clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
INTERNAL_KB_ID = os.environ.get('INTERNAL_KB_ID', 'D0JU8Q7IQS')
EXTERNAL_KB_ID = os.environ.get('EXTERNAL_KB_ID', 'LYMQLKZNY7')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Query Knowledge Base for relevant context."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    
    query = event.get('query', '')
    message_id = event.get('messageId', '')
    kb_type = event.get('kbType', 'external')  # default to external for WhatsApp
    
    # Select KB based on type
    kb_id = INTERNAL_KB_ID if kb_type == 'internal' else EXTERNAL_KB_ID
    
    logger.info(json.dumps({
        'event': 'kb_query_start',
        'kbId': kb_id,
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
        # Query the knowledge base
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 3
                }
            }
        )
        
        # Extract relevant context from results
        results = response.get('retrievalResults', [])
        context_parts = []
        
        for result in results:
            content = result.get('content', {}).get('text', '')
            score = result.get('score', 0)
            if content and score > 0.5:  # Only include relevant results
                context_parts.append(content)
        
        context_text = '\n\n'.join(context_parts[:3])  # Limit to top 3
        
        logger.info(json.dumps({
            'event': 'kb_query_success',
            'kbId': kb_id,
            'resultsCount': len(results),
            'contextLength': len(context_text),
            'messageId': message_id,
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'context': context_text,
                'resultsCount': len(results),
                'kbId': kb_id
            })
        }
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'kb_query_error',
            'kbId': kb_id,
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
