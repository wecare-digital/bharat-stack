import { defineFunction } from '@aws-amplify/backend';

/**
 * Invoice Engine Lambda
 *
 * DEPLOYMENT NOTE — Pillow Lambda Layer required:
 * This function uses PIL (Pillow) for PNG/PDF rendering.
 * Attach the Pillow layer to the Lambda in AWS Console or via CDK:
 *   ARN: arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p312-Pillow:4
 *   (Klayers community layer for Python 3.12 / us-east-1)
 *
 * Without the layer, image generation falls back to PIL's default bitmap
 * font (no TrueType) and will fail if Pillow is not bundled.
 */
export const invoiceEngine = defineFunction({
  name: 'wecare-invoice-engine',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60, // Pillow image/PDF rendering needs time
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    INVOICES_TABLE: 'base-wecare-digital-InvoicesTable',
    INVOICE_ITEMS_TABLE: 'base-wecare-digital-InvoiceItemsTable',
    INVOICE_SEQ_TABLE: 'base-wecare-digital-InvoiceSequenceTable',
    INVOICE_ASSETS_TABLE: 'base-wecare-digital-InvoiceAssetsTable',
    INVOICE_DELIVERY_TABLE: 'base-wecare-digital-InvoiceDeliveryLogTable',
    PAYMENTS_TABLE: 'base-wecare-digital-PaymentsTable',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    MEDIA_BUCKET: 'app.wecare.digital',
    CDN_DOMAIN: 'app.wecare.digital',
  },
});
