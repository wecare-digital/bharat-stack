/**
 * API Route: /api/seo-tools/page-audit
 * Runs AI SEO audit on a site page, product page, or system page.
 * Unlike ai-seo-audit (blog-only), this fetches SEO data from /_functions/seohead
 * and uses page-specific prompts.
 *
 * POST { path: "/faq", name: "FAQ", pageType: "informational" }
 * POST { path: "partner-up", name: "Partner Up", pageType: "product", price: "₹999", inStock: true }
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import { invokeClaudeOpus, parseAIJson } from '../../../lib/bedrock';
import { PAGE_SEO_SYSTEM_PROMPT, buildPageUserMessage, type PageData } from '../../../lib/seo-page-prompt';
import { saveAudit, saveLog, type BlogSEOAudit, type AILog } from '../../../lib/seo-db';

const BASE = 'https://www.wecare.digital';
const INPUT_COST_PER_M = 5.0;
const OUTPUT_COST_PER_M = 25.0;

async function fetchPageSeo(pagePath: string): Promise<Partial<PageData>> {
  try {
    const r = await fetch(`${BASE}/_functions/seohead?path=${encodeURIComponent(pagePath)}`, {
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) return {};
    const data = await r.json();
    return {
      title: data.title || '',
      metaDescription: data.description || '',
      keywords: data.keywords || [],
      jsonLdTypes: (data.structuredData || []).map((s: any) => s['@type']).filter(Boolean),
      hasJsonLd: (data.structuredData || []).length > 0,
      canonical: data.canonical || '',
    };
  } catch {
    return {};
  }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { path: pagePath, name, pageType, price, inStock, image, description } = req.body;
  if (!pagePath) return res.status(400).json({ error: 'path is required' });

  const startTime = Date.now();
  const slug = pagePath.startsWith('/') ? pagePath : `/${pagePath}`;
  const auditId = `audit_page_${slug.replace(/\//g, '_')}_${Date.now()}`;
  const logId = `log_page_${slug.replace(/\//g, '_')}_${Date.now()}`;

  try {
    // 1. Fetch current SEO data from live site
    const liveSeo = await fetchPageSeo(slug);

    // 2. Build page data
    const pageData: PageData = {
      path: slug,
      name: name || slug.replace(/^\//, '').replace(/-/g, ' '),
      type: pageType || 'site',
      url: `${BASE}${slug}`,
      title: liveSeo.title || name || '',
      metaDescription: liveSeo.metaDescription || '',
      keywords: liveSeo.keywords || [],
      jsonLdTypes: liveSeo.jsonLdTypes || [],
      hasJsonLd: liveSeo.hasJsonLd || false,
      canonical: liveSeo.canonical || `${BASE}${slug}`,
      price,
      inStock,
      image,
      description,
    };

    // 3. Build prompt and call AI
    const userMessage = buildPageUserMessage(pageData);
    const aiResponse = await invokeClaudeOpus(PAGE_SEO_SYSTEM_PROMPT, userMessage);

    // 4. Parse response
    const aiResult = parseAIJson(aiResponse.text);

    // 5. Calculate cost
    const costEstimate =
      (aiResponse.inputTokens / 1_000_000) * INPUT_COST_PER_M +
      (aiResponse.outputTokens / 1_000_000) * OUTPUT_COST_PER_M;

    // 6. Save log
    const log: AILog = {
      id: logId,
      blogPostId: '',
      blogSlug: slug,
      requestPayload: { path: slug, pageType, name },
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

    // 7. Save audit
    const audit: BlogSEOAudit = {
      id: auditId,
      blogPostId: '',
      blogSlug: slug,
      blogTitle: name || slug,
      pageType: (pageType === 'product' ? 'product' : pageType === 'system' ? 'system' : 'page') as any,
      currentSeoTitle: pageData.title,
      suggestedSeoTitle: aiResult.seoTitle || '',
      currentMetaDescription: pageData.metaDescription,
      suggestedMetaDescription: aiResult.metaDescription || '',
      focusKeyword: aiResult.focusKeyword || '',
      secondaryKeywords: aiResult.secondaryKeywords || [],
      suggestedTags: [],
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

    // 8. Return
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
    const errorLog: AILog = {
      id: logId,
      blogPostId: '',
      blogSlug: slug,
      requestPayload: { path: slug, pageType, name },
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
