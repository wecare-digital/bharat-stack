# Wix API Capability Map — WECARE.DIGITAL

## What Can Be Updated Via API vs Manual Dashboard

| Page Type | SEO Title | Meta Desc | JSON-LD | Canonical | OG Tags | Robots | Slug | Method |
|---|---|---|---|---|---|---|---|---|
| Blog Posts (108) | ✅ API | ✅ API | ✅ API | ✅ API | ✅ API | ✅ API | ⚠️ Risky | Wix Blog API `PATCH /blog/v3/draft-posts/{id}` → seoData.tags + publish |
| Blog Categories | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Manual: Wix Dashboard → Blog → Categories → SEO |
| Blog Tags | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Manual: Wix Dashboard → Blog → Tags |
| Products (6) | ⚠️ Limited | ⚠️ Limited | ❌ No API | ❌ | ❌ | ❌ | ✅ API | Wix Stores Catalog V3 for name/desc/slug; JSON-LD via Dashboard SEO Panel |
| Collections | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Manual: Wix Dashboard → Store → Collections → SEO |
| Static Pages (37) | ❌ No API | ❌ No API | ❌ No API | ❌ | ❌ | ❌ | ❌ | Manual: Wix Dashboard → Pages → SEO Panel per page |
| Homepage | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | N/A | Manual: Wix Dashboard → Home → SEO Panel |
| System Pages | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Manual: Wix Dashboard → Pages → SEO Panel (set noindex) |
| Dynamic/Router Pages | ✅ Velo | ✅ Velo | ✅ Velo | ✅ Velo | ✅ Velo | ✅ Velo | ✅ Router | Velo `wix-seo-frontend` API in page code |
| Booking Pages | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Manual: Wix Dashboard → Bookings → SEO |

## Wix Blog API — What seoData.tags Supports

Each tag in `seoData.tags` array:
```json
{ "type": "title|meta|link|script", "props": {...}, "children": "...", "custom": true, "disabled": false }
```

Supported tag types:
- `title` — SEO title
- `meta` with `name: description` — Meta description
- `meta` with `name: robots` — Robots directive
- `meta` with `property: og:*` — Open Graph tags
- `meta` with `name: twitter:*` — Twitter Card tags
- `meta` with `property: article:*` — Article meta tags
- `link` with `rel: canonical` — Canonical URL
- `script` with `type: application/ld+json` — JSON-LD structured data

seoData.settings:
- `keywords` — Array of `{ term: string, isMain: boolean }`
- `preventAutoRedirect` — Boolean

## Wix Stores Catalog V3 — SEO-Relevant Fields

Writable via API:
- `product.name` — Product title (affects SEO title)
- `product.description` — Product description (affects meta desc)
- `product.slug` — URL slug
- `product.media` — Product images
- `product.seoData` — ⚠️ Check V3 support

NOT writable via API (manual dashboard only):
- Custom JSON-LD markup
- OG tags override
- Canonical URL override
- Robots directive

## Wix Velo Frontend SEO API — For Dynamic/Router Pages

Available in page `onReady()`:
```javascript
import wixSeoFrontend from 'wix-seo-frontend';
wixSeoFrontend.setTitle('Page Title');
wixSeoFrontend.setMetaTags([{property: 'og:title', content: '...'}]);
wixSeoFrontend.setLinks([{rel: 'canonical', href: '...'}]);
wixSeoFrontend.setStructuredData([{...jsonLd}]);
```

## What CANNOT Be Done Via Any API

These require manual Wix Dashboard work:
1. Static page SEO titles/descriptions (37 pages)
2. Homepage SEO settings
3. Product page JSON-LD (custom markup)
4. Collection/category page SEO
5. System page noindex settings
6. Blog category/tag SEO
7. Booking page SEO
8. Global site-level SEO defaults
9. robots.txt customization (Wix manages this)
10. Sitemap customization (Wix auto-generates)
