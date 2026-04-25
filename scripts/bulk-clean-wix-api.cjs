/**
 * Bulk Clean ALL Pages via Wix REST API
 * 
 * Blog posts (108): Wix Blog API — wipe seoData.tags + keywords, republish
 * Products (5): Wix Stores V3 API — clear seoData
 * Static pages (37): NO API EXISTS — generates Velo page code files instead
 * System pages (14): NO API EXISTS — generates manual dashboard task list
 * 
 * Usage: node scripts/bulk-clean-wix-api.js
 */

const WIX_API = 'https://www.wixapis.com';
const WIX_API_KEY = process.env.WIX_API_KEY;
const WIX_SITE_ID = process.env.WIX_SITE_ID;
const fs = require('fs');
const path = require('path');

if (!WIX_API_KEY || !WIX_SITE_ID) {
  // Load from .env.local
  const envPath = path.join(__dirname, '..', '.env.local');
  if (fs.existsSync(envPath)) {
    const env = fs.readFileSync(envPath, 'utf-8');
    for (const line of env.split('\n')) {
      const [k, ...v] = line.split('=');
      if (k && !k.startsWith('#')) process.env[k.trim()] = v.join('=').trim();
    }
  }
}

const API_KEY = process.env.WIX_API_KEY;
const SITE_ID = process.env.WIX_SITE_ID;
const headers = { Authorization: API_KEY, 'wix-site-id': SITE_ID, 'Content-Type': 'application/json' };

async function wixApi(method, path, body) {
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(WIX_API + path, opts);
  const text = await r.text();
  try { return { ok: r.ok, status: r.status, data: JSON.parse(text) }; }
  catch { return { ok: r.ok, status: r.status, data: text }; }
}

// ═══════════════════════════════════════════
// STEP 1: CLEAN ALL BLOG POSTS (Wix Blog API)
// ═══════════════════════════════════════════
async function cleanAllBlogPosts() {
  console.log('\n=== STEP 1: CLEAN ALL BLOG POSTS (Wix Blog API) ===');
  
  let allPosts = [];
  let offset = 0;
  while (true) {
    const r = await wixApi('GET', `/v3/posts?paging.limit=100&paging.offset=${offset}&fieldsToInclude=SEO`);
    if (!r.ok || !r.data?.posts?.length) break;
    allPosts.push(...r.data.posts);
    if (r.data.posts.length < 100) break;
    offset += 100;
  }
  console.log(`Found ${allPosts.length} blog posts`);

  let ok = 0, fail = 0;
  for (const post of allPosts) {
    const id = post.id;
    const slug = post.slug;
    const currentTags = post.seoData?.tags?.length || 0;
    const currentKw = post.seoData?.settings?.keywords?.length || 0;

    if (currentTags === 0 && currentKw === 0) {
      console.log(`  ⏭️  ${slug} — already clean`);
      ok++;
      continue;
    }

    // Revert to draft + wipe seoData
    const r1 = await wixApi('PATCH', `/blog/v3/draft-posts/${id}`, {
      draftPost: { seoData: { tags: [], settings: { keywords: [] } } },
      action: 'UPDATE_REVERT_TO_DRAFT',
    });
    if (!r1.ok) { console.log(`  ❌ ${slug} — revert failed: ${r1.status}`); fail++; continue; }

    // Republish
    const r2 = await wixApi('POST', `/blog/v3/draft-posts/${id}/publish`, {});
    if (!r2.ok) { console.log(`  ❌ ${slug} — publish failed: ${r2.status}`); fail++; continue; }

    console.log(`  ✅ ${slug} — cleared ${currentTags} tags, ${currentKw} keywords`);
    ok++;

    // Rate limit: 500ms between posts
    await new Promise(r => setTimeout(r, 500));
  }

  console.log(`\nBlog: ${ok} cleaned, ${fail} failed out of ${allPosts.length}`);
  return { total: allPosts.length, ok, fail };
}

// ═══════════════════════════════════════════
// STEP 2: CLEAN ALL PRODUCTS (Wix Stores V3 API)
// ═══════════════════════════════════════════
async function cleanAllProducts() {
  console.log('\n=== STEP 2: CLEAN ALL PRODUCTS (Wix Stores V3 API) ===');

  // Try V3 first
  let products = [];
  const r = await wixApi('POST', '/stores/v3/products/query', {
    query: { paging: { limit: 100 } },
    fields: ['SEO_DATA'],
  });

  if (r.ok && r.data?.products) {
    products = r.data.products;
    console.log(`Found ${products.length} products (Catalog V3)`);

    let ok = 0, fail = 0;
    for (const p of products) {
      const id = p.id;
      const name = p.name || 'Unknown';

      // Clear seoData
      const r2 = await wixApi('PATCH', `/stores/v3/products/${id}`, {
        product: { seoData: null },
      });

      if (r2.ok) {
        console.log(`  ✅ ${name} — seoData cleared`);
        ok++;
      } else {
        console.log(`  ❌ ${name} — failed: ${r2.status} ${JSON.stringify(r2.data).substring(0, 200)}`);
        fail++;
      }
      await new Promise(r => setTimeout(r, 300));
    }
    console.log(`\nProducts: ${ok} cleaned, ${fail} failed out of ${products.length}`);
    return { total: products.length, ok, fail };
  } else {
    console.log(`V3 query failed (${r.status}). Trying V1...`);
    
    // Fallback to V1
    const r1 = await wixApi('POST', '/stores/v1/products/query', {
      query: { paging: { limit: 100 } },
    });
    if (r1.ok && r1.data?.products) {
      products = r1.data.products;
      console.log(`Found ${products.length} products (Catalog V1)`);
      console.log(`⚠️  V1 does not support seoData field. Products need manual dashboard cleanup.`);
    } else {
      console.log(`Both V3 and V1 failed. Products need manual cleanup.`);
    }
    return { total: products.length, ok: 0, fail: 0, manual: true };
  }
}

// ═══════════════════════════════════════════
// STEP 3: STATIC PAGES — NO API (generate Velo code)
// ═══════════════════════════════════════════
function generateStaticPageVeloCode() {
  console.log('\n=== STEP 3: STATIC PAGES — NO WRITE API EXISTS ===');
  console.log('Wix has NO REST API to clear/set SEO on static pages.');
  console.log('Options: 1) Velo wix-seo-frontend code  2) Manual Wix Dashboard');
  console.log('\nGenerating Velo page code template...\n');

  const STATIC_PAGES = [
    '/', '/bnb', '/bnb-store', '/legal-champ', '/legalchamp-store',
    '/ritual', '/ritual-store', '/swdhya', '/swdhya-store', '/no-fault',
    '/nofault-store', '/expoweek', '/star', '/one', '/faq', '/contact',
    '/legal-stuff', '/privacy', '/careers-plus-culture', '/partner-up',
    '/enterprise-assist', '/gift-card', '/blog', '/sitemap', '/appointment',
    '/submit-request', '/track-request', '/amend-request', '/order-notes',
    '/drop-docs', '/rx-slot', '/selfservice', '/search', '/leave-review',
    '/loyalty', '/referral', '/bring-friends',
  ];

  console.log(`${STATIC_PAGES.length} static pages need Velo code or manual dashboard work.`);
  console.log('These pages CANNOT be cleared via API.\n');

  // Generate a Velo code template
  const veloTemplate = `// Velo SEO code — add to each page's code panel
// This clears any runtime SEO and sets fresh values
import wixSeoFrontend from 'wix-seo-frontend';

$w.onReady(() => {
  // Clear existing SEO (set to empty/defaults)
  wixSeoFrontend.setTitle('');
  wixSeoFrontend.setMetaTags([]);
  wixSeoFrontend.setLinks([]);
  wixSeoFrontend.setStructuredData([]);
});
`;

  const outDir = path.join(__dirname, '..', 'seo', 'velo');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'clear-page-seo.js'), veloTemplate);
  console.log('Saved: seo/velo/clear-page-seo.js');

  return { total: STATIC_PAGES.length, method: 'velo_or_manual_dashboard' };
}

// ═══════════════════════════════════════════
// STEP 4: SYSTEM PAGES — NO API (manual only)
// ═══════════════════════════════════════════
function generateSystemPageTasks() {
  console.log('\n=== STEP 4: SYSTEM PAGES — NO WRITE API EXISTS ===');

  const SYSTEM_PAGES = [
    '/cart-page', '/checkout', '/thank-you', '/login', '/signup',
    '/404', '/members-area', '/account/my-orders', '/account/my-subscriptions',
    '/account/my-rewards', '/account/settings', '/order-confirmation',
    '/payment', '/wishlist',
  ];

  console.log(`${SYSTEM_PAGES.length} system pages — manual Wix Dashboard only.`);
  console.log('Action: Set each to noindex, nofollow in Wix Dashboard → Pages → SEO Panel\n');

  return { total: SYSTEM_PAGES.length, method: 'manual_dashboard_only' };
}

// ═══════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════
async function main() {
  console.log('╔══════════════════════════════════════════════════╗');
  console.log('║  BULK CLEAN ALL PAGES — Wix REST API            ║');
  console.log('║  Blog: Wix Blog API (full control)              ║');
  console.log('║  Products: Wix Stores V3 API (seoData)          ║');
  console.log('║  Static: NO API — Velo code or manual           ║');
  console.log('║  System: NO API — manual dashboard only         ║');
  console.log('╚══════════════════════════════════════════════════╝');

  const blog = await cleanAllBlogPosts();
  const products = await cleanAllProducts();
  const staticPages = generateStaticPageVeloCode();
  const systemPages = generateSystemPageTasks();

  console.log('\n╔══════════════════════════════════════════════════╗');
  console.log('║  CLEAN SUMMARY                                  ║');
  console.log('╠══════════════════════════════════════════════════╣');
  console.log(`║  Blog posts:   ${blog.ok}/${blog.total} cleaned via Wix Blog API`);
  console.log(`║  Products:     ${products.ok}/${products.total} cleaned via Wix Stores V3 API`);
  console.log(`║  Static pages: ${staticPages.total} — NO API (Velo/manual)`);
  console.log(`║  System pages: ${systemPages.total} — NO API (manual only)`);
  console.log(`║  ─────────────────────────────────────────────── ║`);
  console.log(`║  API cleaned:  ${blog.ok + products.ok}/${blog.total + products.total}`);
  console.log(`║  Manual needed: ${staticPages.total + systemPages.total} pages`);
  console.log('╚══════════════════════════════════════════════════╝');
}

main().catch(console.error);
