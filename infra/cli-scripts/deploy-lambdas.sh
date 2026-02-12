#!/bin/bash
# infra/cli-scripts/deploy-lambdas.sh
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-775261844268}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/wecare-digital-lambda-role"
RUNTIME="python3.12"
SNS_TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:base-wecare-digital"

# Package inbound handler — zip from lambdas/ root so shared/ imports work
cd lambdas
zip -r /tmp/inbound_handler.zip inbound_handler/handler.py inbound_handler/__init__.py shared/ -x '*.pyc' '*__pycache__*'
cd ..

# Deploy inbound handler
aws lambda create-function \
  --function-name "wecare-inbound-whatsapp" \
  --runtime "${RUNTIME}" \
  --handler "inbound_handler.handler.handler" \
  --role "${ROLE_ARN}" \
  --zip-file "fileb:///tmp/inbound_handler.zip" \
  --timeout 60 \
  --memory-size 512 \
  --environment "Variables={
    LOG_LEVEL=INFO,
    SEND_MODE=LIVE,
    CONTACTS_TABLE=base-wecare-digital-ContactsTable,
    MESSAGES_TABLE=base-wecare-digital-WhatsAppInboundTable,
    MEDIA_FILES_TABLE=base-wecare-digital-MediaFilesTable,
    SYSTEM_CONFIG_TABLE=base-wecare-digital-SystemConfigTable,
    IDEMPOTENCY_TABLE=base-wecare-digital-IdempotencyTable,
    MEDIA_BUCKET=app.wecare.digital,
    MEDIA_INBOUND_PREFIX=whatsapp-media/whatsapp-media-incoming/,
    INBOUND_DLQ_URL=https://sqs.us-east-1.amazonaws.com/${ACCOUNT_ID}/base-wecare-digital-inbound-dlq,
    OUTBOUND_WHATSAPP_FUNCTION=wecare-outbound-whatsapp,
    WHATSAPP_PHONE_NUMBER_ID_1=phone-number-id-5e020cecd221429996f6ae721cc42206,
    WHATSAPP_PHONE_NUMBER_ID_2=phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c
  }" \
  --region "${REGION}" 2>/dev/null || \
aws lambda update-function-code \
  --function-name "wecare-inbound-whatsapp" \
  --zip-file "fileb:///tmp/inbound_handler.zip" \
  --region "${REGION}"

# Subscribe inbound Lambda to SNS topic
aws sns subscribe \
  --topic-arn "${SNS_TOPIC_ARN}" \
  --protocol lambda \
  --notification-endpoint "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:wecare-inbound-whatsapp" \
  --region "${REGION}"

# Grant SNS permission to invoke Lambda
aws lambda add-permission \
  --function-name "wecare-inbound-whatsapp" \
  --statement-id "sns-invoke" \
  --action "lambda:InvokeFunction" \
  --principal "sns.amazonaws.com" \
  --source-arn "${SNS_TOPIC_ARN}" \
  --region "${REGION}" 2>/dev/null || echo "Permission already exists"

# Package outbound handler — zip from lambdas/ root so shared/ imports work
cd lambdas
zip -r /tmp/outbound_sender.zip outbound_sender/handler.py outbound_sender/__init__.py shared/ -x '*.pyc' '*__pycache__*'
cd ..

# Deploy outbound handler
aws lambda create-function \
  --function-name "wecare-outbound-whatsapp" \
  --runtime "${RUNTIME}" \
  --handler "outbound_sender.handler.handler" \
  --role "${ROLE_ARN}" \
  --zip-file "fileb:///tmp/outbound_sender.zip" \
  --timeout 30 \
  --memory-size 256 \
  --environment "Variables={
    LOG_LEVEL=INFO,
    SEND_MODE=LIVE,
    CONTACTS_TABLE=base-wecare-digital-ContactsTable,
    MESSAGES_TABLE=base-wecare-digital-WhatsAppOutboundTable,
    MEDIA_FILES_TABLE=base-wecare-digital-MediaFilesTable,
    RATE_LIMIT_TABLE=base-wecare-digital-RateLimitTable,
    MEDIA_BUCKET=app.wecare.digital,
    MEDIA_OUTBOUND_PREFIX=whatsapp-media/whatsapp-media-outgoing/,
    WHATSAPP_PHONE_NUMBER_ID_1=phone-number-id-5e020cecd221429996f6ae721cc42206,
    WHATSAPP_PHONE_NUMBER_ID_2=phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c
  }" \
  --region "${REGION}" 2>/dev/null || \
aws lambda update-function-code \
  --function-name "wecare-outbound-whatsapp" \
  --zip-file "fileb:///tmp/outbound_sender.zip" \
  --region "${REGION}"

echo "Lambda functions deployed and SNS subscription created"
