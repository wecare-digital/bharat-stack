/**************************************************************
 * pages/home.js
 * Home: full backend SEO + hygiene + SPA-safe bridge + ops log
 **************************************************************/
import { autoSEO } from 'public/global-apply';
import { installSeoBridge } from 'public/seo-bridge';
import { initHygiene } from 'public/site-hygiene';
import { runOpsLite } from 'public/ops-lite';

$w.onReady(async () => {
  // Hygiene (strip UTM/IDs/tech, canonicalize, enforce <img alt>)
  initHygiene({ useCanonicalize: true });

  // Backend-driven SEO (includes WebSite + SearchAction for '/')
  await autoSEO();

  // Keep JSON-LD in sync on SPA route changes
  installSeoBridge({ relaxedDynamic: true });

  // Optional: console health log
  runOpsLite().catch(() => {});
});
