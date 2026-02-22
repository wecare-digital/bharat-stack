/**
 * Site Hygiene — WECARE.DIGITAL
 *
 * Maintenance and cleanup utilities for the Wix site.
 * Handles broken image fallbacks, stale data cleanup,
 * and console logging in production.
 *
 * Import in page code or global-apply.js:
 *   import { fixBrokenImages, cleanConsole } from 'public/site-hygiene.js';
 */

import wixWindow from 'wix-window';

const FALLBACK_IMAGE = 'https://static.wixstatic.com/media/placeholder.png';

/**
 * Replace broken product/collection images with a fallback.
 * Call after repeaters or galleries are populated.
 * @param {string} repeaterSelector - e.g. '#productRepeater'
 * @param {string} imageSelector - e.g. '#productImage'
 */
export function fixBrokenImages(repeaterSelector, imageSelector) {
  try {
    const repeater = $w(repeaterSelector);
    if (!repeater) return;

    repeater.forEachItem(($item) => {
      const img = $item(imageSelector);
      if (img && !img.src) {
        img.src = FALLBACK_IMAGE;
      }
    });
  } catch { /* element may not exist */ }
}

/**
 * Suppress console.log in production (published site).
 * Keeps console.warn and console.error active.
 */
export function cleanConsole() {
  if (wixWindow.rendering.env === 'browser' && wixWindow.viewMode === 'Site') {
    const noop = () => {};
    console.log = noop;
    console.debug = noop;
    console.info = noop;
  }
}

/**
 * Remove expired items from a Wix Data collection.
 * Items with an `expiresAt` field older than now are deleted.
 *
 * @param {string} collectionName
 * @param {string} expiresField - Field name for expiry timestamp (default: 'expiresAt')
 * @returns {{ deleted: number }}
 */
export async function cleanExpiredItems(collectionName, expiresField = 'expiresAt') {
  const wixData = (await import('wix-data')).default;
  const now = new Date();
  let deleted = 0;
  let offset = 0;

  while (true) {
    const result = await wixData.query(collectionName)
      .lt(expiresField, now)
      .limit(100)
      .skip(offset)
      .find({ suppressAuth: true });

    if (result.items.length === 0) break;

    for (const item of result.items) {
      try {
        await wixData.remove(collectionName, item._id, { suppressAuth: true });
        deleted++;
      } catch { /* item may already be deleted */ }
    }

    if (result.items.length < 100) break;
    offset += 100;
  }

  return { deleted };
}

/**
 * Validate that required Wix Data collections exist.
 * Useful for setup verification.
 * @param {string[]} collections - Array of collection names to check
 * @returns {{ valid: string[], missing: string[] }}
 */
export async function validateCollections(collections) {
  const wixData = (await import('wix-data')).default;
  const valid = [];
  const missing = [];

  for (const name of collections) {
    try {
      await wixData.query(name).limit(1).find({ suppressAuth: true });
      valid.push(name);
    } catch {
      missing.push(name);
    }
  }

  return { valid, missing };
}
