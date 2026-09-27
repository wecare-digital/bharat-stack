# Manual Wix Dashboard SEO Tasks
## These CANNOT be done via API — must be done in Wix Dashboard

---

## P0 — CRITICAL (Do First)

### Task 1: Homepage JSON-LD
**Path:** Wix Dashboard → Pages → Home → SEO (Google) → Advanced SEO → Add structured data markup

Add these 3 JSON-LD blocks:

**Block 1 — Organization:**
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://www.wecare.digital/#organization",
  "name": "WECARE.DIGITAL",
  "url": "https://www.wecare.digital/",
  "logo": "https://wecare.digital/get/o/stream/media/m/wecare-digital.png",
  "email": "one@wecare.digital",
  "telephone": "+919330994400",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "The W.B.S.I.D.C. Building, Unit 1/20, 81/2/7, Phears Lane",
    "addressLocality": "Kolkata",
    "addressRegion": "West Bengal",
    "postalCode": "700012",
    "addressCountry": "IN"
  },
  "sameAs": ["https://www.instagram.com/wecare.digital/"],
  "inLanguage": "en-IN"
}
```

**Block 2 — WebSite:**
```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "@id": "https://www.wecare.digital/#website",
  "name": "WECARE.DIGITAL",
  "url": "https://www.wecare.digital/",
  "potentialAction": {
    "@type": "SearchAction",
    "target": "https://www.wecare.digital/search?q={search_term_string}",
    "query-input": "required name=search_term_string"
  },
  "inLanguage": "en-IN"
}
```

**Block 3 — WebPage:**
```json
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "@id": "https://www.wecare.digital/#webpage",
  "name": "Microservice Brands for Everyday Bharat | WECARE.DIGITAL",
  "description": "Digital services for everyday Bharat — travel, legal, ritual, reflection, and dispute resolution with transparent pricing.",
  "url": "https://www.wecare.digital/",
  "inLanguage": "en-IN"
}
```

### Task 2: Homepage SEO Title & Description
**Path:** Wix Dashboard → Pages → Home → SEO (Google)
- Title: `Microservice Brands for Everyday Bharat | WECARE.DIGITAL`
- Description: `WECARE.DIGITAL connects everyday Bharat with trusted microservice brands in travel, legal, spiritual, events, dispute resolution & personal growth.`

### Task 3: Set System Pages to noindex
**Path:** Wix Dashboard → Pages → [each page] → SEO (Google) → Advanced → Robots

Set `noindex, nofollow` on:
- Cart Page
- Checkout
- Thank You
- Login
- Sign Up
- 404
- Members Area
- Account Settings
- My Orders
- My Subscriptions
- My Rewards
- Order Notes

---

## P1 — HIGH (Do This Week)

### Task 4: Brand Hub Pages — SEO Title & Description
For each brand page, go to Wix Dashboard → Pages → [page] → SEO (Google):

| Page | SEO Title | Meta Description |
|---|---|---|
| /bnb | BNB Club: Travel Stays & Experiences \| WECARE.DIGITAL | Book travel stays and curated experiences across India with BNB Club by WECARE.DIGITAL. Transparent pricing, easy booking. |
| /legal-champ | Legal Champ: Document & Paralegal Services \| WECARE.DIGITAL | Professional legal document preparation and paralegal workflows. Fast, affordable legal support for everyday Bharat. |
| /ritual | Ritual Guru: Temple-Grade Puja Kits \| WECARE.DIGITAL | Authentic temple-grade puja kits and spiritual services delivered to your door. Ritual Guru by WECARE.DIGITAL. |
| /swdhya | Swdhya: Reflection & Personal Growth \| WECARE.DIGITAL | Explore philosophical reflections on being, choice, and transformation. Swdhya by WECARE.DIGITAL. |
| /no-fault | No Fault: Guided Dispute Resolution \| WECARE.DIGITAL | Resolve disputes fairly with guided online dispute resolution. No Fault by WECARE.DIGITAL. |
| /expoweek | Expo Week: Virtual Events & Offers \| WECARE.DIGITAL | Discover exclusive virtual events and limited-time offers. Expo Week by WECARE.DIGITAL. |

### Task 5: Service Pages — SEO Title & Description
| Page | SEO Title | Meta Description |
|---|---|---|
| /appointment | Book an Appointment \| WECARE.DIGITAL | Schedule appointments for supported services. Choose your slot, provide details, get confirmation. |
| /submit-request | Submit a Service Request \| WECARE.DIGITAL | Submit a new request with your details and Order ID. Track progress from submission to completion. |
| /faq | Frequently Asked Questions \| WECARE.DIGITAL | Find answers about submitting requests, tracking orders, booking appointments, payments, and more. |
| /contact | Contact Us \| WECARE.DIGITAL | Reach WECARE.DIGITAL — email one@wecare.digital, call +91 9330994400, or visit us in Kolkata. |
| /gift-card | Buy Gift Cards \| WECARE.DIGITAL | Send e-gift cards instantly with any amount and a personal message. WECARE.DIGITAL gift cards. |

### Task 6: Product Pages — Add JSON-LD
For each product in Wix Dashboard → Store → Products → [product] → SEO:

Add Product + Offer schema with real price, availability, and brand. Example:
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Partner Up",
  "description": "Partner with WECARE.DIGITAL...",
  "brand": {"@type": "Organization", "name": "WECARE.DIGITAL"},
  "offers": {
    "@type": "Offer",
    "price": "999",
    "priceCurrency": "INR",
    "availability": "https://schema.org/InStock",
    "url": "https://www.wecare.digital/product-page/partner-up"
  },
  "inLanguage": "en-IN"
}
```

### Task 7: FAQ Page — Add FAQPage JSON-LD
**Path:** Wix Dashboard → Pages → FAQ → SEO (Google) → Advanced → Add structured data

Use the 13 FAQ items from `faq_data.py` to build FAQPage schema.

### Task 8: Contact Page — Add LocalBusiness JSON-LD
**Path:** Wix Dashboard → Pages → Contact → SEO (Google) → Advanced → Add structured data

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "WECARE.DIGITAL",
  "url": "https://www.wecare.digital/contact",
  "email": "one@wecare.digital",
  "telephone": "+919330994400",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "The W.B.S.I.D.C. Building, Unit 1/20, 81/2/7, Phears Lane",
    "addressLocality": "Kolkata",
    "addressRegion": "West Bengal",
    "postalCode": "700012",
    "addressCountry": "IN"
  },
  "inLanguage": "en-IN"
}
```

---

## P2 — MEDIUM (Do This Month)

### Task 9: Legal Pages — Set noindex
- /legal-stuff → noindex, follow
- /privacy → noindex, follow

### Task 10: Search Page — Set noindex
- /search → noindex, follow

### Task 11: Brand Store Pages — Add BreadcrumbList
Each store page should have BreadcrumbList: Home > Brand > Store

### Task 12: Add Cover Images to Blog Posts
Review all 108 blog posts. Add featured images to posts missing them.

### Task 13: Expand Thin Blog Content
Posts under 300 words should be expanded with examples, context, or reflections.
