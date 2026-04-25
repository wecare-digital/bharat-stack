/**
 * Bulk Clean ALL Pages — wipe SEO data across entire site
 * 
 * Blog posts (108): Wix Blog API — wipe seoData.tags + keywords, republish
 * Site pages (37): Clean local audit records only (Wix Dashboard SEO = manual)
 * System pages (14): Clean local audit records only
 * Products (5): Clean local audit records only
 * 
 * Usage: node scripts/bulk-clean-all.js
 */

const BASE = 'http://localhost:3000';

// All site pages
const SITE_PAGES = [
  { path: '/', name: 'Homepage', type: 'landing' },
  { path: '/bnb', name: 'BNB Club', type: 'brand_hub' },
  { path: '/bnb-store', name: 'BNB Store', type: 'store' },
  { path: '/legal-champ', name: 'Legal Champ', type: 'brand_hub' },
  { path: '/legalchamp-store', name: 'Legal Champ Store', type: 'store' },
  { path: '/ritual', name: 'Ritual Guru', type: 'brand_hub' },
  { path: '/ritual-store', name: 'Ritual Store', type: 'store' },
  { path: '/swdhya', name: 'Swdhya', type: 'brand_hub' },
  { path: '/swdhya-store', name: 'Swdhya Store', type: 'store' },
  { path: '/no-fault', name: 'No Fault', type: 'brand_hub' },
  { path: '/nofault-store', name: 'No Fault Store', type: 'store' },
  { path: '/expoweek', name: 'Expo Week', type: 'brand_hub' },
  { path: '/star', name: 'STAR', type: 'utility' },
  { path: '/one', name: 'Download App', type: 'informational' },
  { path: '/faq', name: 'FAQ', type: 'informational' },
  { path: '/contact', name: 'Contact', type: 'informational' },
  { path: '/legal-stuff', name: 'Legal Stuff', type: 'legal' },
  { path: '/privacy', name: 'Privacy Policy', type: 'legal' },
  { path: '/careers-plus-culture', name: 'Careers + Culture', type: 'informational' },
  { path: '/partner-up', name: 'Partner Up', type: 'informational' },
  { path: '/enterprise-assist', name: 'Enterprise Assist', type: 'service' },
  { path: '/gift-card', name: 'Gift Card', type: 'informational' },
  { path: '/blog', name: 'Blog Hub', type: 'utility' },
  { path: '/sitemap', name: 'Sitemap', type: 'utility' },
  { path: '/appointment', name: 'Appointment', type: 'service' },
  { path: '/submit-request', name: 'Submit Request', type: 'service' },
  { path: '/track-request', name: 'Track Request', type: 'service' },
  { path: '/amend-request', name: 'Amend Request', type: 'service' },
  { path: '/order-notes', name: 'Order Notes', type: 'service' },
  { path: '/drop-docs', name: 'Drop Docs', type: 'service' },
  { path: '/rx-slot', name: 'RX Slot', type: 'service' },
  { path: '/selfservice', name: 'Self Service', type: 'service' },
  { path: '/search', name: 'Search', type: 'utility' },
  { path: '/leave-review', name: 'Leave Review', type: 'service' },
  { path: '/loyalty', name: 'Loyalty', type: 'service' },
  { path: '/referral', name: 'Referral', type: 'service' },
  { path: '/bring-friends', name: 'Bring Friends', type: 'service' },
];

// System pages
const SYSTEM_PAGES = [
  { path: '/cart-page', name: 'Cart', type: 'system' },
  { path: '/checkout', name: 'Checkout', type: 'system' },
  { path: '/thank-you', name: 'Thank You', type: 'system' },
  { path: '/login', name: 'Login', type: 'system' },
  { path: '/signup', name: 'Sign Up', type: 'system' },
  { path: '/404', name: '404 Not Found', type: 'system' },
  { path: '/members-area', name: 'Members Area', type: 'system' },
  { path: '/account/my-orders', name: 'My Orders', type: 'system' },
  { path: '/account/my-subscriptions', name: 'My Subscriptions', type: 'system' },
  { path: '/account/my-rewards', name: 'My Rewards', type: 'system' },
  { path: '/account/settings', name: 'Account Settings', type: 'system' },
  { path: '/order-confirmation', name: 'Order Confirmation', type: 'system' },
  { path: '/payment', name: 'Payment', type: 'system' },
  { path: '/wishlist', name: 'Wishlist', type: 'system' },
];

// Product pages
const PRODUCT_PAGES = [
  { path: '/product-page/partner-up', name: 'Partner Up', type: 'product', price: '999', inStock: true },
  { path: '/product-page/sahachintan', name: 'Sahachintan', type: 'product', price: '1', inStock: true },
  { path: '/product-page/bnb-club-membership', name: 'BNB Club Membership', type: 'product', price: '0', inStock: true },
  { path: '/product-page/legal-champ-starter', name: 'Legal Champ Starter', type: 'product', price: '0', inStock: true },
  { path: '/product-page/ritual-guru-puja-kit', name: 'Ritual Guru Puja Kit', type: 'product', price: '0', inStock: true },
];

async function cleanBlogPost(slug) {
  try {
    const r = await fetch(`${BASE}/api/seo-tools/seo-clean/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug }),
    });
    const d = await r.json();
    if (d.ok) {
      console.log(`  ✅ Blog: ${slug} — tags:${d.cleaned.tagsRemoved} kw:${d.cleaned.keywordsRemoved}`);
    } else {
      console.log(`  ❌ Blog: ${slug} — ${d.error}`);
    }
    return d;
  } catch (e) {
    console.log(`  ❌ Blog: ${slug} — ${e.message}`);
    return { ok: false, error: e.message };
  }
}

async function cleanPage(page) {
  try {
    const r = await fetch(`${BASE}/api/seo-tools/page-clean/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: page.path, name: page.name, pageType: page.type }),
    });
    const d = await r.json();
    if (d.ok) {
      console.log(`  ✅ ${page.type}: ${page.path} — audits removed: ${d.cleaned.auditsRemoved}`);
    } else {
      console.log(`  ❌ ${page.type}: ${page.path} — ${d.error}`);
    }
    return d;
  } catch (e) {
    console.log(`  ❌ ${page.type}: ${page.path} — ${e.message}`);
    return { ok: false, error: e.message };
  }
}

async function main() {
  console.log('=== BULK CLEAN ALL PAGES ===\n');

  // 1. Get all blog posts
  console.log('--- STEP 1: Fetching all blog posts ---');
  let blogSlugs = [];
  try {
    const r = await fetch(`${BASE}/api/seo-tools/blog-posts/`);
    const d = await r.json();
    blogSlugs = d.posts.map(p => p.slug);
    console.log(`Found ${blogSlugs.length} blog posts\n`);
  } catch (e) {
    console.log(`Failed to fetch blog posts: ${e.message}\n`);
  }

  // 2. Clean all blog posts (wipe seoData via Wix API)
  console.log('--- STEP 2: Cleaning ALL blog posts (Wix API) ---');
  let blogOk = 0, blogFail = 0;
  for (const slug of blogSlugs) {
    const r = await cleanBlogPost(slug);
    if (r.ok) blogOk++; else blogFail++;
    // Small delay to avoid rate limiting
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  console.log(`\nBlog: ${blogOk} cleaned, ${blogFail} failed\n`);

  // 3. Clean all site pages (local audit records)
  console.log('--- STEP 3: Cleaning ALL site pages (local audits) ---');
  let siteOk = 0;
  for (const page of SITE_PAGES) {
    await cleanPage(page);
    siteOk++;
  }
  console.log(`\nSite pages: ${siteOk} cleaned\n`);

  // 4. Clean all system pages
  console.log('--- STEP 4: Cleaning ALL system pages (local audits) ---');
  let sysOk = 0;
  for (const page of SYSTEM_PAGES) {
    await cleanPage(page);
    sysOk++;
  }
  console.log(`\nSystem pages: ${sysOk} cleaned\n`);

  // 5. Clean all product pages
  console.log('--- STEP 5: Cleaning ALL product pages (local audits) ---');
  let prodOk = 0;
  for (const page of PRODUCT_PAGES) {
    await cleanPage(page);
    prodOk++;
  }
  console.log(`\nProduct pages: ${prodOk} cleaned\n`);

  // Summary
  console.log('=== CLEAN COMPLETE ===');
  console.log(`Blog posts: ${blogOk}/${blogSlugs.length} cleaned via Wix API`);
  console.log(`Site pages: ${siteOk}/${SITE_PAGES.length} audit records cleared`);
  console.log(`System pages: ${sysOk}/${SYSTEM_PAGES.length} audit records cleared`);
  console.log(`Product pages: ${prodOk}/${PRODUCT_PAGES.length} audit records cleared`);
  console.log(`\nTotal: ${blogOk + siteOk + sysOk + prodOk} pages cleaned`);
  console.log('\nNOTE: Blog posts had seoData wiped via Wix Blog API.');
  console.log('NOTE: Site/system/product pages only had local audit records cleared.');
  console.log('NOTE: To clear Wix Dashboard SEO settings on static pages, do it manually in Wix Dashboard.');
}

main().catch(console.error);
