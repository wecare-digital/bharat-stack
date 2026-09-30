import React from 'react';
import Head from 'next/head';
import { ORIGIN, ORG_ID, WEBSITE_ID, SITE_ENTITIES, ld } from '../lib/schema';
import {
  SOCIAL_CARD_URL, SOCIAL_CARD_TYPE, SOCIAL_CARD_W, SOCIAL_CARD_H, SOCIAL_CARD_ALT,
  SHARE_CARD_TYPE,
} from '../config/share';
import { shopMetaDescription, shopPageTitle, shopProductPath } from '../content/shop';
import type { ShopProduct } from '../content/shop';

/**
 * The whole document head for a /shop/<slug>/ page.
 *
 * WHY THIS OWNS EVERY TAG instead of leaning on _app.tsx's sitewide Head, as the fourteen
 * PageMeta pages do. PUBLIC_PAGE_META in _app.tsx is keyed on `router.pathname`, and for a
 * dynamic route that string is the PATTERN - '/shop/[slug]'. Everything computed from it is then
 * computed from the pattern: the canonical would read https://wecare.digital/shop/[slug]/, and so
 * would og:url, twitter:url and the WebPage node's @id and url. PageMeta can override the first
 * three because they carry a `key` and next/head dedupes on it, but the JSON-LD script does not
 * and cannot be replaced - the page would ship two graphs, one of them naming a URL that does not
 * exist, on all seven pages.
 *
 * So '/shop/[slug]' joins `isContentPublic` in _app.tsx instead, which suppresses the sitewide
 * Head and makes this component responsible for the lot. That is the established arrangement for
 * every dynamic public route here: /post/[slug] does it through SEO.tsx and the four blog index
 * routes through BlogIndexHead.tsx, for exactly this reason.
 *
 * THE SITE ENTITIES ARE EMITTED HERE. Because _app.tsx's Head is suppressed, #organization and
 * #website do not otherwise exist on this page - so the `publisher`, `seller` and `brand`
 * references below would dangle. BlogIndexHead learned that the hard way; see the note there.
 *
 * THE SHARE TAGS ARE WRITTEN OUT, not factored into a helper. next/head reads its DIRECT children
 * to build the tag list, so wrapping them in a component puts a layer between it and the tags and
 * they silently vanish. The values come from src/config/share.ts, so there is still one source
 * for what the card is.
 *
 * NO PRODUCT IMAGE, ANYWHERE. The catalogue snapshot reports mediaCount 0 for all seven products,
 * so there is no image URL to give og:image or Product.image. The share card falls back to the
 * company mark, which is what every other page on this site uses, and Product.image is absent -
 * which costs eligibility for Google's product rich result. Naming a file that does not exist
 * would be worse: a broken image in every WhatsApp preview, and a structured-data error.
 */

interface ShopProductHeadProps {
  product: ShopProduct;
}

/**
 * The JSON-LD graph for one product page, as a PURE FUNCTION so it can be asserted.
 *
 * EXPORTED BECAUSE next/head IS UNTESTABLE FROM jsdom. `<Head>` does not render into the
 * component's container - it is a side effect onto document.head that next/head manages - so a
 * test that rendered this component and queried the container for
 * `script[type="application/ld+json"]` found ZERO scripts. The first version of the test for this
 * did exactly that and passed VACUOUSLY: with no scripts to read, "the graph contains no Product"
 * was trivially satisfied, which is the shape of gate that protects nothing.
 *
 * Building the graph here and rendering it below means the test asserts the object and the browser
 * harness asserts the built HTML - tools/audit/schemacheck.js reads the real export. Neither is a
 * stand-in for the other.
 */
/** One JSON-LD node. Deliberately loose: a schema.org graph is heterogeneous by design. */
type LdNode = Record<string, unknown>;

export const shopProductSchema = (
  product: ShopProduct,
): { '@context': string; '@graph': LdNode[] } => {
  const url = ORIGIN + shopProductPath( product );
  const shopUrl = ORIGIN + '/shop/';
  const description = shopMetaDescription( product );

  /**
   * THE Product NODE CARRIES THE SAME PRICE THE PAGE PRINTS, and that is the whole reason it is
   * safe to emit at all. The number comes from the committed snapshot, so it can go stale - but
   * it goes stale in the visible copy and in the markup together, and refreshing the snapshot
   * fixes both in one commit. Structured data that disagreed with the rendered page would be the
   * real defect, and it is the one Google penalises.
   *
   * `price` is the bare decimal Wix returns ("6999.00"), because schema.org/price wants a number
   * with no grouping and no symbol. The visible price uses Wix's own formatted string. Two
   * spellings of one value, read from the same field.
   *
   * NO sku: the snapshot's only identifier is a Wix UUID, which is a database key rather than a
   * stock-keeping unit, and publishing it as one would be a claim about inventory that nothing
   * here backs. NO aggregateRating and NO review: nobody has rated these, and a fabricated
   * rating was already removed from this site once.
   *
   * `description` is the FULL copy rather than the 160-character meta description, because this
   * node describes the product and the meta tag describes the search result. The WebPage node
   * above it keeps the short one, so neither is a truncated stand-in for the other.
   *
   * availability is read from the snapshot's `inStock`, which is the only thing that field is
   * allowed to do - see the note in src/content/shop.ts about why it never reaches a payment.
   *
   * THE NODE IS EMITTED ONLY WHEN THE PRODUCT HAS AN IMAGE, AND IT HAS NONE TODAY. Google requires
   * name, image and offers on Product; tools/audit/schemacheck.js encodes that as
   * REQUIRED.Product = [ 'name', 'image', 'offers' ] and failed this branch seven times, once per
   * page. Three ways out were available and two are worse than doing nothing:
   *
   *   Send the company logo as the image. It is not a picture of the product, it would be the same
   *     picture for all seven, and Google would render it as the product photo. This site has
   *     already had a fabricated aggregateRating removed; inventing a product image is the same
   *     mistake in a different field.
   *
   *   Exempt /shop/* from the gate. The gate has no exemption mechanism, and adding one to admit a
   *     node the gate exists to reject would weaken it for every future page.
   *
   *   Emit no Product until there is an image. An incomplete Product is INELIGIBLE for the product
   *     rich result however complete the rest of it is - schemacheck's own docblock makes exactly
   *     that point about Article and `image` - so the node buys nothing today. Omitting it costs no
   *     eligibility that was ever available.
   *
   * So the page keeps ItemPage and BreadcrumbList, which are complete and true, and the Product
   * and its Offer appear automatically the moment the snapshot carries an image. The price is still
   * on the page for a human to read; it is the machine-readable claim that waits for the picture
   * Google needs beside it.
   */
  const productNode: LdNode[] = product.image ? [ {
    '@type': 'Product',
    '@id': url + '#product',
    name: product.name,
    description: [ product.tagline, ...product.body ].join( ' ' ),
    url,
    image: product.image,
    brand: { '@id': ORG_ID },
    offers: {
      '@type': 'Offer',
      '@id': url + '#offer',
      url,
      price: product.price,
      priceCurrency: product.currency,
      availability: product.inStock
        ? 'https://schema.org/InStock'
        : 'https://schema.org/OutOfStock',
      seller: { '@id': ORG_ID },
    },
  } ] : [];

  const schema: { '@context': string; '@graph': LdNode[] } = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'ItemPage',
        '@id': url + '#webpage',
        url,
        name: product.name,
        description,
        isPartOf: { '@id': WEBSITE_ID },
        inLanguage: 'en-IN',
        breadcrumb: { '@id': url + '#breadcrumb' },
        // mainEntity ONLY when the Product exists. A reference to an @id that nothing defines is a
        // dangling pointer, and schemacheck asserts "no unresolved @id references" - so leaving it
        // in unconditionally would trade one failure for another.
        ...( productNode.length ? { mainEntity: { '@id': url + '#product' } } : {} ),
        publisher: { '@id': ORG_ID },
      },
      {
        '@type': 'BreadcrumbList',
        '@id': url + '#breadcrumb',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: ORIGIN + '/' },
          { '@type': 'ListItem', position: 2, name: 'Shop', item: shopUrl },
          { '@type': 'ListItem', position: 3, name: product.name, item: url },
        ],
      },
      ...productNode,
    ],
  };

  return schema;
};

const ShopProductHead: React.FC<ShopProductHeadProps> = ( { product } ) => {
  const url = ORIGIN + shopProductPath( product );
  const title = shopPageTitle( product );
  const description = shopMetaDescription( product );
  const schema = shopProductSchema( product );

  return (
    <Head>
      <title>{ title }</title>
      <meta name="description" content={ description } />
      <link rel="canonical" href={ url } />
      <meta property="og:type" content="website" />
      <meta property="og:title" content={ title } />
      <meta property="og:description" content={ description } />
      <meta property="og:url" content={ url } />
      <meta property="og:image" content={ SOCIAL_CARD_URL } />
      <meta property="og:image:secure_url" content={ SOCIAL_CARD_URL } />
      <meta property="og:image:type" content={ SOCIAL_CARD_TYPE } />
      <meta property="og:image:width" content={ SOCIAL_CARD_W } />
      <meta property="og:image:height" content={ SOCIAL_CARD_H } />
      <meta property="og:image:alt" content={ SOCIAL_CARD_ALT } />
      <meta property="og:site_name" content="WECARE.DIGITAL" />
      <meta property="og:locale" content="en_IN" />
      <meta name="twitter:card" content={ SHARE_CARD_TYPE } />
      <meta name="twitter:title" content={ title } />
      <meta name="twitter:description" content={ description } />
      <meta name="twitter:url" content={ url } />
      <meta name="twitter:image" content={ SOCIAL_CARD_URL } />
      <meta name="twitter:image:alt" content={ SOCIAL_CARD_ALT } />
      <meta name="robots" content="index, follow, max-image-preview:large" />
      { SITE_ENTITIES.map( ( entity, index ) => (
        <script key={ `site-entity-${index}` } type="application/ld+json"
          dangerouslySetInnerHTML={ ld( entity ) } />
      ) ) }
      <script type="application/ld+json" dangerouslySetInnerHTML={ ld( schema ) } />
    </Head>
  );
};

export default ShopProductHead;
