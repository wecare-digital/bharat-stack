# WECARE.DIGITAL Admin Platform

Multi-channel messaging platform for WhatsApp, SMS, Email, and Voice communications.

## Quick Start

```bash
npm install
npm run dev
```

## AWS Resources

- **Region**: us-east-1
- **Account**: 775261844268
- **Cognito User Pool**: us-east-1_CC9u1fYh6
- **App Client**: 5na5ba2pbpanm36138jdcd9gck

### S3 Bucket
Single bucket: `app.wecare.digital`
- `whatsapp-media/whatsapp-media-incoming/` - Inbound media
- `whatsapp-media/whatsapp-media-outgoing/` - Outbound media
- `stream/` - Reports and exports

### DynamoDB Tables
- `base-wecare-digital-ContactsTable`
- `base-wecare-digital-WhatsAppInboundTable`
- `base-wecare-digital-WhatsAppOutboundTable`
- `base-wecare-digital-BulkJobsTable`
- `base-wecare-digital-VoiceCalls`

### WhatsApp Phone Numbers
| Name | Phone | ID |
|------|-------|-----|
| WECARE.DIGITAL | +91 93309 94400 | phone-number-id-5e020cecd221429996f6ae721cc42206 |
| Manish Agarwal | +91 99033 00044 | phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c |

### WhatsApp Business Accounts (WABA)
| Name | Meta ID | WABA ID |
|------|---------|---------|
| WECARE.DIGITAL | 1912405516040025 | waba-e47d916f3c7a47e1a34a19653893dd4b |
| Manish Agarwal | 1633959101297902 | waba-dbe343f210204752b74c80a0a59631a6 |

## Project Structure

```
├── amplify/           # AWS Amplify backend
│   ├── auth/          # Cognito configuration
│   ├── data/          # DynamoDB schema
│   ├── functions/     # Lambda functions (Python)
│   └── storage/       # S3 configuration
├── src/
│   ├── api/           # API client
│   ├── components/    # React components
│   ├── pages/         # Next.js pages
│   └── styles/        # CSS styles
├── docs/aws/          # AWS Documentation
└── scripts/           # Admin scripts
```

## Lambda Functions

All Lambda functions use Python 3.12 runtime with prefix `wecare-*`:
- `wecare-contacts-*` - Contact CRUD operations
- `wecare-messages-*` - Message read/delete
- `wecare-inbound-whatsapp` - Webhook handler
- `wecare-outbound-whatsapp` - Send messages
- `wecare-bulk-*` - Bulk messaging
- `wecare-ai-*` - AI/Bedrock integration

## Documentation

See `docs/aws/` folder for:
- [AWS Resources](docs/aws/RESOURCES.md)
- [WhatsApp API Reference](docs/aws/WHATSAPP-API-REFERENCE.md)
- [WhatsApp Payments](docs/aws/WHATSAPP-PAYMENTS.md)
- [S3 Bucket Config](docs/aws/S3-BUCKET-CONFIG.md)
- [Bedrock KB Setup](docs/aws/BEDROCK-KB.md)

## Admin Scripts

- `scripts/delete_all_messages.py` - Delete all messages from DynamoDB and S3
