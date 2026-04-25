/**
 * API Route: /api/seo-tools/blog-posts
 * Fetches all blog posts from Wix Blog API (not RSS).
 * Returns structured data for the SEO dashboard.
 */
import type { NextApiRequest, NextApiResponse } from 'next';

const WIX_API = 'https://www.wixapis.com';
const WIX_API_KEY = process.env.WIX_API_KEY || '';
const WIX_SITE_ID = process.env.WIX_SITE_ID || '';
const BASE = 'https://www.wecare.digital';

async function wixFetch(path: string) {
  const res = await fetch(`${WIX_API}${path}`, {
    headers: {
      Authorization: WIX_API_KEY,
      'wix-site-id': WIX_SITE_ID,
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) throw new Error(`Wix API ${res.status}: ${await res.text()}`);
  return res.json();
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET only' });

  try {
    const posts: any[] = [];
    let offset = 0;
    const limit = 100;

    // Paginate through all posts
    while (true) {
      const data = await wixFetch(
        `/v3/posts?paging.limit=${limit}&paging.offset=${offset}&fieldsToInclude=SEO&fieldsToInclude=CONTENT_TEXT`
      );
      if (!data.posts?.length) break;

      for (const p of data.posts) {
        const seoTags = p.seoData?.tags || [];
        const titleTag = seoTags.find((t: any) => t.type === 'title');
        const descTag = seoTags.find((t: any) => t.type === 'meta' && t.props?.name === 'description');
        const jsonLdTags = seoTags.filter((t: any) => t.type === 'script' && t.props?.type === 'application/ld+json');
        const keywords = p.seoData?.settings?.keywords || [];

        posts.push({
          id: p.id,
          title: p.title || '',
          slug: p.slug || '',
          excerpt: p.excerpt || '',
          contentText: p.contentText?.substring(0, 3000) || '',
          url: `${BASE}/post/${p.slug}`,
          coverImage: p.media?.coverImage?.image?.url || p.coverImage || '',
          publishedDate: p.firstPublishedDate || p.publishedDate || '',
          modifiedDate: p.lastPublishedDate || '',
          seoTitle: titleTag?.children || '',
          metaDescription: descTag?.props?.content || '',
          focusKeyword: keywords[0]?.term || '',
          keywords: keywords.map((k: any) => k.term),
          jsonLdCount: jsonLdTags.length,
          hasCustomSeo: seoTags.length > 0,
          tagCount: seoTags.length,
        });
      }

      if (data.posts.length < limit) break;
      offset += limit;
    }

    res.status(200).json({ ok: true, posts, total: posts.length });
  } catch (e: any) {
    res.status(500).json({ ok: false, error: e.message });
  }
}
