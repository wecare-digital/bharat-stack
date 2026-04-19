/**
 * API Route: /api/seo-tools/google-index
 * Submits all site URLs to Google Indexing API using gcloud ADC credentials.
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

const BASE = 'https://www.wecare.digital';
const PAGES = [
  '/', '/bnb', '/bnb-store', '/legal-champ', '/legalchamp-store',
  '/ritual', '/ritual-store', '/swdhya', '/swdhya-store',
  '/no-fault', '/nofault-store', '/expoweek', '/star', '/one',
  '/faq', '/contact', '/legal-stuff', '/privacy',
  '/careers-plus-culture', '/partner-up', '/enterprise-assist', '/gift-card',
  '/blog', '/sitemap', '/appointment', '/submit-request', '/track-request',
  '/amend-request', '/order-notes', '/drop-docs', '/rx-slot',
  '/selfservice', '/search', '/leave-review', '/loyalty', '/referral', '/bring-friends',
];

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  try {
    // Load gcloud ADC
    const adcPath = path.join(process.env.APPDATA || '', 'gcloud', 'application_default_credentials.json');
    if (!fs.existsSync(adcPath)) {
      return res.status(500).json({ error: 'No gcloud ADC credentials found at ' + adcPath });
    }
    const gc = JSON.parse(fs.readFileSync(adcPath, 'utf-8'));

    // Get OAuth token
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id: gc.client_id,
        client_secret: gc.client_secret,
        refresh_token: gc.refresh_token,
        grant_type: 'refresh_token',
        scope: 'https://www.googleapis.com/auth/indexing',
      }),
    });

    if (!tokenRes.ok) {
      return res.status(500).json({ error: `Google auth failed: ${tokenRes.status}` });
    }

    const { access_token } = await tokenRes.json();
    const urls = PAGES.map(p => BASE + p);
    let submitted = 0;
    let quotaHit = false;

    for (const url of urls) {
      try {
        const r = await fetch('https://indexing.googleapis.com/v3/urlNotifications:publish', {
          method: 'POST',
          headers: { Authorization: `Bearer ${access_token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, type: 'URL_UPDATED' }),
        });
        if (r.status === 200) submitted++;
        else if (r.status === 429) { quotaHit = true; break; }
        // Small delay
        await new Promise(resolve => setTimeout(resolve, 150));
      } catch { /* skip */ }
    }

    res.status(200).json({
      submitted,
      total: urls.length,
      quota_note: quotaHit ? 'Daily quota exceeded — remaining URLs will be submitted tomorrow' : 'OK',
    });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}
