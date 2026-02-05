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

// API Configuration
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';

// Payment Phone Configuration (Razorpay-enabled WABA)
export const PAYMENT_CONFIG = {
  phoneNumberId: process.env.NEXT_PUBLIC_PAYMENT_PHONE_ID || 'phone-number-id-2ff05755631b41f29151c0573b7a4e2a',
  phoneDisplay: process.env.NEXT_PUBLIC_PAYMENT_PHONE_DISPLAY || '+91 93309 94400',
  phoneName: process.env.NEXT_PUBLIC_PAYMENT_PHONE_NAME || 'WECARE.DIGITAL',
};

// Default GSTIN for invoices
export const DEFAULT_GSTIN = process.env.NEXT_PUBLIC_DEFAULT_GSTIN || '19AADFW7431N1ZK';

// WhatsApp Phone Numbers
export const WHATSAPP_PHONES = {
  primary: {
    id: 'phone-number-id-2ff05755631b41f29151c0573b7a4e2a',
    display: '+91 93309 94400',
    name: 'WECARE.DIGITAL',
    hasPayment: true,
  },
  secondary: {
    id: 'phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6',
    display: '+91 99033 00044',
    name: 'Manish Agarwal',
    hasPayment: false,
  },
};

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
