/**
 * API Route: /api/seo-tools/pagespeed
 * Runs Google PageSpeed Insights on sample pages.
 * Uses public API (no key needed, but rate-limited).
 */
import type { NextApiRequest, NextApiResponse } from 'next';

const BASE = 'https://www.wecare.digital';
const SAMPLE_PAGES = ['/', '/bnb', '/legal-champ', '/faq', '/blog', '/contact'];

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const results: any[] = [];

  for (const pg of SAMPLE_PAGES) {
    const url = BASE + pg;
    try {
      const r = await fetch(
        `https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=${encodeURIComponent(url)}&strategy=mobile&category=performance&category=seo`,
        { signal: AbortSignal.timeout(45000) }
      );

      if (r.status === 429) {
        results.push({ url, perf: '—', seo: '—', note: 'Rate limited (429)' });
        break;
      }

      if (r.ok) {
        const d = await r.json();
        const perf = d.lighthouseResult?.categories?.performance?.score;
        const seo = d.lighthouseResult?.categories?.seo?.score;
        results.push({
          url,
          perf: perf != null ? Math.round(perf * 100) : '—',
          seo: seo != null ? Math.round(seo * 100) : '—',
        });
      } else {
        results.push({ url, perf: '—', seo: '—', note: `HTTP ${r.status}` });
      }

      // Delay between requests
      await new Promise(resolve => setTimeout(resolve, 3000));
    } catch (e: any) {
      results.push({ url, perf: '—', seo: '—', note: e.message });
    }
  }

  res.status(200).json({ results });
}
