#!/bin/bash
# infra/cli-scripts/create-dynamodb-tables.sh
set -euo pipefail

REGION="us-east-1"
PREFIX="base-wecare-digital"

# MessagesTable (Inbound) — PK: id, GSI: whatsappMessageId-index
aws dynamodb create-table \
  --table-name "${PREFIX}-WhatsAppInboundTable" \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=whatsappMessageId,AttributeType=S \
    AttributeName=contactId,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"whatsappMessageId-index","KeySchema":[{"AttributeName":"whatsappMessageId","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}},
      {"IndexName":"contactId-timestamp-index","KeySchema":[{"AttributeName":"contactId","KeyType":"HASH"},{"AttributeName":"timestamp","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

# MessagesTable (Outbound) — PK: id
aws dynamodb create-table \
  --table-name "${PREFIX}-WhatsAppOutboundTable" \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=contactId,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"contactId-timestamp-index","KeySchema":[{"AttributeName":"contactId","KeyType":"HASH"},{"AttributeName":"timestamp","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

# ContactsTable — PK: id, GSI: phone-index
aws dynamodb create-table \
  --table-name "${PREFIX}-ContactsTable" \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=phone,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"phone-index","KeySchema":[{"AttributeName":"phone","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

# IdempotencyTable — PK: eventId, TTL on expiresAt
aws dynamodb create-table \
  --table-name "${PREFIX}-IdempotencyTable" \
  --attribute-definitions \
    AttributeName=eventId,AttributeType=S \
  --key-schema AttributeName=eventId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

aws dynamodb update-time-to-live \
  --table-name "${PREFIX}-IdempotencyTable" \
  --time-to-live-specification "Enabled=true,AttributeName=expiresAt" \
  --region "${REGION}" 2>/dev/null || echo "TTL already enabled"

# Enable TTL on message tables (expiresAt attribute)
aws dynamodb update-time-to-live \
  --table-name "${PREFIX}-WhatsAppInboundTable" \
  --time-to-live-specification "Enabled=true,AttributeName=expiresAt" \
  --region "${REGION}" 2>/dev/null || echo "TTL already enabled"

aws dynamodb update-time-to-live \
  --table-name "${PREFIX}-WhatsAppOutboundTable" \
  --time-to-live-specification "Enabled=true,AttributeName=expiresAt" \
  --region "${REGION}" 2>/dev/null || echo "TTL already enabled"

# MediaFilesTable — PK: fileId
aws dynamodb create-table \
  --table-name "${PREFIX}-MediaFilesTable" \
  --attribute-definitions \
    AttributeName=fileId,AttributeType=S \
  --key-schema AttributeName=fileId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

# SystemConfigTable — PK: configKey
aws dynamodb create-table \
  --table-name "${PREFIX}-SystemConfigTable" \
  --attribute-definitions \
    AttributeName=configKey,AttributeType=S \
  --key-schema AttributeName=configKey,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

echo "All DynamoDB tables created"
