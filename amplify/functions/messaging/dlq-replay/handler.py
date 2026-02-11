"""
DLQ Replay Lambda Function

Purpose: Replay failed messages from the inbound DLQ back to the inbound handler.
Triggered manually or on schedule via EventBridge.
Reads messages from SQS DLQ and re-publishes to SNS topic for reprocessing.
"""

import os
import json
import logging
import boto3
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

sqs = boto3.client('sqs', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sns = boto3.client('sns', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

DLQ_URL = os.environ.get('DLQ_URL', 'https://sqs.us-east-1.amazonaws.com/775261844268/base-wecare-digital-inbound-dlq')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:775261844268:base-wecare-digital')
MAX_MESSAGES = int(os.environ.get('MAX_MESSAGES', '10'))


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Replay DLQ messages. Reads up to MAX_MESSAGES from DLQ,
    re-publishes the original SNS message to the topic for reprocessing,
    then deletes the DLQ message.
    """
    request_id = context.aws_request_id if context else 'local'
    replayed = 0
    failed = 0
    empty = False

    logger.info(json.dumps({
        'event': 'dlq_replay_start',
        'dlqUrl': DLQ_URL,
        'maxMessages': MAX_MESSAGES,
        'requestId': request_id
    }))

    while replayed + failed < MAX_MESSAGES and not empty:
        batch_size = min(10, MAX_MESSAGES - replayed - failed)
        response = sqs.receive_message(
            QueueUrl=DLQ_URL,
            MaxNumberOfMessages=batch_size,
            WaitTimeSeconds=1,
            MessageAttributeNames=['All']
        )

        messages = response.get('Messages', [])
        if not messages:
            empty = True
            break

        for msg in messages:
            try:
                body = json.loads(msg.get('Body', '{}'))
                original_record = body.get('originalRecord', {})

                # Extract the original SNS message
                sns_message = original_record.get('Sns', {}).get('Message', '')
                if not sns_message:
                    logger.warning(json.dumps({
                        'event': 'dlq_replay_skip_no_sns',
                        'messageId': msg.get('MessageId'),
                        'requestId': request_id
                    }))
                    failed += 1
                    continue

                # Re-publish to SNS topic
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=sns_message,
                    MessageAttributes={
                        'replay': {
                            'DataType': 'String',
                            'StringValue': 'true'
                        }
                    }
                )

                # Delete from DLQ
                sqs.delete_message(
                    QueueUrl=DLQ_URL,
                    ReceiptHandle=msg['ReceiptHandle']
                )

                replayed += 1
                logger.info(json.dumps({
                    'event': 'dlq_message_replayed',
                    'messageId': msg.get('MessageId'),
                    'requestId': request_id
                }))

            except Exception as e:
                failed += 1
                logger.error(json.dumps({
                    'event': 'dlq_replay_error',
                    'messageId': msg.get('MessageId'),
                    'error': str(e),
                    'requestId': request_id
                }))

    logger.info(json.dumps({
        'event': 'dlq_replay_complete',
        'replayed': replayed,
        'failed': failed,
        'requestId': request_id
    }))

    return {
        'statusCode': 200,
        'body': json.dumps({
            'replayed': replayed,
            'failed': failed
        })
    }
