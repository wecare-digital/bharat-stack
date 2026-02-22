/**
 * Pinger — WECARE.DIGITAL
 *
 * Health checks for SEO endpoints and Store API availability.
 * Runs on a schedule via jobs.config to keep the site warm
 * and verify critical endpoints are responding.
 *
 * Checks:
 *   1. Site homepage (SEO)
 *   2. Sitemap.xml
 *   3. Store products page
 *   4. Velo HTTP functions endpoint (/_functions/health)
 *   5. Wix Stores API (product count)
 */

import { fetch } from 'wix-fetch';
import wixData from 'wix-data';

const SITE_URL = 'https://www.wecare.digital';
const PING_LOG_COLLECTION = 'PingLogs';

const ENDPOINTS = [
  { name: 'Homepage', url: `${SITE_URL}/`, type: 'seo' },
  { name: 'Sitemap', url: `${SITE_URL}/sitemap.xml`, type: 'seo' },
  { name: 'Store', url: `${SITE_URL}/store`, type: 'store' },
  { name: 'Velo Health', url: `${SITE_URL}/_functions/health`, type: 'api' },
];

/**
 * Ping all endpoints and log results.
 * Called by jobs.config on schedule.
 */
export async function pingAll() {
  const results = [];

  for (const endpoint of ENDPOINTS) {
    const start = Date.now();
    let status = 'ok';
    let statusCode = 0;
    let latency = 0;

    try {
      const response = await fetch(endpoint.url, { method: 'GET' });
      statusCode = response.status;
      latency = Date.now() - start;
      if (statusCode >= 400) status = 'error';
    } catch (err) {
      status = 'error';
      latency = Date.now() - start;
      statusCode = 0;
    }

    results.push({
      name: endpoint.name,
      url: endpoint.url,
      type: endpoint.type,
      status,
      statusCode,
      latencyMs: latency,
      checkedAt: new Date().toISOString(),
    });
  }

  // Check store product count via Wix Data
  try {
    const count = await wixData.query('Stores/Products')
      .count({ suppressAuth: true });
    results.push({
      name: 'Product Count',
      url: 'wix-data://Stores/Products',
      type: 'store',
      status: count > 0 ? 'ok' : 'warning',
      statusCode: count,
      latencyMs: 0,
      checkedAt: new Date().toISOString(),
    });
  } catch (err) {
    results.push({
      name: 'Product Count',
      url: 'wix-data://Stores/Products',
      type: 'store',
      status: 'error',
      statusCode: 0,
      latencyMs: 0,
      checkedAt: new Date().toISOString(),
    });
  }

  // Log to collection (optional — remove if PingLogs collection doesn't exist)
  try {
    await wixData.insert(PING_LOG_COLLECTION, {
      results: JSON.stringify(results),
      allOk: results.every(r => r.status === 'ok'),
      timestamp: new Date(),
    }, { suppressAuth: true });
  } catch { /* collection may not exist */ }

  return results;
}
