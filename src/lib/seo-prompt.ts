/**
 * AI SEO Prompt Template — Claude Sonnet 4.6 via Bedrock
 * Generates the system prompt and user message for SEO audit.
 *
 * Key capabilities:
 * - Reads blog content and generates SEO-optimized metadata
 * - Builds FAQ schema from blog content (Q&A pairs extracted from text)
 * - Cleans all duplicate JSON-LD — outputs exactly 1 BlogPosting + 1 BreadcrumbList + optional FAQPage
 * - Generates relevant, search-friendly meta description from actual content
 * - Suggests internal links to related blog posts
 */

const BRAND = 'WECARE.DIGITAL';
const BASE = 'https://www.wecare.digital';
const AUTHOR = 'Swdhya Vaksetu';
const AUTHOR_URL = `${BASE}/swdhya`;
const LOGO = 'https://app.wecare.digital/stream/media/m/wecare-digital.png';

export const SEO_SYSTEM_PROMPT = `You are an expert SEO editor and content strategist specializing in Wix websites. You follow Google's E-E-A-T guidelines and Wix SEO best practices.

YOUR PRIMARY MISSION:
Read the blog post content carefully. Understand what the author is saying. Then generate SEO metadata that is RELEVANT to the actual content — not generic filler. Every field you generate must reflect the real substance of the blog post.

CONTENT ANALYSIS RULES:
- Read the full blog content. Identify the core message, key concepts, and unique insights.
- The meta description MUST summarize what the reader will actually learn — not generic marketing language.
- Keywords MUST come from the actual content — real terms the author uses, not invented phrases.
- If the blog discusses a concept (e.g., "standing with another"), the focus keyword should be that concept.
- The SEO title should make a searcher want to click — it should promise what the content delivers.

FAQ SCHEMA GENERATION:
- Read the blog content and extract 2-5 natural question-and-answer pairs from the material.
- These should be questions a reader might search for that this blog post answers.
- Format as valid FAQPage schema (schema.org/FAQPage).
- Each Q&A: question is what someone would type into Google, answer is a concise 1-3 sentence response drawn from the blog content.
- If the blog content is too short or doesn't lend itself to FAQs, set "faqSchema" to null and explain in warnings.
- FAQ answers must be factual summaries of what the blog actually says — never invent content.

DUPLICATE CLEANUP:
- The output must contain EXACTLY these JSON-LD schemas and NO duplicates:
  1. BlogPosting (exactly 1)
  2. BreadcrumbList (exactly 1)
  3. FAQPage (exactly 1, or null if not applicable)
- When this SEO data is applied to Wix, it REPLACES all existing seoData tags completely — a clean slate.
- No leftover Wix-generated schemas, no duplicate BlogPosting, no stale BreadcrumbList.

STRICT FIELD RULES:
- SEO title: ≤60 characters, include primary keyword near the start, end with " | ${BRAND}"
- Meta description: 120-160 characters, action-oriented, keyword-front-loaded, based on ACTUAL blog content
- Focus keyword: 1 primary keyword phrase (2-4 words ideal) — must appear in the blog content
- Secondary keywords: exactly 9 (long-tail + semantic variations from the actual content)
- NO keyword stuffing — natural language only
- JSON-LD must be valid schema.org markup
- All URLs must use ${BASE} as base
- Author is always: ${AUTHOR} (Person type, not Organization)
- Author URL: ${AUTHOR_URL}
- Publisher: ${BRAND} (Organization type)
- Publisher logo: ${LOGO}
- Language: en-IN
- Robots: index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1
- og:locale: en_IN
- twitter:card: summary_large_image
- Canonical URL must match the page URL exactly
- Return ONLY valid JSON — no markdown, no explanation, no commentary
- Include confidence scores (0.0-1.0) for each major field
- Include warnings array for any SEO issues found
- Calculate SEO score before (based on current data) and after (based on your suggestions) out of 100

EXCERPT RULES:
- Generate a compelling 150-200 character excerpt that summarizes the blog post.
- This excerpt should work as a standalone teaser — someone reading it should understand what the post is about and want to read more.
- Use the author's voice and tone — these are philosophical/reflective posts by Swdhya Vaksetu.

SCORING CRITERIA (10 points each, 100 total):
1. Title tag (length, keyword placement, uniqueness, click-worthiness)
2. Meta description (length, CTA, keyword inclusion, content relevance)
3. Focus keyword (relevance to content, search volume potential)
4. JSON-LD (completeness, validity, schema types, FAQ inclusion)
5. Internal links (suggestions count and thematic relevance)
6. Image alt text (descriptive, keyword-relevant)
7. Canonical URL (present, correct)
8. Open Graph tags (complete set, content-matched)
9. Twitter cards (complete set)
10. Robots directive (correct for page type)`;

export interface BlogPostData {
  slug: string;
  title: string;
  excerpt: string;
  content?: string;
  url: string;
  coverImage?: string;
  publishedDate?: string;
  modifiedDate?: string;
  currentSeoTitle?: string;
  currentMetaDescription?: string;
  currentKeywords?: string[];
  hasJsonLd?: boolean;
}

/** Blog slugs for internal link suggestions */
const BLOG_SLUGS_SAMPLE = [
  'stand', 'the-stone-must-fall-as-the-tiger-must-leap', 'vitality',
  'transformation', '__act', 'no-agreement', 'velocity', 'values',
  'trump-card', 'transformative-learning', 'commitment', 'choice',
  'integrity-and-balance', 'responsibility', 'listening', 'being',
  'principles', 'standards', 'sharing', 'breakdown', 'aliveness',
  'competencies', 'complete-completion', 'decision', 'disappear',
  'empty-meaningless', 'force-vs-power', 'i-identity', 'ideals',
  'informative-learning', 'occur-occurring', 'on-the-court',
  'payoff-in-rackets', 'problems-worthy-of-a-life',
  'realm-of-survival-realm-of-enrollment', 'reason-reasonable',
  'shadow-side-of-strong-suits', 'story-1', 'touch-move-or-inspire',
  'throwing-your-hat-over-the-wall', 'the-real-birthday-gift',
  'right-wrong-or-an-honored-place-in-the-dialogue',
  'lenses-we-live-through', 'choice-the-word-that-allows-yes',
  'law-of-universal-gravitation', 'world-of-knowing',
  'being-cause-in-the-matter', 'the-portal-of-admiration-loyalty-the-true-cost',
  're-filing-the-past', 'introduction-to-cells', 'the-paradox-of-popular',
  'at-stake', 'at-choice-vs-at-effect',
];

export function buildUserMessage(post: BlogPostData): string {
  const parts = [
    `BLOG POST TO AUDIT:`,
    `Title: ${post.title}`,
    `Slug: ${post.slug}`,
    `URL: ${post.url}`,
    `Excerpt: ${post.excerpt || '(none)'}`,
  ];

  if (post.content) {
    // Send more content for better FAQ generation — up to 5000 chars
    const truncated = post.content.length > 5000
      ? post.content.substring(0, 5000) + '...'
      : post.content;
    parts.push(`Full Content:\n${truncated}`);
  }

  if (post.coverImage) parts.push(`Cover Image: ${post.coverImage}`);
  if (post.publishedDate) parts.push(`Published: ${post.publishedDate}`);
  if (post.modifiedDate) parts.push(`Modified: ${post.modifiedDate}`);

  parts.push('');
  parts.push('CURRENT SEO STATE (to be COMPLETELY REPLACED — clean slate):');
  parts.push(`Current SEO Title: ${post.currentSeoTitle || '(none)'}`);
  parts.push(`Current Meta Description: ${post.currentMetaDescription || '(none)'}`);
  parts.push(`Current Keywords: ${post.currentKeywords?.join(', ') || '(none)'}`);
  parts.push(`Has JSON-LD: ${post.hasJsonLd ? 'Yes (will be replaced)' : 'No'}`);
  parts.push('NOTE: All existing seoData tags will be WIPED and replaced with your output. No duplicates possible.');

  parts.push('');
  parts.push(`OTHER BLOG POSTS ON SITE (for internal link suggestions — link to thematically related posts only):`);
  parts.push(BLOG_SLUGS_SAMPLE.join(', '));

  parts.push('');
  parts.push(`IMPORTANT: Read the blog content above carefully. Generate ALL fields based on what the content actually says.`);
  parts.push(`Generate 2-5 FAQ Q&A pairs from the content for FAQPage schema. If content is too short for FAQs, set faqSchema to null.`);
  parts.push(`MANDATORY: You MUST include the "metaTags" array with all 18 OG, Twitter, article, and robots meta tags. Do NOT skip this field.`);
  parts.push(`MANDATORY: metaDescription MUST be 120-155 characters. Never exceed 160.`);
  parts.push(`MANDATORY: secondaryKeywords MUST be exactly 9 items, not 10.`);

  parts.push('');
  parts.push(`Return a single JSON object with this EXACT structure:
{
  "seoTitle": "string (≤60 chars, keyword-first, ends with | WECARE.DIGITAL)",
  "seoTitleLength": number,
  "seoTitleConfidence": number,
  "metaDescription": "string (120-160 chars, based on actual blog content)",
  "metaDescriptionLength": number,
  "metaDescriptionConfidence": number,
  "focusKeyword": "string (from the actual content)",
  "focusKeywordConfidence": number,
  "secondaryKeywords": ["exactly 9 strings from content"],
  "slugSuggestion": "string",
  "slugNote": "string",
  "excerpt": "string (150-200 chars, compelling teaser from content)",
  "jsonLd": {
    "blogPosting": {
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      "headline": "string",
      "description": "string",
      "keywords": "comma-separated string",
      "url": "string",
      "image": ["string"],
      "datePublished": "ISO date",
      "dateModified": "ISO date",
      "wordCount": number,
      "author": { "@type": "Person", "name": "Swdhya Vaksetu", "url": "https://www.wecare.digital/swdhya" },
      "publisher": { "@type": "Organization", "name": "WECARE.DIGITAL", "logo": { "@type": "ImageObject", "url": "logo_url" } },
      "mainEntityOfPage": { "@type": "WebPage", "@id": "page_url" },
      "inLanguage": "en-IN",
      "articleSection": "string"
    },
    "breadcrumbList": {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.wecare.digital/" },
        { "@type": "ListItem", "position": 2, "name": "Blog", "item": "https://www.wecare.digital/blog" },
        { "@type": "ListItem", "position": 3, "name": "Post Title", "item": "post_url" }
      ]
    },
    "faqSchema": {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "question from content",
          "acceptedAnswer": { "@type": "Answer", "text": "answer from content" }
        }
      ]
    }
  },
  "metaTags": [
    {"property": "og:title", "content": "same as seoTitle without | WECARE.DIGITAL suffix"},
    {"property": "og:description", "content": "same as metaDescription"},
    {"property": "og:url", "content": "page URL"},
    {"property": "og:type", "content": "article"},
    {"property": "og:site_name", "content": "WECARE.DIGITAL"},
    {"property": "og:locale", "content": "en_IN"},
    {"property": "og:image", "content": "cover image URL or default logo"},
    {"property": "og:image:width", "content": "1200"},
    {"property": "og:image:height", "content": "630"},
    {"property": "og:image:alt", "content": "same as seoTitle"},
    {"property": "article:author", "content": "Swdhya Vaksetu"},
    {"property": "article:published_time", "content": "ISO date"},
    {"property": "article:modified_time", "content": "ISO date"},
    {"name": "twitter:card", "content": "summary_large_image"},
    {"name": "twitter:title", "content": "same as og:title"},
    {"name": "twitter:description", "content": "same as og:description"},
    {"name": "twitter:image", "content": "same as og:image"},
    {"name": "robots", "content": "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"}
  ],
  "internalLinks": [
    {"text": "anchor text", "url": "/post/slug", "reason": "why this post is related"}
  ],
  "imageAltText": [
    {"current": "string", "suggested": "string", "reason": "string"}
  ],
  "categoryTags": ["strings"],
  "hashtags": ["strings"],
  "seoScoreBefore": number,
  "seoScoreAfter": number,
  "scoreBreakdown": {
    "title": {"before": n, "after": n, "max": 10},
    "metaDescription": {"before": n, "after": n, "max": 10},
    "keywords": {"before": n, "after": n, "max": 10},
    "jsonLd": {"before": n, "after": n, "max": 10},
    "internalLinks": {"before": n, "after": n, "max": 10},
    "imageAlt": {"before": n, "after": n, "max": 10},
    "canonical": {"before": n, "after": n, "max": 10},
    "ogTags": {"before": n, "after": n, "max": 10},
    "twitterCards": {"before": n, "after": n, "max": 10},
    "robots": {"before": n, "after": n, "max": 10}
  },
  "warnings": ["strings"],
  "approvalRequired": true,
  "confidence": number
}`);

  return parts.join('\n');
}
