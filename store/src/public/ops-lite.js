/**
 * Operations Lite — WECARE.DIGITAL
 *
 * Lightweight utility functions used across Velo page code.
 * Import in page code: import { formatPrice, debounce, ... } from 'public/ops-lite.js';
 */

/**
 * Format a number as INR currency string.
 * @param {number} amount
 * @param {string} currency - ISO currency code (default: INR)
 * @returns {string} e.g. "₹1,299.00"
 */
export function formatPrice(amount, currency = 'INR') {
  const locale = currency === 'INR' ? 'en-IN' : 'en-US';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

/**
 * Debounce a function call.
 * @param {Function} fn
 * @param {number} delay - ms
 * @returns {Function}
 */
export function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Truncate text with ellipsis.
 * @param {string} text
 * @param {number} maxLength
 * @returns {string}
 */
export function truncate(text, maxLength = 100) {
  if (!text || text.length <= maxLength) return text || '';
  return text.slice(0, maxLength).trimEnd() + '…';
}

/**
 * Format a date string to Indian locale.
 * @param {string|Date} date
 * @param {{ time?: boolean }} options
 * @returns {string} e.g. "22 Feb 2026" or "22 Feb 2026, 3:45 PM"
 */
export function formatDate(date, { time = false } = {}) {
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '—';

  const options = { day: 'numeric', month: 'short', year: 'numeric' };
  if (time) {
    options.hour = 'numeric';
    options.minute = '2-digit';
    options.hour12 = true;
  }
  return d.toLocaleDateString('en-IN', options);
}

/**
 * Generate a simple unique ID.
 * @param {string} prefix
 * @returns {string}
 */
export function uid(prefix = '') {
  const rand = Math.random().toString(36).slice(2, 8);
  const ts = Date.now().toString(36);
  return prefix ? `${prefix}-${ts}-${rand}` : `${ts}-${rand}`;
}

/**
 * Parse query string parameters from current URL.
 * @param {string} url - Full URL or query string
 * @returns {Object}
 */
export function parseQuery(url) {
  const params = {};
  const qs = url.includes('?') ? url.split('?')[1] : url;
  if (!qs) return params;

  qs.split('&').forEach((pair) => {
    const [key, val] = pair.split('=');
    if (key) params[decodeURIComponent(key)] = decodeURIComponent(val || '');
  });
  return params;
}

/**
 * Sleep for a given number of milliseconds.
 * @param {number} ms
 * @returns {Promise<void>}
 */
export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
