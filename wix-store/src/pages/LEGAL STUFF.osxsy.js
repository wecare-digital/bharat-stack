/**************************************************************
 * pages/_allPagesFallback.js
 * Runs on every page BUT no-ops if master/global already applied SEO.
 * Minimal-but-complete fallback: title/description/keywords,
 * canonical + hreflang, OG/Twitter, JSON-LD (seohead),
 * Blog/Product stubs, FAQ (full + per-page), Org/WebSite.
 **************************************************************/
import wixLocation from 'wix-location-frontend';
import { seo } from 'wix-seo-frontend';

/* ─────────────────────────────────────────────────────────────
   Small fetch helpers
   ───────────────────────────────────────────────────────────── */
async function fetchJSON(u){
  try{
    const r = await fetch(u, { credentials:'same-origin', cache:'no-store' });
    if (!r.ok) return null;
    return await r.json().catch(()=>null);
  }catch{ return null; }
}
async function fetchText(u){
  try{
    const r = await fetch(u, { credentials:'same-origin', cache:'no-store' });
    if (!r.ok) return null;
    return await r.text().catch(()=>null);
  }catch{ return null; }
}
async function fetchLD(u){
  const t = await fetchText(u);
  if (!t) return null;
  try { return JSON.parse(t); } catch { return null; }
}

/* ─────────────────────────────────────────────────────────────
   Path helpers
   ───────────────────────────────────────────────────────────── */
function parts(){ return (wixLocation.path || []); }
function currentPath(){
  try{
    const p = '/' + parts().join('/');
    return (!p || p==='//') ? '/' : p;
  }catch{ return '/'; }
}
function isBlogPostRoute(){
  const ps = parts();
  if (!ps.length) return false;
  if (ps[0] !== 'blog') return false;
  const s = ps[1] || '';
  return !!s && s !== 'categories' && s !== 'tags';
}
function isProductPath(){
  const p = currentPath();
  return p.startsWith('/product-page') || p.includes('/product');
}

/* ─────────────────────────────────────────────────────────────
   DOM/meta helpers
   ───────────────────────────────────────────────────────────── */
function upsertMetaByName(name, content){
  if (!name || !content) return;
  let el = document.head.querySelector(`meta[name="${name}"]`);
  if (!el){ el = document.createElement('meta'); el.setAttribute('name', name); document.head.appendChild(el); }
  el.setAttribute('content', content);
}
function upsertMetaByProp(prop, content){
  if (!prop || !content) return;
  let el = document.head.querySelector(`meta[property="${prop}"]`);
  if (!el){ el = document.createElement('meta'); el.setAttribute('property', prop); document.head.appendChild(el); }
  el.setAttribute('content', content);
}
function upsertLink(rel, attrs = {}){
  let sel = `link[rel="${rel}"]`;
  if (attrs.href) sel += `[href="${attrs.href}"]`;
  let el = document.head.querySelector(sel);
  if (!el){ el = document.createElement('link'); el.setAttribute('rel', rel); document.head.appendChild(el); }
  Object.entries(attrs).forEach(([k,v]) => { if (v != null) el.setAttribute(k, v); });
}

/* Title / Description / Keywords */
function safeSetTitle(title){
  if (!title) return;
  try { if (seo.setTitle) { seo.setTitle(title); return; } } catch {}
  try { document.title = title; } catch {}
}
function safeSetDescription(desc){
  if (!desc) return;
  try { if (seo.setDescription) { seo.setDescription(desc); return; } } catch {}
  upsertMetaByName('description', desc);
}
function safeSetKeywords(arr){
  const content = Array.isArray(arr) ? arr.join(', ') : String(arr||'').trim();
  if (!content) return;
  try { if (seo.setMetaTags) { seo.setMetaTags([{ name:'keywords', content }]); return; } } catch {}
  upsertMetaByName('keywords', content);
}

/* Canonical + hreflang */
function setCanonicalLink(canonicalUrl){
  if (!canonicalUrl) return;
  // remove any previous canonical we might have added
  Array.from(document.head.querySelectorAll('link[rel="canonical"].x-wc'))
    .forEach(n => n.parentNode && n.parentNode.removeChild(n));
  const link = document.createElement('link');
  link.setAttribute('rel','canonical');
  link.setAttribute('href', canonicalUrl);
  link.className = 'x-wc';
  document.head.appendChild(link);
}
function setHreflangLinks(canonicalUrl, langs = ['en-IN','en-US','x-default']){
  if (!canonicalUrl) return;
  // clear prior fallbacks we added
  Array.from(document.head.querySelectorAll('link[rel="alternate"][hreflang].x-wc'))
    .forEach(n => n.parentNode && n.parentNode.removeChild(n));
  langs.forEach(h => {
    const link = document.createElement('link');
    link.setAttribute('rel','alternate');
    link.setAttribute('hreflang', h);
    link.setAttribute('href', canonicalUrl);
    link.className = 'x-wc';
    document.head.appendChild(link);
  });
}

/* OG / Twitter */
function applyOpenGraphTwitter({ url, title, description, image, imageAlt = 'WECARE.DIGITAL', locale = 'en_IN', type = 'website', siteName='WECARE.DIGITAL' }){
  if (url)   upsertMetaByProp('og:url', url);
  if (title) { upsertMetaByProp('og:title', title); upsertMetaByName('twitter:title', title); }
  if (description) { upsertMetaByProp('og:description', description); upsertMetaByName('twitter:description', description); }
  upsertMetaByProp('og:type', type);
  upsertMetaByProp('og:site_name', siteName);
  upsertMetaByProp('og:locale', locale);
  upsertMetaByName('twitter:card', image ? 'summary_large_image' : 'summary');
  if (image){
    upsertMetaByProp('og:image', image);
    upsertMetaByName('twitter:image', image);
    upsertMetaByProp('og:image:alt', imageAlt);
  }
}

/* Page-scoped FAQ via pathHints */
async function addPerPageFAQ(path){
  const faq = await fetchJSON('/_functions/faq');
  if (!faq || !faq.faqs) return;
  const buckets = faq.faqs;
  const matches = [];
  Object.keys(buckets).forEach(section=>{
    const list = Array.isArray(buckets[section]) ? buckets[section] : [];
    list.forEach(item=>{
      const hints = Array.isArray(item.pathHints) ? item.pathHints : [];
      if (hints.includes(path)) matches.push(item);
    });
  });
  if (!matches.length) return;
  const node = {
    "@context":"https://schema.org",
    "@type":"FAQPage",
    "mainEntity": matches.map(m=>({
      "@type":"Question",
      "name": m.q,
      "acceptedAnswer": { "@type":"Answer", "text": m.a }
    }))
  };
  try { if (seo.addStructuredData) seo.addStructuredData(node); else if (seo.setStructuredData) seo.setStructuredData([node]); } catch {}
}

/* Org + Website nodes (harmless de-dupe via @id) */
async function addOrgAndWebsite(path){
  const origin = (typeof location!=='undefined' && location.origin) ? location.origin : 'https://www.wecare.digital';
  const ORG_ID  = `${origin}/#org`;
  const SITE_ID = `${origin}/#website`;

  const org = await fetchJSON('/_functions/contact');
  if (org){
    const orgNode = {
      "@context":"https://schema.org",
      "@type":["Organization","LocalBusiness"],
      "@id": ORG_ID,
      "name": org.name,
      "url": org.url || origin + '/',
      "email": org.email,
      "telephone": org.telephone,
      "logo": org.logo,
      "image": org.image,
      "address": org.address,
      "sameAs": org.sameAs || org.social || []
    };
    try { if (seo.addStructuredData) seo.addStructuredData(orgNode); else if (seo.setStructuredData) seo.setStructuredData([orgNode]); } catch {}
  }

  const siteNode = {
    "@context":"https://schema.org",
    "@type":"WebSite",
    "@id": SITE_ID,
    "url": origin,
    "name": "WECARE.DIGITAL",
    "inLanguage": "en-US"
  };
  if (path === '/'){
    siteNode.potentialAction = {
      "@type":"SearchAction",
      "target": `${origin}/search?q={search_term_string}`,
      "query-input":"required name=search_term_string"
    };
  }
  try { if (seo.addStructuredData) seo.addStructuredData(siteNode); else if (seo.setStructuredData) seo.setStructuredData([siteNode]); } catch {}
}

/* Canonicalize current URL via backend normalizer */
async function canonicalizeFallback(){
  try{
    const res = await fetchJSON(`/_functions/canonicalize?url=${encodeURIComponent(location.href)}`);
    if (res && res.ok){
      return res.canonical || null;
    }
  }catch{}
  return null;
}

/* Best-effort OG image from /_functions/icons */
async function bestOgImage(){
  try{
    const icons = await fetchJSON('/_functions/icons');
    if (icons && Array.isArray(icons.icons)){
      const png = icons.icons.find(u => u.endsWith('.png'));
      return png || null;
    }
  }catch{}
  return null;
}

/* ─────────────────────────────────────────────────────────────
   MAIN
   ───────────────────────────────────────────────────────────── */
$w.onReady(async () => {
  // If master/global already marked work done, bail out
  if (typeof window !== 'undefined' && (window.__WECARE_MASTER_READY__ || window.__WECARE_SEO_APPLIED__)) return;

  const path = currentPath();
  const relaxed = isBlogPostRoute() || isProductPath();

  // 1) Pull SEO head (title/desc/keywords/canonical/graph)
  const head = await fetchJSON(`/_functions/seohead?path=${encodeURIComponent(path)}${relaxed?'&relaxed=1':''}`);

  // Title / Description / Keywords
  if (head?.ok){
    safeSetTitle(head.title);
    safeSetDescription(head.description);

    const pageKW   = Array.isArray(head.keywords) ? head.keywords : [];
    const globalKW = Array.isArray(head.keywordsGlobal) ? head.keywordsGlobal : [];
    const commonKW = Array.isArray(head.keywordsCommon) ? head.keywordsCommon : [];
    const mergedKW = [...new Set([...pageKW, ...globalKW, ...commonKW])];
    safeSetKeywords(mergedKW);
  }

  // 2) Canonical + hreflang (fallback via canonicalize if needed)
  let canonical = head?.canonical;
  if (!canonical){
    canonical = await canonicalizeFallback();
  }
  if (!canonical){
    canonical = (typeof location!=='undefined') ? location.href : '';
  }
  if (canonical){
    setCanonicalLink(canonical);
    setHreflangLinks(canonical, ['en-IN','en-US','x-default']);
  }

  // 3) OG/Twitter (basic; with locale + image alt)
  const ogType = isBlogPostRoute() ? 'article' : (isProductPath() ? 'product' : 'website');
  let ogImage = null;
  if (head?.image || head?.ogImage) ogImage = head.image || head.ogImage;
  if (!ogImage) ogImage = await bestOgImage();
  applyOpenGraphTwitter({
    url: canonical,
    title: head?.title || document?.title || 'WECARE.DIGITAL',
    description: head?.description || '',
    image: ogImage || undefined,
    imageAlt: 'WECARE.DIGITAL',
    locale: 'en_IN',
    type: ogType,
    siteName: 'WECARE.DIGITAL'
  });

  // 4) JSON-LD graph from backend
  if (Array.isArray(head?.structuredData) && head.structuredData.length){
    try { seo.setStructuredData(head.structuredData); } catch {}
  }

  // 5) Blog/Product entity stubs
  if (isBlogPostRoute()){
    const slug = parts().slice(1).join('/');
    const blogSD = await fetchLD(`/_functions/schemablog?slug=${encodeURIComponent(slug)}`);
    if (blogSD){ try { seo.addStructuredData(blogSD); } catch {} }
  } else if (isProductPath()){
    const id = (wixLocation.query?.id) ? wixLocation.query.id : (parts()[parts().length-1] || '');
    const prodSD = await fetchLD(`/_functions/schemaproduct?id=${encodeURIComponent(id)}`);
    if (prodSD){ try { seo.addStructuredData(prodSD); } catch {} }
  }

  // 6) FAQ
  if (path === '/faq'){
    const faq = await fetchJSON('/_functions/faq');
    if (faq?.schema){ try { seo.addStructuredData(faq.schema); } catch {} }
  } else {
    await addPerPageFAQ(path);
  }

  // 7) Org + Website (always include; safe de-dupe via @id)
  await addOrgAndWebsite(path);

  // Mark as applied so we don't double-work on this page load
  try { window.__WECARE_SEO_APPLIED__ = true; } catch {}
});
