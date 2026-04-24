import dotenv from "dotenv";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import fs from "node:fs/promises";

const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: resolve(__dirname, ".env") });

const { WIX_API_KEY, WIX_SITE_ID, WIX_MEMBER_ID, BRAND_NAME, BRAND_LOGO_URL, BASE_URL } = process.env;
if (!WIX_API_KEY || !WIX_SITE_ID) throw new Error("Missing WIX_API_KEY or WIX_SITE_ID in .env");

const headers = { Authorization: WIX_API_KEY, "wix-site-id": WIX_SITE_ID, "Content-Type": "application/json" };

// ── Validation ──

function validate(post) {
  const warnings = [];
  if (!Array.isArray(post.keywords)) warnings.push("keywords must be an array");
  if (!Array.isArray(post.tagIds)) warnings.push("tagIds must be an array");
  if (!Array.isArray(post.hashtags)) warnings.push("hashtags must be an array");
  if (post.seoTitle && post.seoTitle.length > 60) warnings.push(`seoTitle is ${post.seoTitle.length} chars (ideal: ≤60)`);
  if (post.seoDescription && post.seoDescription.length > 160) warnings.push(`seoDescription is ${post.seoDescription.length} chars (ideal: ≤160)`);
  return warnings;
}

// ── Tag builders ──

function jsonLdTag(schema) {
  return { type: "script", props: { type: "application/ld+json" }, children: JSON.stringify(schema), custom: true, disabled: false };
}

function metaTag(nameOrProp, content) {
  const isOg = nameOrProp.startsWith("og:") || nameOrProp.startsWith("article:");
  return { type: "meta", props: isOg ? { property: nameOrProp, content } : { name: nameOrProp, content }, children: "", custom: true, disabled: false };
}

function buildBlogPostingSchema(post) {
  return {
    "@context": "https://schema.org",
    "@type": post.schemaType || "BlogPosting",
    headline: post.ogTitle || post.seoTitle || post.title,
    description: post.ogDescription || post.seoDescription || post.excerpt,
    keywords: Array.isArray(post.keywords) ? post.keywords.join(", ") : "",
    image: post.image ? [post.image] : undefined,
    datePublished: post.datePublished,
    dateModified: post.dateModified || post.datePublished,
    url: post.url,
    author: { "@type": "Person", name: post.authorName, url: post.authorUrl || `${BASE_URL}/swdhya` },
    publisher: { "@type": "Organization", name: BRAND_NAME, logo: BRAND_LOGO_URL ? { "@type": "ImageObject", url: BRAND_LOGO_URL } : undefined },
    mainEntityOfPage: { "@type": "WebPage", "@id": post.url },
    inLanguage: "en-IN"
  };
}

function buildBreadcrumbSchema(post) {
  return {
    "@context": "https://schema.org", "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: `${BASE_URL}/` },
      { "@type": "ListItem", position: 2, name: "Blog", item: `${BASE_URL}/blog` },
      { "@type": "ListItem", position: 3, name: post.title, item: post.url }
    ]
  };
}

function buildFaqSchema(post) {
  if (!post.faqs || post.faqs.length === 0) return null;
  return {
    "@context": "https://schema.org", "@type": "FAQPage",
    mainEntity: post.faqs.map(faq => ({ "@type": "Question", name: faq.question, acceptedAnswer: { "@type": "Answer", text: faq.answer } }))
  };
}

function buildSeoData(post) {
  const title = post.seoTitle || `${post.title} | ${BRAND_NAME}`;
  const desc = post.seoDescription || post.excerpt;
  const tags = [
    { type: "title", children: title, custom: true, disabled: false },
    metaTag("description", desc),
    metaTag("robots", "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"),
    // NO meta keywords tag — keywords go in content, title, description, tags, hashtags, and schema instead
    metaTag("og:title", post.ogTitle || post.title),
    metaTag("og:description", post.ogDescription || desc),
    metaTag("og:url", post.url),
    metaTag("og:type", "article"),
    metaTag("og:site_name", BRAND_NAME),
    metaTag("og:locale", "en_IN"),
    metaTag("og:image", post.image || BRAND_LOGO_URL),
    metaTag("og:image:width", "1200"),
    metaTag("og:image:height", "630"),
    metaTag("og:image:alt", `${post.ogTitle || post.title} — ${BRAND_NAME}`),
    metaTag("article:author", post.authorName || "Swdhya Vaksetu"),
    metaTag("twitter:card", "summary_large_image"),
    metaTag("twitter:title", post.ogTitle || post.title),
    metaTag("twitter:description", post.twitterDescription || desc),
    { type: "link", props: { rel: "canonical", href: post.url }, children: "", custom: true, disabled: false },
    jsonLdTag(buildBlogPostingSchema(post)),
    jsonLdTag(buildBreadcrumbSchema(post)),
  ];
  const faq = buildFaqSchema(post);
  if (faq) tags.push(jsonLdTag(faq));

  // Focus keyword — Wix supports one main keyword in settings
  // All keywords go into the BlogPosting schema keywords field
  return {
    tags,
    settings: {
      preventAutoRedirect: false,
      keywords: post.focusKeyword ? [{ term: post.focusKeyword, isMain: true }] : []
    }
  };
}

function buildRichContent(post) {
  return { nodes: [{ type: "PARAGRAPH", id: "intro", nodes: [{ type: "TEXT", id: "t1", textData: { text: post.content || post.excerpt || post.title } }] }] };
}

// ── Create ──

async function createPost(post) {
  const warnings = validate(post);
  console.log(`\n📝 Creating: "${post.title}"`);
  console.log(`  📎 Slug: ${post.slug}`);
  console.log(`  🔑 Keywords: ${(post.keywords || []).join(", ")}`);
  console.log(`  #️⃣  Hashtags: ${(post.hashtags || []).join(", ")}`);
  console.log(`  🏷️  TagIds: ${(post.tagIds || []).length}`);
  if (warnings.length) warnings.forEach(w => console.log(`  ⚠️  ${w}`));

  const body = {
    publish: true,
    draftPost: {
      title: post.title,
      excerpt: post.excerpt,
      seoSlug: post.slug,
      richContent: buildRichContent(post),
      seoData: buildSeoData(post),
      ...(post.tagIds?.length ? { tagIds: post.tagIds } : {}),
      ...(post.hashtags?.length ? { hashtags: post.hashtags } : {}),
      ...(WIX_MEMBER_ID ? { memberId: WIX_MEMBER_ID } : {})
    },
    fieldsets: ["URL"]
  };

  const r = await fetch("https://www.wixapis.com/blog/v3/draft-posts", { method: "POST", headers, body: JSON.stringify(body) });
  const data = await r.json();
  if (!r.ok) { console.error(`  ❌ Failed (${r.status}):`, JSON.stringify(data, null, 2)); return; }

  const jsonLdCount = (data.draftPost?.seoData?.tags || []).filter(t => t.type === "script").length;
  console.log(`  ✅ Created & published`);
  console.log(`  📊 Structured data: ${jsonLdCount} JSON-LD schema(s) added`);
}

// ── Main ──
const posts = JSON.parse(await fs.readFile(resolve(__dirname, "posts.json"), "utf8"));
console.log(`📦 ${posts.length} post(s) loaded`);
for (const post of posts) await createPost(post);
console.log("\n✅ Done.");
