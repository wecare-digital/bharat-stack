/**
 * API Route: /api/seo-tools/ai-seo-audit
 * Runs AI SEO audit on a single blog post using Claude Opus 4.6 via Bedrock.
 *
 * POST { slug: "stand" }
 * Returns: full AI SEO audit result
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import { invokeClaudeOpus, parseAIJson } from '../../../lib/bedrock';
import { SEO_SYSTEM_PROMPT, buildUserMessage } from '../../../lib/seo-prompt';
import { saveAudit, saveLog, type BlogSEOAudit, type AILog } from '../../../lib/seo-db';

const WIX_API = 'https://www.wixapis.com';
const WIX_API_KEY = process.env.WIX_API_KEY || '';
const WIX_SITE_ID = process.env.WIX_SITE_ID || '';
const BASE = 'https://www.wecare.digital';

// Cost per 1M tokens — Sonnet 4.6 (primary), falls back to Nova Pro
const INPUT_COST_PER_M = 3.0;
const OUTPUT_COST_PER_M = 15.0;

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

async function fetchPost(slug: string) {
  // Try to find by slug via list endpoint
  const data = await wixFetch(`/v3/posts?paging.limit=100&fieldsToInclude=SEO&fieldsToInclude=CONTENT_TEXT`);
  if (!data.posts) throw new Error('No posts returned from Wix API');
  const post = data.posts.find((p: any) => p.slug === slug);
  if (!post) {
    // Try next page
    const data2 = await wixFetch(`/v3/posts?paging.limit=100&paging.offset=100&fieldsToInclude=SEO&fieldsToInclude=CONTENT_TEXT`);
    const post2 = data2.posts?.find((p: any) => p.slug === slug);
    if (!post2) throw new Error(`Post not found: ${slug}`);
    return post2;
  }
  return post;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { slug } = req.body;
  if (!slug) return res.status(400).json({ error: 'slug is required' });

  const startTime = Date.now();
  const auditId = `audit_${slug}_${Date.now()}`;
  const logId = `log_${slug}_${Date.now()}`;

  try {
    // 1. Fetch post from Wix
    const post = await fetchPost(slug);
    const seoTags = post.seoData?.tags || [];
    const titleTag = seoTags.find((t: any) => t.type === 'title');
    const descTag = seoTags.find((t: any) => t.type === 'meta' && t.props?.name === 'description');
    const keywords = (post.seoData?.settings?.keywords || []).map((k: any) => k.term);
    const jsonLdTags = seoTags.filter((t: any) => t.type === 'script' && t.props?.type === 'application/ld+json');

    // 2. Build prompt
    const postData = {
      slug: post.slug,
      title: post.title,
      excerpt: post.excerpt || '',
      content: post.contentText || '',
      url: `${BASE}/post/${post.slug}`,
      coverImage: post.media?.coverImage?.image?.url || '',
      publishedDate: post.firstPublishedDate || post.publishedDate || '',
      modifiedDate: post.lastPublishedDate || '',
      currentSeoTitle: titleTag?.children || '',
      currentMetaDescription: descTag?.props?.content || '',
      currentKeywords: keywords,
      hasJsonLd: jsonLdTags.length > 0,
    };

    const userMessage = buildUserMessage(postData);

    // 3. Call Claude Opus 4.7
    const aiResponse = await invokeClaudeOpus(SEO_SYSTEM_PROMPT, userMessage);

    // 4. Parse JSON response
    const aiResult = parseAIJson(aiResponse.text);

    // 5. Calculate cost
    const costEstimate =
      (aiResponse.inputTokens / 1_000_000) * INPUT_COST_PER_M +
      (aiResponse.outputTokens / 1_000_000) * OUTPUT_COST_PER_M;

    // 6. Save AI log
    const log: AILog = {
      id: logId,
      blogPostId: post.id,
      blogSlug: slug,
      requestPayload: { systemPrompt: '(see seo-prompt.ts)', userMessage: userMessage.substring(0, 500) + '...' },
      responsePayload: { text: aiResponse.text.substring(0, 500) + '...' },
      inputTokens: aiResponse.inputTokens,
      outputTokens: aiResponse.outputTokens,
      costEstimate: Math.round(costEstimate * 10000) / 10000,
      provider: 'aws-bedrock',
      model: aiResponse.model,
      status: 'success',
      durationMs: Date.now() - startTime,
      createdAt: new Date().toISOString(),
    };
    saveLog(log);

    // 7. Save audit record
    const audit: BlogSEOAudit = {
      id: auditId,
      blogPostId: post.id,
      blogSlug: slug,
      blogTitle: post.title,
      pageType: 'blog',
      currentSeoTitle: postData.currentSeoTitle,
      suggestedSeoTitle: aiResult.seoTitle || '',
      currentMetaDescription: postData.currentMetaDescription,
      suggestedMetaDescription: aiResult.metaDescription || '',
      focusKeyword: aiResult.focusKeyword || '',
      secondaryKeywords: aiResult.secondaryKeywords || [],
      suggestedTags: aiResult.categoryTags || [],
      suggestedJsonLd: aiResult.jsonLd || {},
      internalLinkSuggestions: aiResult.internalLinks || [],
      imageAltSuggestions: aiResult.imageAltText || [],
      seoScoreBefore: aiResult.seoScoreBefore || 0,
      seoScoreAfter: aiResult.seoScoreAfter || 0,
      scoreBreakdown: aiResult.scoreBreakdown || {},
      warnings: aiResult.warnings || [],
      fullAiResponse: aiResult,
      aiProvider: 'aws-bedrock',
      aiModel: aiResponse.model,
      status: 'pending_review',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    saveAudit(audit);

    // 8. Return result
    res.status(200).json({
      ok: true,
      audit,
      log: {
        inputTokens: aiResponse.inputTokens,
        outputTokens: aiResponse.outputTokens,
        costEstimate: log.costEstimate,
        durationMs: log.durationMs,
        model: aiResponse.model,
      },
    });
  } catch (e: any) {
    // Log error
    const errorLog: AILog = {
      id: logId,
      blogPostId: '',
      blogSlug: slug,
      requestPayload: { slug },
      responsePayload: null,
      inputTokens: 0,
      outputTokens: 0,
      costEstimate: 0,
      provider: 'aws-bedrock',
      model: process.env.BEDROCK_MODEL_ID || 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      status: 'error',
      errorMessage: e.message,
      durationMs: Date.now() - startTime,
      createdAt: new Date().toISOString(),
    };
    saveLog(errorLog);

    res.status(500).json({ ok: false, error: e.message });
  }
}
