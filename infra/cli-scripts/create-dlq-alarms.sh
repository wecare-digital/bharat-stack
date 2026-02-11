#!/bin/bash
# infra/cli-scripts/create-dlq-alarms.sh
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="775261844268"
ALARM_TOPIC="arn:aws:sns:${REGION}:${ACCOUNT_ID}:base-wecare-digital"

# Create inbound DLQ
aws sqs create-queue \
  --queue-name "base-wecare-digital-inbound-dlq" \
  --attributes '{
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "604800"
  }' \
  --region "${REGION}" 2>/dev/null || echo "Queue already exists"

# Create outbound DLQ
aws sqs create-queue \
  --queue-name "base-wecare-digital-outbound-dlq" \
  --attributes '{
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "604800"
  }' \
  --region "${REGION}" 2>/dev/null || echo "Queue already exists"

# CloudWatch Alarm: Lambda error rate
aws cloudwatch put-metric-alarm \
  --alarm-name "wecare-lambda-error-rate" \
  --alarm-description "Lambda error rate exceeds 1%" \
  --metric-name "Errors" \
  --namespace "AWS/Lambda" \
  --statistic "Average" \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.01 \
  --comparison-operator "GreaterThanThreshold" \
  --treat-missing-data "notBreaching" \
  --alarm-actions "${ALARM_TOPIC}" \
  --region "${REGION}"

# CloudWatch Alarm: DLQ depth
aws cloudwatch put-metric-alarm \
  --alarm-name "wecare-dlq-depth" \
  --alarm-description "DLQ depth exceeds 10 messages" \
  --metric-name "ApproximateNumberOfMessagesVisible" \
  --namespace "AWS/SQS" \
  --dimensions "Name=QueueName,Value=base-wecare-digital-inbound-dlq" \
  --statistic "Maximum" \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator "GreaterThanThreshold" \
  --treat-missing-data "notBreaching" \
  --alarm-actions "${ALARM_TOPIC}" \
  --region "${REGION}"

echo "DLQ queues and CloudWatch alarms created"
