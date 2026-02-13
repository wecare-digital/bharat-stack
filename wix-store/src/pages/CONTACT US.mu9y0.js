/**************************************************************
 * pages/contact.js
 * Contact: Org + LocalBusiness schema ensured by autoSEO + hygiene
 **************************************************************/
import { autoSEO } from 'public/global-apply';
import { installSeoBridge } from 'public/seo-bridge';
import { initHygiene } from 'public/site-hygiene';
import { runOpsLite } from 'public/ops-lite';

$w.onReady(async () => {
  initHygiene({ useCanonicalize: true });
  await autoSEO();            // ensures Organization + LocalBusiness node
  installSeoBridge({ relaxedDynamic: true });
  runOpsLite().catch(() => {});
});
