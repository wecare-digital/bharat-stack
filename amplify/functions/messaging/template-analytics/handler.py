"""
Template Analytics Lambda Function
Aggregates template message metrics from outbound messages table

Routes:
- GET /templates/analytics - Get summary analytics for all templates
- GET /templates/analytics/{templateName} - Get analytics for specific template
"""

import os
import json
import logging
import boto3
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List
from collections import defaultdict

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for template analytics."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    
    request_context = event.get('requestContext', {})
    if 'http' in request_context:
        http_method = request_context.get('http', {}).get('method', 'GET')
        path = request_context.get('http', {}).get('path', '') or event.get('rawPath', '')
    else:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
    
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({'event': 'analytics_request', 'method': http_method, 'path': path}))
    
    if http_method == 'OPTIONS':
        return options_response(origin)

    try:
        if http_method == 'GET':
            # Check if specific template requested
            template_name = path_params.get('templateName')
            if not template_name and '/analytics/' in path:
                parts = path.split('/analytics/')
                if len(parts) > 1 and parts[1]:
                    template_name = parts[1].split('/')[0]
            
            if template_name:
                return _get_template_analytics(template_name, query_params, request_id)
            else:
                return _get_analytics_summary(query_params, request_id)
        
        return _error_response(400, 'Invalid request method')
    except Exception as e:
        logger.error(f'Analytics error: {str(e)}')
        return _error_response(500, str(e))


def _get_analytics_summary(query_params: Dict[str, str], request_id: str) -> Dict[str, Any]:
    """Get summary analytics for all templates."""
    table = dynamodb.Table(OUTBOUND_TABLE)
    
    # Get date range (default: last 30 days)
    days = int(query_params.get('days', '30'))
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    try:
        # Scan outbound messages for template messages
        response = table.scan(
            FilterExpression='#isTemplate = :true AND #timestamp >= :start',
            ExpressionAttributeNames={
                '#isTemplate': 'isTemplate',
                '#timestamp': 'timestamp'
            },
            ExpressionAttributeValues={
                ':true': True,
                ':start': start_date
            }
        )
        
        items = response.get('Items', [])
        
        # Aggregate by template
        template_stats = defaultdict(lambda: {
            'totalSent': 0,
            'delivered': 0,
            'read': 0,
            'failed': 0,
            'category': 'UTILITY'
        })
        
        category_counts = defaultdict(int)
        
        for item in items:
            template_name = item.get('templateName', 'unknown')
            status = item.get('status', '').lower()
            category = item.get('templateCategory', 'UTILITY')
            
            template_stats[template_name]['totalSent'] += 1
            template_stats[template_name]['category'] = category
            category_counts[category] += 1
            
            if status in ['delivered', 'read', 'sent']:
                template_stats[template_name]['delivered'] += 1
            if status == 'read':
                template_stats[template_name]['read'] += 1
            if status in ['failed', 'error', 'undelivered']:
                template_stats[template_name]['failed'] += 1
        
        # Calculate totals
        total_sent = sum(s['totalSent'] for s in template_stats.values())
        total_delivered = sum(s['delivered'] for s in template_stats.values())
        total_read = sum(s['read'] for s in template_stats.values())
        
        avg_delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        avg_read_rate = (total_read / total_delivered * 100) if total_delivered > 0 else 0
        
        # Get top templates
        top_templates = []
        for name, stats in sorted(template_stats.items(), key=lambda x: x[1]['totalSent'], reverse=True)[:10]:
            delivery_rate = (stats['delivered'] / stats['totalSent'] * 100) if stats['totalSent'] > 0 else 0
            read_rate = (stats['read'] / stats['delivered'] * 100) if stats['delivered'] > 0 else 0
            
            top_templates.append({
                'templateName': name,
                'language': 'en_US',  # Default, could be extracted from data
                'totalSent': stats['totalSent'],
                'delivered': stats['delivered'],
                'read': stats['read'],
                'failed': stats['failed'],
                'deliveryRate': round(delivery_rate, 1),
                'readRate': round(read_rate, 1)
            })
        
        return cors_response(200, {
                'totalTemplatesSent': total_sent,
                'avgDeliveryRate': round(avg_delivery_rate, 1),
                'avgReadRate': round(avg_read_rate, 1),
                'topTemplates': top_templates,
                'byCategory': dict(category_counts),
                'period': f'Last {days} days'
            }, origin)
    except Exception as e:
        logger.error(f'Analytics summary error: {str(e)}')
        return _error_response(500, f'Failed to get analytics: {str(e)}')


def _get_template_analytics(template_name: str, query_params: Dict[str, str], request_id: str) -> Dict[str, Any]:
    """Get analytics for a specific template."""
    table = dynamodb.Table(OUTBOUND_TABLE)
    
    days = int(query_params.get('days', '30'))
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    try:
        response = table.scan(
            FilterExpression='#templateName = :name AND #timestamp >= :start',
            ExpressionAttributeNames={
                '#templateName': 'templateName',
                '#timestamp': 'timestamp'
            },
            ExpressionAttributeValues={
                ':name': template_name,
                ':start': start_date
            }
        )
        
        items = response.get('Items', [])
        
        total_sent = len(items)
        delivered = sum(1 for i in items if i.get('status', '').lower() in ['delivered', 'read', 'sent'])
        read = sum(1 for i in items if i.get('status', '').lower() == 'read')
        failed = sum(1 for i in items if i.get('status', '').lower() in ['failed', 'error', 'undelivered'])
        
        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        read_rate = (read / delivered * 100) if delivered > 0 else 0
        
        # Daily breakdown
        daily_stats = defaultdict(lambda: {'sent': 0, 'delivered': 0, 'read': 0})
        for item in items:
            date = item.get('timestamp', '')[:10]  # YYYY-MM-DD
            daily_stats[date]['sent'] += 1
            if item.get('status', '').lower() in ['delivered', 'read', 'sent']:
                daily_stats[date]['delivered'] += 1
            if item.get('status', '').lower() == 'read':
                daily_stats[date]['read'] += 1
        
        return cors_response(200, {
                'templateName': template_name,
                'totalSent': total_sent,
                'delivered': delivered,
                'read': read,
                'failed': failed,
                'deliveryRate': round(delivery_rate, 1),
                'readRate': round(read_rate, 1),
                'dailyStats': dict(daily_stats),
                'period': f'Last {days} days'
            })
    except Exception as e:
        logger.error(f'Template analytics error: {str(e)}')
        return _error_response(500, f'Failed to get template analytics: {str(e)}')


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Return error response."""
    return cors_response(status_code, {'error': message})
