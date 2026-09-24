/**
 * /product-page/partner-up - retired, redirects to /contact/.
 *
 * 27 references remain, including structured data in src/components/seo/InstructionsContent.tsx
 * (an Offer url, a BreadcrumbList item) and the placeholder in the WhatsApp catalog builder
 * at src/pages/dm/whatsapp/catalog-builder.tsx. This was the Wix storefront page for partner
 * signup; the storefront is gone and there is no partner page on this site, so /contact/ is
 * where a would-be partner can actually reach someone.
 *
 * See src/components/RetiredUrl.tsx for the redirect mechanics and why this is not a 301.
 */

import RetiredUrl from '../../components/RetiredUrl';

export default function PartnerUp() {
  return <RetiredUrl to="/contact/" was="Partner Up" />;
}
