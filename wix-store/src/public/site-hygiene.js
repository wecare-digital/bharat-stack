/**************************************************************
 * public/site-hygiene.js
 * Client hygiene:
 *  - strip tracking/ad/tech params
 *  - remove appSectionParams when origin=wixcode
 *  - optional canonicalize via /_functions/canonicalize
 *  - enforce <img alt> (MutationObserver), with configurable defaultAlt
 *  - SPA-safe (re-runs on wixLocation.onChange)
 **************************************************************/
import wixLocation from 'wix-location-frontend';
import wixWindow from 'wix-window-frontend';

const STRIP = [
  'utm_source','utm_medium','utm_campaign','utm_term','utm_content','utm_id',
  'utm_source_platform','utm_creative_format','utm_marketing_tactic',
  'fbclid','gclid','msclkid','wbraid','gbraid','ttclid','twclid','yclid',
  'mc_eid','irclickid',
  'wixCodeMetaId','wixCodePageId','wixCodeInstance',
  'instance','compId','viewerCompId','siteRevision',
  'ref','src','appSectionParams'
];

async function fetchJSON(url){
  try{
    const res = await fetch(url, { method:'GET', credentials:'same-origin', cache:'no-store' });
    if (!res.ok) return null;
    return await res.json().catch(()=>null);
  }catch{ return null; }
}

function removeQueryParams(keys){
  if (wixWindow.rendering.env !== 'browser') return;
  try {
    if (wixLocation?.queryParams?.remove) {
      wixLocation.queryParams.remove(keys);
      return;
    }
  } catch {}
  try{
    const url = new URL(location.href);
    let changed = false;
    keys.forEach(k => { if (url.searchParams.has(k)){ url.searchParams.delete(k); changed = true; }});
    if (changed){
      history.replaceState({}, document.title,
        url.pathname + (url.searchParams.toString()?`?${url.searchParams.toString()}`:'') + url.hash
      );
    }
  }catch{}
}

function stripCartWixcodeOrigin(){
  if (wixWindow.rendering.env !== 'browser') return;
  try{
    const url = new URL(location.href);
    const asp = url.searchParams.get('appSectionParams');
    if (!asp) return;
    let obj = null;
    try { obj = JSON.parse(decodeURIComponent(asp)); } catch {}
    if (obj && obj.origin === 'wixcode'){
      url.searchParams.delete('appSectionParams');
      history.replaceState({}, document.title,
        url.pathname + (url.searchParams.toString()?`?${url.searchParams.toString()}`:'') + url.hash
      );
    }
  }catch{}
}

async function normalizeWithCanonicalizer(){
  try{
    const current = location.href;
    const res = await fetchJSON(`/_functions/canonicalize?url=${encodeURIComponent(current)}`);
    if (res && res.ok && res.changed && res.canonical){
      const u = new URL(res.canonical);
      history.replaceState({}, document.title,
        u.pathname + (u.search?u.search:'') + (u.hash?u.hash:'')
      );
    }
  }catch{}
}

function setDefaultImageAltsIn(doc, { defaultAlt='WECARE.DIGITAL', honorDecorative=false } = {}){
  const scope = doc || document;
  const imgs = scope.querySelectorAll('img');
  imgs.forEach(img => {
    try {
      const hasAlt = img.hasAttribute('alt');
      const rawAlt = img.getAttribute('alt');
      const isDecor = honorDecorative && rawAlt === '';
      if (!hasAlt || (!rawAlt && !isDecor)){
        img.setAttribute('alt', defaultAlt);
      }
    } catch {}
  });
}

let altObserver;
function ensureAltObserver(opts){
  if (altObserver) return;
  try{
    altObserver = new MutationObserver((muts) => {
      for (const m of muts){
        if (m.type === 'childList'){
          m.addedNodes.forEach(n => {
            if (n.nodeType === 1){
              if (n.tagName === 'IMG') setDefaultImageAltsIn(n.parentNode || document, opts);
              else setDefaultImageAltsIn(n, opts);
            }
          });
        } else if (m.type === 'attributes' && m.target.tagName === 'IMG'){
          const alt = m.target.getAttribute('alt');
          if (!alt) m.target.setAttribute('alt', (opts && opts.defaultAlt) || 'WECARE.DIGITAL');
        }
      }
    });
    altObserver.observe(document.documentElement, {
      childList: true, subtree: true, attributes: true, attributeFilter: ['alt']
    });
  }catch{}
}

async function runOnce({ useCanonicalize=true, defaultAlt='WECARE.DIGITAL', honorDecorative=false } = {}){
  stripCartWixcodeOrigin();
  removeQueryParams(STRIP);
  if (useCanonicalize) await normalizeWithCanonicalizer();

  const opts = { defaultAlt, honorDecorative };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      setDefaultImageAltsIn(document, opts);
      ensureAltObserver(opts);
    });
  } else {
    setDefaultImageAltsIn(document, opts);
    ensureAltObserver(opts);
  }
}

let started = false;
export function initHygiene(options = { useCanonicalize:true, defaultAlt:'WECARE.DIGITAL', honorDecorative:false }){
  if (started) return;
  started = true;
  if (wixWindow.rendering.env !== 'browser') return;

  runOnce(options).catch(()=>{});
  try { wixLocation.onChange(() => runOnce(options).catch(()=>{})); } catch {}
}

export default { initHygiene };
