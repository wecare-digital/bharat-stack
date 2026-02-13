/**************************************************************
 * pages/store-product.js
 * Dynamic Store Product template:
 * - hygiene (strip UTMs/IDs, canonicalize, <img alt> guard)
 * - backend-driven SEO (title/desc/keywords, canonical+hreflang,
 *   OG/Twitter incl. locale & image alt, JSON-LD graph)
 * - adds Product JSON-LD stub via /_functions/schemaproduct
 * - SPA-safe SEO bridge
 * - optional lite ops console log
 **************************************************************/
import { autoSEO } from 'public/global-apply';
import { installSeoBridge } from 'public/seo-bridge';
import { initHygiene } from 'public/site-hygiene';
import { runOpsLite } from 'public/ops-lite';
import wixLocation from 'wix-location-frontend';
import { seo } from 'wix-seo-frontend';

/* tiny helpers (local, just for the product stub) */
async function fetchText(url){
  try{
    const res = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
    if (!res.ok) return null;
    return await res.text().catch(()=>null);
  }catch{ return null; }
}
async function fetchLD(url){
  const t = await fetchText(url);
  if (!t) return null;
  try { return JSON.parse(t); } catch { return null; }
}

function getProductIdFromUrl(){
  // prefer explicit query ?id=... (your backend supports it),
  // else fall back to last path segment for dynamic routes.
  const qId = (wixLocation.query && wixLocation.query.id) ? wixLocation.query.id : '';
  if (qId) return qId;
  const parts = (wixLocation.path || []);
  return parts.length ? parts[parts.length - 1] : '';
}

$w.onReady(async () => {
  // 1) Client hygiene (strip UTMs/IDs, canonicalize, enforce <img alt>)
  initHygiene({ useCanonicalize: true });

  // 2) Backend-driven SEO (auto detects product dynamic -> relaxed=1)
  await autoSEO();

  // 3) Ensure Product JSON-LD (backend usually covers; this is a safe extra)
  try {
    const id = getProductIdFromUrl();
    if (id) {
      const prodSD = await fetchLD(`/_functions/schemaproduct?id=${encodeURIComponent(id)}`);
      if (prodSD) {
        try { seo.addStructuredData(prodSD); } catch {}
      }
    }
  } catch {}

  // 4) Keep SEO graph fresh on SPA route changes
  installSeoBridge({ relaxedDynamic: true });

  // 5) Optional: log a quick self-test to console
  runOpsLite().catch(() => {});
});
