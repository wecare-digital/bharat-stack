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
- **Cognito User Pool**: us-east-1_cSx0RHCIR
- **App Client**: 1j8kbi48m4v2rped3n224rlevb

### S3 Bucket
Single bucket: `app.wecare.digital` (versioning enabled)
- `stack/` - All user/transactional data (factory reset = wipe stack/ only)
  - `whatsapp-media/incoming/` - Inbound media
  - `whatsapp-media/outgoing/` - Outbound media
  - `whatsapp-media/voice/` - TTS audio
  - `whatsapp-media/calling-ai/` - Call transcripts & TTS
  - `whatsapp-media/template-headers/` - Template media
  - `whatsapp-media/downloads/` - Media downloads
  - `invoices/` - Invoice PNGs and PDFs
  - `voice/` - Voice recordings (Airtel OBD)
  - `reports/` - Bulk job reports
  - `store/products/` - Product images
- `stream/` - Static internal assets (NEVER wiped by cleanup)
  - `media/m/` - Logos, branding
  - `media/fonts/` - Invoice PDF fonts
  - `media/ivr/` - IVR audio files


### DynamoDB Tables
- `stack-wecare-digital-ContactsTable`
- `stack-wecare-digital-WhatsAppInboundTable`
- `stack-wecare-digital-WhatsAppOutboundTable`
- `stack-wecare-digital-BulkJobsTable`
- `stack-wecare-digital-VoiceCalls`

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
│   ├── components/    # React components (Header, Footer, Layout, etc.)
│   ├── pages/         # Next.js pages
│   └── styles/        # CSS styles
├── docs/              # Documentation
├── shared/            # Shared config (FAQ, Wix)
└── scripts/           # Deploy & sync scripts
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

- [FAQ System](docs/FAQ-SYSTEM.md)
- [OpenAPI Spec](docs/openapi.yaml)

## Admin Scripts

- `scripts/deploy_all.ps1` - Deploy all Lambda functions
- `scripts/deploy_all.cmd` - Deploy all Lambda functions (CMD)
- `scripts/sync_faq.py` - Sync FAQ config to Python + TypeScript
