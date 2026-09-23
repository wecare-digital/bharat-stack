import React from 'react';
import ProductPage from '../components/ProductPage';
import { productBySlug } from '../content/products';

/**
 * /swdhya — the Swdhya product page.
 *
 * DELIBERATELY THIN. Copy lives in src/content/products.ts and the layout in
 * ProductPage.tsx, so all seven product pages cannot drift apart. This file exists only to
 * own the route.
 *
 * ROUTING: '/swdhya' must be in the EXACT-MATCH allowlist in _app.tsx or this renders an
 * empty body with HTTP 200, and in PUBLIC_EXACT in scripts/generate-sitemap.js or it is
 * never advertised. trailingSlash means the URL is /swdhya/.
 *
 * A STATIC ROUTE, NOT A DYNAMIC ONE. A single pages/[slug].tsx would have been less code,
 * but _app.tsx gates public access on an exact router.pathname match and the sitemap uses an
 * exact allowlist; a catch-all would have to be special-cased in both, and would also
 * swallow every unknown path on a static export.
 */
const SwdhyaPage: React.FC = () => <ProductPage product={ productBySlug( 'swdhya' ) } />;

export default SwdhyaPage;
