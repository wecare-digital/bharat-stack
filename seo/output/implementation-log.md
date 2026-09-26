# SEO Implementation Log — WECARE.DIGITAL
## 2026-04-25

### Already Implemented (Code Complete, Deployed)

| # | What | Where | Status |
|---|---|---|---|
| 1 | Blog SEO automation (108 posts) | `http-functions.js` buildSeoTags + `ai-seo-audit.ts` | ✅ Deployed |
| 2 | BlogPosting + BreadcrumbList + FAQPage schemas | `seo-prompt.ts` + `seo-approve.ts` | ✅ Deployed |
| 3 | 20 meta tags per blog post (OG, Twitter, article, canonical, robots) | `http-functions.js` + `seo-approve.ts` | ✅ Deployed |
| 4 | AI SEO audit with Claude Sonnet 4.6 | `bedrock.ts` (global.anthropic.claude-sonnet-4-6) | ✅ Deployed |
| 5 | Page-type-specific schema prompts (9 types) | `seo-page-prompt.ts` | ✅ Deployed |
| 6 | Schema engine with validation | `schema_engine.py` | ✅ Deployed |
| 7 | llms.txt (spec-compliant) | `http-functions.js` get_llmstxt | ✅ Deployed |
| 8 | llms-full.txt (expanded) | `http-functions.js` get_llmsfull | ✅ Deployed |
| 9 | Agent discovery card | `http-functions.js` get_agentcard | ✅ Deployed |
| 10 | Product feed API | `http-functions.js` get_productfeed | ✅ Deployed |
| 11 | Services API | `http-functions.js` get_services | ✅ Deployed |
| 12 | robots.txt with AI bot allowances | `http-functions.js` get_robots | ✅ Deployed |
| 13 | RSS feeds (site, blog, products) | `http-functions.js` | ✅ Deployed |
| 14 | FAQ endpoint with FAQPage schema | `http-functions.js` get_faq | ✅ Deployed |
| 15 | Blog schema endpoint | `http-functions.js` get_schemablog | ✅ Deployed |
| 16 | Product schema endpoint | `http-functions.js` get_schemaproduct | ✅ Deployed |
| 17 | Feed discovery endpoint | `http-functions.js` get_discovery | ✅ Deployed |
| 18 | SEO dashboard (blog + pages + products) | `src/pages/seo/` | ✅ Deployed |
| 19 | Bedrock model chain (Sonnet 4.6 → Opus 4.6 → Nova Pro) | `bedrock.ts` | ✅ Deployed |
| 20 | All Lambdas updated (nova-pro, agent IDs) | `_deploy_all_lambdas.py` | ✅ Deployed |

### Requires Manual Wix Dashboard Work

| # | What | Priority | Est. Time |
|---|---|---|---|
| 1 | Homepage JSON-LD (Organization + WebSite + WebPage) | P0 | 10 min |
| 2 | Homepage SEO title + description | P0 | 5 min |
| 3 | 14 system pages → noindex | P1 | 15 min |
| 4 | 6 brand hub pages → SEO title + description | P1 | 20 min |
| 5 | 11 service pages → SEO title + description | P1 | 30 min |
| 6 | 5 product pages → custom JSON-LD | P1 | 20 min |
| 7 | FAQ page → FAQPage JSON-LD | P1 | 10 min |
| 8 | Contact page → LocalBusiness JSON-LD | P1 | 10 min |
| 9 | Legal pages → noindex | P2 | 5 min |
| 10 | Search page → noindex | P2 | 2 min |
| 11 | Blog posts → add cover images | P2 | 2-3 hours |
| 12 | Thin blog posts → expand content | P2 | Ongoing |

**Total manual dashboard time: ~2-3 hours for P0+P1**

### Not Applicable / Not Needed

- Multilingual SEO: Site is en-IN only, no Wix Multilingual installed
- Booking schema: No Wix Bookings installed
- Event schema: No Wix Events installed
- Portfolio schema: No Wix Portfolio installed
- Video schema: No video content
- Router SEO: No custom routers in use
