/**************************************************************
 * masterPage.js
 * Site-wide bootstrap: hygiene + backend-driven SEO + lite ops
 **************************************************************/
import { initHygiene } from 'public/site-hygiene.js';
import { installSiteBootstrap } from 'public/global-apply.js';
import { installSeoBridge } from 'public/seo-bridge.js'; // SD-only second pass (de-duped)
import { runOpsLite } from 'public/ops-lite.js';

$w.onReady(function () {
  // 1) Hygiene (URL cleanup, canonicalize, enforce <img alt>)
  initHygiene({
    useCanonicalize : true,
    defaultAlt      : 'WECARE.DIGITAL',
    honorDecorative : false
  });

  // 2) Full SEO (Title/Desc/Keywords, Canonical/Hreflang, OG/Twitter, JSON-LD, FAQ, Org/WebSite, RSS)
  installSiteBootstrap({
    relaxedDynamic : true,  // relaxed for /blog/* and product routes
    autoRSS        : true
  });

  // 3) Optional SD-only bridge (skips if global already applied SD)
  installSeoBridge({ relaxedDynamic: true });

  // 4) Tiny ops log
  runOpsLite().catch(()=>{});
});
