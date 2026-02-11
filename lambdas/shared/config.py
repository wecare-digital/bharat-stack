"""
Centralized configuration. All values from environment variables.
No hardcoded secrets. Secrets Manager for tokens.
"""
import os

REGION = os.environ.get('AWS_REGION', 'us-east-1')
ACCOUNT_ID = '775261844268'

# DynamoDB Tables
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
MESSAGES_INBOUND_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
MESSAGES_OUTBOUND_TABLE = os.environ.get('MESSAGES_OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
MEDIA_FILES_TABLE = os.environ.get('MEDIA_FILES_TABLE', 'base-wecare-digital-MediaFilesTable')
IDEMPOTENCY_TABLE = os.environ.get('IDEMPOTENCY_TABLE', 'base-wecare-digital-IdempotencyTable')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'base-wecare-digital-SystemConfigTable')

# S3
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
MEDIA_INBOUND_PREFIX = os.environ.get('MEDIA_INBOUND_PREFIX', 'whatsapp-media/whatsapp-media-incoming/')
MEDIA_OUTBOUND_PREFIX = os.environ.get('MEDIA_OUTBOUND_PREFIX', 'whatsapp-media/whatsapp-media-outgoing/')

# SNS / SQS
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', f'arn:aws:sns:{REGION}:{ACCOUNT_ID}:base-wecare-digital')
INBOUND_DLQ_URL = os.environ.get('INBOUND_DLQ_URL', '')

# WhatsApp Phone Number IDs
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-5e020cecd221429996f6ae721cc42206')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c')

# WABA IDs
WABA_ID_1 = os.environ.get('WABA_ID_1', 'waba-e47d916f3c7a47e1a34a19653893dd4b')
WABA_ID_2 = os.environ.get('WABA_ID_2', 'waba-dbe343f210204752b74c80a0a59631a6')

# Meta API
META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')

# Operational
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
RATE_LIMIT_PER_SECOND = int(os.environ.get('RATE_LIMIT_PER_SECOND', '80'))
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60
IDEMPOTENCY_TTL_SECONDS = 30 * 24 * 60 * 60
MAX_TEXT_LENGTH = 4096
