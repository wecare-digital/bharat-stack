/**************************************************************
 * pages/search.js
 * Search results: indexable per your setup; hygiene + backend SEO
 **************************************************************/
import { autoSEO } from 'public/global-apply';
import { installSeoBridge } from 'public/seo-bridge';
import { initHygiene } from 'public/site-hygiene';
import { runOpsLite } from 'public/ops-lite';

$w.onReady(async () => {
  initHygiene({ useCanonicalize: true });
  await autoSEO();            // canonical & hreflang + OG/Twitter + JSON-LD graph
  installSeoBridge({ relaxedDynamic: true });
  runOpsLite().catch(() => {});
});
