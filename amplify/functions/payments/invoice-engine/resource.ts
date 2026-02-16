import { defineFunction } from '@aws-amplify/backend';

export const invoiceEngine = defineFunction({
  name: 'wecare-invoice-engine',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
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
