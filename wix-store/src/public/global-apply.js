/**************************************************************
 * public/global-apply.js
 * Apply backend-driven SEO:
 *  - Title / Meta description / Keywords
 *  - Canonical (with /canonicalize fallback) & Hreflang
 *  - Open Graph + Twitter (incl. og:locale, image alt)
 *  - JSON-LD: full graph (/seohead) + blog/product stubs + Org + WebSite
 *  - FAQ: full on /faq and page-scoped via pathHints elsewhere
 *  - RSS autodiscovery: /_functions/rss, /_functions/rssblog, /_functions/rssproducts
 *  - SPA-safe (wixLocation.onChange) with de-duped SD
 **************************************************************/
import wixLocation from 'wix-location-frontend';
import wixWindow from 'wix-window-frontend';
import { seo } from 'wix-seo-frontend';

const HREFLANGS = ['en-IN','en-US','x-default'];
const OG_LOCALE = 'en_IN';
const OG_LOCALE_ALT = ['en_US'];

function getPath() {
  const parts = (wixLocation.path || []);
  return '/' + parts.join('/');
}
function isBlogPath(path)    { return path.startsWith('/blog'); }
function isProductPath(path) { return path.includes('/product'); }
function isDynamicPath(path) { return isBlogPath(path) || isProductPath(path); }

async function fetchJSON(url) {
  try {
    const res = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json().catch(() => null);
  } catch { return null; }
}
async function fetchText(url) {
  try {
    const res = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
    if (!res.ok) return null;
    return await res.text().catch(() => null);
  } catch { return null; }
}
async function fetchLD(url) {
  const t = await fetchText(url);
  if (!t) return null;
  try { return JSON.parse(t); } catch { return null; }
}

/* ---------- Safe meta setters ---------- */
function safeSetTitle(title){
  if (!title) return;
  try { if (seo.setTitle) { seo.setTitle(title); return; } } catch {}
  try { document.title = title; } catch {}
}
function safeSetDescription(desc){
  if (!desc) return;
  try { if (seo.setDescription) { seo.setDescription(desc); return; } } catch {}
  try {
    let el = document.head.querySelector('meta[name="description"]');
    if (!el) { el = document.createElement('meta'); el.setAttribute('name','description'); document.head.appendChild(el); }
    el.setAttribute('content', desc);
  } catch {}
}
function safeSetKeywords(arr){
  const content = Array.isArray(arr) ? arr.join(', ') : String(arr||'').trim();
  if (!content) return;
  try { if (seo.setMetaTags) { seo.setMetaTags([{ name:'keywords', content }]); return; } } catch {}
  try {
    let el = document.head.querySelector('meta[name="keywords"]');
    if (!el) { el = document.createElement('meta'); el.setAttribute('name','keywords'); document.head.appendChild(el); }
    el.setAttribute('content', content);
  } catch {}
}
function setMetaName(name, content){
  if (!content) return;
  try{
    let el = document.head.querySelector(`meta[name="${name}"]`);
    if (!el){ el = document.createElement('meta'); el.setAttribute('name', name); document.head.appendChild(el); }
    el.setAttribute('content', content);
  }catch{}
}
function setMetaProp(prop, content){
  if (!content) return;
  try{
    let el = document.head.querySelector(`meta[property="${prop}"]`);
    if (!el){ el = document.createElement('meta'); el.setAttribute('property', prop); document.head.appendChild(el); }
    el.setAttribute('content', content);
  }catch{}
}
function setLink(rel, attrs = {}){
  try{
    let sel = `link[rel="${rel}"]`;
    if (attrs.href) sel += `[href="${attrs.href}"]`;
    let el = document.head.querySelector(sel);
    if (!el){ el = document.createElement('link'); el.setAttribute('rel', rel); document.head.appendChild(el); }
    Object.entries(attrs).forEach(([k,v])=>{ if (v!=null && v!=='') el.setAttribute(k, v); });
  }catch{}
}
function removeLinks(selector){
  try{ document.querySelectorAll(selector).forEach(n => n.parentNode && n.parentNode.removeChild(n)); }catch{}
}

/* ---------- Canonical & Hreflang ---------- */
async function setCanonicalLinkWithFallback(canonical){
  let href = canonical || '';
  try {
    if (!href) href = location.href;
    // normalize via backend canonicalizer
    const norm = await fetchJSON(`/_functions/canonicalize?url=${encodeURIComponent(href)}`);
    if (norm && norm.ok && norm.canonical){ href = norm.canonical; }
  } catch {}
  if (href) {
    // clear any prior canonical we added
    removeLinks('link[rel="canonical"].x-wc');
    const link = document.createElement('link');
    link.setAttribute('rel','canonical');
    link.setAttribute('href', href);
    link.className = 'x-wc';
    try{ document.head.appendChild(link); }catch{}
  }
  return href;
}
function setHreflangLinks(canonical, langs = HREFLANGS){
  if (!canonical) return;
  // clear previous alternates we added
  removeLinks('link[rel="alternate"][hreflang].x-wc');
  (langs || HREFLANGS).forEach(h => {
    const link = document.createElement('link');
    link.setAttribute('rel','alternate');
    link.setAttribute('hreflang', h);
    link.setAttribute('href', canonical);
    link.className = 'x-wc';
    try{ document.head.appendChild(link); }catch{}
  });
}

/* ---------- Open Graph & Twitter ---------- */
async function setSocialTags({ url, title, description, image, imageAlt = 'WECARE.DIGITAL', type='website', siteName='WECARE.DIGITAL' }){
  if (!image){
    try{
      const icons = await fetchJSON('/_functions/icons');
      if (icons && Array.isArray(icons.icons)) {
        const png = icons.icons.find(u => u.endsWith('.png'));
        image = png || image;
      }
    }catch{}
  }
  setMetaProp('og:url', url);
  setMetaProp('og:type', type);
  setMetaProp('og:site_name', siteName);
  setMetaProp('og:title', title);
  setMetaProp('og:description', description);
  if (image){ setMetaProp('og:image', image); setMetaProp('og:image:alt', imageAlt); }
  setMetaProp('og:locale', OG_LOCALE);
  OG_LOCALE_ALT.forEach(loc => setMetaProp('og:locale:alternate', loc));

  setMetaName('twitter:card', image ? 'summary_large_image' : 'summary');
  setMetaName('twitter:title', title);
  setMetaName('twitter:description', description);
  if (image) setMetaName('twitter:image', image);
  setMetaName('twitter:site', '@wecaredigital');
}

/* ---------- JSON-LD helpers ---------- */
function applyStructuredData(graphOrNode){
  if (!graphOrNode) return;
  try {
    if (Array.isArray(graphOrNode)) {
      if (seo.setStructuredData) seo.setStructuredData(graphOrNode);
      else graphOrNode.forEach(n => injectScriptLD(n));
    } else {
      if (seo.addStructuredData) seo.addStructuredData(graphOrNode);
      else injectScriptLD(graphOrNode);
    }
    // marker for other modules to skip double-inject
    try { window.__WECARE_SD_FROM_GLOBAL__ = true; } catch {}
  } catch {
    // fallback
    injectScriptLD(graphOrNode);
  }
}
function injectScriptLD(node){
  try{
    const s = document.createElement('script');
    s.type = 'application/ld+json';
    s.className = 'x-wc';
    s.textContent = JSON.stringify(node);
    document.head.appendChild(s);
  }catch{}
}

/* ---------- FAQ: page-scoped via pathHints ---------- */
async function addPerPageFAQ(path){
  const payload = await fetchJSON('/_functions/faq');
  if (!payload || !payload.faqs) return;
  const buckets = payload.faqs;
  const matches = [];
  Object.keys(buckets).forEach(section => {
    const list = Array.isArray(buckets[section]) ? buckets[section] : [];
    list.forEach(item => {
      const hints = Array.isArray(item.pathHints) ? item.pathHints : [];
      if (hints.includes(path)) matches.push(item);
    });
  });
  if (!matches.length) return;
  const faqSchema = {
    "@context":"https://schema.org",
    "@type":"FAQPage",
    "mainEntity": matches.map(m => ({
      "@type":"Question",
      "name": m.q,
      "acceptedAnswer": { "@type":"Answer", "text": m.a }
    }))
  };
  applyStructuredData(faqSchema);
}

/* ---------- Org + WebSite nodes (always present) ---------- */
async function addOrgAndSiteNodes(){
  const origin = (typeof location !== 'undefined' ? location.origin : 'https://www.wecare.digital');
  const ORG_ID  = `${origin}/#org`;
  const SITE_ID = `${origin}/#website`;

  const org = await fetchJSON('/_functions/contact');
  if (org){
    applyStructuredData({
      "@context":"https://schema.org",
      "@type":["Organization","LocalBusiness"],
      "@id": ORG_ID,
      "name": org.name,
      "url":  org.url || origin + '/',
      "email": org.email,
      "telephone": org.telephone,
      "logo": org.logo,
      "image": org.image,
      "address": org.address,
      "sameAs": org.sameAs || org.social || []
    });
  }
  const siteNode = {
    "@context":"https://schema.org",
    "@type":"WebSite",
    "@id": SITE_ID,
    "url": origin,
    "name": "WECARE.DIGITAL",
    "inLanguage": "en-US"
  };
  if ((wixLocation.path || []).length === 0){ // homepage
    siteNode.potentialAction = {
      "@type": "SearchAction",
      "target": `${origin}/search?q={search_term_string}`,
      "query-input": "required name=search_term_string"
    };
  }
  applyStructuredData(siteNode);
}

/* ---------- RSS autodiscovery ---------- */
function addRSSAutodiscovery(){
  setLink('alternate', { type:'application/rss+xml', title:'WECARE.DIGITAL – Site feed',     href:'/_functions/rss' });
  setLink('alternate', { type:'application/rss+xml', title:'WECARE.DIGITAL – Blog feed',     href:'/_functions/rssblog' });
  setLink('alternate', { type:'application/rss+xml', title:'WECARE.DIGITAL – Products feed', href:'/_functions/rssproducts' });
}

/* ---------- Blog/Product SD stubs ---------- */
async function maybeAddBlogOrProductSD(path){
  const parts = (wixLocation.path || []);
  if (isBlogPath(path)){
    if (parts[1] === 'categories' || parts[1] === 'tags') return;
    const slug = parts.slice(1).join('/');
    const sd = await fetchLD(`/_functions/schemablog?slug=${encodeURIComponent(slug)}`);
    if (sd) applyStructuredData(sd);
  } else if (isProductPath(path) || path.includes('/product-page')){
    const id = (wixLocation.query && wixLocation.query.id) ? wixLocation.query.id : (parts[parts.length-1] || '');
    const sd = await fetchLD(`/_functions/schemaproduct?id=${encodeURIComponent(id)}`);
    if (sd) applyStructuredData(sd);
  }
}

/* ---------- Main pass ---------- */
export async function autoSEO(){
  const path = getPath();
  const relaxed = isDynamicPath(path);
  const headURL = `/_functions/seohead?path=${encodeURIComponent(path)}${relaxed ? '&relaxed=1':''}`;
  const data = await fetchJSON(headURL);

  // Title / Description / Keywords
  if (data && data.ok){
    safeSetTitle(data.title);
    safeSetDescription(data.description);
    const pageKW   = Array.isArray(data.keywords) ? data.keywords : [];
    const globalKW = Array.isArray(data.keywordsGlobal) ? data.keywordsGlobal : [];
    const commonKW = Array.isArray(data.keywordsCommon) ? data.keywordsCommon : [];
    const mergedKW = [...new Set([...pageKW, ...globalKW, ...commonKW])];
    safeSetKeywords(mergedKW);
  } else {
    // best-effort fallback: probe current HTML
    const probe = await fetchJSON(`/_functions/pagehead?url=${encodeURIComponent(wixLocation.url)}`);
    if (probe && probe.ok){
      safeSetTitle(probe.title);
      safeSetDescription(probe.description);
    }
  }

  // Canonical + Hreflang
  const canonical = await setCanonicalLinkWithFallback((data && data.canonical) ? data.canonical : wixLocation.url);
  setHreflangLinks(canonical, HREFLANGS);

  // Open Graph / Twitter
  const ogType = isBlogPath(path) ? 'article' : (isProductPath(path) ? 'product' : 'website');
  await setSocialTags({
    url: canonical,
    title: (data && data.title) || document?.title || 'WECARE.DIGITAL',
    description: (data && data.description) || '',
    image: (data && (data.ogImage || data.image)) || undefined,
    imageAlt: (data && data.defaultImageAlt) || 'WECARE.DIGITAL',
    type: ogType,
    siteName: 'WECARE.DIGITAL'
  });

  // Structured data from backend graph
  if (data && data.ok && Array.isArray(data.structuredData) && data.structuredData.length){
    applyStructuredData(data.structuredData);
  }

  // FAQ (page-scoped via hints), plus full FAQ on /faq
  await addPerPageFAQ(path);
  if (path === '/faq'){
    const faq = await fetchJSON('/_functions/faq');
    if (faq && faq.schema) applyStructuredData(faq.schema);
  }

  // Always present: Org + LocalBusiness + WebSite
  await addOrgAndSiteNodes();

  // Blog/Product stubs
  await maybeAddBlogOrProductSD(path);

  // RSS links
  addRSSAutodiscovery();
}

/* ---------- SPA-safe installer ---------- */
export function installSiteBootstrap({ relaxedDynamic = true, autoRSS = true } = {}){
  if (wixWindow.rendering.env !== 'browser') return;
  const run = async () => {
    // mark to help seo-bridge avoid double-apply
    try { window.__WECARE_SD_FROM_GLOBAL__ = false; } catch {}
    await autoSEO();
  };
  run().catch(()=>{});
  try { wixLocation.onChange(() => run().catch(()=>{})); } catch {}
}

export default { autoSEO, installSiteBootstrap };
