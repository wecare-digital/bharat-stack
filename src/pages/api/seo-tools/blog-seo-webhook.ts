/**
 * API Route: /api/seo-tools/blog-seo-webhook
 * 
 * Auto-trigger: When a blog post is published on Wix, this endpoint
 * receives the post data and pushes full SEO (meta tags + JSON-LD)
 * back to the post via the Wix Blog REST API.
 * 
 * Called by: Wix Velo events.js → onBlogPostPublished()
 * 
 * Flow:
 * 1. Wix publishes a blog post
 * 2. Velo event handler calls this endpoint with { postId, slug, title }
 * 3. This endpoint fetches full post data from Wix Blog API
 * 4. Generates seoData (meta tags + BlogPosting + BreadcrumbList JSON-LD)
 * 5. PATCHes the draft post with seoData
 * 6. Re-publishes the post
 */
import type { NextApiRequest, NextApiResponse } from 'next';

const WIX_API = 'https://www.wixapis.com';
const WIX_API_KEY = process.env.WIX_API_KEY || '';
const WIX_SITE_ID = process.env.WIX_SITE_ID || 'c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5';
const WEBHOOK_SECRET = process.env.BLOG_WEBHOOK_SECRET || '';
const BRAND = 'WECARE.DIGITAL';
const BASE = 'https://www.wecare.digital';
const LOGO = 'https://app.wecare.digital/stream/media/m/wecare-digital.png';
const AUTHOR = 'Swdhya Vaksetu';
const AUTHOR_URL = `${BASE}/swdhya`;

// ── Wix API helper ──

const wixHeaders = {
  Authorization: WIX_API_KEY,
  'wix-site-id': WIX_SITE_ID,
  'Content-Type': 'application/json',
};

async function wixApi(method: string, path: string, body?: any) {
  const opts: RequestInit = { method, headers: wixHeaders };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(WIX_API + path, opts);
  const text = await r.text();
  try { return { ok: r.ok, status: r.status, data: JSON.parse(text) }; }
  catch { return { ok: r.ok, status: r.status, data: text }; }
}

// ── SEO builders ──

function metaTag(nameOrProp: string, content: string) {
  const isOg = nameOrProp.startsWith('og:') || nameOrProp.startsWith('article:');
  return {
    type: 'meta',
    props: isOg ? { property: nameOrProp, content } : { name: nameOrProp, content },
    children: '', custom: true, disabled: false,
  };
}

function jsonLdTag(schema: any) {
  return {
    type: 'script',
    props: { type: 'application/ld+json' },
    children: JSON.stringify(schema),
    custom: true, disabled: false,
  };
}

function buildSeoTitle(title: string): string {
  let t = `${title} | ${BRAND}`;
  if (t.length > 60) t = title.length > 57 ? title.substring(0, 57) + '...' : title;
  return t;
}

function buildDescription(excerpt: string, title: string): string {
  if (excerpt && excerpt.length >= 30) {
    return excerpt.length <= 160 ? excerpt : excerpt.substring(0, excerpt.lastIndexOf(' ', 155)) + '...';
  }
  return `${title}. Read more on ${BRAND}.`.substring(0, 160);
}

function generateKeywordsFromTitle(title: string): string[] {
  // Extract meaningful words from title as default keywords
  const stopWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'it', 'its', 'this', 'that', 'these', 'those']);
  const words = title.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/).filter(w => w.length > 2 && !stopWords.has(w));
  const keywords = [title.toLowerCase()];
  // Add individual meaningful words
  words.forEach(w => { if (!keywords.includes(w)) keywords.push(w); });
  // Pad to at least 5
  while (keywords.length < 5) keywords.push(`${BRAND.toLowerCase()} ${keywords[0] || 'blog'}`);
  return keywords.slice(0, 10);
}

function buildBlogPostingSchema(post: any, seoTitle: string, desc: string, keywords: string[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: post.title || seoTitle,
    description: desc,
    keywords: keywords.join(', '),
    image: post.coverImage ? [post.coverImage] : [LOGO],
    datePublished: post.firstPublishedDate || post.publishedDate || new Date().toISOString(),
    dateModified: post.lastPublishedDate || post.publishedDate || new Date().toISOString(),
    url: `${BASE}/post/${post.slug}`,
    author: { '@type': 'Person', name: AUTHOR, url: AUTHOR_URL },
    publisher: { '@type': 'Organization', name: BRAND, logo: { '@type': 'ImageObject', url: LOGO } },
    mainEntityOfPage: { '@type': 'WebPage', '@id': `${BASE}/post/${post.slug}` },
    inLanguage: 'en-IN',
  };
}

function buildBreadcrumbSchema(post: any) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: `${BASE}/` },
      { '@type': 'ListItem', position: 2, name: 'Blog', item: `${BASE}/blog` },
      { '@type': 'ListItem', position: 3, name: post.title, item: `${BASE}/post/${post.slug}` },
    ],
  };
}

function buildFullSeoData(post: any) {
  const title = post.title || 'Untitled';
  const excerpt = (post.excerpt || '').trim();
  const seoTitle = buildSeoTitle(title);
  const desc = buildDescription(excerpt, title);
  const url = `${BASE}/post/${post.slug}`;
  const image = post.coverImage || LOGO;
  const keywords = generateKeywordsFromTitle(title);
  const focusKeyword = keywords[0] || title.toLowerCase();

  const tags = [
    { type: 'title', children: seoTitle, custom: true, disabled: false },
    metaTag('description', desc),
    metaTag('robots', 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1'),
    metaTag('og:title', title),
    metaTag('og:description', desc),
    metaTag('og:url', url),
    metaTag('og:type', 'article'),
    metaTag('og:site_name', BRAND),
    metaTag('og:locale', 'en_IN'),
    metaTag('og:image', image),
    metaTag('og:image:width', '1200'),
    metaTag('og:image:height', '630'),
    metaTag('og:image:alt', `${title} — ${BRAND}`),
    metaTag('article:author', AUTHOR),
    metaTag('twitter:card', 'summary_large_image'),
    metaTag('twitter:title', title),
    metaTag('twitter:description', desc),
    { type: 'link', props: { rel: 'canonical', href: url }, children: '', custom: true, disabled: false },
    jsonLdTag(buildBlogPostingSchema(post, seoTitle, desc, keywords)),
    jsonLdTag(buildBreadcrumbSchema(post)),
  ];

  return {
    seoData: {
      tags,
      settings: {
        preventAutoRedirect: false,
        keywords: [{ term: focusKeyword, isMain: true }],
      },
    },
    meta: { seoTitle, desc, focusKeyword, keywords, tagCount: tags.length },
  };
}

// ── Main handler ──

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Only POST
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  // Auth check
  if (WEBHOOK_SECRET) {
    const secret = req.headers['x-webhook-secret'] || req.body?.secret;
    if (secret !== WEBHOOK_SECRET) return res.status(403).json({ error: 'Unauthorized' });
  }

  // Validate API key
  if (!WIX_API_KEY) return res.status(500).json({ error: 'WIX_API_KEY not configured' });

  const { postId, slug, title, action } = req.body || {};

  // Support manual trigger for all posts
  if (action === 'bulk') {
    return handleBulk(res);
  }

  // Single post — need either postId or slug
  if (!postId && !slug) {
    return res.status(400).json({ error: 'postId or slug required' });
  }

  try {
    const result = await processPost(postId, slug);
    return res.status(200).json(result);
  } catch (e: any) {
    return res.status(500).json({ error: e.message });
  }
}

async function findPost(postId?: string, slug?: string) {
  if (postId) {
    // Try direct fetch
    const r = await wixApi('GET', `/blog/v3/posts/${postId}?fieldsToInclude=SEO`);
    if (r.ok && r.data?.post) return r.data.post;
  }
  // Fallback: search by slug
  const r = await wixApi('GET', '/blog/v3/posts?paging.limit=100&fieldsToInclude=SEO');
  if (!r.ok) throw new Error(`Failed to list posts: ${r.status}`);
  const post = r.data?.posts?.find((p: any) => slug ? p.slug === slug : p.id === postId);
  if (!post) throw new Error(`Post not found: ${slug || postId}`);
  return post;
}

async function processPost(postId?: string, slug?: string) {
  const post = await findPost(postId, slug);
  const id = post.id;
  const { seoData, meta } = buildFullSeoData(post);

  // Check if post already has custom seoData with JSON-LD
  const existingScripts = (post.seoData?.tags || []).filter((t: any) => t.type === 'script');
  if (existingScripts.length >= 2) {
    return {
      ok: true, action: 'skipped', postId: id, slug: post.slug, title: post.title,
      reason: 'Post already has JSON-LD schemas — use update-post-schema.js to override',
      existingSchemas: existingScripts.length,
    };
  }

  // PATCH seoData
  const patch = await wixApi('PATCH', `/blog/v3/draft-posts/${id}`, {
    draftPost: { seoData },
  });
  if (!patch.ok) throw new Error(`PATCH failed (${patch.status}): ${JSON.stringify(patch.data)}`);

  // Publish
  const pub = await wixApi('POST', `/blog/v3/draft-posts/${id}/publish`);

  return {
    ok: true, action: 'pushed', postId: id, slug: post.slug, title: post.title,
    ...meta,
    published: pub.ok,
  };
}

async function handleBulk(res: NextApiResponse) {
  const r = await wixApi('GET', '/blog/v3/posts?paging.limit=100&fieldsToInclude=SEO');
  if (!r.ok) return res.status(500).json({ error: 'Failed to list posts' });

  const posts = r.data?.posts || [];
  const results: any[] = [];
  let pushed = 0, skipped = 0, failed = 0;

  for (const post of posts) {
    try {
      const result = await processPost(post.id, post.slug);
      results.push(result);
      if (result.action === 'pushed') pushed++;
      else skipped++;
    } catch (e: any) {
      failed++;
      results.push({ ok: false, slug: post.slug, error: e.message });
    }
  }

  // Handle pagination if more than 100 posts
  let cursor = r.data?.pagingMetadata?.cursors?.next;
  while (cursor) {
    const next = await wixApi('GET', `/blog/v3/posts?paging.limit=100&paging.cursor=${cursor}&fieldsToInclude=SEO`);
    if (!next.ok || !next.data?.posts?.length) break;
    for (const post of next.data.posts) {
      try {
        const result = await processPost(post.id, post.slug);
        results.push(result);
        if (result.action === 'pushed') pushed++;
        else skipped++;
      } catch (e: any) {
        failed++;
        results.push({ ok: false, slug: post.slug, error: e.message });
      }
    }
    cursor = next.data?.pagingMetadata?.cursors?.next;
  }

  return res.status(200).json({ ok: true, total: results.length, pushed, skipped, failed, results });
}
