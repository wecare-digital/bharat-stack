#!/usr/bin/env node
/**
 * SEO Blog Test — Step-by-step test for blog post "Stand"
 * 
 * Usage:
 *   node scripts/seo-blog-test.mjs get-post          # Step 2: Show current seoData
 *   node scripts/seo-blog-test.mjs clear-seo          # Step 3: Clear existing seoData (unpublish + update + publish)
 *   node scripts/seo-blog-test.mjs set-seo             # Step 5: Set new seoData (unpublish + update, NO publish)
 *   node scripts/seo-blog-test.mjs publish              # Step 7: Publish the draft
 */

const WIX_API = 'https://www.wixapis.com';

// Read Wix API key — try env var, then .env.local, then AWS Secrets Manager
async function getWixKey() {
  if (process.env.WIX_API_KEY) return process.env.WIX_API_KEY;
  // Read from .env.local
  try {
    const { readFileSync } = await import('fs');
    const { resolve } = await import('path');
    const { fileURLToPath } = await import('url');
    const dir = resolve(fileURLToPath(import.meta.url), '../..');
    const env = readFileSync(resolve(dir, '.env.local'), 'utf8');
    const match = env.match(/^WIX_API_KEY=(.+)$/m);
    if (match) return match[1].trim();
  } catch {}
  // Try AWS Secrets Manager
  try {
    const { execSync } = await import('child_process');
    const raw = execSync('aws secretsmanager get-secret-value --secret-id wecare/wix-api-key --query SecretString --output text --region us-east-1', { encoding: 'utf8', timeout: 15000 });
    const parsed = JSON.parse(raw.trim());
    return parsed.api_key || parsed.WIX_API_KEY || '';
  } catch {}
  return '';
}

const WIX_KEY = await getWixKey();
if (!WIX_KEY) { console.error('❌ No WIX_API_KEY found'); process.exit(1); }
console.log('✅ Wix API key loaded (length:', WIX_KEY.length, ')');
const WIX_SITE = process.env.WIX_SITE_ID || 'c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5';
const TARGET_SLUG = 'stand';

const HEADERS = {
  'Authorization': WIX_KEY,
  'Content-Type': 'application/json',
  'wix-site-id': WIX_SITE,
};

// ── Wix API helper ──
async function wixApi(method, path, body) {
  const opts = { method, headers: HEADERS };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(WIX_API + path, opts);
  const text = await r.text();
  try { return { ok: r.ok, status: r.status, data: JSON.parse(text) }; }
  catch { return { ok: r.ok, status: r.status, data: text }; }
}

// ── Find post by slug ──
async function findPost() {
  console.log(`\n🔍 Finding blog post with slug: "${TARGET_SLUG}"...\n`);
  const r = await wixApi('GET', `/blog/v3/posts?paging.limit=100&fieldsToInclude=SEO`);
  if (!r.ok) { console.error('❌ API error:', r.status, r.data); return null; }
  const post = r.data.posts?.find(p => p.slug === TARGET_SLUG);
  if (!post) { console.error(`❌ Post with slug "${TARGET_SLUG}" not found`); return null; }
  console.log(`✅ Found: "${post.title}" (id: ${post.id})`);
  return post;
}

// ── Step 2: Show current seoData ──
async function getPost() {
  const post = await findPost();
  if (!post) return;
  console.log('\n📋 CURRENT SEO DATA:');
  console.log(JSON.stringify(post.seoData || {}, null, 2));
  console.log('\n📋 Post details:');
  console.log(`  Title: ${post.title}`);
  console.log(`  Slug: ${post.slug}`);
  console.log(`  URL: https://www.wecare.digital/post/${post.slug}`);
  console.log(`  Excerpt: ${(post.excerpt || '').substring(0, 100)}...`);
  console.log(`  Tags count: ${post.seoData?.tags?.length || 0}`);
}

// ── Step 3: Clear seoData ──
async function clearSeo() {
  const post = await findPost();
  if (!post) return;
  
  console.log('\n🧹 CLEARING seoData on "Stand"...');
  console.log('  Step 3a: Unpublishing...');
  const unpub = await wixApi('POST', `/blog/v3/posts/${post.id}/unpublish`);
  console.log(`  Unpublish: ${unpub.ok ? '✅' : '❌'} (${unpub.status})`);
  
  console.log('  Step 3b: Updating with empty seoData...');
  const update = await wixApi('PATCH', `/blog/v3/draft-posts/${post.id}`, {
    draftPost: { seoData: { tags: [] } }
  });
  console.log(`  Update: ${update.ok ? '✅' : '❌'} (${update.status})`);
  if (!update.ok) console.log('  Error:', JSON.stringify(update.data));
  
  console.log('  Step 3c: Publishing with clean seoData...');
  const pub = await wixApi('POST', `/blog/v3/draft-posts/${post.id}/publish`);
  console.log(`  Publish: ${pub.ok ? '✅' : '❌'} (${pub.status})`);
  
  console.log('\n✅ Done. Check https://www.wecare.digital/post/stand');
  console.log('   Verify in Wix Dashboard that seoData is clean.');
}

// ── Step 5: Set new seoData (NO publish) ──
async function setSeo() {
  const post = await findPost();
  if (!post) return;
  
  const BASE = 'https://www.wecare.digital';
  const BRAND = 'WECARE.DIGITAL';
  const LOGO = 'https://app.wecare.digital/stream/media/m/wecare-digital.png';
  const url = `${BASE}/post/stand`;
  
  const newSeoData = {
    tags: [
      { type: 'title', children: 'Stand: The Practice of Standing With Another | WECARE.DIGITAL', custom: true, disabled: false },
      { type: 'meta', props: { name: 'description', content: 'Explore the practice of standing with another — a conscious choice rooted in integrity, responsibility, and reciprocity. Discover how intentional support transforms relationships at WECARE.DIGITAL.' }, children: '', custom: true, disabled: false },
      // NO meta keywords tag — keywords go in content, title, description, tags, hashtags, and schema instead
      { type: 'meta', props: { name: 'robots', content: 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:title', content: 'Stand: The Practice of Standing With Another' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:description', content: 'Explore the practice of standing with another — a conscious choice rooted in integrity, responsibility, and reciprocity. Discover how intentional support transforms relationships.' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:url', content: url }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:type', content: 'article' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:site_name', content: BRAND }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:locale', content: 'en_IN' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:image', content: LOGO }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:image:width', content: '1200' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:image:height', content: '630' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'og:image:alt', content: 'Stand: The Practice of Standing With Another — WECARE.DIGITAL' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { property: 'article:author', content: 'Swdhya Vaksetu' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { name: 'twitter:card', content: 'summary_large_image' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { name: 'twitter:title', content: 'Stand: The Practice of Standing With Another' }, children: '', custom: true, disabled: false },
      { type: 'meta', props: { name: 'twitter:description', content: 'Explore the practice of standing with another — a conscious choice rooted in integrity, responsibility, and reciprocity.' }, children: '', custom: true, disabled: false },
      { type: 'link', props: { rel: 'canonical', href: url }, children: '', custom: true, disabled: false },
      { type: 'script', props: { type: 'application/ld+json' }, children: JSON.stringify({
        '@context': 'https://schema.org', '@type': 'BlogPosting',
        headline: 'Stand: The Practice of Standing With Another',
        description: 'Explore the practice of standing with another — a conscious choice rooted in integrity, responsibility, and reciprocity. Discover how intentional support transforms relationships.',
        keywords: 'standing with another, conscious choice, intentionality, integrity, relationship, free choice, support, responsibility, reciprocity, self-inquiry',
        url, image: LOGO,
        author: { '@type': 'Person', name: 'Swdhya Vaksetu', url: `${BASE}/swdhya` },
        publisher: { '@type': 'Organization', name: BRAND, logo: { '@type': 'ImageObject', url: LOGO } },
        mainEntityOfPage: { '@type': 'WebPage', '@id': url },
        inLanguage: 'en-IN'
      }), custom: true, disabled: false },
      { type: 'script', props: { type: 'application/ld+json' }, children: JSON.stringify({
        '@context': 'https://schema.org', '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: `${BASE}/` },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: `${BASE}/blog` },
          { '@type': 'ListItem', position: 3, name: 'Stand', item: url }
        ]
      }), custom: true, disabled: false },
    ],
    settings: {
      preventAutoRedirect: false,
      keywords: [{ term: 'standing with another', isMain: true }]
    }
  };
  
  console.log('\n📝 NEW SEO DATA to set:');
  console.log(`  Title: Stand: The Practice of Standing With Another | WECARE.DIGITAL`);
  console.log(`  Description: Explore the practice of standing with another...`);
  console.log(`  Keywords: 10 focus keywords`);
  console.log(`  OG tags: title, description, url, type, site_name, locale, image (w/h/alt)`);
  console.log(`  Twitter: card, title, description`);
  console.log(`  Canonical: ${url}`);
  console.log(`  JSON-LD: BlogPosting + BreadcrumbList`);
  console.log(`  Total tags: ${newSeoData.tags.length}`);
  
  console.log('\n🔄 Unpublishing...');
  const unpub = await wixApi('POST', `/blog/v3/posts/${post.id}/unpublish`);
  console.log(`  Unpublish: ${unpub.ok ? '✅' : '❌'} (${unpub.status})`);
  
  console.log('🔄 Updating seoData...');
  const update = await wixApi('PATCH', `/blog/v3/draft-posts/${post.id}`, {
    draftPost: { seoData: newSeoData }
  });
  console.log(`  Update: ${update.ok ? '✅' : '❌'} (${update.status})`);
  if (!update.ok) console.log('  Error:', JSON.stringify(update.data));
  
  console.log('\n⏸️  NOT publishing yet. Post is in draft state.');
  console.log('   Check Wix Dashboard → Blog → Drafts → "Stand"');
  console.log('   Verify the seoData looks correct.');
  console.log('   Then run: node scripts/seo-blog-test.mjs publish');
}

// ── Step 7: Publish ──
async function publish() {
  const post = await findPost();
  if (!post) return;
  
  console.log('\n🚀 Publishing "Stand"...');
  const pub = await wixApi('POST', `/blog/v3/draft-posts/${post.id}/publish`);
  console.log(`  Publish: ${pub.ok ? '✅' : '❌'} (${pub.status})`);
  if (!pub.ok) console.log('  Error:', JSON.stringify(pub.data));
  else console.log('\n✅ Published! Check https://www.wecare.digital/post/stand');
}

// ── CLI ──
const cmd = process.argv[2];
switch (cmd) {
  case 'get-post': await getPost(); break;
  case 'clear-seo': await clearSeo(); break;
  case 'set-seo': await setSeo(); break;
  case 'publish': await publish(); break;
  default:
    console.log('Usage:');
    console.log('  node scripts/seo-blog-test.mjs get-post    # Show current seoData');
    console.log('  node scripts/seo-blog-test.mjs clear-seo   # Clear seoData + publish clean');
    console.log('  node scripts/seo-blog-test.mjs set-seo     # Set new seoData (NO publish)');
    console.log('  node scripts/seo-blog-test.mjs publish      # Publish the draft');
}
