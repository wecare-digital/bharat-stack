/**
 * API Route: /api/seo-tools/site-pages
 * Returns all 37 public site pages with their current SEO data.
 * Source: seo-pages-data.js definitions + live /_functions/seohead endpoint.
 */
import type { NextApiRequest, NextApiResponse } from 'next';

const BASE = 'https://www.wecare.digital';

// All 37 public pages from seo-pages-data.js
const SITE_PAGES = [
  { path: '/', name: 'Homepage', type: 'landing' },
  { path: '/bnb', name: 'BNB Club', type: 'brand_hub' },
  { path: '/bnb-store', name: 'BNB Club Store', type: 'store' },
  { path: '/legal-champ', name: 'Legal Champ', type: 'brand_hub' },
  { path: '/legalchamp-store', name: 'Legal Champ Store', type: 'store' },
  { path: '/ritual', name: 'Ritual Guru', type: 'brand_hub' },
  { path: '/ritual-store', name: 'Ritual Guru Store', type: 'store' },
  { path: '/swdhya', name: 'Swdhya', type: 'brand_hub' },
  { path: '/swdhya-store', name: 'Swdhya Store', type: 'store' },
  { path: '/no-fault', name: 'No Fault', type: 'brand_hub' },
  { path: '/nofault-store', name: 'No Fault Store', type: 'store' },
  { path: '/expoweek', name: 'Expo Week', type: 'brand_hub' },
  { path: '/star', name: 'STAR Member Hub', type: 'utility' },
  { path: '/one', name: 'WECARE.DIGITAL App', type: 'utility' },
  { path: '/faq', name: 'FAQ', type: 'informational' },
  { path: '/contact', name: 'Contact Us', type: 'informational' },
  { path: '/legal-stuff', name: 'Terms & Policies', type: 'legal' },
  { path: '/privacy', name: 'Privacy Policy', type: 'legal' },
  { path: '/careers-plus-culture', name: 'Careers & Culture', type: 'informational' },
  { path: '/partner-up', name: 'Partnership Program', type: 'informational' },
  { path: '/enterprise-assist', name: 'Enterprise Support', type: 'service' },
  { path: '/gift-card', name: 'eGift Card', type: 'service' },
  { path: '/blog', name: 'Blog Index', type: 'blog_hub' },
  { path: '/sitemap', name: 'HTML Sitemap', type: 'utility' },
  { path: '/appointment', name: 'Schedule Appointment', type: 'service' },
  { path: '/submit-request', name: 'Submit Request', type: 'service' },
  { path: '/track-request', name: 'Track Request', type: 'service' },
  { path: '/amend-request', name: 'Amend Request', type: 'service' },
  { path: '/order-notes', name: 'Order Notes', type: 'service' },
  { path: '/drop-docs', name: 'Document Upload', type: 'service' },
  { path: '/rx-slot', name: 'Prescription Slot', type: 'service' },
  { path: '/selfservice', name: 'Self-Service Portal', type: 'service' },
  { path: '/search', name: 'Search', type: 'utility' },
  { path: '/leave-review', name: 'Leave Review', type: 'service' },
  { path: '/loyalty', name: 'Loyalty Rewards', type: 'service' },
  { path: '/referral', name: 'Referral Program', type: 'service' },
  { path: '/bring-friends', name: 'Refer Friends', type: 'service' },
];

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET only' });
  try {
    // Fetch live SEO data from Wix for each page
    const pages = await Promise.all(SITE_PAGES.map(async (page) => {
      let seoData: any = {};
      try {
        const r = await fetch(`${BASE}/_functions/seohead?path=${encodeURIComponent(page.path)}`, { signal: AbortSignal.timeout(5000) });
        if (r.ok) seoData = await r.json();
      } catch {}
      return {
        ...page,
        url: `${BASE}${page.path}`,
        title: seoData.title || page.name,
        metaDescription: seoData.description || '',
        keywords: seoData.keywords || [],
        jsonLdTypes: (seoData.structuredData || []).map((s: any) => s['@type']).filter(Boolean),
        hasJsonLd: (seoData.structuredData || []).length > 0,
        canonical: seoData.canonical || `${BASE}${page.path}`,
      };
    }));
    res.json({ ok: true, pages, total: pages.length });
  } catch (e: any) {
    res.status(500).json({ ok: false, error: e.message });
  }
}
