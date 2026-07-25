import React from 'react';

const S: React.CSSProperties = { fontSize: 14, fontWeight: 700, marginBottom: 8, color: '#1a3a2a' };
const pre: React.CSSProperties = { background: '#0f1117', color: '#a3e635', padding: 12, borderRadius: 8, fontSize: 10, lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0, maxHeight: 280, overflowY: 'auto' };
const thI: React.CSSProperties = { padding: '8px 12px', textAlign: 'left' as const, fontSize: 11, fontWeight: 600 };
const tdI: React.CSSProperties = { padding: '6px 12px', fontSize: 12 };

function Card ( { title, children }: { title: string; children: React.ReactNode } ) {
  return <div className="card" style={ { padding: 20, marginBottom: 16 } }><h3 style={ S }>{ title }</h3>{ children }</div>;
}

function JCard ( { n, title, desc, code }: { n: string; title: string; desc: string; code: string } ) {
  return (
    <div className="card" style={ { padding: 16, marginBottom: 12 } }>
      <div style={ { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 } }>
        <span style={ { padding: '2px 8px', background: '#d1f470', color: '#1a3a2a', borderRadius: 6, fontSize: 11, fontWeight: 700 } }>#{ n }</span>
        <span style={ { fontSize: 13, fontWeight: 600, color: '#111827' } }>{ title }</span>
      </div>
      <div style={ { fontSize: 11, color: '#6b7280', marginBottom: 8 } }>{ desc }</div>
      <pre style={ pre }>{ code }</pre>
    </div>
  );
}

export default function InstructionsContent () {
  return (
    <div style={ { maxWidth: 960 } }>
      <h2 style={ { fontSize: 18, fontWeight: 700, marginBottom: 16 } }>SEO Autopilot — Instructions & Standards</h2>

      <Card title="Overview">
        <p style={ { fontSize: 13, color: '#374151', lineHeight: 1.7, margin: 0 } }>
          AI-powered SEO for wecare.digital using Claude Sonnet 4.6 via AWS Bedrock.
          164 total pages: 108 blogs + 37 site pages + 5 products + 14 system pages.
          Every page gets clean JSON-LD (no duplicates), meta tags, keywords, FAQ schema, and SEO score.
          Human approval required. 🧹🤖 = Clean first then Audit. 🤖 = Audit only.
        </p>
      </Card>

      {/* ═══ 1. BLOG POST JSON-LD ═══ */ }
      <JCard n="1" title='Blog Post (/post/*) — BlogPosting + BreadcrumbList + FAQPage'
        desc="108 blog posts. Author: Person (Swdhya Vaksetu). FAQ extracted from content by AI. All 3 schemas pushed via Wix Blog API seoData.tags."
        code={ `// ── 1. BlogPosting ──
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Stand: The Practice of Standing With Another",
  "description": "Standing with another is a conscious free choice rooted in responsibility and intentionality—without requiring reciprocity.",
  "keywords": "standing with another, conscious free choice, willingness to be responsible, being in relationship, intentionality",
  "url": "https://www.wecare.digital/post/stand",
  "image": ["https://app.wecare.digital/stream/media/m/wecare-digital.png"],
  "datePublished": "2025-09-12T00:18:04.958Z",
  "dateModified": "2025-09-12T00:18:04.958Z",
  "wordCount": 75,
  "author": { "@type": "Person", "name": "Swdhya Vaksetu", "url": "https://www.wecare.digital/swdhya" },
  "publisher": { "@type": "Organization", "name": "WECARE.DIGITAL", "logo": { "@type": "ImageObject", "url": "https://app.wecare.digital/stream/media/m/wecare-digital.png" } },
  "mainEntityOfPage": { "@type": "WebPage", "@id": "https://www.wecare.digital/post/stand" },
  "inLanguage": "en-IN",
  "articleSection": "Philosophy of Relationship"
}

// ── 2. BreadcrumbList ──
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.wecare.digital/" },
    { "@type": "ListItem", "position": 2, "name": "Blog", "item": "https://www.wecare.digital/blog" },
    { "@type": "ListItem", "position": 3, "name": "Stand", "item": "https://www.wecare.digital/post/stand" }
  ]
}

// ── 3. FAQPage (AI-generated from blog content) ──
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What does it mean to stand with another person?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Standing with another means being willing to be responsible for standing up for and supporting another person, even while acknowledging they may require neither."
      }
    },
    {
      "@type": "Question",
      "name": "Does standing with someone require reciprocity?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "No. Making a choice to stand with another neither requires nor depends on the other person's reciprocity or their choice to also stand with you."
      }
    }
  ]
}`} />

      {/* ═══ 2. SITE PAGE JSON-LD ═══ */ }
      <JCard n="2" title='Site Page (/, /bnb, /legal-champ...) — WebPage + Organization + BreadcrumbList + FAQPage'
        desc="37 public pages. Homepage also gets WebSite + ItemList. FAQ page gets FAQPage with all Q&As."
        code={ `// ── 1. WebPage ──
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Microservices for Everyday Bharat",
  "description": "Digital services for everyday Bharat — travel, legal, ritual, reflection, and dispute resolution with transparent pricing.",
  "keywords": "digital services India, everyday Bharat, travel support, legal support, WECARE.DIGITAL",
  "url": "https://www.wecare.digital/",
  "image": "https://app.wecare.digital/stream/media/m/wecare-digital.png",
  "publisher": { "@type": "Organization", "name": "WECARE.DIGITAL" },
  "mainEntityOfPage": { "@type": "WebPage", "@id": "https://www.wecare.digital/" },
  "inLanguage": "en-IN"
}

// ── 2. Organization (homepage) ──
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "WECARE.DIGITAL",
  "url": "https://www.wecare.digital/",
  "logo": "https://app.wecare.digital/stream/media/m/wecare-digital.png",
  "email": "one@wecare.digital",
  "telephone": "+91 9330994400",
  "address": { "@type": "PostalAddress", "streetAddress": "The W.B.S.I.D.C. Building", "addressLocality": "Kolkata", "addressRegion": "West Bengal", "postalCode": "700012", "addressCountry": "IN" }
}

// ── 3. BreadcrumbList ──
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.wecare.digital/" },
    { "@type": "ListItem", "position": 2, "name": "BNB Club", "item": "https://www.wecare.digital/bnb" }
  ]
}

// ── 4. FAQPage (AI-generated from page content) ──
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What services does WECARE.DIGITAL offer?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Travel, legal documentation, ritual kits, self-inquiry sessions, and online dispute resolution across India."
      }
    },
    {
      "@type": "Question",
      "name": "Where is WECARE.DIGITAL based?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Kolkata, West Bengal, India. The W.B.S.I.D.C. Building, Phears Lane, 700012."
      }
    }
  ]
}`} />

      {/* ═══ 3. PRODUCT JSON-LD ═══ */ }
      <JCard n="3" title='Product (/product-page/*) — Product + Offer + BreadcrumbList + FAQPage'
        desc="5 products. Includes price, currency (INR), availability. FAQ about the product."
        code={ `// ── 1. Product + Offer ──
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Partner Up — Activate 4,000+ SKUs",
  "description": "Unlock earnings across 4,000+ SKUs from BNB Club, Expo Week, Legal Champ, No-Fault, Ritual Guru, Swdhya.",
  "url": "https://www.wecare.digital/product-page/partner-up",
  "image": "https://static.wixstatic.com/media/6b2d7a_cffca42eb2e7428fb618600456d257d9~mv2.png",
  "brand": { "@type": "Brand", "name": "WECARE.DIGITAL" },
  "offers": {
    "@type": "Offer",
    "price": "4599",
    "priceCurrency": "INR",
    "availability": "https://schema.org/InStock",
    "url": "https://www.wecare.digital/product-page/partner-up"
  },
  "inLanguage": "en-IN"
}

// ── 2. BreadcrumbList ──
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.wecare.digital/" },
    { "@type": "ListItem", "position": 2, "name": "Store", "item": "https://www.wecare.digital/store" },
    { "@type": "ListItem", "position": 3, "name": "Partner Up", "item": "https://www.wecare.digital/product-page/partner-up" }
  ]
}

// ── 3. FAQPage ──
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is Partner Up?",
      "acceptedAnswer": { "@type": "Answer", "text": "A one-time activation that unlocks 4,000+ SKUs across all WECARE.DIGITAL brands — earn on every valid order with no renewals." }
    },
    {
      "@type": "Question",
      "name": "How much does Partner Up cost?",
      "acceptedAnswer": { "@type": "Answer", "text": "₹4,599 (reduced from ₹6,999). One-time payment, no recurring fees." }
    }
  ]
}`} />

      {/* ═══ 4. SYSTEM PAGE JSON-LD ═══ */ }
      <JCard n="4" title='System Page (cart, checkout, 404...) — WebPage (minimal) or null'
        desc="14 system pages. Noindex. No rich schema. Checkout/login get no JSON-LD at all."
        code={ `// Cart page — minimal WebPage only
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Your Cart",
  "description": "Review items in your cart before checkout.",
  "url": "https://www.wecare.digital/cart-page",
  "publisher": { "@type": "Organization", "name": "WECARE.DIGITAL" },
  "inLanguage": "en-IN"
}

// Checkout → null (noindex, nofollow — no JSON-LD)
// Thank You → null (noindex, nofollow — no JSON-LD)
// 404 → null (noindex, nofollow — no JSON-LD)
// Login-gated pages → null (not crawlable)
// Side Cart, Fullscreen, Search Suggestions → UI overlays, not pages`} />

      {/* ═══ 5. NEW PAGE ═══ */ }
      <JCard n="5" title='Any New Page (future) — AI auto-detects type'
        desc="New blog/page/product created → AI detects type → applies correct schema set."
        code={ `// New blog post published → Wix Velo events.js fires automatically
// AI reads content → generates: BlogPosting + BreadcrumbList + FAQPage
// Saved as pending_review → admin approves in dashboard → pushed to Wix

// New site page → manual audit from dashboard
// AI generates: WebPage + BreadcrumbList + Organization + FAQPage

// New product → manual audit from dashboard
// AI generates: Product + Offer + BreadcrumbList + FAQPage

// System page → minimal WebPage or null (noindex)`} />

      {/* Phases */ }
      <Card title="Phases">
        <table style={ { width: '100%', borderCollapse: 'collapse', fontSize: 12 } }>
          <thead><tr style={ { borderBottom: '2px solid #e5e7eb', background: '#f9fafb' } }>
            <th style={ thI }>Phase</th><th style={ thI }>Scope</th><th style={ { ...thI, textAlign: 'center' as const } }>Cost</th><th style={ { ...thI, textAlign: 'center' as const } }>Status</th>
          </tr></thead>
          <tbody>
            { [ [ '1. Pilot', 'Stand blog post', '$0.08', '✅ Done' ], [ '2. All Blogs', '108 blog posts', '$6.48', '⏳' ], [ '3. Site Pages', '37 public pages', '$2.22', '⏳' ], [ '4. Products', '5 products', '$0.30', '⏳' ], [ '5. System', '14 system pages', '$0.84', '⏳' ], [ '6. Autopilot', 'New posts auto', '$0.08/post', '✅ Active' ] ].map( ( [ a, b, c, d ] ) => (
              <tr key={ a } style={ { borderBottom: '1px solid #f3f4f6' } }><td style={ { ...tdI, fontWeight: 600 } }>{ a }</td><td style={ tdI }>{ b }</td><td style={ { ...tdI, textAlign: 'center' as const, fontWeight: 600 } }>{ c }</td><td style={ { ...tdI, textAlign: 'center' as const } }>{ d }</td></tr>
            ) ) }
          </tbody>
        </table>
      </Card>

      {/* Rules */ }
      <Card title="Rules">
        <ul style={ { fontSize: 13, color: '#374151', lineHeight: 2, margin: 0, paddingLeft: 20 } }>
          <li>🧹🤖 Clean + Audit = wipe all old SEO data first, then run AI audit (recommended for first time)</li>
          <li>🤖 Audit only = run AI on current state (use for re-audits after content changes)</li>
          <li>Blog titles: expert-written only — AI suggests but NEVER auto-publishes</li>
          <li>All changes require human approval before pushing to Wix</li>
          <li>No monthly refresh — set once, done. Re-audit only on request</li>
          <li>Multiple keywords pushed to Wix: 1 focus (isMain) + 9 secondary</li>
          <li>All old duplicate JSON-LD wiped on Apply — complete replacement</li>
          <li>Author: always Swdhya Vaksetu (Person, not Organization)</li>
          <li>Model: Claude Sonnet 4.6 via Bedrock — ~$0.05/page (fallback: Nova Pro)</li>
        </ul>
      </Card>

      {/* Architecture */ }
      <Card title="Architecture">
        <pre style={ { ...pre, lineHeight: 1.8 } }>{ `Dashboard → authenticated api.wecare.digital/seo-tools/*
         → Admin-only SEO Lambda → Wix Blog API / live page SEO
         → AWS Bedrock (Claude Sonnet 4.6, fallback models)
         → retained DynamoDB audit + AI log records (PITR)
         → conditional approval → blog-only Wix apply

Keywords: 1 focus (isMain:true) + 9 secondary pushed to Wix seoData.settings.keywords
JSON-LD: BlogPosting + BreadcrumbList + FAQPage (3 scripts, no duplicates)
Mutations: fail-closed idempotency claims; actor always comes from Cognito
Pages/products: audit and review only; apply is intentionally unsupported

Flow: clean or audit → pending_review → approve/reject → blog apply`}</pre>
      </Card>
    </div>
  );
}
