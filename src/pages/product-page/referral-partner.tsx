/**
 * /product-page/referral-partner - retired, redirects to /contact/.
 *
 * The Wix storefront page for the "Referral Partner" product (still in the catalog at ₹999,
 * see src/content/wix-catalog.json). The storefront is gone, so the address 404s.
 *
 * NOTE for whoever wires up commerce: when product pages exist on this site again, this
 * stub should point at the real one rather than at /contact/. The catalog entry is the
 * source of truth for whether that page exists.
 *
 * See src/components/RetiredUrl.tsx for the redirect mechanics and why this is not a 301.
 */

import RetiredUrl from '../../components/RetiredUrl';

export default function ReferralPartner() {
  return <RetiredUrl to="/contact/" was="Referral Partner" />;
}
