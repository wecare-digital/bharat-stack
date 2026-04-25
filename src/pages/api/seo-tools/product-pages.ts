/**
 * API Route: /api/seo-tools/product-pages
 * Returns all product pages with their current SEO data.
 * Source: Wix Stores API via /_functions/products
 */
import type { NextApiRequest, NextApiResponse } from 'next';

const WIX_API = 'https://www.wixapis.com';
const WIX_API_KEY = process.env.WIX_API_KEY || '';
const WIX_SITE_ID = process.env.WIX_SITE_ID || '';
const BASE = 'https://www.wecare.digital';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET only' });
  try {
    // Fetch products from Wix Stores API
    const r = await fetch(`${BASE}/_functions/products`, {
      headers: { 'X-Api-Key': WIX_API_KEY },
    });
    let products: any[] = [];
    if (r.ok) {
      const data = await r.json();
      products = (data.products || data || []).map((p: any) => ({
        id: p._id || p.id,
        name: p.name || p.title || '',
        slug: p.slug || '',
        url: `${BASE}/product-page/${p.slug}`,
        description: (p.description || '').substring(0, 200),
        price: p.price?.formatted?.price || p.priceData?.formatted?.price || '',
        priceAmount: p.price?.amount || p.priceData?.price || 0,
        currency: p.price?.currency || p.priceData?.currency || 'INR',
        inStock: p.stock?.inStock !== false,
        image: p.media?.mainMedia?.image?.url || p.mainMedia?.image?.url || '',
        type: p.productType || 'physical',
      }));
    }
    // Also try fetching JSON-LD for each product
    for (const p of products) {
      try {
        const sr = await fetch(`${BASE}/_functions/schemaproduct?id=${p.slug}`, { signal: AbortSignal.timeout(3000) });
        if (sr.ok) {
          const schema = await sr.json();
          p.hasJsonLd = !!schema;
          p.jsonLdType = schema?.['@type'] || '';
        }
      } catch { p.hasJsonLd = false; }
    }
    res.json({ ok: true, products, total: products.length });
  } catch (e: any) {
    res.status(500).json({ ok: false, error: e.message });
  }
}
