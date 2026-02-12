/**
 * Application Constants - WECARE.DIGITAL
 * Centralized configuration for all hardcoded values
 * 
 * These values can be overridden by environment variables:
 * - NEXT_PUBLIC_API_BASE
 * - NEXT_PUBLIC_PAYMENT_PHONE_ID
 * - NEXT_PUBLIC_PAYMENT_PHONE_DISPLAY
 * - NEXT_PUBLIC_PAYMENT_PHONE_NAME
 * - NEXT_PUBLIC_DEFAULT_GSTIN
 */

// AWS Account Configuration
export const AWS_ACCOUNT_ID = process.env.NEXT_PUBLIC_AWS_ACCOUNT_ID || '775261844268';
export const AWS_REGION = process.env.NEXT_PUBLIC_AWS_REGION || 'us-east-1';

// API Configuration
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';

// Payment Phone Configuration (Razorpay-enabled WABA)
export const PAYMENT_CONFIG = {
  phoneNumberId: process.env.NEXT_PUBLIC_PAYMENT_PHONE_ID || 'phone-number-id-5e020cecd221429996f6ae721cc42206',
  phoneDisplay: process.env.NEXT_PUBLIC_PAYMENT_PHONE_DISPLAY || '+91 93309 94400',
  phoneName: process.env.NEXT_PUBLIC_PAYMENT_PHONE_NAME || 'WECARE.DIGITAL',
};

// Default GSTIN for invoices
export const DEFAULT_GSTIN = process.env.NEXT_PUBLIC_DEFAULT_GSTIN || '19AADFW7431N1ZK';

// WhatsApp Phone Numbers
// Payment config names must match EXACTLY what's configured on the WABA in Meta Business Manager
export const WHATSAPP_PHONES = {
  primary: {
    id: 'phone-number-id-5e020cecd221429996f6ae721cc42206',
    display: '+91 93309 94400',
    name: 'WECARE.DIGITAL',
    wabaId: '1912405516040025',
    hasPayment: true,
    paymentConfigName: 'WECARE-DIGITAL',
    paymentProtected: false,
  },
  secondary: {
    id: 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c',
    display: '+91 99033 00044',
    name: 'Manish Agarwal',
    wabaId: '1633959101297902',
    hasPayment: true,
    paymentConfigName: 'ManishAgarwal_Pay',
    paymentProtected: true,
  },
};

// Password required to send payments from protected phone numbers
export const PAYMENT_UNLOCK_PASSWORD = 'WeCare@Pay2026';

// GST Rate Options
export const GST_RATES = [
  { value: 0, label: 'No GST (0%)' },
  { value: 3, label: 'GST 3%' },
  { value: 5, label: 'GST 5%' },
  { value: 12, label: 'GST 12%' },
  { value: 18, label: 'GST 18%' },
  { value: 28, label: 'GST 28%' },
];

// Convenience Fee Configuration
export const CONVENIENCE_FEE = {
  percent: 2.0,
  gstPercent: 18.0,
};

// WhatsApp Payment Configuration Details
// +919330994400 (WABA 1912405516040025): config "WECARE-DIGITAL"
// +919903300044 (WABA 1633959101297902): config "ManishAgarwal_Pay"
// MCC: 4722 (Travel agencies and tour operators) | Purpose Code: 03 (Travel)
export const PAYMENT_DETAILS = {
  razorpayMID: 'acc_HDfub6wOfQybuH',
  upiId: 'wecaredigital83.rzp@icici',
  mcc: '4722',
  purposeCode: '03',
};

// All payment-enabled phones (convenience helper)
export const PAYMENT_PHONES = Object.values(WHATSAPP_PHONES).filter(p => p.hasPayment);

// Message TTL (30 days in seconds)
export const MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60;

// Pagination defaults
export const PAGINATION = {
  defaultPageSize: 20,
  maxPageSize: 100,
};

// Retry configuration for API calls
export const RETRY_CONFIG = {
  maxRetries: 3,
  baseDelayMs: 1000,
  maxDelayMs: 10000,
};
