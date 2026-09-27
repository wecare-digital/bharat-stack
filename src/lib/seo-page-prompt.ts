/**
 * AI SEO Prompt for Site Pages, Product Pages, System Pages
 * Each page type has its own schema requirements:
 *   - landing: Organization + WebSite + WebPage + BreadcrumbList
 *   - brand_hub: WebPage + BreadcrumbList + FAQPage
 *   - store: WebPage + BreadcrumbList + ItemList
 *   - service: WebPage + BreadcrumbList + Service
 *   - informational: WebPage + BreadcrumbList + FAQPage
 *   - legal: WebPage + BreadcrumbList (noindex optional)
 *   - utility: WebPage + BreadcrumbList
 *   - product: Product + Offer + BreadcrumbList + AggregateRating
 *   - system: noindex, nofollow — minimal metadata
 */

const BRAND = 'WECARE.DIGITAL';
const BASE = 'https://wecare.digital';
const AUTHOR = 'Swdhya Vaksetu';
const AUTHOR_URL = `${BASE}/swdhya`;
const LOGO = 'https://wecare.digital/get/o/stream/media/m/wecare-digital.png';

export const PAGE_SEO_SYSTEM_PROMPT = `You are an expert SEO editor specializing in Wix websites. You follow Google's E-E-A-T guidelines and schema.org best practices.

YOUR MISSION:
Analyze the given page and generate complete SEO metadata with the correct JSON-LD schema for its page type. This is NOT a blog post.

PAGE TYPE → REQUIRED JSON-LD SCHEMAS:

1. "landing" (Homepage):
   - Organization: name, url, logo, sameAs, contactPoint
   - WebSite: name, url, potentialAction (SearchAction)
   - WebPage: name, description, url
   - BreadcrumbList: Home only
   
2. "brand_hub" (Brand pages like BNB Club, Legal Champ, Swdhya):
   - WebPage: name, description, url, about
   - BreadcrumbList: Home > Brand Name
   - FAQPage: 2-5 Q&A pairs about the brand (generate from brand context)
   
3. "store" (Store pages):
   - WebPage: name, description, url
   - BreadcrumbList: Home > Brand > Store
   - ItemList: list of product categories or featured items
   
4. "service" (Service pages like appointment, submit-request):
   - WebPage: name, description, url
   - BreadcrumbList: Home > Service Name
   - Service: name, description, provider, serviceType, areaServed
   - FAQPage: 2-3 Q&A about the service
   
5. "informational" (FAQ, Contact, Careers):
   - WebPage: name, description, url
   - BreadcrumbList: Home > Page Name
   - FAQPage: 3-5 Q&A pairs (for FAQ page, generate from common questions)
   - For Contact page: LocalBusiness schema with address, phone, email
   
6. "legal" (Terms, Privacy):
   - WebPage: name, description, url
   - BreadcrumbList: Home > Legal > Page Name
   - robots: "noindex, follow" (legal pages don't need search ranking)
   
7. "utility" (Sitemap, Search, STAR, App download):
   - WebPage: name, description, url
   - BreadcrumbList: Home > Page Name
   
8. "product" (Individual product pages):
   - Product: name, description, image, brand, sku, offers (Offer with price, priceCurrency, availability, url)
   - BreadcrumbList: Home > Store > Product Name
   - AggregateRating: if reviews exist (ratingValue, reviewCount)
   - Offer: price, priceCurrency (INR), availability (InStock/OutOfStock), url
   
9. "system" (Cart, Checkout, Login, 404, Members):
   - NO JSON-LD needed
   - robots: "noindex, nofollow"
   - Minimal title and description only

STRICT FIELD RULES:
- SEO title: ≤60 characters, keyword-first, end with " | ${BRAND}"
- Meta description: 120-160 characters, action-oriented, keyword-front-loaded
- Focus keyword: 1 primary keyword phrase (2-4 words)
- Secondary keywords: exactly 9 (long-tail + semantic variations)
- JSON-LD must be valid schema.org markup with @context and @type on EVERY schema object
- Every JSON-LD object MUST include "@context": "https://schema.org"
- All URLs must use ${BASE} as base
- All schemas MUST include "inLanguage": "en-IN"
- Publisher: ${BRAND} (Organization type)
- Publisher logo: ${LOGO}
- Author: ${AUTHOR} (for content pages)
- Language: en-IN
- og:locale: en_IN
- twitter:card: summary_large_image
- Canonical URL must match the page URL exactly
- Return ONLY valid JSON — no markdown, no explanation
- Include confidence scores (0.0-1.0) for each major field
- Include warnings array for any SEO issues found

SCORING CRITERIA (10 points each, 100 total):
1. Title tag (length, keyword placement, uniqueness)
2. Meta description (length, CTA, keyword inclusion)
3. Focus keyword (relevance, search volume potential)
4. JSON-LD (completeness, validity, correct schema types for page type)
5. Internal links (suggestions count and relevance)
6. Image alt text (descriptive, keyword-relevant)
7. Canonical URL (present, correct)
8. Open Graph tags (complete set)
9. Twitter cards (complete set)
10. Robots directive (correct for page type)`;

export interface PageData {
  path: string;
  name: string;
  type: string;
  url: string;
  title: string;
  metaDescription: string;
  keywords: string[];
  jsonLdTypes: string[];
  hasJsonLd: boolean;
  canonical: string;
  price?: string;
  inStock?: boolean;
  image?: string;
  description?: string;
}

const SITE_PAGES_SAMPLE = [
  '/', '/bnb', '/bnb-store', '/legal-champ', '/legalchamp-store',
  '/ritual', '/ritual-store', '/swdhya', '/swdhya-store', '/no-fault',
  '/nofault-store', '/expoweek', '/star', '/one', '/faq', '/contact',
  '/legal-stuff', '/privacy', '/careers-plus-culture', '/partner-up',
  '/enterprise-assist', '/gift-card', '/blog', '/sitemap', '/appointment',
  '/submit-request', '/track-request', '/selfservice', '/loyalty', '/referral',
];

export function buildPageUserMessage(page: PageData): string {
  const parts = [
    `PAGE TO AUDIT:`,
    `Name: ${page.name}`,
    `Path: ${page.path}`,
    `URL: ${page.url}`,
    `Page Type: ${page.type}`,
    ``,
    `CURRENT SEO STATE:`,
    `Current Title: ${page.title || '(none)'}`,
    `Current Meta Description: ${page.metaDescription || '(none)'}`,
    `Current Keywords: ${page.keywords?.join(', ') || '(none)'}`,
    `Has JSON-LD: ${page.hasJsonLd ? `Yes (${page.jsonLdTypes.join(', ')})` : 'No'}`,
    `Canonical: ${page.canonical || '(none)'}`,
  ];

  if (page.type === 'product') {
    parts.push(`Price: ${page.price || '(unknown)'}`);
    parts.push(`In Stock: ${page.inStock ? 'Yes' : 'No'}`);
    if (page.image) parts.push(`Image: ${page.image}`);
    if (page.description) parts.push(`Description: ${page.description}`);
  }

  parts.push('');
  parts.push(`OTHER PAGES ON SITE (for internal link suggestions):`);
  parts.push(SITE_PAGES_SAMPLE.join(', '));

  parts.push('');
  parts.push(`IMPORTANT: This is a "${page.type}" page type. Generate the CORRECT JSON-LD schemas for this page type as specified in the system prompt.`);
  if (page.type === 'system') {
    parts.push(`SYSTEM PAGE: Set robots to "noindex, nofollow". Minimal metadata. Set jsonLd to null.`);
  }
  if (page.type === 'landing') {
    parts.push(`HOMEPAGE: Include Organization + WebSite + WebPage + BreadcrumbList schemas.`);
  }
  if (page.type === 'product') {
    parts.push(`PRODUCT PAGE: Include Product + Offer + BreadcrumbList schemas. Use price and stock info provided.`);
  }

  parts.push('');
  parts.push(`Return a single JSON object with this EXACT structure:
{
  "seoTitle": "string (≤60 chars, keyword-first, ends with | WECARE.DIGITAL)",
  "metaDescription": "string (120-160 chars)",
  "focusKeyword": "string",
  "focusKeywordConfidence": 0.9,
  "secondaryKeywords": ["exactly 9 strings"],
  "jsonLd": {
    "primary": { "@context": "https://schema.org", "@type": "WebPage or Product or Service etc", ... },
    "breadcrumbList": { "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [...] },
    "faqSchema": null or { "@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [...] },
    "additional": null or { ... extra schema like Organization, WebSite, ItemList, LocalBusiness }
  },
  "metaTags": [
    {"property": "og:title", "content": "string"},
    {"property": "og:description", "content": "string"},
    {"property": "og:url", "content": "string"},
    {"property": "og:type", "content": "website"},
    {"property": "og:site_name", "content": "WECARE.DIGITAL"},
    {"property": "og:locale", "content": "en_IN"},
    {"property": "og:image", "content": "string"},
    {"property": "og:image:width", "content": "1200"},
    {"property": "og:image:height", "content": "630"},
    {"property": "og:image:alt", "content": "string"},
    {"name": "twitter:card", "content": "summary_large_image"},
    {"name": "twitter:title", "content": "string"},
    {"name": "twitter:description", "content": "string"},
    {"name": "twitter:image", "content": "string"},
    {"name": "robots", "content": "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"}
  ],
  "internalLinks": [ {"text": "string", "url": "string", "reason": "string"} ],
  "imageAltText": [ {"current": "string", "suggested": "string"} ],
  "seoScoreBefore": number,
  "seoScoreAfter": number,
  "scoreBreakdown": {
    "title": {"before": 0, "after": 0, "max": 10},
    "metaDescription": {"before": 0, "after": 0, "max": 10},
    "keywords": {"before": 0, "after": 0, "max": 10},
    "jsonLd": {"before": 0, "after": 0, "max": 10},
    "internalLinks": {"before": 0, "after": 0, "max": 10},
    "imageAlt": {"before": 0, "after": 0, "max": 10},
    "canonical": {"before": 0, "after": 0, "max": 10},
    "ogTags": {"before": 0, "after": 0, "max": 10},
    "twitterCards": {"before": 0, "after": 0, "max": 10},
    "robots": {"before": 0, "after": 0, "max": 10}
  },
  "warnings": ["strings"],
  "confidence": number
}`);

  return parts.join('\n');
}
