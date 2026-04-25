/**
 * API Route: /api/seo-tools/blog-create
 * Creates and publishes a new blog post on Wix.
 * Matches existing post styling: Ricos richContent format.
 *
 * POST { title, content, categoryIds?, tagIds?, hashtags? }
 *
 * Wix Blog richContent format (Ricos):
 * - HEADING nodes: { type: "HEADING", headingData: { level: 2 }, nodes: [{ type: "TEXT", textData: { text: "..." } }] }
 * - PARAGRAPH nodes: { type: "PARAGRAPH", nodes: [{ type: "TEXT", textData: { text: "..." } }] }
 * - Lines starting with ## = H2, ### = H3, else = paragraph
 * - Empty lines = paragraph break
 *
 * Existing post style reference:
 * - Author: Swdhya Vaksetu
 * - Language: en-IN
 * - Category: Swdhya Vaksetu (articleSection)
 * - Font: Wix default (Helvetica Neue / system font)
 * - No custom CSS — Wix Blog renders with its own theme
 */
import type { NextApiRequest, NextApiResponse } from 'next';

const WIX_API = 'https://www.wixapis.com';
const WIX_API_KEY = process.env.WIX_API_KEY || '';
const WIX_SITE_ID = process.env.WIX_SITE_ID || '';

async function wixApi(method: string, path: string, body?: any) {
  const opts: RequestInit = { method, headers: { Authorization: WIX_API_KEY, 'wix-site-id': WIX_SITE_ID, 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`${WIX_API}${path}`, opts);
  const text = await r.text();
  try { return { ok: r.ok, status: r.status, data: JSON.parse(text) }; }
  catch { return { ok: r.ok, status: r.status, data: text }; }
}

/** Convert plain text to Wix Ricos richContent nodes */
function textToRichContent(text: string) {
  const lines = text.split('\n');
  const nodes: any[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue; // skip empty lines

    if (trimmed.startsWith('### ')) {
      nodes.push({
        type: 'HEADING',
        headingData: { level: 3 },
        nodes: [{ type: 'TEXT', textData: { text: trimmed.substring(4) } }],
      });
    } else if (trimmed.startsWith('## ')) {
      nodes.push({
        type: 'HEADING',
        headingData: { level: 2 },
        nodes: [{ type: 'TEXT', textData: { text: trimmed.substring(3) } }],
      });
    } else if (trimmed.startsWith('# ')) {
      nodes.push({
        type: 'HEADING',
        headingData: { level: 1 },
        nodes: [{ type: 'TEXT', textData: { text: trimmed.substring(2) } }],
      });
    } else {
      nodes.push({
        type: 'PARAGRAPH',
        nodes: [{ type: 'TEXT', textData: { text: trimmed } }],
      });
    }
  }

  return { nodes };
}

/** Fetch existing categories from Wix Blog */
async function getCategories() {
  const r = await wixApi('GET', '/blog/v3/categories?paging.limit=50');
  if (!r.ok) return [];
  return (r.data?.categories || []).map((c: any) => ({ id: c.id, label: c.label, slug: c.slug }));
}

/** Fetch existing tags from Wix Blog */
async function getTags() {
  const r = await wixApi('GET', '/blog/v3/tags?paging.limit=100');
  if (!r.ok) return [];
  return (r.data?.tags || []).map((t: any) => ({ id: t.id, label: t.label, slug: t.slug }));
}

/** Create a new tag if it doesn't exist */
async function findOrCreateTag(label: string, existingTags: any[]) {
  const existing = existingTags.find(t => t.label.toLowerCase() === label.toLowerCase());
  if (existing) return existing.id;
  const r = await wixApi('POST', '/blog/v3/tags', { tag: { label } });
  return r.data?.tag?.id || null;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // GET = return categories and tags for the form
  if (req.method === 'GET') {
    try {
      const [categories, tags] = await Promise.all([getCategories(), getTags()]);
      return res.json({ ok: true, categories, tags });
    } catch (e: any) {
      return res.status(500).json({ ok: false, error: e.message });
    }
  }

  if (req.method !== 'POST') return res.status(405).json({ error: 'GET or POST only' });

  const { title, content, categoryIds, tagLabels, hashtags } = req.body;
  if (!title || !content) return res.status(400).json({ error: 'title and content required' });

  try {
    // Resolve tag labels to IDs (create if needed)
    let resolvedTagIds: string[] = [];
    if (tagLabels?.length) {
      const existingTags = await getTags();
      for (const label of tagLabels) {
        const tagId = await findOrCreateTag(label.trim(), existingTags);
        if (tagId) resolvedTagIds.push(tagId);
      }
    }

    // Build draft post
    const draftPost: any = {
      title,
      richContent: textToRichContent(content),
      language: 'en',
    };
    if (categoryIds?.length) draftPost.categoryIds = categoryIds;
    if (resolvedTagIds.length) draftPost.tagIds = resolvedTagIds;
    if (hashtags?.length) {
      draftPost.hashtags = hashtags.map((h: string) => ({
        value: h.replace(/^#/, '').trim(),
      }));
    }

    // Create draft
    const r1 = await wixApi('POST', '/blog/v3/draft-posts', { draftPost });
    if (!r1.ok) return res.status(500).json({ error: `Create failed: ${r1.status}`, detail: r1.data });

    const postId = r1.data?.draftPost?.id;
    const slug = r1.data?.draftPost?.slug || '';
    if (!postId) return res.status(500).json({ error: 'No post ID returned', detail: r1.data });

    // Publish
    const r2 = await wixApi('POST', `/blog/v3/draft-posts/${postId}/publish`, {});
    if (!r2.ok) return res.status(500).json({ error: `Publish failed: ${r2.status}`, detail: r2.data });

    res.status(200).json({ ok: true, postId, slug, title });
  } catch (e: any) {
    res.status(500).json({ ok: false, error: e.message });
  }
}
