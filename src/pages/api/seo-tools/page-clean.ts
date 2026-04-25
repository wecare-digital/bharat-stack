/**
 * API Route: /api/seo-tools/page-clean
 * Cleans/resets SEO audit data for a site page, product page, or system page.
 *
 * For blog posts, "clean" means wiping seoData tags via Wix Blog API.
 * For site pages, "clean" means:
 *   1. Removing all previous audit records for this page from our local DB
 *   2. Fetching fresh SEO data from the live site to confirm current state
 *   3. Returning the current SEO state so the UI can show accurate data
 *
 * This ensures the page starts fresh for a new audit cycle.
 *
 * POST { path: "/faq", name: "FAQ", pageType: "informational" }
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

const BASE = 'https://www.wecare.digital';
const DATA_DIR = path.join(process.cwd(), '.seo-data');

function readJson<T>(file: string, fallback: T): T {
  const fp = path.join(DATA_DIR, file);
  if (!fs.existsSync(fp)) return fallback;
  try { return JSON.parse(fs.readFileSync(fp, 'utf-8')); } catch { return fallback; }
}
function writeJson(file: string, data: any) {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(path.join(DATA_DIR, file), JSON.stringify(data, null, 2));
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { path: pagePath, name, pageType } = req.body;
  if (!pagePath) return res.status(400).json({ error: 'path required' });

  const slug = pagePath.startsWith('/') ? pagePath : `/${pagePath}`;

  try {
    // 1. Remove all previous audits for this page slug
    const audits = readJson<any[]>('audits.json', []);
    const before = audits.length;
    const cleaned = audits.filter((a: any) => a.blogSlug !== slug);
    const removedCount = before - cleaned.length;
    writeJson('audits.json', cleaned);

    // 2. Fetch current live SEO state
    let liveSeo: any = {};
    try {
      const r = await fetch(`${BASE}/_functions/seohead?path=${encodeURIComponent(slug)}`, {
        signal: AbortSignal.timeout(8000),
      });
      if (r.ok) liveSeo = await r.json();
    } catch {}

    const currentState = {
      title: liveSeo.title || '',
      metaDescription: liveSeo.description || '',
      keywords: liveSeo.keywords || [],
      jsonLdTypes: (liveSeo.structuredData || []).map((s: any) => s['@type']).filter(Boolean),
      hasJsonLd: (liveSeo.structuredData || []).length > 0,
      canonical: liveSeo.canonical || '',
    };

    res.status(200).json({
      ok: true,
      slug,
      name: name || slug,
      pageType: pageType || 'site',
      cleaned: {
        auditsRemoved: removedCount,
        message: removedCount > 0
          ? `Removed ${removedCount} previous audit(s) for ${slug}. Page is now clean for fresh audit.`
          : `No previous audits found for ${slug}. Page is already clean.`,
      },
      currentSeo: currentState,
    });
  } catch (e: any) {
    res.status(500).json({ ok: false, error: e.message });
  }
}
