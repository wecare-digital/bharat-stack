/**
 * Shared validation utilities for form inputs.
 */

/** Validate Indian phone number: +91XXXXXXXXXX or 91XXXXXXXXXX or 10 digits */
export function isValidPhone(phone: string): boolean {
  if (!phone) return false;
  const cleaned = phone.replace(/[\s\-()]/g, '');
  // +91 followed by 10 digits
  if (/^\+91\d{10}$/.test(cleaned)) return true;
  // 91 followed by 10 digits
  if (/^91\d{10}$/.test(cleaned)) return true;
  // Just 10 digits
  if (/^\d{10}$/.test(cleaned)) return true;
  // International format with country code
  if (/^\+\d{10,15}$/.test(cleaned)) return true;
  return false;
}

/** Validate email address */
export function isValidEmail(email: string): boolean {
  if (!email) return true; // optional field — empty is OK
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

/** Check if a date string (YYYY-MM-DD) is today or in the future */
export function isNotPastDate(dateStr: string): boolean {
  if (!dateStr) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const input = new Date(dateStr + 'T00:00:00');
  return input >= today;
}

/** Normalize phone to +91XXXXXXXXXX format */
export function normalizePhone(phone: string): string {
  const cleaned = phone.replace(/[\s\-()]/g, '');
  if (cleaned.startsWith('+')) return cleaned;
  if (cleaned.startsWith('91') && cleaned.length === 12) return '+' + cleaned;
  if (cleaned.length === 10) return '+91' + cleaned;
  return cleaned;
}

/** Get today's date as YYYY-MM-DD for min attribute on date inputs */
export function getTodayISO(): string {
  const d = new Date();
  return d.toISOString().split('T')[0];
}

/** Collect validation errors for a form. Returns array of error messages. */
export function validateForm(rules: { condition: boolean; message: string }[]): string[] {
  return rules.filter(r => r.condition).map(r => r.message);
}
