"""
AWS Billing Lambda Function

Purpose: Fetch real AWS Cost Explorer data for the dashboard
Account: 809904170947
Region: us-east-1

Uses AWS Cost Explorer API to get actual billing data.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
ce_client = boto3.client('ce', region_name='us-east-1')  # Cost Explorer is global but use us-east-1

# Account info
AWS_ACCOUNT_ID = '809904170947'


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle billing data requests."""
    request_id = context.aws_request_id if context else 'local'
    
    logger.info(json.dumps({
        'event': 'billing_handler',
        'requestId': request_id
    }))
    
    try:
        # Parse query parameters for month selection
        query_params = event.get('queryStringParameters') or {}
        month_offset = int(query_params.get('month', '0'))  # 0 = current, -1 = previous
        
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
    
    logger.info(json.dumps({
        'event': 'billing_fetched',
        'totalCost': total_cost,
        'serviceCount': len(services),
        'period': f'{start_date} to {end_date}',
        'requestId': request_id
    }))
    
    return {
        'totalCost': round(total_cost, 2),
        'period': f'{start_date} to {end_date}',
        'services': services,
        'lastUpdated': datetime.utcnow().isoformat() + 'Z',
        'accountId': AWS_ACCOUNT_ID,
        'currency': 'USD'
    }


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
        'AWS End User Messaging': 'messages',
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
        'AWS End User Messaging': 'Pay per message',
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
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
