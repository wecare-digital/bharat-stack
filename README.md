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
| WECARE.DIGITAL | 2094615664435155 | waba-e47d916f3c7a47e1a34a19653893dd4b |
| Manish Agarwal | 2513394156072604 | waba-dbe343f210204752b74c80a0a59631a6 |

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

- `scripts/deploy_all_lambdas.py` - Deploy all 60 zip-packaged Lambda functions.
  Cross-platform, validates every top-level import against the function's live
  layers, checks the configured handler symbol exists, then publishes a version
  and moves the `live` alias. That last step matters: 53 of 62 functions are
  invoked through their `live` alias, so `update-function-code` alone does not
  reach production. `--dry-run` builds and validates without uploading,
  `--list` prints the function map.
- `scripts/deploy_seo_tools.py` - Deploys `wecare-seo-tools` (different in-zip
  layout; also owns its DynamoDB table and IAM policy).
- `scripts/snapstart_publish.py` - Publish a version + move the `live` alias
  on its own, e.g. after deploying a function by hand.
- `scripts/sync_faq.py` - Sync FAQ config to Python + TypeScript

The PowerShell and CMD deploy scripts were **deleted on 2026-09-20**. They could
not run on this platform at all (`\`-separated paths), they wrote zip entries with
`\` separators, and the deploy-all variant copied `flows\*.py` only, dropping the
`flows/*.json` flow definitions that `wecare-whatsapp-business-api` serves. Keeping
a broken deploy path in the tree is how someone runs it by mistake.
`scripts/deploy_all_lambdas.py` is the only deploy-all entrypoint; its docstring
records what those scripts got wrong. They remain in history if ever needed:

```sh
git log --diff-filter=D --format=%h -1 -- scripts/deploy_all.ps1   # the deleting commit
git show <that-sha>~1:scripts/deploy_all.ps1
```
