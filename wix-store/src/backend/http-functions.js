/**************************************************************
 * backend/http-functions.js
 * WECARE.DIGITAL ΓÇö SEO + AI + DISCOVERY + STORE API (PROD)
 * Updated: 2026-02-13 IST
 **************************************************************/
import { ok, notFound, badRequest, forbidden, serverError, options } from 'wix-http-functions';
import { fetch } from 'wix-fetch';
import wixData from 'wix-data';
import { getSecret } from 'wix-secrets-backend';

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   Canonical & IDs
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
const CANONICAL   = "https://www.wecare.digital";
const ALT_ORIGIN  = "https://wecare.digital";
const ORG         = "WECARE.DIGITAL";
const ORG_ID      = `${CANONICAL}/#org`;
const SITE_ID     = `${CANONICAL}/#website`;
const HOME_ID     = `${CANONICAL}/#home`;

const VERSION = "2026-02-13T12:00:00+05:30";

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   Assets & Social
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
const LOGO_SVG     = "https://selfcare.wecare.digital/wecare-digital.svg";
const LOGO_PNG     = "https://selfcare.wecare.digital/wecare-digital.png";
const LOGO_FAVICON = "https://selfcare.wecare.digital/wecare-digital.ico";
const SOCIAL       = ["https://www.instagram.com/wecare.digital"];

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   Caching, MIME & robots headers
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
const CACHE_10M = { 'Cache-Control': 'public, max-age=600, stale-while-revalidate=600' };

const CT_XML  = 'application/xml; charset=utf-8';
const CT_TXT  = 'text/plain; charset=utf-8';
const CT_JSON = 'application/json; charset=utf-8';
const CT_LD   = 'application/ld+json; charset=utf-8';

const NOINDEX = { 'X-Robots-Tag': 'noindex, noarchive' };

const csvHeaders = (filename) => ({
  'Content-Type': 'text/csv; charset=utf-8',
  'Content-Disposition': `attachment; filename="${filename}"`,
  'Access-Control-Allow-Origin': '*',
  ...NOINDEX,
  'X-WeCare-Version': VERSION
});

/* ETag helpers */
function hashString(s){
  let h = 2166136261 >>> 0;
  for (let i=0;i<s.length;i++){
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h.toString(16);
}
function etagFromString(body){ return 'W/"' + hashString(body) + '"'; }
function etagResponse(body, contentType, request, extraHeaders = {}){
  const etag = etagFromString(body);
  const inm  = request?.headers?.['if-none-match'] || request?.headers?.['If-None-Match'];
  if (inm && inm === etag){
    return { status: 304, headers: { ETag: etag, ...CACHE_10M, 'X-WeCare-Version': VERSION, ...extraHeaders }, body: "" };
  }
  return { headers: { ETag: etag, 'Content-Type': contentType, ...CACHE_10M, 'X-WeCare-Version': VERSION, ...extraHeaders }, body };
}
function etagOk(body, contentType, request, extraHeaders = {}){
  const r = etagResponse(body, contentType, request, extraHeaders);
  if (r.status === 304) return r;
  return ok(r);
}

/* Small helpers */
const withVersion = (h = {}) => ({ ...h, 'X-WeCare-Version': VERSION });
const apiHeaders  = (extra={}) => withVersion({ 'Content-Type': CT_JSON, 'Access-Control-Allow-Origin':'*', ...NOINDEX, ...extra });
const H_JSON      = apiHeaders();
const H_NOINDEX   = H_JSON;
const NO_CACHE    = { ...H_NOINDEX, 'Cache-Control': 'no-store' };

function corsPreflight() {
  return ok({
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': '*'
    },
    body: ''
  });
}
function http(status, headers, body){ return { status, headers, body }; }

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   Single source of truth (DATA) ΓÇö Updated from live site 2026-02-13
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
const DATA = {
  org: {
    name: "WECARE.DIGITAL",
    url: `${CANONICAL}/`,
    email: "one@wecare.digital",
    telephone: "+91 9330994400",
    addressOneLine: "The W.B.S.I.D.C. Building, Unit 1/20, 81/2/7, Phears Ln, Kolkata, West Bengal 700012, India"
  },
  assets: { logoSvg: LOGO_SVG, logoPng: LOGO_PNG, faviconIco: LOGO_FAVICON },
  social: SOCIAL,
  cta: {
    primary: [
      { label:"Submit Request",       href:"/submit-request" },
      { label:"Request Amendment",    href:"/request-amendment" },
      { label:"Request Tracking",     href:"/request-tracking" },
      { label:"RX Slot",              href:"/rx-slot" },
      { label:"Drop Docs",            href:"/drop-docs" },
      { label:"Enterprise Support",   href:"/enterprise-assist" }
    ],
    secondary: [
      { label:"Order Notes",          href:"/order-notes" },
      { label:"E-Commerce Portal",    href:"/ecom" },
      { label:"STAR (Account Hub)",   href:"/star" }
    ]
  },
  keywords: {
    global: [
      "wecare.digital","microservices company","customer self service",
      "digital services","secure","fast","smart","India","Kolkata","app","contact","faq",
      "digital ecosystem","everyday Bharat","Viksit Bharat"
    ],
    common: ["online","pricing","availability","support","guided","partner","store","blog"],
    relatedGroups: {
      selfService: ["submit request","request amendment","request tracking","RX slot","upload documents","enterprise support"],
      noFault:     ["online dispute resolution","ODR India","ODR platform","uncontested","mediation","flat fee","documentation","access to justice"],
      bnb:         ["travel club India","MICE","FIT","visa support","concierge","itinerary","medical tours","corporate travel"],
      swdhya:      ["self inquiry","samvad","leadership conversations","clarity","coaching","self-awareness","reflection"],
      ritual:      ["puja kits","temple grade","vrat","aarti guide","yatra","satsang","eco-conscious","delivered worldwide"],
      legalChamp:  ["company registration","trademark","GST","documentation","filings","attestation","paralegal"],
      policies:    ["terms","refund","shipping","privacy","acceptable use"]
    }
  },
  faq: {
    global: [
      { q:"What is WECARE.DIGITAL?", a:"A Kolkata-based digital company building a digital ecosystem for everyday BharatΓÇöoperating microservice brands including No Fault, BNB Club, Ritual Guru, Legal Champ, Swdhya, and Expo Week on one secure platform.", pathHints:["/","/faq"] },
      { q:"How can I contact you?", a:"Use the Contact page, call +91 9330994400, or email one@wecare.digital. We typically reply within business hours.", pathHints:["/contact","/faq"] },
      { q:"What are your support hours?", a:"MondayΓÇôFriday, 09:00ΓÇô17:00 IST for assisted help. The Self-Service portal is available 24├ù7.", pathHints:["/faq","/selfservice"] },
      { q:"Where are you located?", a:"The W.B.S.I.D.C. Building, Unit 1/20 81/2/7, Phears Ln, Kolkata 700012, West Bengal, India.", pathHints:["/contact"] },
      { q:"Is there a mobile app?", a:"Yes. The ONE app lets you track, book, upload documents and pay from your phone. See the /one page for details.", pathHints:["/one","/faq"] }
    ],
    selfservice: [
      { q:"What can I do in Self-Service?", a:"Submit a new request, amend an existing one, track status, book an RX slot, upload documents, or get enterprise support.", pathHints:["/selfservice"] },
      { q:"How do I submit a new request?", a:"Open /submit-request, fill in the guided form, and you'll receive a reference ID and updates.", pathHints:["/submit-request","/selfservice"] },
      { q:"How do I amend my request?", a:"Go to /request-amendment, provide your reference ID or contact details, and attach new information if required.", pathHints:["/request-amendment","/selfservice"] },
      { q:"How do I track my request?", a:"Use /request-tracking with your reference ID or contact to see status: Received ΓåÆ Reviewing ΓåÆ Completed.", pathHints:["/request-tracking","/selfservice"] },
      { q:"Where do I upload documents?", a:"Use /drop-docs to upload supported file types securely; they attach to your request automatically.", pathHints:["/drop-docs","/selfservice"] },
      { q:"How do I book or reschedule an RX slot?", a:"Go to /rx-slot, choose a time, and confirm. You can reschedule in the same flow.", pathHints:["/rx-slot","/selfservice"] },
      { q:"How do I get enterprise assistance?", a:"Use /enterprise-assist with your SRN, company name, and work email for priority help.", pathHints:["/enterprise-assist","/selfservice"] }
    ],
    store: [
      { q:"What is a product page on WECARE.DIGITAL?", a:"A detail page for a service or digital item showing description, price, availability, and purchase/start options.", pathHints:["/product-page"] },
      { q:"What payment methods do you accept?", a:"Options appear during checkout and may vary by provider.", pathHints:["/product-page","/legal-stuff"] },
      { q:"Do you deliver physical items?", a:"Some brands (e.g., Ritual Guru) deliver physical kits; serviceability and shipping options are shown at checkout.", pathHints:["/ritual-store","/product-page"] }
    ],
    brandNoFault: [
      { q:"What is No Fault?", a:"A technology platform for online dispute resolution (ODR), bringing key processes and tools into one secure, easy interface with smart workflows and independent professionals.", pathHints:["/no-fault"] },
      { q:"What documents do I need for No Fault?", a:"It depends on the matter. Start from /no-fault or /submit-request and follow the guided checklist.", pathHints:["/no-fault","/submit-request"] }
    ],
    brandBNB: [
      { q:"What is BNB Club?", a:"A full-service travel club for FIT and MICE with personalized itineraries, concierge, visa support, and medical tours.", pathHints:["/bnb"] },
      { q:"Do you support medical tours?", a:"Yes, including coordination, documentation, and bookings.", pathHints:["/bnb"] }
    ],
    brandRitual: [
      { q:"What is Ritual Guru?", a:"Curated, temple-grade puja kits for festivals, vrats, housewarmings, and daily worship with step-by-step guides. Delivered worldwide.", pathHints:["/ritual"] },
      { q:"Do you deliver puja kits everywhere?", a:"Availability varies by item and location; options are shown at checkout. We deliver worldwide.", pathHints:["/ritual-store"] }
    ],
    brandLegal: [
      { q:"What is Legal Champ?", a:"Affordable documentation and paralegal services with transparent scope and pricing. (We're not a law firm.)", pathHints:["/legal-champ"] },
      { q:"What documents can you help with?", a:"Company setup, basic compliance filings, tax numbers, and IP/trademark support.", pathHints:["/legal-champ","/legalchamp-store"] }
    ],
    brandSwdhya: [
      { q:"What is Swdhya?", a:"A conversational practice of self-inquiry that turns reflection into clarity, connection, and committed action.", pathHints:["/swdhya"] },
      { q:"How do I book a Swdhya session?", a:"Go to /swdhya or /swdhya-store and choose a session.", pathHints:["/swdhya","/swdhya-store"] }
    ],
    blogAndPolicies: [
      { q:"What do you publish on the blog?", a:"Short reads and updates across brands, products, and practice.", pathHints:["/blog"] },
      { q:"Can I browse by category or tag?", a:"YesΓÇöuse /blog categories/tags to find topics.", pathHints:["/blog"] },
      { q:"Where can I see refund/cancellation policy?", a:"See /legal-stuff for terms.", pathHints:["/legal-stuff"] },
      { q:"How do you handle my data?", a:"See /privacy for data and rights.", pathHints:["/privacy"] }
    ]
  },
  pages: [
    { path:"/",                  title:"WECARE.DIGITAL | MICROSERVICES COMPANY", meta:"Building a digital ecosystem for everyday BharatΓÇöa network of microservice brands designed to solve real problems for real people, while laying the digital railroads for a Viksit Bharat.", keywords:{ primary:["microservices company","digital ecosystem"], related:["consumer marketplaces","DIY + assisted","partner programs","app","gift card","everyday Bharat","Viksit Bharat"] } },
    { path:"/selfservice",       title:"Customer Self-Service Portal | WECARE.DIGITAL", meta:"Submit or amend a request, track status, book RX slots, upload documents, or get enterprise supportΓÇö24├ù7.", keywords:{ primary:["customer self service"], related:["submit request","request tracking","request amendment","RX slot","upload documents","enterprise support"] } },
    { path:"/submit-request",    title:"Submit a Request | WECARE.DIGITAL", meta:"Start a new request in minutes with a guided form and secure uploads. Get a reference ID and real-time updates.", keywords:{ primary:["submit request online"], related:["guided intake","reference ID","secure uploads"] } },
    { path:"/request-amendment", title:"Request Amendment | WECARE.DIGITAL", meta:"Update details for an existing requestΓÇöattach documents and resubmit without starting over.", keywords:{ primary:["amend request"], related:["update details","attach files","resubmit"] } },
    { path:"/request-tracking",  title:"Track a Request | WECARE.DIGITAL", meta:"Check real-time status and notifications for any request using your ID or contact details.", keywords:{ primary:["request tracking"], related:["status updates","notifications","milestones"] } },
    { path:"/rx-slot",           title:"Book an RX Slot | WECARE.DIGITAL", meta:"Schedule or reschedule a prescription slot with reminders and calendar sync.", keywords:{ primary:["RX slot"], related:["appointment booking","reschedule","reminders"] } },
    { path:"/drop-docs",         title:"Upload Documents Securely | WECARE.DIGITAL", meta:"Encrypted uploads with virus scans and audit trails. Attach to existing requests automatically.", keywords:{ primary:["upload documents"], related:["secure upload","audit trail","file types"] } },
    { path:"/enterprise-assist", title:"Enterprise Support (SRN) | WECARE.DIGITAL", meta:"Dedicated assistance for enterprise casesΓÇöshare your SRN, company name, and work email.", keywords:{ primary:["enterprise support"], related:["SRN","SLA","onboarding"] } },
    { path:"/order-notes",       title:"Add Order Notes | WECARE.DIGITAL", meta:"Add notes to your order in the account portal for faster resolution and traceability.", keywords:{ primary:["order notes"], related:["account portal","traceability"] } },
    { path:"/ecom",              title:"E-Commerce Portal Login | WECARE.DIGITAL", meta:"Access the merchant portal for store and order operations.", keywords:{ primary:["portal login"], related:["merchant tools","e-commerce access"] } },
    { path:"/star",              title:"STAR | Account Hub | WECARE.DIGITAL", meta:"One hub for account actions and quick links across brands.", keywords:{ primary:["account hub"], related:["quick actions","account access"] } },
    { path:"/no-fault",          title:"Online Dispute Resolution (ODR) Platform | No Fault", meta:"A technology platform for online dispute resolution (ODR), bringing key processes and tools into one secure, easy interface with smart workflows and independent professionals.", keywords:{ primary:["online dispute resolution","ODR platform"], related:["ODR India","uncontested","mediation","flat fee","access to justice"] } },
    { path:"/nofault-store",     title:"No Fault Store | Uncontested Dispute Resolution Online", meta:"Start online for uncontested matters with flat-fee transparency and expert guidance.", keywords:{ primary:["uncontested dispute resolution online"], related:["ODR","flat fee","guided process"] } },
    { path:"/bnb",               title:"BNB Club | Full-Service Travel Club (MICE & FIT)", meta:"A full-service travel club run by creative leaders. Corporate (MICE) and free independent travel (FIT) with personalized itineraries, concierge, and visa support.", keywords:{ primary:["travel club India","full-service travel"], related:["MICE","FIT","visa support","concierge","itinerary","medical tours","corporate travel"] } },
    { path:"/bnb-store",         title:"BNB Club Store | Itinerary & Visa Support", meta:"Products and services for personalized itineraries with seamless visa support.", keywords:{ primary:["itinerary planning"], related:["visa support","concierge","bundles"] } },
    { path:"/swdhya",            title:"Swdhya | Self-Inquiry Conversations for Clarity", meta:"A conversational practice of self-inquiry. Turn reflection into clarity, connection, and committed actionΓÇöso you can move toward what truly matters.", keywords:{ primary:["self inquiry","samvad"], related:["leadership conversations","clarity","self-awareness","reflection","committed action"] } },
    { path:"/swdhya-store",      title:"Swdhya Store | Sessions & Resources", meta:"Book guided conversations and access practice resourcesΓÇöno physical shipments.", keywords:{ primary:["guided sessions"], related:["leadership","resources"] } },
    { path:"/ritual",            title:"Ritual Guru | Temple-Grade Puja Kits & Guides", meta:"Curated, temple-grade puja kits for festivals, vrats, housewarmings, and daily worship. Pure, practical, step-by-step guides. Delivered worldwide.", keywords:{ primary:["puja kits","temple grade"], related:["vrat","aarti guide","eco-conscious","delivered worldwide"] } },
    { path:"/ritual-store",      title:"Ritual Guru Store | Sacred Essentials", meta:"Practice, Satsang, Yatras, WisdomΓÇöplus From Box to Blessing kits & guides.", keywords:{ primary:["puja kits store"], related:["sacred essentials","guides"] } },
    { path:"/legal-champ",       title:"Legal Champ | Documentation & Paralegal Services", meta:"Affordable documentation and paralegal services with transparent scope and pricing. We help legal paperwork be done reliably with minimal effort. (We're not a law firm.)", keywords:{ primary:["legal documentation","paralegal services"], related:["company registration","trademark","GST","business documentation"] } },
    { path:"/legalchamp-store",  title:"Legal Champ Store | Start Online", meta:"Start documentation and filings online; guided flows with clear deliverables.", keywords:{ primary:["documentation services"], related:["filings","attestation"] } },
    { path:"/expoweek",          title:"Expo Week | Virtual Travel Fair in India", meta:"Talks, panels, and curated experiences for travel professionals and explorers.", keywords:{ primary:["virtual travel fair"], related:["tourism","offers","workshops"] } },
    { path:"/partner-up",        title:"Partner With WECARE.DIGITAL", meta:"Co-sell, co-market, and bundle with WECARE brands. Earn with lifetime partner codes.", keywords:{ primary:["partner program"], related:["reseller","bundles","StoreSlate"] } },
    { path:"/gift-card",         title:"Digital eGift Card | WECARE.DIGITAL", meta:"Send an e-gift instantlyΓÇöchoose an amount and add a message.", keywords:{ primary:["gift card"], related:["egift","instant delivery"] } },
    { path:"/one",               title:"WECARE.DIGITAL App | Track, Book, Upload, Pay", meta:"Manage orders, bookings, documents and payments in one app.", keywords:{ primary:["customer app"], related:["track","book","upload","pay"] } },
    { path:"/blog",              title:"WECARE.DIGITAL Blog | Stories & Updates", meta:"Short reads across brandsΓÇöideas, product updates, and practice.", keywords:{ primary:["wecare blog"], related:["stories","updates"] } },
    { path:"/faq",               title:"Frequently Asked Questions | WECARE.DIGITAL", meta:"One place for answersΓÇöSelf-Service how-tos, brands, store, and policies.", keywords:{ primary:["FAQ"], related:["self service help","policies","contact"] } },
    { path:"/contact",           title:"CONTACT US | WECARE.DIGITAL", meta:"Call +91 9330994400 or email one@wecare.digital. Visit The W.B.S.I.D.C. Building, Phears Ln, Kolkata 700012.", keywords:{ primary:["contact wecare.digital"], related:["Kolkata address","phone","email"] } },
    { path:"/legal-stuff",       title:"Legal Stuff | Terms, Shipping, Refund", meta:"Our terms and policy notes, including cancellations, shipping, payments and acceptable use.", keywords:{ primary:["terms and conditions"], related:["refund policy","shipping policy","privacy"] } },
    { path:"/privacy",           title:"Privacy Policy | WECARE.DIGITAL", meta:"What we collect and why, retention and rights, cookies and processors.", keywords:{ primary:["privacy policy"], related:["data protection","security"] } },
    { path:"/search",            title:"Search Results | WECARE.DIGITAL", meta:"Find pages, posts and products; filter by type and recency.", keywords:{ primary:["site search"], related:["discover","results"] } },
    { path:"/sitemap",           title:"Sitemap | WECARE.DIGITAL", meta:"Browse every section of the siteΓÇöbrands, stores, self-service, legal, and blog.", keywords:{ primary:["sitemap"], related:["site index","navigation"] } },
    { path:"/careers-plus-culture", title:"Careers + Culture | WECARE.DIGITAL", meta:"Join a team of builders focused on small services with big outcomes.", keywords:{ primary:["careers wecare.digital"], related:["culture","remote","hiring"] } },
    { path:"/products",          title:"All Products | WECARE.DIGITAL", meta:"Browse all products and service packages across brands.", keywords:{ primary:["products"] } },
    { path:"/product-page",      title:"Product Details | WECARE.DIGITAL", meta:"Description, price, availability, and how to start.", keywords:{ primary:["product details"] } },
    { path:"/cart",              title:"Cart | WECARE.DIGITAL", meta:"Review items and proceed to checkout.", keywords:{ primary:["cart"] } },
    { path:"/cart-page",         title:"Cart | WECARE.DIGITAL", meta:"Your cart overview and checkout.", keywords:{ primary:["cart"] } }
  ],
  pageAugment: {
    globalKeywords: [
      "wecare.digital","microservices company","customer self service",
      "digital services","secure","fast","smart","India","Kolkata","app","contact","faq",
      "digital ecosystem","everyday Bharat","Viksit Bharat"
    ],
    commonKeywords: ["online","pricing","availability","support","guided","partner","store","blog"],
    byPath: {
      "/":                  { relatedGroup:"global",      faqSection:"global",          canonical:`${CANONICAL}/`,                 showOrg:true, showFAQ:true,  showCTA:true  },
      "/selfservice":       { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/selfservice`,      showOrg:true, showFAQ:true,  showCTA:true  },
      "/submit-request":    { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/submit-request`,   showOrg:true, showFAQ:true,  showCTA:true  },
      "/request-amendment": { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/request-amendment`,showOrg:true, showFAQ:true,  showCTA:true  },
      "/request-tracking":  { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/request-tracking`, showOrg:true, showFAQ:true,  showCTA:true  },
      "/rx-slot":           { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/rx-slot`,          showOrg:true, showFAQ:true,  showCTA:true  },
      "/drop-docs":         { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/drop-docs`,        showOrg:true, showFAQ:true,  showCTA:true  },
      "/enterprise-assist": { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/enterprise-assist`,showOrg:true, showFAQ:true,  showCTA:true  },
      "/order-notes":       { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/order-notes`,      showOrg:true, showFAQ:true,  showCTA:true  },
      "/ecom":              { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/ecom`,             showOrg:true, showFAQ:true,  showCTA:true  },
      "/star":              { relatedGroup:"selfService", faqSection:"selfservice",     canonical:`${CANONICAL}/star`,             showOrg:true, showFAQ:true,  showCTA:true  },
      "/no-fault":          { relatedGroup:"noFault",     faqSection:"brandNoFault",    canonical:`${CANONICAL}/no-fault`,         showOrg:true, showFAQ:true,  showCTA:true  },
      "/nofault-store":     { relatedGroup:"noFault",     faqSection:"brandNoFault",    canonical:`${CANONICAL}/nofault-store`,    showOrg:true, showFAQ:true,  showCTA:true  },
      "/bnb":               { relatedGroup:"bnb",         faqSection:"brandBNB",        canonical:`${CANONICAL}/bnb`,              showOrg:true, showFAQ:true,  showCTA:true  },
      "/bnb-store":         { relatedGroup:"bnb",         faqSection:"brandBNB",        canonical:`${CANONICAL}/bnb-store`,        showOrg:true, showFAQ:true,  showCTA:true  },
      "/swdhya":            { relatedGroup:"swdhya",      faqSection:"brandSwdhya",     canonical:`${CANONICAL}/swdhya`,           showOrg:true, showFAQ:true,  showCTA:true  },
      "/swdhya-store":      { relatedGroup:"swdhya",      faqSection:"brandSwdhya",     canonical:`${CANONICAL}/swdhya-store`,     showOrg:true, showFAQ:true,  showCTA:true  },
      "/ritual":            { relatedGroup:"ritual",      faqSection:"brandRitual",     canonical:`${CANONICAL}/ritual`,           showOrg:true, showFAQ:true,  showCTA:true  },
      "/ritual-store":      { relatedGroup:"ritual",      faqSection:"brandRitual",     canonical:`${CANONICAL}/ritual-store`,     showOrg:true, showFAQ:true,  showCTA:true  },
      "/legal-champ":       { relatedGroup:"legalChamp",  faqSection:"brandLegal",      canonical:`${CANONICAL}/legal-champ`,      showOrg:true, showFAQ:true,  showCTA:true  },
      "/legalchamp-store":  { relatedGroup:"legalChamp",  faqSection:"brandLegal",      canonical:`${CANONICAL}/legalchamp-store`, showOrg:true, showFAQ:true,  showCTA:true  },
      "/expoweek":          { relatedGroup:"bnb",         faqSection:"global",          canonical:`${CANONICAL}/expoweek`,         showOrg:true, showFAQ:true,  showCTA:true  },
      "/partner-up":        { relatedGroup:"global",      faqSection:"global",          canonical:`${CANONICAL}/partner-up`,       showOrg:true, showFAQ:true,  showCTA:true  },
      "/gift-card":         { relatedGroup:"global",      faqSection:"global",          canonical:`${CANONICAL}/gift-card`,        showOrg:true, showFAQ:true,  showCTA:true  },
      "/one":               { relatedGroup:"global",      faqSection:"global",          canonical:`${CANONICAL}/one`,              showOrg:true, showFAQ:true,  showCTA:true  },
      "/blog":              { relatedGroup:"global",      faqSection:"blogAndPolicies", canonical:`${CANONICAL}/blog`,             showOrg:true, showFAQ:true,  showCTA:true  },
      "/faq":               { relatedGroup:"global",      faqSection:"global",          canonical:`${CANONICAL}/faq`,              showOrg:true, showFAQ:true,  showCTA:true  },
      "/contact":           { relatedGroup:"global",      faqSection:"global",          canonical:`${CANONICAL}/contact`,          showOrg:true, showFAQ:false, showCTA:false },
      "/legal-stuff":       { relatedGroup:"policies",    faqSection:"blogAndPolicies", canonical:`${CANONICAL}/legal-stuff`,      showOrg:true, showFAQ:true,  showCTA:false },
      "/privacy":           { relatedGroup:"policies",    faqSection:"blogAndPolicies", canonical:`${CANONICAL}/privacy`,          showOrg:true, showFAQ:true,  showCTA:false },
      "/search":            { relatedGroup:"global",      faqSection:"global",          canonical:`${CANONICAL}/search`,           showOrg:true, showFAQ:false, showCTA:false },
      "/sitemap":           { relatedGroup:"global",      faqSection:"global",          canonical:`${CANONICAL}/sitemap`,          showOrg:true, showFAQ:false, showCTA:false },
      "/careers-plus-culture": { relatedGroup:"global",   faqSection:"global",          canonical:`${CANONICAL}/careers-plus-culture`, showOrg:true, showFAQ:false, showCTA:false },
      "/products":     { relatedGroup:"global", faqSection:"global", canonical:`${CANONICAL}/products`,     showOrg:true, showFAQ:false, showCTA:false },
      "/product-page": { relatedGroup:"global", faqSection:"global", canonical:`${CANONICAL}/product-page`, showOrg:true, showFAQ:false, showCTA:false },
      "/cart":         { relatedGroup:"global", faqSection:"global", canonical:`${CANONICAL}/cart`,         showOrg:true, showFAQ:false, showCTA:false },
      "/cart-page":    { relatedGroup:"global", faqSection:"global", canonical:`${CANONICAL}/cart-page`,    showOrg:true, showFAQ:false, showCTA:false }
    }
  }
};

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   Constants & helpers
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
const SITE_HOST  = "www.wecare.digital";
const SITE_BASE  = CANONICAL;
const LANGUAGE   = "en-US";
const DEFAULT_IMAGE_ALT = "WECARE.DIGITAL";
const HREFLANGS  = ["en-IN","en-US","x-default"];

const CANONICAL_PARAMS_TO_STRIP = [
  "utm_source","utm_medium","utm_campaign","utm_term","utm_content","utm_id",
  "utm_source_platform","utm_creative_format","utm_marketing_tactic",
  "fbclid","gclid","msclkid","wbraid","gbraid","ttclid","twclid","yclid",
  "mc_eid","irclickid",
  "wixCodeMetaId","wixCodePageId","wixCodeInstance",
  "instance","compId","viewerCompId","siteRevision",
  "ref","src"
];

const BLOCKED_URLS = new Set([]);

const FUNCTION_URL_GRID = [
  { name:"get_smtxt",          url:"/_functions/smtxt" },
  { name:"get_smextra",        url:"/_functions/smextra" },
  { name:"get_smindex",        url:"/_functions/smindex" },
  { name:"get_sitemap",        url:"/_functions/sitemap" },
  { name:"get_robots",         url:"/_functions/robots" },

  { name:"get_llms",           url:"/_functions/llms" },
  { name:"get_llmslong",       url:"/_functions/llmslong" },
  { name:"get_llmstxt",        url:"/_functions/llmstxt" },
  { name:"get_aiindex",        url:"/_functions/aiindex" },

  { name:"get_faq",            url:"/_functions/faq" },
  { name:"get_contact",        url:"/_functions/contact" },

  { name:"get_siteinfo",       url:"/_functions/siteinfo" },
  { name:"get_discovery",      url:"/_functions/discovery" },

  { name:"get_pagemeta",       url:"/_functions/pagemeta" },
  { name:"get_pagehead",       url:"/_functions/pagehead" },
  { name:"get_seohead",        url:"/_functions/seohead" },

  { name:"get_icons",          url:"/_functions/icons" },

  { name:"get_diag",           url:"/_functions/diag" },
  { name:"get_seoerrors",      url:"/_functions/seoerrors" },
  { name:"get_selftest",       url:"/_functions/selftest" },

  { name:"get_keywordscloud",  url:"/_functions/keywordscloud" },
  { name:"get_keywordscommon", url:"/_functions/keywordscommon" },
  { name:"get_keywordsrelated",url:"/_functions/keywordsrelated" },
  { name:"get_keywordsglobal", url:"/_functions/keywordsglobal" },
  { name:"get_keywordsmeta",   url:"/_functions/keywordsmeta" },

  { name:"get_schemablog",     url:"/_functions/schemablog" },
  { name:"get_schemaproduct",  url:"/_functions/schemaproduct" },

  { name:"get_canonicalize",   url:"/_functions/canonicalize" },
  { name:"get_rss",            url:"/_functions/rss" },
  { name:"get_rssblog",        url:"/_functions/rssblog" },
  { name:"get_rssproducts",    url:"/_functions/rssproducts" },

  { name:"get_ping",           url:"/_functions/ping" },
  { name:"get_pin",            url:"/_functions/pin" },
  { name:"get_pingnow",        url:"/_functions/pingnow" },

  // Store API endpoints
  { name:"get_products",       url:"/_functions/products" },
  { name:"get_product",        url:"/_functions/product" },
  { name:"get_orders",         url:"/_functions/orders" },
  { name:"get_order",          url:"/_functions/order" },
  { name:"get_collections",    url:"/_functions/collections" },
  { name:"get_inventory",      url:"/_functions/inventory" },
  { name:"get_inventoryAll",   url:"/_functions/inventoryAll" },
  { name:"get_stats",          url:"/_functions/stats" }
];

const ICON_GRID = [ LOGO_SVG, LOGO_PNG, LOGO_FAVICON ];

const BREADCRUMB_GRID = {
  "/": ["Home"],
  "/no-fault": ["Home","No Fault"],
  "/nofault-store": ["Home","No Fault","Store"],
  "/bnb": ["Home","BNB Club"],
  "/bnb-store": ["Home","BNB Club","Store"],
  "/ritual": ["Home","Ritual Guru"],
  "/ritual-store": ["Home","Ritual Guru","Store"],
  "/legal-champ": ["Home","Legal Champ"],
  "/legalchamp-store": ["Home","Legal Champ","Store"],
  "/swdhya": ["Home","Swdhya"],
  "/swdhya-store": ["Home","Swdhya","Store"],
  "/expoweek": ["Home","Expo Week"],
  "/selfservice": ["Home","Self-Service"],
  "/submit-request": ["Home","Self-Service","Submit Request"],
  "/request-amendment": ["Home","Self-Service","Request Amendment"],
  "/request-tracking": ["Home","Self-Service","Request Tracking"],
  "/rx-slot": ["Home","Self-Service","RX Slot"],
  "/drop-docs": ["Home","Self-Service","Drop Docs"],
  "/enterprise-assist": ["Home","Self-Service","Enterprise Assist"],
  "/order-notes": ["Home","Self-Service","Order Notes"],
  "/ecom": ["Home","E-Commerce"],
  "/star": ["Home","STAR"],
  "/partner-up": ["Home","Partner Up"],
  "/gift-card": ["Home","Gift Card"],
  "/blog": ["Home","Blog"],
  "/careers-plus-culture": ["Home","Careers + Culture"],
  "/one": ["Home","One"],
  "/faq": ["Home","FAQ"],
  "/search": ["Home","Search"],
  "/contact": ["Home","Contact"],
  "/legal-stuff": ["Home","Legal"],
  "/privacy": ["Home","Privacy"],
  "/sitemap": ["Home","Sitemap"],
  "/products": ["Home","Products"],
  "/product-page": ["Home","Products","Product Page"],
  "/cart-page": ["Home","Cart"],
  "/cart": ["Home","Cart"]
};

/* Helpers */
function normalizeHost(request){
  const h = request?.headers?.host || request?.headers?.Host || SITE_HOST;
  return String(h).toLowerCase();
}
function decodeMaybeJSON(str){
  try { return JSON.parse(decodeURIComponent(str)); } catch(_) { return null; }
}
function stripParams(urlString){
  const u = new URL(urlString);
  const removed = [];
  const appParam = u.searchParams.get("appSectionParams");
  if (appParam){
    const obj = decodeMaybeJSON(appParam);
    if (obj && obj.origin === "wixcode"){
      u.searchParams.delete("appSectionParams");
      removed.push("appSectionParams(origin=wixcode)");
    }
  }
  CANONICAL_PARAMS_TO_STRIP.forEach(p=>{
    if (u.searchParams.has(p)){ u.searchParams.delete(p); removed.push(p); }
  });
  return { canonical: u.toString(), removed };
}
function findStaticPage(path){
  return DATA.pages.find(p => p.path === path);
}
async function fetchTextMaybe(url){
  try {
    const res = await fetch(url, { method:"get" });
    if (!res.ok) return null;
    return await res.text();
  } catch(_) { return null; }
}

/* Sitemap parsing helpers */
function extractLocs(xml){
  if (!xml) return [];
  const urls = [];
  const blocks = xml.match(/<url>[\s\S]*?<\/url>/g) || [];
  for (const b of blocks){
    const loc = (b.match(/<loc>([^<]+)<\/loc>/) || [])[1];
    const lastmod = (b.match(/<lastmod>([^<]+)<\/lastmod>/) || [])[1];
    if (loc) urls.push({ loc, lastmod });
  }
  if (urls.length === 0){
    const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m=>({ loc:m[1], lastmod:undefined }));
    return locs;
  }
  return urls;
}

async function getLivePagesFromSitemap(){
  const xml = await fetchTextMaybe(`${SITE_BASE}/pages-sitemap.xml`);
  if (!xml) return [];
  const matches = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)];
  return matches.map(m=>m[1]).filter(u=>!BLOCKED_URLS.has(u));
}
async function getDynamicBlogUrls(){
  const out = new Set();
  const cats = await fetchTextMaybe(`${SITE_BASE}/blog-categories-sitemap.xml`);
  if (cats){ [...cats.matchAll(/<loc>([^<]+)<\/loc>/g)].forEach(mm => { const u=mm[1]; if(!BLOCKED_URLS.has(u)) out.add(u); }); }
  const tags = await fetchTextMaybe(`${SITE_BASE}/blog-tags-sitemap.xml`);
  if (tags){ [...tags.matchAll(/<loc>([^<]+)<\/loc>/g)].forEach(mm => { const u=mm[1]; if(!BLOCKED_URLS.has(u)) out.add(u); }); }
  const posts = await fetchTextMaybe(`${SITE_BASE}/blog-posts-sitemap.xml`);
  if (posts){ [...posts.matchAll(/<loc>([^<]+)<\/loc>/g)].forEach(mm => { const u=mm[1]; if(!BLOCKED_URLS.has(u)) out.add(u); }); }
  return Array.from(out);
}
async function getDynamicProductUrls(){
  const xml = await fetchTextMaybe(`${SITE_BASE}/store-products-sitemap.xml`);
  if (!xml) return [];
  const matches = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)];
  return matches.map(m=>m[1]).filter(u=>!BLOCKED_URLS.has(u));
}

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   0) Breadcrumb builder
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
function buildBreadcrumbItems(path){
  const labels = BREADCRUMB_GRID[path];
  if (!labels || labels.length === 0) return null;

  const urls = [ `${CANONICAL}/` ];
  const addIf = (cond, url) => { if (cond) urls.push(url); };
  addIf(path.startsWith("/selfservice") && path !== "/selfservice", `${CANONICAL}/selfservice`);

  const storePairs = [
    ["/nofault-store",   "/no-fault"],
    ["/bnb-store",       "/bnb"],
    ["/swdhya-store",    "/swdhya"],
    ["/ritual-store",    "/ritual"],
    ["/legalchamp-store","/legal-champ"]
  ];
  for (const [storePath, hub] of storePairs){
    if (path === storePath) { urls.push(`${CANONICAL}${hub}`); break; }
  }
  if (path !== "/") urls.push(`${CANONICAL}${path}`);

  return labels.map((name, i) => ({
    name,
    url: urls[i] || urls[urls.length - 1]
  }));
}

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   1) Sitemaps & Robots
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
export async function get_smtxt(request){
  const [livePages, blogs, products] = await Promise.all([
    getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls()
  ]);
  const set = new Set();
  DATA.pages.forEach(p => set.add(`${SITE_BASE}${p.path}`));
  livePages.forEach(u => set.add(u));
  blogs.forEach(u => set.add(u));
  products.forEach(u => set.add(u));
  FUNCTION_URL_GRID.forEach(f => set.add(`${SITE_BASE}${f.url}`));
  set.add("https://selfcare.wecare.digital/");
  ICON_GRID.forEach(i => set.add(i));
  const body = Array.from(set).join("\n");
  return ok({ headers: withVersion({ 'Content-Type': CT_TXT, ...CACHE_10M }), body });
}
export function get_smextra(request){
  const urls = [
    "https://selfcare.wecare.digital/",
    ...ICON_GRID
  ];
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map(u => `  <url><loc>${u}</loc><changefreq>weekly</changefreq><priority>0.4</priority></url>`).join('\n')}
</urlset>`;
  return etagOk(xml, CT_XML, request);
}
export function get_smindex(request){
  const sitemaps = [
    `${SITE_BASE}/_functions/sitemap`,
    `${SITE_BASE}/pages-sitemap.xml`,
    `${SITE_BASE}/blog-posts-sitemap.xml`,
    `${SITE_BASE}/blog-categories-sitemap.xml`,
    `${SITE_BASE}/blog-tags-sitemap.xml`,
    `${SITE_BASE}/store-products-sitemap.xml`,
    `${SITE_BASE}/_functions/smextra`,
    `${SITE_BASE}/_functions/smtxt`
  ];
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemaps.map(u => `  <sitemap><loc>${u}</loc></sitemap>`).join('\n')}
</sitemapindex>`;
  return etagOk(xml, CT_XML, request);
}
export async function get_sitemap(request){
  const [livePages, blogs, products] = await Promise.all([
    getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls()
  ]);
  const urls = new Set();
  DATA.pages.forEach(p => urls.add(`${SITE_BASE}${p.path}`));
  livePages.forEach(u => urls.add(u));
  blogs.forEach(u => urls.add(u));
  products.forEach(u => urls.add(u));
  FUNCTION_URL_GRID.forEach(f => urls.add(`${SITE_BASE}${f.url}`));
  urls.add("https://selfcare.wecare.digital/");

  const items = Array.from(urls).map(u => {
    const alts = HREFLANGS.map(h => `<xhtml:link rel="alternate" hreflang="${h}" href="${u}"/>`).join('');
    return `<url><loc>${u}</loc>${alts}</url>`;
  }).join("");
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">` +
    items + `</urlset>`;

  return etagOk(xml, CT_XML, request);
}

export function get_robots(request){
  const xmlSitemaps = [
    `${SITE_BASE}/_functions/smindex`,
    `${SITE_BASE}/_functions/sitemap`,
    `${SITE_BASE}/pages-sitemap.xml`,
    `${SITE_BASE}/blog-categories-sitemap.xml`,
    `${SITE_BASE}/blog-tags-sitemap.xml`,
    `${SITE_BASE}/blog-posts-sitemap.xml`,
    `${SITE_BASE}/store-products-sitemap.xml`,
    `${SITE_BASE}/_functions/smextra`,
    `${SITE_BASE}/_functions/smtxt`
  ];

  const lines = [
    "# WECARE.DIGITAL robots.txt",
    "User-agent: *",
    "Allow: /",
    "",
    "# De-duplicate by blocking only query variants with tracking/tech params",
    "Disallow: /*utm_source=",
    "Disallow: /*utm_medium=",
    "Disallow: /*utm_campaign=",
    "Disallow: /*utm_term=",
    "Disallow: /*utm_content=",
    "Disallow: /*utm_id=",
    "Disallow: /*utm_source_platform=",
    "Disallow: /*utm_creative_format=",
    "Disallow: /*utm_marketing_tactic=",
    "Disallow: /*fbclid=",
    "Disallow: /*gclid=",
    "Disallow: /*msclkid=",
    "Disallow: /*wbraid=",
    "Disallow: /*gbraid=",
    "Disallow: /*ttclid=",
    "Disallow: /*twclid=",
    "Disallow: /*yclid=",
    "Disallow: /*mc_eid=",
    "Disallow: /*irclickid=",
    "Disallow: /*wixCodeMetaId=",
    "Disallow: /*wixCodePageId=",
    "Disallow: /*wixCodeInstance=",
    "Disallow: /*instance=",
    "Disallow: /*compId=",
    "Disallow: /*viewerCompId=",
    "Disallow: /*siteRevision=",
    "Disallow: /*ref=",
    "Disallow: /*src=",
    "Disallow: /*appSectionParams=",
    "",
    "# --- Sitemaps ---",
    ...xmlSitemaps.map(u => `Sitemap: ${u}`),
    "",
    "# --- AI Discovery ---",
    `# llms.txt: ${SITE_BASE}/_functions/llmstxt`,
    `# AI index: ${SITE_BASE}/_functions/aiindex`,
    `# Discovery: ${SITE_BASE}/_functions/discovery`,
    "",
    "# --- Cross-site: Selfcare (own host) ---",
    "# https://selfcare.wecare.digital",
    "",
    "# Language: en-us | Country: India"
  ];

  return ok({ headers: withVersion({ 'Content-Type': CT_TXT, ...CACHE_10M }), body: lines.join("\n") });
}

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   2) JSON-LD / Meta / SEO Head
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
export async function get_pagemeta(request){
  const urlParam = request.query?.url;
  if (!urlParam){
    return http(400, NO_CACHE, {
      ok:false, reason:"url param required",
      usage:`/_functions/pagemeta?url=${encodeURIComponent(`${SITE_BASE}/`)}`,
      expects:["ok:boolean","title?:string","description?:string","keywords?:string[]"]
    });
  }
  const { canonical } = stripParams(urlParam);
  const path = new URL(canonical).pathname;
  const staticPage = findStaticPage(path);
  if (staticPage){
    return ok({
      headers: H_JSON,
      body: { ok:true, source:"static-grid", url:canonical, title:staticPage.title, description:staticPage.meta, keywords: staticPage.keywords?.primary || [] }
    });
  }
  const [livePages, blogs, products] = await Promise.all([ getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls() ]);
  const found = livePages.includes(canonical) || blogs.includes(canonical) || products.includes(canonical);
  if (!found){
    return http(404, NO_CACHE, { ok:false, reason:"url is not in site discovery", url: canonical });
  }
  return http(404, NO_CACHE, { ok:false, reason:"dynamic url found but no manual/meta entry ΓÇö add to DATA.pages or consume via /seohead?relaxed=1", url: canonical });
}

export async function get_pagehead(request){
  const urlParam = request.query?.url;
  if (!urlParam){
    return http(400, NO_CACHE, {
      ok:false, reason:"url param required",
      usage:`/_functions/pagehead?url=${encodeURIComponent(`${SITE_BASE}/`)}`,
      expects:["ok:boolean","title?:string","description?:string"]
    });
  }
  if (!/^https:\/\//i.test(urlParam)) return http(400, NO_CACHE, { ok:false, reason:"only https URLs supported" });
  const html = await fetchTextMaybe(urlParam);
  if (!html) return http(502, NO_CACHE, { ok:false, reason:"fetch failed" });
  const titleMatch = html.match(/<title>([^<]+)<\/title>/i);
  const descMatch  =
      html.match(/<meta\s+[^>]*name\s*=\s*["']description["'][^>]*content\s*=\s*["']([^"']+)["'][^>]*>/i)
   || html.match(/<meta\s+[^>]*content\s*=\s*["']([^"']+)["'][^>]*name\s*=\s*["']description["'][^>]*>/i);
  return ok({ headers: H_JSON, body:{ ok:true, title:titleMatch?.[1]||"", description:descMatch?.[1]||"" }});
}

export async function get_seohead(request){
  const host = normalizeHost(request);
  const qPath = request.query?.path || "/";
  const relaxed = request.query?.relaxed === "1";
  const { canonical, removed } = stripParams(`https://${host}${qPath}`);
  const cleanPath = new URL(canonical).pathname;

  const staticPage = findStaticPage(cleanPath);
  if (staticPage){
    const bcItems = buildBreadcrumbItems(cleanPath);

    const websiteNode = {
      "@context":"https://schema.org", "@type":"WebSite", "@id": SITE_ID, url: CANONICAL, name: ORG, inLanguage: LANGUAGE,
      "potentialAction": cleanPath === "/" ? {
        "@type": "SearchAction",
        "target": `${CANONICAL}/search?q={search_term_string}`,
        "query-input": "required name=search_term_string"
      } : undefined
    };

    const graph = [
      { "@context":"https://schema.org", "@id": ORG_ID, "@type":["Organization","LocalBusiness"],
        name:DATA.org.name, url:CANONICAL, email:DATA.org.email, telephone:DATA.org.telephone,
        logo:LOGO_PNG, image:LOGO_SVG, sameAs: DATA.social,
        address:{ "@type":"PostalAddress", "streetAddress":"The W.B.S.I.D.C. Building, Unit 1/20 81/2/7, Phears Ln",
                  "addressLocality":"Kolkata", "addressRegion":"West Bengal", "postalCode":"700012", "addressCountry":"India" } },
      websiteNode,
      { "@context":"https://schema.org", "@type":"WebPage", url: canonical, name: staticPage.title, description: staticPage.meta, inLanguage: LANGUAGE }
    ];
    if (bcItems && bcItems.length > 1){
      graph.push({
        "@context":"https://schema.org", "@type":"BreadcrumbList",
        "itemListElement": bcItems.map((it, idx) => ({
          "@type":"ListItem", position: idx + 1, name: it.name, item: it.url
        }))
      });
    }

    return ok({
      headers: H_JSON,
      body: {
        ok:true, host, path: cleanPath,
        title: staticPage.title, description: staticPage.meta,
        keywords: staticPage.keywords?.primary || [],
        keywordsGlobal: DATA.pageAugment?.globalKeywords || DATA.keywords?.global || [],
        keywordsCommon: DATA.pageAugment?.commonKeywords || DATA.keywords?.common || [],
        canonical, canonicalParamsRemoved: removed,
        defaultImageAlt: DEFAULT_IMAGE_ALT,
        structuredData: graph
      }
    });
  }

  const [blogs, products] = await Promise.all([ getDynamicBlogUrls(), getDynamicProductUrls() ]);
  const full = `https://${host}${cleanPath}`;
  const isDynamic = blogs.includes(full) || products.includes(full);
  if (isDynamic){
    if (!relaxed){
      return http(404, NO_CACHE, { ok:false, reason:"dynamic page exists but no explicit SEO ΓÇö call with ?relaxed=1 or add to DATA.pages", path: cleanPath, canonicalParamsRemoved: removed });
    }
    return ok({ headers: H_JSON, body:{ ok:true, host, path: cleanPath, title:"", description:"", keywords:[], canonical, canonicalParamsRemoved: removed, defaultImageAlt: DEFAULT_IMAGE_ALT, structuredData: [] }});
  }

  return http(404, NO_CACHE, { ok:false, reason:"not in static grid or Wix sitemaps", path: cleanPath, canonicalParamsRemoved: removed });
}

export function get_schemablog(request){
  const slug = request.query?.slug || "";
  const url  = `${CANONICAL}/blog/${encodeURIComponent(slug)}`;
  const sd = {
    "@context":"https://schema.org",
    "@type":"Article",
    "headline": slug.replace(/[-_]+/g,' ').trim() || "Blog Post",
    "author": { "@type":"Organization", "name": ORG },
    "isAccessibleForFree": true,
    "mainEntityOfPage": url,
    "url": url,
    "image": [ LOGO_PNG ],
    "datePublished": new Date().toISOString(),
    "dateModified": new Date().toISOString()
  };
  return ok({ headers: withVersion({ 'Content-Type': CT_LD, ...CACHE_10M, ...NOINDEX, 'Access-Control-Allow-Origin': '*' }), body: JSON.stringify(sd) });
}
export function get_schemaproduct(request){
  const id  = request.query?.id || "";
  const url = `${CANONICAL}/product-page?id=${encodeURIComponent(id)}`;
  const sd = {
    "@context":"https://schema.org",
    "@type":"Product",
    "name": `Product ${id || ""}`.trim(),
    "sku": id || undefined,
    "image": [ LOGO_PNG ],
    "url": url,
    "brand": { "@type":"Brand", "name": ORG },
    "offers": {
      "@type":"Offer",
      "priceCurrency":"INR",
      "price":"0",
      "availability":"https://schema.org/InStock",
      "url": url
    }
  };
  return ok({ headers: withVersion({ 'Content-Type': CT_LD, ...CACHE_10M, ...NOINDEX, 'Access-Control-Allow-Origin': '*' }), body: JSON.stringify(sd) });
}

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   3) FAQ / Contact / Icons / Siteinfo
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
export function get_faq(request){
  try{
    const schema = {
      "@context":"https://schema.org","@type":"FAQPage",
      "mainEntity": (DATA.faq.global || []).map(f=>({
        "@type":"Question","name": f.q,"acceptedAnswer":{ "@type":"Answer","text": f.a }
      })),
      "inLanguage": LANGUAGE
    };
    return ok({ headers: H_JSON, body:{ ok:true, source:"wecare.digital", faqs: DATA.faq, schema }});
  } catch(e){
    return http(500, NO_CACHE, { ok:false, error:String(e?.message||e) });
  }
}
export function get_contact(request){
  try{
    const org = {
      name: DATA.org.name, legalName: DATA.org.name, url: CANONICAL,
      logo: LOGO_PNG, icon: LOGO_FAVICON, image: LOGO_SVG, sameAs: DATA.social,
      address: {
        streetAddress: "The W.B.S.I.D.C. Building, Unit 1/20 81/2/7, Phears Ln",
        addressLocality: "Kolkata", addressRegion: "West Bengal",
        postalCode: "700012", addressCountry: "India"
      },
      telephone: DATA.org.telephone, email: DATA.org.email,
      customerService: `${CANONICAL}/selfservice`
    };
    return ok({ headers: H_JSON, body: org });
  } catch(e){
    return http(500, NO_CACHE, { ok:false, error:String(e?.message||e) });
  }
}
export function get_icons(request){
  try{
    return ok({ headers: H_JSON, body:{ icons: ICON_GRID }});
  } catch(e){
    return http(500, NO_CACHE, { ok:false, error:String(e?.message||e) });
  }
}
export function get_siteinfo(request){
  try{
    return ok({ headers: H_JSON, body:{
      site: SITE_BASE,
      alias: ALT_ORIGIN,
      subdomains: [ "https://selfcare.wecare.digital", "*.wecare.digital" ],
      language: LANGUAGE,
      defaultImageAlt: DEFAULT_IMAGE_ALT,
      contact: { name: DATA.org.name, email: DATA.org.email, telephone: DATA.org.telephone, address: DATA.org.addressOneLine },
      social: DATA.social,
      icons: ICON_GRID,
      functions: FUNCTION_URL_GRID.map(f => `${SITE_BASE}${f.url}`)
    }});
  } catch(e){
    return http(500, NO_CACHE, { ok:false, error:String(e?.message||e) });
  }
}

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   4) AI Feeds (ETag + CORS + noindex) + NEW llms.txt
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */

/** llms.txt ΓÇö Standard AI discovery format */
export async function get_llmstxt(request){
  try{
    const [livePages, blogs, products] = await Promise.all([ getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls() ]);
    const lines = [
      `# ${ORG}`,
      "",
      `> ${DATA.pages[0].meta}`,
      "",
      "## About",
      "",
      `${ORG} is a Kolkata-based digital company building a digital ecosystem for everyday Bharat.`,
      `We operate microservice brands: No Fault (ODR), BNB Club (Travel), Ritual Guru (Puja Kits), Legal Champ (Documentation), Swdhya (Self-Inquiry), and Expo Week (Travel Fair).`,
      "",
      "## Contact",
      "",
      `- Email: ${DATA.org.email}`,
      `- Phone: ${DATA.org.telephone}`,
      `- Address: ${DATA.org.addressOneLine}`,
      `- Website: ${CANONICAL}`,
      "",
      "## Brands",
      "",
      "- [No Fault ΓÇö Online Dispute Resolution](https://www.wecare.digital/no-fault)",
      "- [BNB Club ΓÇö Full-Service Travel](https://www.wecare.digital/bnb)",
      "- [Ritual Guru ΓÇö Temple-Grade Puja Kits](https://www.wecare.digital/ritual)",
      "- [Legal Champ ΓÇö Documentation & Paralegal](https://www.wecare.digital/legal-champ)",
      "- [Swdhya ΓÇö Self-Inquiry Conversations](https://www.wecare.digital/swdhya)",
      "- [Expo Week ΓÇö Virtual Travel Fair](https://www.wecare.digital/expoweek)",
      "",
      "## Pages",
      ""
    ];
    DATA.pages.forEach(p => lines.push(`- [${p.title}](${SITE_BASE}${p.path})`));
    if (blogs.length) {
      lines.push("", "## Blog Posts", "");
      blogs.slice(0, 50).forEach(u => lines.push(`- ${u}`));
      if (blogs.length > 50) lines.push(`- ... and ${blogs.length - 50} more`);
    }
    if (products.length) {
      lines.push("", "## Products", "");
      products.slice(0, 50).forEach(u => lines.push(`- ${u}`));
      if (products.length > 50) lines.push(`- ... and ${products.length - 50} more`);
    }
    lines.push("", "## API Endpoints", "");
    FUNCTION_URL_GRID.forEach(f => lines.push(`- [${f.name}](${SITE_BASE}${f.url})`));

    const body = lines.join("\n");
    return etagOk(body, CT_TXT, request, { 'Access-Control-Allow-Origin':'*' });
  } catch(e){
    return http(500, withVersion({ 'Content-Type': CT_TXT }), `error: ${String(e?.message||e)}`);
  }
}

export async function get_llms(request){
  try{
    const [livePages, blogs, products] = await Promise.all([ getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls() ]);
    const lines = [
      "source: wecare.digital feed",
      `site: ${SITE_BASE}`,
      `alias: ${ALT_ORIGIN}`,
      "sub: https://selfcare.wecare.digital",
      "wildcard: *.wecare.digital",
      "",
      "## static"
    ];
    DATA.pages.forEach(p => lines.push(`- ${SITE_BASE}${p.path}`));
    lines.push("", "## pages (wix)");  livePages.forEach(u => lines.push(`- ${u}`));
    lines.push("", "## blog (wix)");   blogs.forEach(u => lines.push(`- ${u}`));
    lines.push("", "## products (wix)"); products.forEach(u => lines.push(`- ${u}`));
    const body = lines.join("\n");
    return etagOk(body, CT_TXT, request, { 'Access-Control-Allow-Origin':'*', ...NOINDEX });
  } catch(e){
    return http(500, withVersion({ 'Content-Type': CT_TXT, ...NOINDEX }), `error: ${String(e?.message||e)}`);
  }
}
export async function get_llmslong(request){
  try{
    const [livePages, blogs, products] = await Promise.all([ getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls() ]);
    const lines = [
      "source: wecare.digital feed",
      "",
      "## sites",
      `- ${SITE_BASE}`,
      `- ${ALT_ORIGIN}`,
      "- https://selfcare.wecare.digital",
      "- *.wecare.digital",
      "",
      "## org",
      JSON.stringify({ name:DATA.org.name, email:DATA.org.email, telephone:DATA.org.telephone, address:DATA.org.addressOneLine }),
      "",
      "## static pages"
    ];
    DATA.pages.forEach(p => lines.push(`- ${SITE_BASE}${p.path}`));
    lines.push("", "## pages (wix)");  livePages.forEach(u => lines.push(`- ${u}`));
    lines.push("", "## blog (wix)");   blogs.forEach(u => lines.push(`- ${u}`));
    lines.push("", "## products (wix)"); products.forEach(u => lines.push(`- ${u}`));
    lines.push("", "## functions"); FUNCTION_URL_GRID.forEach(f => lines.push(`- ${SITE_BASE}${f.url}`));
    lines.push("", "## icons");     ICON_GRID.forEach(i => lines.push(`- ${i}`));
    const body = lines.join("\n");
    return etagOk(body, CT_TXT, request, { 'Access-Control-Allow-Origin':'*', ...NOINDEX });
  } catch(e){
    return http(500, withVersion({ 'Content-Type': CT_TXT, ...NOINDEX }), `error: ${String(e?.message||e)}`);
  }
}
export async function get_aiindex(request){
  try{
    const [livePages, blogs, products] = await Promise.all([ getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls() ]);
    const payload = {
      site: SITE_BASE, language: LANGUAGE, hreflang: HREFLANGS, defaultImageAlt: DEFAULT_IMAGE_ALT,
      static: DATA.pages.map(p=>({ url:`${SITE_BASE}${p.path}`, title:p.title, description:p.meta, keywords: p.keywords?.primary || [] })),
      pages: livePages, blog: blogs, products: products,
      icons: ICON_GRID, social: DATA.social,
      functions: FUNCTION_URL_GRID.map(f => `${SITE_BASE}${f.url}`),
      canonicalParamsRemoved: CANONICAL_PARAMS_TO_STRIP.concat(["appSectionParams(origin=wixcode)"])
    };
    const body = JSON.stringify(payload);
    return etagOk(body, CT_JSON, request, { 'Access-Control-Allow-Origin':'*', ...NOINDEX });
  } catch(e){
    return http(500, H_JSON, { ok:false, error:String(e?.message||e) });
  }
}

/* OPTIONS preflight for browser calls */
export function options_llms()            { return corsPreflight(); }
export function options_llmslong()        { return corsPreflight(); }
export function options_llmstxt()         { return corsPreflight(); }
export function options_aiindex()         { return corsPreflight(); }
export function options_pagemeta()        { return corsPreflight(); }
export function options_pagehead()        { return corsPreflight(); }
export function options_seohead()         { return corsPreflight(); }
export function options_keywordscloud()   { return corsPreflight(); }
export function options_keywordscommon()  { return corsPreflight(); }
export function options_keywordsrelated() { return corsPreflight(); }
export function options_keywordsglobal()  { return corsPreflight(); }
export function options_keywordsmeta()    { return corsPreflight(); }

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   5) Canonicalization & Diagnostics
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
export function get_canonicalize(request){
  const url = request.query?.url;
  if (!url) return http(400, NO_CACHE, { ok:false, reason:"url param required" });
  const { canonical, removed } = stripParams(url);
  const original = url;
  const changed  = original !== canonical;
  return ok({ headers: H_JSON, body:{ ok:true, original, canonical, changed, removed }});
}
export function get_discovery(request){
  return ok({ headers: H_JSON, body:{
    ok:true, count: FUNCTION_URL_GRID.length,
    functions: FUNCTION_URL_GRID.map(f => ({ name:f.name, url:`${SITE_BASE}${f.url}` }))
  }});
}
function findDuplicateTitles(arr){
  const map = new Map();
  arr.forEach(i => { const t = (i.title||"").trim(); if (!t) return; if(!map.has(t)) map.set(t,[]); map.get(t).push(i.url); });
  const out = [];
  map.forEach((urls, title)=>{ if (urls.length>1) out.push({ title, urls }); });
  return out;
}

const PING_SECRET = "";
function requireAuth(request){
  if (!PING_SECRET) return true;
  const hdr = request?.headers?.['x-wecare-key'] || request?.headers?.['X-WeCare-Key'];
  const q   = request?.query?.key;
  return (hdr && hdr === PING_SECRET) || (q && q === PING_SECRET);
}
export async function get_diag(request){
  if (!requireAuth(request)) return http(403, NO_CACHE, { ok:false });
  const [pages, blogs, products] = await Promise.all([ getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls() ]);
  const dups = findDuplicateTitles(DATA.pages.map(p=>({ url:`${SITE_BASE}${p.path}`, title:p.title })));
  return ok({ headers: H_NOINDEX, body:{
    ok:true,
    totals: { static: DATA.pages.length, livePages: pages.length, blog: blogs.length, products: products.length, functions: FUNCTION_URL_GRID.length },
    duplicates: dups
  }});
}
export async function get_seoerrors(request){
  if (!requireAuth(request)) return http(403, NO_CACHE, { ok:false });
  const missingMeta = DATA.pages.filter(p => !p.meta || !p.title);
  const missingKW   = DATA.pages.filter(p => !p.keywords || !p.keywords.primary || !p.keywords.primary.length);
  const missingBC   = DATA.pages.filter(p => !BREADCRUMB_GRID[p.path]);
  return ok({ headers: H_NOINDEX, body:{
    ok:true,
    missing: { metaOrTitle: missingMeta.map(p=>p.path), keywords: missingKW.map(p=>p.path), breadcrumbs: missingBC.map(p=>p.path) },
    blockedCount: BLOCKED_URLS.size
  }});
}
export async function get_selftest(request){
  if (!requireAuth(request)) return http(403, NO_CACHE, { ok:false });
  const sample = [
    `${SITE_BASE}/_functions/sitemap`,
    `${SITE_BASE}/_functions/smextra`,
    `${SITE_BASE}/_functions/robots`,
    `${SITE_BASE}/_functions/seohead?path=/`,
    `${SITE_BASE}/_functions/aiindex`,
    `${SITE_BASE}/_functions/faq`,
    `${SITE_BASE}/pages-sitemap.xml`
  ];
  const results = [];
  for (const url of sample){
    try {
      const res = await fetch(url, { method:"get" });
      results.push({ url, status: res.status, ok: res.ok });
      await res.text().catch(()=>null);
    } catch(e){
      results.push({ url, status: 0, ok: false, error: String(e?.message||e) });
    }
  }
  return ok({ headers: H_NOINDEX, body:{ ok:true, results }});
}
async function runPingTargets(){
  const urls = [
    `${SITE_BASE}/_functions/robots`,
    `${SITE_BASE}/_functions/smindex`,
    `${SITE_BASE}/_functions/sitemap`,
    `${SITE_BASE}/_functions/smextra`,
    `${SITE_BASE}/_functions/smtxt`,
    `${SITE_BASE}/_functions/llms`,
    `${SITE_BASE}/_functions/llmslong`,
    `${SITE_BASE}/_functions/llmstxt`,
    `${SITE_BASE}/_functions/aiindex`,
    `${SITE_BASE}/_functions/faq`,
    `${SITE_BASE}/_functions/siteinfo`,
    `${SITE_BASE}/_functions/discovery`,
    `${SITE_BASE}/_functions/pagemeta`,
    `${SITE_BASE}/_functions/pagehead`,
    `${SITE_BASE}/_functions/seohead?path=/`,
    `${SITE_BASE}/_functions/seohead?path=/blog/example-slug&relaxed=1`,
    `${SITE_BASE}/_functions/canonicalize?url=${encodeURIComponent(`${SITE_BASE}/?utm_source=x`)}`,
    `${SITE_BASE}/_functions/seoerrors`,
    `${SITE_BASE}/_functions/keywordscloud`,
    `${SITE_BASE}/_functions/keywordscommon`,
    `${SITE_BASE}/_functions/keywordsrelated`,
    `${SITE_BASE}/_functions/keywordsglobal`,
    `${SITE_BASE}/_functions/keywordsmeta`,
    `${SITE_BASE}/_functions/rss`,
    `${SITE_BASE}/_functions/rssblog`,
    `${SITE_BASE}/_functions/rssproducts`,
    `${SITE_BASE}/_functions/products?limit=1`,
    `${SITE_BASE}/_functions/orders?limit=1`,
    `${SITE_BASE}/_functions/collections?limit=1`,
    `${SITE_BASE}/_functions/stats`,
    `${SITE_BASE}/pages-sitemap.xml`,
    `${SITE_BASE}/blog-categories-sitemap.xml`,
    `${SITE_BASE}/blog-tags-sitemap.xml`,
    `${SITE_BASE}/blog-posts-sitemap.xml`,
    `${SITE_BASE}/store-products-sitemap.xml`
  ];
  const out = [];
  for (const url of urls){
    try{
      const res = await fetch(url, { method:"get" });
      await res.text().catch(()=>null);
      out.push({ url, status: res.status, ok: res.ok });
    }catch(e){
      out.push({ url, status:0, ok:false, error:String(e?.message||e) });
    }
  }
  return out;
}
export async function get_ping(request){
  if (!requireAuth(request)) return http(403, NO_CACHE, { ok:false });
  const results = await runPingTargets();
  return ok({ headers: H_NOINDEX, body:{ ok:true, ran:new Date().toISOString(), results }});
}
export async function get_pin(request){    return get_ping(request); }
export async function get_pingnow(request){ return get_ping(request); }

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   6) Keywords & CSV
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
function toCSV(rows, cols){
  const esc = (v)=> {
    const s = (v==null?"":String(v));
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g,'""')}"`;
    return s;
  };
  const head = cols.map(esc).join(",");
  const body = rows.map(r => cols.map(c => esc(r[c])).join(",")).join("\n");
  return `${head}\n${body}\n`;
}
function keywordCloudFromPages(){
  const map = new Map();
  DATA.pages.forEach(p=>{
    const all = []
      .concat(DATA.keywords.global)
      .concat(DATA.keywords.common)
      .concat(p.keywords?.primary||[])
      .concat(p.keywords?.related||[]);
    all.forEach(term=>{
      const t = term.toLowerCase().trim();
      if (!t) return;
      map.set(t, (map.get(t)||0) + 1);
    });
  });
  const out = Array.from(map.entries()).map(([term,count])=>({ term,count })).sort((a,b)=>b.count-a.count);
  return out;
}
function keywordCommon(){
  const cloud = keywordCloudFromPages();
  const total = DATA.pages.length || 1;
  return cloud.map(r => ({ term:r.term, count:r.count, share: +(r.count/total).toFixed(3) }));
}
function keywordRelatedPairs(){
  const groups = DATA.keywords.relatedGroups || {};
  const pairs = [];
  Object.keys(groups).forEach(g=>{
    const arr = (groups[g]||[]).map(s=>s.toLowerCase());
    for (let i=0;i<arr.length;i++){
      for (let j=i+1;j<arr.length;j++){
        pairs.push({ a:arr[i], b:arr[j], score:1, count:1 });
      }
    }
  });
  return pairs;
}
export function get_keywordscloud(request){
  const format = (request.query?.format||"json").toLowerCase();
  const ranked = keywordCloudFromPages();
  if (format==="csv"){
    return ok({ headers: csvHeaders('keywords-cloud.csv'), body: toCSV(ranked, ['term','count']) });
  }
  return ok({ headers: H_JSON, body:{ ok:true, cloud: ranked }});
}
export function get_keywordscommon(request){
  const format = (request.query?.format||"json").toLowerCase();
  const ranked = keywordCommon();
  if (format==="csv"){
    return ok({ headers: csvHeaders('keywords-common.csv'), body: toCSV(ranked, ['term','count','share']) });
  }
  return ok({ headers: H_JSON, body:{ ok:true, common: ranked }});
}
export function get_keywordsrelated(request){
  const format = (request.query?.format||"json").toLowerCase();
  const pairs = keywordRelatedPairs();
  if (format==="csv"){
    return ok({ headers: csvHeaders('keywords-related.csv'), body: toCSV(pairs, ['a','b','score','count']) });
  }
  return ok({ headers: H_JSON, body:{ ok:true, related: pairs }});
}
export function get_keywordsglobal(request){
  const format = (request.query?.format||"json").toLowerCase();
  const view   = (request.query?.view||"cloud").toLowerCase();
  const cloud   = keywordCloudFromPages();
  const common  = keywordCommon();
  const related = keywordRelatedPairs();
  if (format==="csv"){
    if (view==="common"){
      return ok({ headers: csvHeaders('keywords-global-common.csv'), body: toCSV(common, ['term','count','share']) });
    } else if (view==="related"){
      return ok({ headers: csvHeaders('keywords-global-related.csv'), body: toCSV(related, ['a','b','score','count']) });
    } else {
      return ok({ headers: csvHeaders('keywords-global-cloud.csv'), body: toCSV(cloud, ['term','count']) });
    }
  }
  return ok({ headers: H_JSON, body:{ ok:true, view, cloud, common, related }});
}
export function get_keywordsmeta(request){
  const format = (request.query?.format||"json").toLowerCase();
  const view   = (request.query?.view||"pages").toLowerCase();
  const perPage = DATA.pages.map(p => ({
    url:`${SITE_BASE}${p.path}`,
    title: p.title || "",
    description: p.meta || "",
    tokens: (p.keywords?.primary||[]).concat(p.keywords?.related||[])
  }));
  const cloud  = keywordCloudFromPages();
  const common = keywordCommon();
  if (format==="csv"){
    if (view==="pages"){
      const flat = perPage.map(p=>({ url:p.url, title:p.title, description:p.description, keywords: p.tokens.join(' ') }));
      return ok({ headers: csvHeaders('keywords-meta-pages.csv'), body: toCSV(flat, ['url','title','description','keywords']) });
    } else if (view==="common"){
      return ok({ headers: csvHeaders('keywords-meta-common.csv'), body: toCSV(common, ['term','count','share']) });
    } else {
      return ok({ headers: csvHeaders('keywords-meta-cloud.csv'), body: toCSV(cloud, ['term','count']) });
    }
  }
  return ok({ headers: H_JSON, body:{ ok:true, view, pages: perPage, cloud, common }});
}

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   7) RSS Feeds (XML + ETag)
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
function rssHeader({ title, link, selfHref, description }){
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(title)}</title>
    <link>${link}</link>
    <description>${escapeXml(description || title)}</description>
    <atom:link href="${selfHref}" rel="self" type="application/rss+xml" />`;
}
function rssFooter(){ return `  </channel>\n</rss>`; }
function escapeXml(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function rssItem({ link, guid, title, pubDate }){
  const t = title || link;
  const d = pubDate ? new Date(pubDate).toUTCString() : new Date().toUTCString();
  return `
    <item>
      <title>${escapeXml(t)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${guid || link}</guid>
      <pubDate>${d}</pubDate>
    </item>`;
}

export async function get_rss(request){
  const [livePages, blogs, products] = await Promise.all([
    getLivePagesFromSitemap(), getDynamicBlogUrls(), getDynamicProductUrls()
  ]);
  const items = new Set();
  DATA.pages.forEach(p => items.add(`${SITE_BASE}${p.path}`));
  livePages.forEach(u => items.add(u));
  blogs.forEach(u => items.add(u));
  products.forEach(u => items.add(u));
  const arr = Array.from(items);
  const feed = [
    rssHeader({ title: "WECARE.DIGITAL ΓÇö Site Feed", link: SITE_BASE, selfHref: `${SITE_BASE}/_functions/rss`, description: "Site-wide updates (static, blog, products)" }),
    ...arr.map(u => rssItem({ link:u, guid:u, title:u.split('/').filter(Boolean).pop() })),
    rssFooter()
  ].join('\n');
  return etagOk(feed, CT_XML, request);
}

export async function get_rssblog(request){
  const xmlCats = await fetchTextMaybe(`${SITE_BASE}/blog-categories-sitemap.xml`);
  const xmlTags = await fetchTextMaybe(`${SITE_BASE}/blog-tags-sitemap.xml`);
  const xmlPosts= await fetchTextMaybe(`${SITE_BASE}/blog-posts-sitemap.xml`);
  const urls = [
    ...extractLocs(xmlPosts),
    ...extractLocs(xmlCats),
    ...extractLocs(xmlTags)
  ];
  const seen = new Set();
  const items = [];
  for (const {loc,lastmod} of urls){
    if (BLOCKED_URLS.has(loc) || seen.has(loc)) continue;
    seen.add(loc);
    items.push(rssItem({ link: loc, guid: loc, title: loc.split('/').filter(Boolean).pop(), pubDate: lastmod }));
  }
  const feed = [
    rssHeader({ title: "WECARE.DIGITAL ΓÇö Blog Feed", link: `${SITE_BASE}/blog`, selfHref: `${SITE_BASE}/_functions/rssblog`, description: "All blog posts, categories, and tags" }),
    ...items,
    rssFooter()
  ].join('\n');
  return etagOk(feed, CT_XML, request);
}

export async function get_rssproducts(request){
  const xml = await fetchTextMaybe(`${SITE_BASE}/store-products-sitemap.xml`);
  const urls = extractLocs(xml);
  const items = urls
    .filter(({loc}) => !BLOCKED_URLS.has(loc))
    .map(({loc,lastmod}) => rssItem({ link: loc, guid: loc, title: loc.split('/').filter(Boolean).pop(), pubDate: lastmod }));
  const feed = [
    rssHeader({ title: "WECARE.DIGITAL ΓÇö Products Feed", link: `${SITE_BASE}/products`, selfHref: `${SITE_BASE}/_functions/rssproducts`, description: "All published product pages" }),
    ...items,
    rssFooter()
  ].join('\n');
  return etagOk(feed, CT_XML, request);
}

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
   8) Store API ΓÇö WECARE Integration Endpoints
   Auth via X-Api-Key header validated against Wix Secret "WECARE_API_KEY"
   ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */
const STORE_CORS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-Api-Key, Authorization',
  'X-WeCare-Version': VERSION
};

async function storeAuth(request) {
  try {
    const secret = await getSecret('WECARE_API_KEY');
    const apiKey = request.headers['x-api-key'];
    return apiKey === secret;
  } catch {
    return true; // Dev mode: allow all if secret not configured
  }
}

function storeJson(data) {
  return ok({ body: JSON.stringify(data), headers: STORE_CORS });
}
function storeErr400(msg) {
  return badRequest({ body: JSON.stringify({ error: msg }), headers: STORE_CORS });
}
function storeErr500(e) {
  return serverError({ body: JSON.stringify({ error: e.message }), headers: STORE_CORS });
}

// CORS preflight for store endpoints
export function options_products()    { return options({ headers: STORE_CORS }); }
export function options_product()     { return options({ headers: STORE_CORS }); }
export function options_orders()      { return options({ headers: STORE_CORS }); }
export function options_order()       { return options({ headers: STORE_CORS }); }
export function options_collections() { return options({ headers: STORE_CORS }); }
export function options_inventory()   { return options({ headers: STORE_CORS }); }
export function options_inventoryAll(){ return options({ headers: STORE_CORS }); }
export function options_stats()       { return options({ headers: STORE_CORS }); }

function formatProduct(p) {
  return {
    _id: p._id,
    name: p.name,
    description: p.description,
    price: p.price,
    formattedPrice: p.formattedPrice,
    discountedPrice: p.discountedPrice,
    formattedDiscountedPrice: p.formattedDiscountedPrice,
    currency: p.currency,
    sku: p.sku,
    ribbon: p.ribbon,
    brand: p.brand,
    weight: p.weight,
    inStock: p.inStock,
    quantityInStock: p.quantityInStock,
    trackInventory: p.trackInventory,
    productType: p.productType,
    slug: p.slug,
    visible: p.visible,
    mainMedia: p.mainMedia,
    mediaItems: p.mediaItems,
    collections: (p.collections || []).map(c => ({ _id: c._id, name: c.name })),
    customTextFields: p.customTextFields,
    productOptions: p.productOptions,
    variants: p.variants,
    additionalInfoSections: p.additionalInfoSections,
    createdDate: p._createdDate,
    lastUpdated: p._updatedDate,
  };
}

function formatOrder(o) {
  const buyerEmail = o.buyerInfo?.email || '';
  const buyerPhone = o.billingInfo?.phone || o.buyerInfo?.phone || '';
  const buyerName = [
    o.billingInfo?.firstName || o.buyerInfo?.firstName || '',
    o.billingInfo?.lastName || o.buyerInfo?.lastName || '',
  ].filter(Boolean).join(' ');
  const customOrderNumber = o.customField?.value || '';
  const lineItemsSummary = (o.lineItems || []).map(item => ({
    name: item.name || item.productName || '',
    quantity: item.quantity || 0,
    price: item.price || item.priceData?.price || 0,
    totalPrice: item.totalPrice || item.priceData?.totalPrice || 0,
    sku: item.sku || '',
    weight: item.weight || 0,
    mediaItem: item.mediaItem || null,
    customTextFields: item.customTextFields || [],
    options: item.options || [],
  }));

  return {
    _id: o._id,
    number: o.number,
    customOrderNumber,
    customField: o.customField,
    buyerEmail,
    buyerPhone,
    buyerName,
    buyerInfo: o.buyerInfo,
    buyerNote: o.buyerNote || '',
    billingInfo: o.billingInfo,
    shippingInfo: o.shippingInfo,
    lineItems: o.lineItems,
    lineItemsSummary,
    lineItemCount: (o.lineItems || []).length,
    totals: o.totals,
    currency: o.currency || 'INR',
    weightUnit: o.weightUnit || 'KG',
    paymentStatus: o.paymentStatus || '',
    fulfillmentStatus: o.fulfillmentStatus || '',
    fulfillments: o.fulfillments || [],
    activities: o.activities || [],
    channelInfo: o.channelInfo,
    enteredBy: o.enteredBy,
    cartId: o.cartId,
    refunds: o.refunds || [],
    subscriptionInfo: o.subscriptionInfo,
    archived: o.archived || false,
    read: o.read || false,
    buyerLanguage: o.buyerLanguage || '',
    dateCreated: o._dateCreated,
    dateUpdated: o._updatedDate,
  };
}

// GET /products
export async function get_products(request) {
  if (!(await storeAuth(request))) return forbidden({ body: 'Unauthorized' });
  try {
    const limit = Math.min(Number(request.query.limit) || 100, 100);
    const skip = Number(request.query.skip) || 0;
    const search = request.query.search || '';
    const collectionId = request.query.collectionId || '';
    const sortField = request.query.sort || '_updatedDate';
    const sortDir = request.query.dir || 'desc';

    let query = wixData.query('Stores/Products')
      .include('collections')
      .limit(limit)
      .skip(skip);

    if (search) { query = query.contains('name', search); }
    if (collectionId) { query = query.hasSome('collections', [collectionId]); }
    if (sortDir === 'asc') { query = query.ascending(sortField); }
    else { query = query.descending(sortField); }

    const results = await query.find();
    return storeJson({
      products: results.items.map(formatProduct),
      totalCount: results.totalCount,
      hasNext: results.hasNext(),
      skip, limit,
    });
  } catch (e) { return storeErr500(e); }
}

// GET /product
export async function get_product(request) {
  if (!(await storeAuth(request))) return forbidden({ body: 'Unauthorized' });
  try {
    const id = request.query.id;
    if (!id) return storeErr400('id is required');
    const results = await wixData.query('Stores/Products')
      .include('collections')
      .eq('_id', id)
      .find();
    if (results.items.length === 0) return storeErr400('Product not found');
    return storeJson({ product: formatProduct(results.items[0]) });
  } catch (e) { return storeErr500(e); }
}

// GET /orders
export async function get_orders(request) {
  if (!(await storeAuth(request))) return forbidden({ body: 'Unauthorized' });
  try {
    const limit = Math.min(Number(request.query.limit) || 50, 100);
    const skip = Number(request.query.skip) || 0;
    const paymentStatus = request.query.paymentStatus || '';
    const fulfillmentStatus = request.query.fulfillmentStatus || '';
    const email = request.query.email || '';
    const orderNumber = request.query.orderNumber || '';
    const customOrderNumber = request.query.customOrderNumber || '';
    const dateFrom = request.query.dateFrom || '';
    const dateTo = request.query.dateTo || '';

    let query = wixData.query('Stores/Orders')
      .descending('_dateCreated')
      .limit(limit)
      .skip(skip);

    if (paymentStatus) { query = query.eq('paymentStatus', paymentStatus); }
    if (fulfillmentStatus) { query = query.eq('fulfillmentStatus', fulfillmentStatus); }
    if (orderNumber) { query = query.eq('number', Number(orderNumber)); }
    if (dateFrom) { query = query.ge('_dateCreated', new Date(dateFrom)); }
    if (dateTo) { query = query.le('_dateCreated', new Date(dateTo)); }

    const results = await query.find({ suppressAuth: true });
    let orders = results.items.map(formatOrder);

    if (email) {
      const emailLower = email.toLowerCase();
      orders = orders.filter(o => o.buyerEmail && o.buyerEmail.toLowerCase().includes(emailLower));
    }
    if (customOrderNumber) {
      orders = orders.filter(o =>
        o.customOrderNumber === customOrderNumber || String(o.number) === customOrderNumber
      );
    }

    return storeJson({
      orders, totalCount: results.totalCount,
      hasNext: results.hasNext(), skip, limit,
    });
  } catch (e) { return storeErr500(e); }
}

// GET /order
export async function get_order(request) {
  if (!(await storeAuth(request))) return forbidden({ body: 'Unauthorized' });
  try {
    const id = request.query.id;
    if (!id) return storeErr400('id is required');
    const order = await wixData.get('Stores/Orders', id, { suppressAuth: true });
    if (!order) return storeErr400('Order not found');
    return storeJson({ order: formatOrder(order) });
  } catch (e) { return storeErr500(e); }
}

// GET /collections
export async function get_collections(request) {
  if (!(await storeAuth(request))) return forbidden({ body: 'Unauthorized' });
  try {
    const limit = Math.min(Number(request.query.limit) || 100, 100);
    const skip = Number(request.query.skip) || 0;
    const results = await wixData.query('Stores/Collections')
      .limit(limit).skip(skip).find();
    return storeJson({
      collections: results.items.map(c => ({
        _id: c._id, name: c.name, description: c.description,
        mainMedia: c.mainMedia, slug: c.slug, numberOfProducts: c.numberOfProducts,
      })),
      totalCount: results.totalCount, hasNext: results.hasNext(),
    });
  } catch (e) { return storeErr500(e); }
}

// GET /inventory
export async function get_inventory(request) {
  if (!(await storeAuth(request))) return forbidden({ body: 'Unauthorized' });
  try {
    const productId = request.query.productId;
    if (!productId) return storeErr400('productId is required');
    const results = await wixData.query('Stores/InventoryItems')
      .eq('productId', productId).find({ suppressAuth: true });
    return storeJson({ productId, inventoryItems: results.items, totalCount: results.totalCount });
  } catch (e) { return storeErr500(e); }
}

// GET /inventoryAll
export async function get_inventoryAll(request) {
  if (!(await storeAuth(request))) return forbidden({ body: 'Unauthorized' });
  try {
    const limit = Math.min(Number(request.query.limit) || 100, 100);
    const skip = Number(request.query.skip) || 0;
    const inStockFilter = request.query.inStock;
    let query = wixData.query('Stores/InventoryItems').limit(limit).skip(skip);
    if (inStockFilter === 'true') { query = query.gt('quantity', 0); }
    else if (inStockFilter === 'false') { query = query.eq('quantity', 0); }
    const results = await query.find({ suppressAuth: true });
    return storeJson({ inventoryItems: results.items, totalCount: results.totalCount, hasNext: results.hasNext() });
  } catch (e) { return storeErr500(e); }
}

// GET /stats
export async function get_stats(request) {
  if (!(await storeAuth(request))) return forbidden({ body: 'Unauthorized' });
  try {
    const [productCount, orders, collectionCount] = await Promise.all([
      wixData.query('Stores/Products').count(),
      wixData.query('Stores/Orders').find({ suppressAuth: true }),
      wixData.query('Stores/Collections').count(),
    ]);
    let totalRevenue = 0, paidOrders = 0, pendingOrders = 0, fulfilledOrders = 0;
    for (const order of orders.items) {
      if (order.totals && order.totals.total) { totalRevenue += Number(order.totals.total) || 0; }
      if (order.paymentStatus === 'PAID') paidOrders++;
      if (order.paymentStatus === 'NOT_PAID' || order.paymentStatus === 'PENDING') pendingOrders++;
      if (order.fulfillmentStatus === 'FULFILLED') fulfilledOrders++;
    }
    return storeJson({
      productCount, orderCount: orders.totalCount, collectionCount,
      totalRevenue, paidOrders, pendingOrders, fulfilledOrders,
      currency: orders.items[0]?.currency || 'INR',
    });
  } catch (e) { return storeErr500(e); }
}