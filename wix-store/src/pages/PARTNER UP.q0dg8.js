// Site Code → All Pages (fallback — optional)
// If masterPage.js already runs autoSEO(), this will no-op via the guard.

import wixLocation from 'wix-location-frontend';
import { seo } from 'wix-seo-frontend';

/* ——— tiny fetch helpers ——— */
async function fetchJSON(url){
  try{
    const res = await fetch(url, { credentials:'same-origin', cache:'no-store' });
    if (!res.ok) return null;
    return await res.json().catch(()=>null);
  }catch{ return null; }
}
async function fetchLD(url){ // expects JSON-LD (object) from backend
  try{
    const res = await fetch(url, { credentials:'same-origin', cache:'no-store' });
    if (!res.ok) return null;
    const text = await res.text();
    try { return JSON.parse(text); } catch { return null; }
  }catch{ return null; }
}

/* ——— page type helpers ——— */
function currentPath(){
  try {
    const parts = wixLocation.path || [];
    const p = '/' + parts.join('/');
    return p === '//' || p === '' ? '/' : p;
  } catch { return '/'; }
}
function isBlogPostPath(path, parts){
  // treat /blog/<slug> as posts; exclude /blog, /blog/categories, /blog/tags
  if (!path.startsWith('/blog/')) return false;
  const seg1 = parts?.[0] || '';
  const seg2 = parts?.[1] || '';
  return !(seg1 === 'blog' && (seg2 === '' || seg2 === 'categories' || seg2 === 'tags'));
}
function isProductPath(path){
  return path.startsWith('/product-page') || path.startsWith('/product');
}

/* ——— main ——— */
$w.onReady(async () => {
  // if masterPage already applied the SEO graph, bail out
  if (typeof window !== 'undefined' && window.__WECARE_SEO_APPLIED__) return;

  const parts = (wixLocation.path || []);
  const path  = currentPath();

  // dynamic gets "relaxed=1" so /_functions/seohead returns an empty-but-ok frame
  const relaxed = path.startsWith('/blog') || isProductPath(path);
  const headURL = `/_functions/seohead?path=${encodeURIComponent(path)}${relaxed ? '&relaxed=1' : ''}`;

  try {
    const head = await fetchJSON(headURL);
    if (head && head.ok) {
      // set title/description if provided
      if (head.title)       seo.setTitle(head.title);
      if (head.description) seo.setDescription(head.description);

      // attach site/page graph
      if (Array.isArray(head.structuredData) && head.structuredData.length){
        // setStructuredData replaces; safer for a full graph injection
        seo.setStructuredData(head.structuredData);
      }
    }

    // entity-specific add-ons (append after the main graph)
    if (isBlogPostPath(path, [''].concat(parts))) {
      const slug = parts.slice(1).join('/'); // everything after /blog/
      const blogSD = await fetchLD(`/_functions/schema_blog?slug=${encodeURIComponent(slug)}`);
      if (blogSD) seo.addStructuredData(blogSD);
    } else if (isProductPath(path)) {
      // prefer id query if present; otherwise fall back to last path segment as a pseudo-id
      const id = (wixLocation.query && wixLocation.query.id) ? wixLocation.query.id : (parts[parts.length-1] || '');
      const prodSD = await fetchLD(`/_functions/schema_product?id=${encodeURIComponent(id)}`);
      if (prodSD) seo.addStructuredData(prodSD);
    }

    // one-run guard so masterPage + fallback never double-inject
    if (typeof window !== 'undefined') window.__WECARE_SEO_APPLIED__ = true;
  } catch (_) {
    // swallow silently — this is a fallback
  }
});
