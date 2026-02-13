/**************************************************************
 * pages/faq.js
 * FAQ: full FAQPage schema (autoSEO already includes it) + hygiene
 **************************************************************/
import { autoSEO } from 'public/global-apply';
import { installSeoBridge } from 'public/seo-bridge';
import { initHygiene } from 'public/site-hygiene';
import { runOpsLite } from 'public/ops-lite';

$w.onReady(async () => {
  initHygiene({ useCanonicalize: true });
  await autoSEO();            // adds full FAQPage + per-page hints elsewhere
  installSeoBridge({ relaxedDynamic: true });
  runOpsLite().catch(() => {});
});
