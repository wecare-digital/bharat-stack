/**
 * API Route: /api/seo-tools/seo-clean
 * Cleans all existing seoData from a blog post (wipes tags + keywords).
 * Use before audit to ensure no duplicate JSON-LD or stale meta tags.
 *
 * POST { slug: "stand" }
 */
import type { NextApiRequest, NextApiResponse } from 'next';

const WIX_API = 'https://www.wixapis.com';
const WIX_API_KEY = process.env.WIX_API_KEY || '';
const WIX_SITE_ID = process.env.WIX_SITE_ID || '';

async function wixApi(method: string, path: string, body?: any) {
  const opts: RequestInit = {
    method,
    headers: { Authorization: WIX_API_KEY, 'wix-site-id': WIX_SITE_ID, 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`${WIX_API}${path}`, opts);
  const text = await r.text();
  try { return { ok: r.ok, status: r.status, data: JSON.parse(text) }; }
  catch { return { ok: r.ok, status: r.status, data: text }; }
}

async function findPostBySlug(slug: string) {
  const data = await wixApi('GET', `/v3/posts?paging.limit=100&fieldsToInclude=SEO`);
  if (!data.ok || !data.data?.posts) return null;
  let post = data.data.posts.find((p: any) => p.slug === slug);
  if (!post) {
    const data2 = await wixApi('GET', `/v3/posts?paging.limit=100&paging.offset=100&fieldsToInclude=SEO`);
    post = data2.data?.posts?.find((p: any) => p.slug === slug);
  }
  return post || null;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { slug } = req.body;
  if (!slug) return res.status(400).json({ error: 'slug required' });

  try {
    const post = await findPostBySlug(slug);
    if (!post) return res.status(404).json({ error: `Post not found: ${slug}` });

    const id = post.id;
    const currentTags = post.seoData?.tags?.length || 0;
    const currentKeywords = post.seoData?.settings?.keywords?.length || 0;

    // Wipe all seoData — empty tags and keywords
    const r1 = await wixApi('PATCH', `/blog/v3/draft-posts/${id}`, {
      draftPost: { seoData: { tags: [], settings: { keywords: [] } } },
      action: 'UPDATE_REVERT_TO_DRAFT',
    });
    if (!r1.ok) return res.status(500).json({ error: `Clean failed: ${r1.status}`, detail: r1.data });

    // Re-publish with clean slate
    const r2 = await wixApi('POST', `/blog/v3/draft-posts/${id}/publish`, {});
    if (!r2.ok) return res.status(500).json({ error: `Republish failed: ${r2.status}`, detail: r2.data });

    res.status(200).json({
      ok: true,
      slug,
      postId: id,
      title: post.title,
      cleaned: { tagsRemoved: currentTags, keywordsRemoved: currentKeywords },
    });
  } catch (e: any) {
    res.status(500).json({ ok: false, error: e.message });
  }
}
