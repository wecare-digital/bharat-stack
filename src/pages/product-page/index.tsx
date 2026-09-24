/**
 * /product-page/ - retired index, redirects to /contact/.
 *
 * The bare path is referenced once and is also what a visitor reaches by trimming a
 * /product-page/<slug> URL, which people do when the deeper link fails. Without this file
 * that trim lands on a 404 immediately after the slug already did.
 *
 * Only the two slugs that appear in the repo have their own stubs (partner-up,
 * referral-partner). A static export cannot match an unlisted slug at request time - there
 * is no server to ask - so any other /product-page/<slug> still 404s. If more retired slugs
 * turn up, add a file per slug beside this one.
 *
 * See src/components/RetiredUrl.tsx for the redirect mechanics and why this is not a 301.
 */

import RetiredUrl from '../../components/RetiredUrl';

export default function ProductPageIndex() {
  return <RetiredUrl to="/contact/" was="Our product pages" />;
}
