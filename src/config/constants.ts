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
  phoneNumberId: process.env.NEXT_PUBLIC_PAYMENT_PHONE_ID || 'phone-number-id-waba3-direct-1016149501586345',
  phoneDisplay: process.env.NEXT_PUBLIC_PAYMENT_PHONE_DISPLAY || '+91 93309 94400',
  phoneName: process.env.NEXT_PUBLIC_PAYMENT_PHONE_NAME || 'WECARE.DIGITAL',
};

// Default GSTIN for invoices
export const DEFAULT_GSTIN = process.env.NEXT_PUBLIC_DEFAULT_GSTIN || '19AADFW7431N1ZK';

// WhatsApp Phone Numbers
// Payment config names must match EXACTLY what's configured on the WABA in Meta Business Manager
export const WHATSAPP_PHONES = {
  primary: {
    id: 'phone-number-id-waba3-direct-1016149501586345',
    display: '+91 93309 94400',
    name: 'WECARE.DIGITAL',
    wabaId: '2094615664435155',
    metaPhoneId: '1016149501586345',
    hasPayment: true,
    paymentConfigName: 'WECARE-RAZOR-PAY',
    paymentConfigs: ['WECARE-RAZOR-PAY', 'WECARE-RAZORPAY-UPIVPA', 'WECARE-PAYU', 'Payu-UPIVPA'],
    paymentProtected: false,
    pendingRegistration: true,  // Blocked by Meta rate limit — registration pending
  },
  secondary: {
    id: 'phone-number-id-waba-t-direct-1055232054343117',
    display: '+91 99033 00044',
    name: 'Manish Agarwal',
    wabaId: '2513394156072604',
    metaPhoneId: '1055232054343117',
    hasPayment: true,
    paymentConfigName: 'Razorpay_ManishAgarwal',
    paymentConfigs: ['Razorpay_ManishAgarwal', 'Razorpay_UPI', 'PayU_ManishAgarwal', 'PayU_UPI'],
    paymentProtected: true,
    directApi: true,
  },
};

// Password required to send payments from protected phone numbers
export const PAYMENT_UNLOCK_PASSWORD = process.env.NEXT_PUBLIC_PAYMENT_UNLOCK_PASSWORD || '';

// GST Rate Options
export const GST_RATES = [
  { value: 0, label: '0%' },
  { value: 3, label: '3%' },
  { value: 5, label: '5%' },
  { value: 12, label: '12%' },
  { value: 18, label: '18%' },
  { value: 28, label: '28%' },
];

// Convenience Fee Configuration
export const CONVENIENCE_FEE = {
  percent: 2.0,
  gstPercent: 18.0,
};

// WhatsApp Payment Configuration Details
// Payment gateway IDs are backend-only — not exposed in the browser bundle.
// MCC and purpose code are non-sensitive category codes.
export const PAYMENT_DETAILS = {
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

// WhatsApp Calling Webhook
export const WHATSAPP_CALLING_VERIFY_TOKEN = process.env.NEXT_PUBLIC_WHATSAPP_CALLING_VERIFY_TOKEN || '';
