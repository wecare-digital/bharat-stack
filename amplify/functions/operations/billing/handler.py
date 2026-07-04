"""
AWS Billing Lambda Function

Purpose: Fetch real AWS Cost Explorer, Health, and Trusted Advisor data
Account: 775261844268
Region: us-east-1

Uses AWS Cost Explorer, Health, and Support APIs.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

# Configure logging
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

# AWS clients
ce_client = boto3.client('ce', region_name='us-east-1')
health_client = boto3.client('health', region_name='us-east-1')
support_client = boto3.client('support', region_name='us-east-1')

# Account info
AWS_ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID', '')


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle billing, health, and trusted advisor requests."""
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)

    from lambda_utils.middleware import require_auth
    _auth = require_auth(event)
    if _auth is not None:
        return _auth

    logger.info(json.dumps({
        'event': 'billing_handler',
        'requestId': request_id
    }))
    
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        month_offset = int(query_params.get('month', '0'))
        include_health = query_params.get('health', 'true').lower() == 'true'
        include_advisor = query_params.get('advisor', 'true').lower() == 'true'
        
        now = datetime.utcnow()
        
        # Calculate target month
        if month_offset == 0:
            # Current month
            start_of_month = datetime(now.year, now.month, 1)
            end_date = now
        else:
            # Previous month(s)
            target_month = now.month + month_offset
            target_year = now.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            while target_month > 12:
                target_month -= 12
                target_year += 1
            
            start_of_month = datetime(target_year, target_month, 1)
            # End of that month
            if target_month == 12:
                end_date = datetime(target_year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(target_year, target_month + 1, 1) - timedelta(days=1)
        
        # Format dates for Cost Explorer (YYYY-MM-DD)
        start_date = start_of_month.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # If we're on the first day, use tomorrow as end date for API
        if start_date == end_date_str:
            end_date_str = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Fetch cost data from Cost Explorer
        billing_data = get_cost_and_usage(start_date, end_date_str, request_id)
        
        # Also fetch previous month total for comparison
        if month_offset == 0:
            prev_month = now.month - 1
            prev_year = now.year
            if prev_month <= 0:
                prev_month = 12
                prev_year -= 1
            prev_start = datetime(prev_year, prev_month, 1).strftime('%Y-%m-%d')
            if prev_month == 12:
                prev_end = datetime(prev_year + 1, 1, 1).strftime('%Y-%m-%d')
            else:
                prev_end = datetime(prev_year, prev_month + 1, 1).strftime('%Y-%m-%d')
            
            try:
                prev_response = ce_client.get_cost_and_usage(
                    TimePeriod={'Start': prev_start, 'End': prev_end},
                    Granularity='MONTHLY',
                    Metrics=['UnblendedCost']
                )
                prev_cost = 0.0
                if prev_response.get('ResultsByTime'):
                    for result in prev_response['ResultsByTime']:
                        cost = result.get('Total', {}).get('UnblendedCost', {}).get('Amount', '0')
                        prev_cost += float(cost)
                billing_data['previousMonthCost'] = round(prev_cost, 2)
                billing_data['previousMonthPeriod'] = f'{prev_start} to {prev_end}'
            except Exception as e:
                logger.warning(f'Failed to fetch previous month: {e}')
        
        # Fetch AWS Health data
        if include_health:
            billing_data['health'] = get_aws_health_status(request_id)
        
        # Fetch Trusted Advisor data
        if include_advisor:
            billing_data['trustedAdvisor'] = get_trusted_advisor_checks(request_id)
        
        return _response(200, billing_data)
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(json.dumps({
            'event': 'billing_error',
            'errorCode': error_code,
            'error': error_msg,
            'requestId': request_id
        }))
        
        # Return fallback data if Cost Explorer access fails
        if error_code in ['AccessDeniedException', 'UnauthorizedAccess']:
            return _response(200, get_fallback_billing_data())
        
        return _response(500, {'error': f'{error_code}: {error_msg}'})
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'billing_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(500, {'error': str(e)})


def get_cost_and_usage(start_date: str, end_date: str, request_id: str) -> Dict[str, Any]:
    """Fetch cost and usage data from AWS Cost Explorer."""
    
    # Get total cost
    total_response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost', 'UsageQuantity']
    )
    
    # Get cost by service
    service_response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost', 'UsageQuantity'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'}
        ]
    )
    
    # Parse total cost
    total_cost = 0.0
    if total_response.get('ResultsByTime'):
        for result in total_response['ResultsByTime']:
            cost = result.get('Total', {}).get('UnblendedCost', {}).get('Amount', '0')
            total_cost += float(cost)
    
    # Parse service costs
    services = []
    if service_response.get('ResultsByTime'):
        for result in service_response['ResultsByTime']:
            for group in result.get('Groups', []):
                service_name = group.get('Keys', ['Unknown'])[0]
                cost = float(group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount', '0'))
                usage = float(group.get('Metrics', {}).get('UsageQuantity', {}).get('Amount', '0'))
                
                # Skip services with zero cost
                if cost < 0.001 and usage < 1:
                    continue
                
                # Determine status based on cost
                if cost == 0:
                    status = 'free'
                elif cost < 1:
                    status = 'warning'
                else:
                    status = 'paid'
                
                services.append({
                    'service': service_name,
                    'cost': round(cost, 2),
                    'usage': int(usage),
                    'unit': get_service_unit(service_name),
                    'freeLimit': get_free_tier_limit(service_name),
                    'status': status
                })
    
    # Sort by cost descending
    services.sort(key=lambda x: x['cost'], reverse=True)
    
    # Generate cost optimization recommendations
    recommendations = generate_cost_recommendations(services, total_cost)
    
    logger.info(json.dumps({
        'event': 'billing_fetched',
        'totalCost': total_cost,
        'serviceCount': len(services),
        'recommendationCount': len(recommendations),
        'period': f'{start_date} to {end_date}',
        'requestId': request_id
    }))
    
    return {
        'totalCost': round(total_cost, 2),
        'period': f'{start_date} to {end_date}',
        'services': services,
        'lastUpdated': datetime.utcnow().isoformat() + 'Z',
        'accountId': AWS_ACCOUNT_ID,
        'currency': 'USD',
        'recommendations': recommendations
    }


def generate_cost_recommendations(services: List[Dict], total_cost: float) -> List[Dict[str, Any]]:
    """Generate cost optimization recommendations based on usage patterns."""
    recommendations = []
    
    service_map = {s['service']: s for s in services}
    
    # Check for AWS Business Support
    if 'AWS Business Support+' in service_map or 'AWS Business Support (Business)' in service_map:
        support_cost = service_map.get('AWS Business Support+', service_map.get('AWS Business Support (Business)', {})).get('cost', 0)
        if support_cost > 0:
            recommendations.append({
                'id': 'support-plan',
                'severity': 'high',
                'title': 'Consider Downgrading Support Plan',
                'description': f'AWS Business Support costs ${support_cost:.2f}/month. For development/testing, consider Basic Support (free) to save the full amount, or Developer Support ($29/month) for technical support.',
                'potentialSavings': round(support_cost, 2),  # Full savings if downgrading to Basic
                'action': 'Review support plan in AWS Support Center',
                'link': 'https://console.aws.amazon.com/support/plans/home'
            })
    
    # Check OpenSearch costs
    if 'Amazon OpenSearch Service' in service_map:
        opensearch = service_map['Amazon OpenSearch Service']
        if opensearch['cost'] > 0:
            recommendations.append({
                'id': 'opensearch-serverless',
                'severity': 'medium',
                'title': 'Optimize OpenSearch Serverless',
                'description': f'OpenSearch Serverless costs ${opensearch["cost"]:.2f}. Consider reducing OCU capacity or using time-based scaling.',
                'potentialSavings': round(opensearch['cost'] * 0.3, 2),
                'action': 'Configure auto-scaling policies',
                'link': 'https://console.aws.amazon.com/aos/home'
            })
    
    # Check Amplify build minutes
    if 'AWS Amplify' in service_map:
        amplify = service_map['AWS Amplify']
        if amplify['usage'] > 1000:  # Over free tier
            recommendations.append({
                'id': 'amplify-builds',
                'severity': 'medium',
                'title': 'Reduce Amplify Build Minutes',
                'description': f'Using {amplify["usage"]} build minutes (free tier: 1000). Consider caching dependencies or reducing build frequency.',
                'potentialSavings': round((amplify['usage'] - 1000) * 0.01, 2),
                'action': 'Enable build caching in amplify.yml',
                'link': 'https://docs.aws.amazon.com/amplify/latest/userguide/build-settings.html'
            })
    
    # Check Route 53 costs
    if 'Amazon Route 53' in service_map:
        route53 = service_map['Amazon Route 53']
        if route53['cost'] > 0.5:
            recommendations.append({
                'id': 'route53-zones',
                'severity': 'low',
                'title': 'Review Route 53 Hosted Zones',
                'description': f'Route 53 costs ${route53["cost"]:.2f}. Each hosted zone costs $0.50/month. Remove unused zones.',
                'potentialSavings': round(route53['cost'] * 0.2, 2),
                'action': 'Delete unused hosted zones',
                'link': 'https://console.aws.amazon.com/route53/v2/hostedzones'
            })
    
    # Check WAF costs
    if 'AWS WAF' in service_map:
        waf = service_map['AWS WAF']
        if waf['cost'] > 5:
            recommendations.append({
                'id': 'waf-rules',
                'severity': 'low',
                'title': 'Optimize WAF Rules',
                'description': f'WAF costs ${waf["cost"]:.2f}. Review and consolidate rules. Each web ACL costs $5/month + $1/rule.',
                'potentialSavings': round(waf['cost'] * 0.2, 2),
                'action': 'Consolidate WAF rules',
                'link': 'https://console.aws.amazon.com/wafv2/homev2'
            })
    
    # Check WhatsApp messaging costs (Meta Cloud API)
    if 'Meta WhatsApp Cloud API' in service_map:
        messaging = service_map['Meta WhatsApp Cloud API']
        if messaging['cost'] > 10:
            recommendations.append({
                'id': 'messaging-templates',
                'severity': 'medium',
                'title': 'Optimize WhatsApp Messaging',
                'description': f'Messaging costs ${messaging["cost"]:.2f}. Use template messages (cheaper) instead of session messages when possible.',
                'potentialSavings': round(messaging['cost'] * 0.4, 2),
                'action': 'Use approved templates for outbound messages',
                'link': 'https://business.facebook.com/latest/whatsapp_manager/message_templates'
            })
    
    # Check Lambda costs (usually free tier)
    if 'AWS Lambda' in service_map:
        lambda_svc = service_map['AWS Lambda']
        if lambda_svc['cost'] > 0:
            recommendations.append({
                'id': 'lambda-memory',
                'severity': 'low',
                'title': 'Right-size Lambda Functions',
                'description': f'Lambda costs ${lambda_svc["cost"]:.2f}. Review function memory settings - lower memory = lower cost.',
                'potentialSavings': round(lambda_svc['cost'] * 0.3, 2),
                'action': 'Use AWS Lambda Power Tuning',
                'link': 'https://console.aws.amazon.com/lambda/home'
            })
    
    # Check DynamoDB costs
    if 'Amazon DynamoDB' in service_map:
        dynamodb = service_map['Amazon DynamoDB']
        if dynamodb['cost'] > 0:
            recommendations.append({
                'id': 'dynamodb-capacity',
                'severity': 'medium',
                'title': 'Review DynamoDB Capacity Mode',
                'description': f'DynamoDB costs ${dynamodb["cost"]:.2f}. Consider on-demand pricing for variable workloads or provisioned for steady traffic.',
                'potentialSavings': round(dynamodb['cost'] * 0.25, 2),
                'action': 'Switch to on-demand or enable auto-scaling',
                'link': 'https://console.aws.amazon.com/dynamodbv2/home'
            })
    
    # General recommendation if total cost is high
    if total_cost > 50:
        recommendations.append({
            'id': 'cost-anomaly',
            'severity': 'high',
            'title': 'Enable Cost Anomaly Detection',
            'description': 'Set up AWS Cost Anomaly Detection to get alerts when spending patterns change unexpectedly.',
            'potentialSavings': 0,
            'action': 'Enable in AWS Cost Management',
            'link': 'https://console.aws.amazon.com/cost-management/home#/anomaly-detection'
        })
    
    # Check for tax (can't optimize but inform)
    if 'Tax' in service_map:
        tax = service_map['Tax']
        if tax['cost'] > 0:
            recommendations.append({
                'id': 'tax-exemption',
                'severity': 'info',
                'title': 'Tax Exemption Status',
                'description': f'Tax charges: ${tax["cost"]:.2f}. If your organization is tax-exempt, upload exemption certificate.',
                'potentialSavings': round(tax['cost'], 2),
                'action': 'Upload tax exemption certificate',
                'link': 'https://console.aws.amazon.com/billing/home#/tax'
            })
    
    # Check S3 costs
    if 'Amazon Simple Storage Service' in service_map:
        s3 = service_map['Amazon Simple Storage Service']
        if s3['cost'] > 0:
            recommendations.append({
                'id': 's3-lifecycle',
                'severity': 'low',
                'title': 'Enable S3 Lifecycle Policies',
                'description': f'S3 costs ${s3["cost"]:.2f}. Move infrequently accessed data to S3 Glacier or enable Intelligent-Tiering.',
                'potentialSavings': round(s3['cost'] * 0.4, 2),
                'action': 'Configure lifecycle rules for buckets',
                'link': 'https://console.aws.amazon.com/s3/home'
            })
    
    # Check CloudWatch costs
    if 'AmazonCloudWatch' in service_map:
        cloudwatch = service_map['AmazonCloudWatch']
        if cloudwatch['cost'] > 0:
            recommendations.append({
                'id': 'cloudwatch-logs',
                'severity': 'low',
                'title': 'Review CloudWatch Log Retention',
                'description': f'CloudWatch costs ${cloudwatch["cost"]:.2f}. Set log retention periods to reduce storage costs.',
                'potentialSavings': round(cloudwatch['cost'] * 0.3, 2),
                'action': 'Set retention policies on log groups',
                'link': 'https://console.aws.amazon.com/cloudwatch/home#logsV2:log-groups'
            })
    
    # Check Bedrock costs
    if 'Amazon Bedrock' in service_map:
        bedrock = service_map['Amazon Bedrock']
        if bedrock['cost'] > 0:
            recommendations.append({
                'id': 'bedrock-model',
                'severity': 'medium',
                'title': 'Optimize Bedrock Model Usage',
                'description': f'Bedrock costs ${bedrock["cost"]:.2f}. Consider using smaller models (Nova Lite vs Pro) for simpler tasks.',
                'potentialSavings': round(bedrock['cost'] * 0.5, 2),
                'action': 'Review model selection per use case',
                'link': 'https://console.aws.amazon.com/bedrock/home'
            })
    
    # Check Secrets Manager costs
    if 'AWS Secrets Manager' in service_map:
        secrets = service_map['AWS Secrets Manager']
        if secrets['cost'] > 0:
            recommendations.append({
                'id': 'secrets-cleanup',
                'severity': 'low',
                'title': 'Review Secrets Manager Usage',
                'description': f'Secrets Manager costs ${secrets["cost"]:.2f} ($0.40/secret/month). Delete unused secrets or use Parameter Store for non-sensitive config.',
                'potentialSavings': round(secrets['cost'] * 0.3, 2),
                'action': 'Audit and delete unused secrets',
                'link': 'https://console.aws.amazon.com/secretsmanager/home'
            })
    
    # Check KMS costs
    if 'AWS Key Management Service' in service_map:
        kms = service_map['AWS Key Management Service']
        if kms['cost'] > 1:
            recommendations.append({
                'id': 'kms-keys',
                'severity': 'low',
                'title': 'Review KMS Key Usage',
                'description': f'KMS costs ${kms["cost"]:.2f}. Each customer-managed key costs $1/month. Use AWS-managed keys where possible.',
                'potentialSavings': round(kms['cost'] * 0.5, 2),
                'action': 'Switch to AWS-managed keys where possible',
                'link': 'https://console.aws.amazon.com/kms/home'
            })
    
    # Sort by potential savings
    recommendations.sort(key=lambda x: x.get('potentialSavings', 0), reverse=True)
    
    return recommendations


def get_service_unit(service_name: str) -> str:
    """Get the unit of measurement for a service."""
    units = {
        'AWS Lambda': 'requests',
        'Amazon DynamoDB': 'operations',
        'Amazon Simple Storage Service': 'operations',
        'Amazon S3': 'operations',
        'Amazon API Gateway': 'requests',
        'Amazon CloudFront': 'requests',
        'AWS Amplify': 'minutes',
        'Amazon Simple Notification Service': 'notifications',
        'Amazon SNS': 'notifications',
        'Amazon Simple Queue Service': 'requests',
        'Amazon SQS': 'requests',
        'Amazon Cognito': 'users',
        'AmazonCloudWatch': 'metrics',
        'Amazon CloudWatch': 'metrics',
        'Amazon Bedrock': 'tokens',
        'Amazon OpenSearch Service': 'OCU-hours',
        'Meta WhatsApp Cloud API': 'conversations',
        'Amazon Route 53': 'queries',
        'AWS WAF': 'requests',
        'AWS Key Management Service': 'requests',
        'Amazon Simple Email Service': 'emails',
        'Amazon SES': 'emails',
        'AWS Secrets Manager': 'secrets',
        'AWS CodeBuild': 'minutes',
        'Amazon Pinpoint': 'messages',
        'Amazon Connect': 'minutes',
        'Amazon Polly': 'characters',
        'AWS Glue': 'DPU-hours',
        'AWS Step Functions': 'transitions',
        'Tax': 'tax',
        'AWS Business Support+': 'support',
        'AWS Business Support (Business)': 'support',
        'AWS Support (Business)': 'support',
        'AWS Certificate Manager': 'certificates',
        'AWS CloudFormation': 'stacks',
        'Amazon Location Service': 'requests',
        'AWS X-Ray': 'traces',
        'Amazon EventBridge': 'events',
        'AWS Systems Manager': 'operations',
    }
    return units.get(service_name, 'units')


def get_free_tier_limit(service_name: str) -> str:
    """Get the free tier limit description for a service."""
    limits = {
        'AWS Lambda': '1M requests/month',
        'Amazon DynamoDB': '25GB + 200M requests',
        'Amazon Simple Storage Service': '5GB + 20K GET',
        'Amazon S3': '5GB + 20K GET',
        'Amazon API Gateway': '1M REST calls/month',
        'Amazon CloudFront': '1TB transfer/month',
        'AWS Amplify': '1000 build mins/month',
        'Amazon Simple Notification Service': '1M publishes/month',
        'Amazon SNS': '1M publishes/month',
        'Amazon Simple Queue Service': '1M requests/month',
        'Amazon SQS': '1M requests/month',
        'Amazon Cognito': '50K MAU',
        'AmazonCloudWatch': '10 metrics free',
        'Amazon CloudWatch': '10 metrics free',
        'Amazon Bedrock': 'Pay per token',
        'Amazon OpenSearch Service': '750 OCU-hours/month',
        'Meta WhatsApp Cloud API': 'Pay per conversation',
        'Amazon Route 53': '$0.50/zone',
        'AWS WAF': '$5/web ACL + $1/rule',
        'AWS Key Management Service': '20K free requests',
        'Amazon Simple Email Service': '62K emails/month',
        'Amazon SES': '62K emails/month',
        'AWS Secrets Manager': '$0.40/secret/month',
        'AWS CodeBuild': '100 build mins/month',
        'Amazon Pinpoint': 'Pay per message',
        'Amazon Connect': 'Pay per minute',
        'Amazon Polly': '5M chars/month',
        'AWS Glue': 'Pay per DPU-hour',
        'AWS Step Functions': '4K free transitions',
        'Tax': 'N/A (Tax)',
        'AWS Business Support+': '$100/month min',
        'AWS Business Support (Business)': '$100/month min',
        'AWS Support (Business)': '$100/month min',
        'AWS Certificate Manager': 'Free public certs',
        'AWS CloudFormation': 'Free',
        'Amazon Location Service': '10K requests/month',
        'AWS X-Ray': '100K traces/month',
        'Amazon EventBridge': '14M events/month',
        'AWS Systems Manager': 'Free tier available',
    }
    return limits.get(service_name, 'Check AWS pricing')


def get_fallback_billing_data() -> Dict[str, Any]:
    """Return fallback billing data when Cost Explorer is not accessible."""
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    
    return {
        'totalCost': 0,
        'period': f'{start_of_month.strftime("%Y-%m-%d")} to {now.strftime("%Y-%m-%d")}',
        'services': [
            {'service': 'AWS Lambda', 'cost': 0, 'usage': 0, 'unit': 'requests', 'freeLimit': '1M/month', 'status': 'free'},
            {'service': 'Amazon DynamoDB', 'cost': 0, 'usage': 0, 'unit': 'operations', 'freeLimit': '200M/month', 'status': 'free'},
            {'service': 'Amazon S3', 'cost': 0, 'usage': 0, 'unit': 'operations', 'freeLimit': '20K GET', 'status': 'free'},
            {'service': 'Amazon API Gateway', 'cost': 0, 'usage': 0, 'unit': 'requests', 'freeLimit': '1M/month', 'status': 'free'},
        ],
        'lastUpdated': now.isoformat() + 'Z',
        'accountId': AWS_ACCOUNT_ID,
        'currency': 'USD',
        'note': 'Cost Explorer access required for real data'
    }


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body, default=str)
    }


def get_aws_health_status(request_id: str) -> Dict[str, Any]:
    """Fetch AWS Health Dashboard status."""
    try:
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        
        # Get open events
        open_events = []
        scheduled_changes = []
        other_notifications = []
        
        try:
            # Describe events affecting this account
            events_response = health_client.describe_events(
                filter={
                    'eventStatusCodes': ['open', 'upcoming'],
                    'startTimes': [
                        {'from': seven_days_ago}
                    ]
                }
            )
            
            for event in events_response.get('events', []):
                event_data = {
                    'arn': event.get('arn', ''),
                    'service': event.get('service', 'Unknown'),
                    'eventTypeCode': event.get('eventTypeCode', ''),
                    'eventTypeCategory': event.get('eventTypeCategory', ''),
                    'region': event.get('region', 'global'),
                    'startTime': event.get('startTime', '').isoformat() if event.get('startTime') else None,
                    'endTime': event.get('endTime', '').isoformat() if event.get('endTime') else None,
                    'statusCode': event.get('statusCode', ''),
                }
                
                category = event.get('eventTypeCategory', '')
                if category == 'issue':
                    open_events.append(event_data)
                elif category == 'scheduledChange':
                    scheduled_changes.append(event_data)
                else:
                    other_notifications.append(event_data)
                    
        except ClientError as e:
            if 'SubscriptionRequiredException' in str(e):
                logger.info('AWS Health API requires Business/Enterprise Support')
            else:
                logger.warning(f'Health API error: {e}')
        
        return {
            'openIssues': len(open_events),
            'scheduledChanges': len(scheduled_changes),
            'otherNotifications': len(other_notifications),
            'events': open_events[:5],  # Return top 5 events
            'scheduledEvents': scheduled_changes[:5],
            'notifications': other_notifications[:5],
            'lastChecked': now.isoformat() + 'Z',
            'status': 'healthy' if len(open_events) == 0 else 'issues'
        }
        
    except Exception as e:
        logger.error(f'Failed to fetch health status: {e}')
        return {
            'openIssues': 0,
            'scheduledChanges': 0,
            'otherNotifications': 0,
            'events': [],
            'scheduledEvents': [],
            'notifications': [],
            'lastChecked': datetime.utcnow().isoformat() + 'Z',
            'status': 'unknown',
            'error': str(e)
        }


def get_trusted_advisor_checks(request_id: str) -> Dict[str, Any]:
    """Fetch Trusted Advisor check results."""
    try:
        checks_summary = {
            'actionRecommended': 0,
            'investigationRecommended': 0,
            'noProblemsDetected': 0,
            'notAvailable': 0,
            'checks': [],
            'categories': {
                'cost_optimizing': {'ok': 0, 'warning': 0, 'error': 0},
                'security': {'ok': 0, 'warning': 0, 'error': 0},
                'fault_tolerance': {'ok': 0, 'warning': 0, 'error': 0},
                'performance': {'ok': 0, 'warning': 0, 'error': 0},
                'service_limits': {'ok': 0, 'warning': 0, 'error': 0},
            }
        }
        
        try:
            # Get all Trusted Advisor checks
            checks_response = support_client.describe_trusted_advisor_checks(language='en')
            checks = checks_response.get('checks', [])
            
            # Get check summaries
            check_ids = [c['id'] for c in checks[:50]]  # Limit to 50 checks
            
            if check_ids:
                summaries_response = support_client.describe_trusted_advisor_check_summaries(
                    checkIds=check_ids
                )
                
                for summary in summaries_response.get('summaries', []):
                    check_id = summary.get('checkId', '')
                    status = summary.get('status', 'not_available')
                    
                    # Find check details
                    check_info = next((c for c in checks if c['id'] == check_id), {})
                    category = check_info.get('category', 'other')
                    
                    # Count by status
                    if status == 'error':
                        checks_summary['actionRecommended'] += 1
                        if category in checks_summary['categories']:
                            checks_summary['categories'][category]['error'] += 1
                    elif status == 'warning':
                        checks_summary['investigationRecommended'] += 1
                        if category in checks_summary['categories']:
                            checks_summary['categories'][category]['warning'] += 1
                    elif status == 'ok':
                        checks_summary['noProblemsDetected'] += 1
                        if category in checks_summary['categories']:
                            checks_summary['categories'][category]['ok'] += 1
                    else:
                        checks_summary['notAvailable'] += 1
                    
                    # Add to checks list if has issues (exclude S3 versioning check)
                    if status in ['error', 'warning']:
                        # Skip S3 Bucket Versioning check (R365s2Qddf) - not needed
                        if check_id == 'R365s2Qddf':
                            checks_summary['investigationRecommended'] -= 1
                            checks_summary['noProblemsDetected'] += 1
                            continue
                        
                        resources_flagged = summary.get('resourcesSummary', {}).get('resourcesFlagged', 0)
                        checks_summary['checks'].append({
                            'id': check_id,
                            'name': check_info.get('name', 'Unknown'),
                            'category': category,
                            'status': status,
                            'resourcesFlagged': resources_flagged,
                            'description': check_info.get('description', '')[:200],
                        })
            
            # Sort checks by severity (errors first)
            checks_summary['checks'].sort(key=lambda x: (0 if x['status'] == 'error' else 1, -x.get('resourcesFlagged', 0)))
            checks_summary['checks'] = checks_summary['checks'][:10]  # Top 10 issues
            
        except ClientError as e:
            if 'SubscriptionRequiredException' in str(e):
                logger.info('Trusted Advisor requires Business/Enterprise Support for full access')
                # Return basic checks available to all accounts
                checks_summary['error'] = 'Business Support required for full Trusted Advisor access'
            else:
                logger.warning(f'Trusted Advisor API error: {e}')
                checks_summary['error'] = str(e)
        
        checks_summary['lastChecked'] = datetime.utcnow().isoformat() + 'Z'
        return checks_summary
        
    except Exception as e:
        logger.error(f'Failed to fetch Trusted Advisor: {e}')
        return {
            'actionRecommended': 0,
            'investigationRecommended': 0,
            'noProblemsDetected': 0,
            'notAvailable': 0,
            'checks': [],
            'categories': {},
            'lastChecked': datetime.utcnow().isoformat() + 'Z',
            'error': str(e)
        }
