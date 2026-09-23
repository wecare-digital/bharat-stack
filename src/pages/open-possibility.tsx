import React from 'react';
import ProductPage from '../components/ProductPage';
import { productBySlug } from '../content/products';

/**
 * /open-possibility — the Open Possibility product page.
 *
 * RENAMED FROM src/pages/swdhya.tsx. The product was called Swdhya; the owner renamed it to
 * Open Possibility and the route moved with the name rather than leaving the new brand at
 * the old address. Nothing needs a redirect: the page only ever existed on this unmerged
 * branch, so /swdhya/ was never published and nothing links to it.
 *
 * NOT TO BE CONFUSED with the other "Swdhya" references still in this repo, which are
 * deliberately untouched - "Swdhya Vaksetu" is the blog author's name (src/lib/seo-prompt.ts,
 * seo-page-prompt.ts), and the WhatsApp brand catalogue in
 * amplify/functions/ai/ai-generate-response/handler.py still advertises Swdhya at swdhya.in.
 * Those are a person and a live external brand, not this page.
 *
 * DELIBERATELY THIN. Copy lives in src/content/products.ts and the layout in
 * ProductPage.tsx, so all seven product pages cannot drift apart. This file exists only to
 * own the route.
 *
 * ROUTING: '/open-possibility' must be in the EXACT-MATCH allowlist in _app.tsx or this
 * renders an empty body with HTTP 200, and in PUBLIC_EXACT in scripts/generate-sitemap.js or
 * it is never advertised. trailingSlash means the URL is /open-possibility/.
 *
 * A STATIC ROUTE, NOT A DYNAMIC ONE. A single pages/[slug].tsx would have been less code,
 * but _app.tsx gates public access on an exact router.pathname match and the sitemap uses an
 * exact allowlist; a catch-all would have to be special-cased in both, and would also
 * swallow every unknown path on a static export.
 */
const OpenPossibilityPage: React.FC = () => <ProductPage product={ productBySlug( 'open-possibility' ) } />;

export default OpenPossibilityPage;
