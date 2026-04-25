/**
 * API Route: /api/seo-tools/seo-approve
 * Approve/reject an AI SEO audit, and optionally apply to Wix.
 *
 * POST { auditId, action: "approve" | "reject" | "apply", reviewedBy? }
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import { getAudit, updateAuditStatus, type BlogSEOAudit } from '../../../lib/seo-db';

const WIX_API = 'https://www.wixapis.com';
const WIX_API_KEY = process.env.WIX_API_KEY || '';
const WIX_SITE_ID = process.env.WIX_SITE_ID || '';
const BASE = 'https://www.wecare.digital';
const BRAND = 'WECARE.DIGITAL';
const LOGO = 'https://app.wecare.digital/stream/media/m/wecare-digital.png';
const AUTHOR = 'Swdhya Vaksetu';
const AUTHOR_URL = `${BASE}/swdhya`;

async function wixApi(method: string, path: string, body?: any) {
  const opts: RequestInit = {
    method,
    headers: {
      Authorization: WIX_API_KEY,
      'wix-site-id': WIX_SITE_ID,
      'Content-Type': 'application/json',
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`${WIX_API}${path}`, opts);
  const text = await r.text();
  try { return { ok: r.ok, status: r.status, data: JSON.parse(text) }; }
  catch { return { ok: r.ok, status: r.status, data: text }; }
}

function buildWixSeoTags(audit: BlogSEOAudit): any {
  const ai = audit.fullAiResponse;
  const url = `${BASE}/post/${audit.blogSlug}`;
  const img = ai.jsonLd?.blogPosting?.image?.[0] || LOGO;

  const tags: any[] = [
    { type: 'title', children: ai.seoTitle, custom: true, disabled: false },
    { type: 'meta', props: { name: 'description', content: ai.metaDescription }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { name: 'robots', content: 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:title', content: ai.seoTitle.replace(` | ${BRAND}`, '') }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:description', content: ai.metaDescription }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:url', content: url }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:type', content: 'article' }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:site_name', content: BRAND }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:locale', content: 'en_IN' }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:image', content: img }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:image:width', content: '1200' }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:image:height', content: '630' }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:image:alt', content: ai.seoTitle }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'article:author', content: AUTHOR }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { name: 'twitter:card', content: 'summary_large_image' }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { name: 'twitter:title', content: ai.seoTitle.replace(` | ${BRAND}`, '') }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { name: 'twitter:description', content: ai.metaDescription }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { name: 'twitter:image', content: img }, children: '', custom: true, disabled: false },
    { type: 'link', props: { rel: 'canonical', href: url }, children: '', custom: true, disabled: false },
  ];

  // Add JSON-LD — exactly 1 BlogPosting + 1 BreadcrumbList + optional FAQPage (no duplicates)
  if (ai.jsonLd?.blogPosting) {
    tags.push({ type: 'script', props: { type: 'application/ld+json' }, children: JSON.stringify(ai.jsonLd.blogPosting), custom: true, disabled: false });
  }
  if (ai.jsonLd?.breadcrumbList) {
    tags.push({ type: 'script', props: { type: 'application/ld+json' }, children: JSON.stringify(ai.jsonLd.breadcrumbList), custom: true, disabled: false });
  }
  // FAQ schema — only if AI generated it from blog content
  if (ai.jsonLd?.faqSchema?.mainEntity?.length > 0) {
    tags.push({ type: 'script', props: { type: 'application/ld+json' }, children: JSON.stringify(ai.jsonLd.faqSchema), custom: true, disabled: false });
  }

  const focusKw = ai.focusKeyword || audit.focusKeyword;
  // Wix supports multiple keywords — first one is isMain: true, rest are secondary
  const allKeywords = [
    { term: focusKw, isMain: true },
    ...(ai.secondaryKeywords || audit.secondaryKeywords || []).slice(0, 9).map((kw: string) => ({ term: kw, isMain: false })),
  ];
  const settings = { keywords: allKeywords };

  return { tags, settings };
}

async function applyToWix(audit: BlogSEOAudit): Promise<{ ok: boolean; error?: string }> {
  const seoData = buildWixSeoTags(audit);
  const postId = audit.blogPostId;

  // Step 1: Revert to draft + update seoData
  const r1 = await wixApi('PATCH', `/blog/v3/draft-posts/${postId}`, {
    draftPost: { seoData },
    action: 'UPDATE_REVERT_TO_DRAFT',
  });
  if (!r1.ok) return { ok: false, error: `Revert+update failed: ${r1.status} ${JSON.stringify(r1.data)}` };

  // Step 2: Re-publish
  const r2 = await wixApi('POST', `/blog/v3/draft-posts/${postId}/publish`, {});
  if (!r2.ok) return { ok: false, error: `Republish failed: ${r2.status} ${JSON.stringify(r2.data)}` };

  return { ok: true };
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { auditId, action, reviewedBy } = req.body;
  if (!auditId || !action) return res.status(400).json({ error: 'auditId and action required' });

  const audit = getAudit(auditId);
  if (!audit) return res.status(404).json({ error: 'Audit not found' });

  if (action === 'reject') {
    const updated = updateAuditStatus(auditId, 'rejected', reviewedBy);
    return res.status(200).json({ ok: true, audit: updated });
  }

  if (action === 'approve') {
    const updated = updateAuditStatus(auditId, 'approved', reviewedBy);
    return res.status(200).json({ ok: true, audit: updated });
  }

  if (action === 'apply') {
    // Must be approved first (or approve + apply in one step)
    if (audit.status !== 'approved') {
      updateAuditStatus(auditId, 'approved', reviewedBy);
    }

    const result = await applyToWix(audit);
    if (result.ok) {
      const updated = updateAuditStatus(auditId, 'applied', reviewedBy);
      return res.status(200).json({ ok: true, audit: updated, applied: true });
    } else {
      return res.status(500).json({ ok: false, error: result.error });
    }
  }

  res.status(400).json({ error: `Unknown action: ${action}` });
}
