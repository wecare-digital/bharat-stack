/**************************************************************
 * public/seo-bridge.js
 * Strict JSON-LD bridge for /_functions/seohead
 * - SD-only pass (skips if global already applied)
 * - Adds FAQ on /faq and Org/WebSite nodes
 * - SPA-safe installer
 **************************************************************/
import { seo as wixSeo } from 'wix-seo-frontend';
import wixLocation from 'wix-location-frontend';
import wixWindow from 'wix-window-frontend';

async function fetchJSON(url){
  try{
    const res = await fetch(url, { method:'GET', credentials:'same-origin', cache:'no-store' });
    if (!res.ok) return null;
    return await res.json().catch(()=>null);
  }catch{ return null; }
}

function injectLD(node){
  try{
    const s = document.createElement('script');
    s.type = 'application/ld+json';
    s.className = 'x-wc';
    s.textContent = JSON.stringify(node);
    document.head.appendChild(s);
  }catch{}
}
function applySD(graphOrNode){
  if (!graphOrNode) return;
  if (Array.isArray(graphOrNode)) {
    try { wixSeo.setStructuredData(graphOrNode); } catch { graphOrNode.forEach(injectLD); }
  } else {
    try { wixSeo.setStructuredData([graphOrNode]); } catch { injectLD(graphOrNode); }
  }
  try { window.__WECARE_SD_FROM_BRIDGE__ = true; } catch {}
}
function pathOf(){
  const parts = (wixLocation.path || []);
  return '/' + parts.join('/');
}

export async function applyStructuredDataFromBackend({ relaxed = true, includeFaq = true, includeOrg = true } = {}){
  if (wixWindow.rendering.env !== 'browser') return;
  // Skip if global already applied SD this tick
  if (typeof window !== 'undefined' && window.__WECARE_SD_FROM_GLOBAL__) return;

  const path = pathOf();
  const qs = `?path=${encodeURIComponent(path)}${relaxed ? '&relaxed=1':''}`;

  const data = await fetchJSON('/_functions/seohead' + qs);
  if (Array.isArray(data?.structuredData) && data.structuredData.length){
    applySD(data.structuredData);
  }

  if (includeFaq && path === '/faq'){
    const faq = await fetchJSON('/_functions/faq');
    if (faq?.schema) applySD(faq.schema);
  }

  if (includeOrg){
    const origin = (typeof location !== 'undefined' ? location.origin : 'https://www.wecare.digital');
    const ORG_ID  = `${origin}/#org`;
    const SITE_ID = `${origin}/#website`;
    const org = await fetchJSON('/_functions/contact');
    if (org){
      applySD({
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
    if ((wixLocation.path || []).length === 0){
      siteNode.potentialAction = {
        "@type":"SearchAction",
        "target": `${origin}/search?q={search_term_string}`,
        "query-input":"required name=search_term_string"
      };
    }
    applySD(siteNode);
  }
}

export function installSeoBridge({ relaxedDynamic = true } = {}){
  if (wixWindow.rendering.env !== 'browser') return;
  const run = () => {
    const path = pathOf();
    const relaxed = relaxedDynamic && (path.startsWith('/blog') || path.includes('/product'));
    applyStructuredDataFromBackend({ relaxed, includeFaq:true, includeOrg:true }).catch(()=>{});
  };
  run();
  try { wixLocation.onChange(run); } catch {}
}

export default { applyStructuredDataFromBackend, installSeoBridge };
