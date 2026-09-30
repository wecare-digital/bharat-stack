/**
 * The shop catalogue, read from the committed Wix snapshot.
 *
 * WHY A SNAPSHOT AND NOT A LIVE CALL. `src/content/wix-catalog.json` is produced by
 * `scripts/fetch-wix-catalog.js` and committed. next.config.js sets `output: 'export'`, so these
 * pages are built once and served as static HTML from CloudFront - there is no server to make a
 * live call from, and adding a client-side fetch would put an unauthenticated Wix read in the
 * browser. Reading the snapshot at build time means the catalogue costs nothing to serve and the
 * pages cannot break because Wix is slow. Measured in this sandbox: `GET /api/wix-store/products`
 * returns 401 without a staff session, so the authenticated route is not an option for a public
 * page even if there were a server to call it from.
 *
 * The snapshot is credential-free by construction - it was taken with an anonymous visitor token,
 * which is recorded in its own `source` field - so it is safe in git.
 *
 * REFRESHING IT IS A DELIBERATE ACT: re-run the fetch script and commit. That is the right shape
 * for a seven-product catalogue that changes rarely. It would be the wrong shape for live
 * inventory, which is why `inStock` here is only used to label a card and never to promise
 * availability at payment time.
 *
 * THE PRICES HERE ARE FOR DISPLAY AND MUST NEVER REACH A PAYMENT. This is the rule the whole
 * commerce architecture is built on: the amount in a payment request comes from a live checkout
 * read, compared in integer paise, and any mismatch fails closed - see
 * amplify/functions/shared/order_creation.py. A price rendered from a snapshot is a price that
 * was true when the snapshot was taken. `formattedPrice` is passed through from Wix rather than
 * reformatted locally, so the page cannot invent a different number from the one Wix would quote.
 *
 * THREE FIELDS IN THE SNAPSHOT ARE DELIBERATELY NOT RENDERED, and each omission is a measurement
 * rather than an oversight:
 *
 *   productType - reads "PHYSICAL" on all seven. Five of them (File Assist, Guided Resolution,
 *     Paperwork, Referral Partner, Viveka) are documents and coordination, not goods. That is
 *     Wix's default for a product with no shipping profile, not a claim about what is sold, so
 *     surfacing it would put a false statement on five pages. It is kept off the interface
 *     entirely so nobody can render it by reaching for the nearest field.
 *
 *   mediaCount - zero on all seven, so the snapshot carries no image URL for any product. The
 *     pages therefore ship no product image and no placeholder frame: an empty grey box is a
 *     promise that a picture exists. It also means the Product schema emits no `image`, which
 *     costs eligibility for Google's product rich result. That is the honest trade - a fabricated
 *     image reference would be worse, and this site has already had one invented
 *     `aggregateRating` removed for the same reason.
 *
 *   productUrl - points at https://xout.wecare.digital/product-page/<slug>, the old Wix-hosted
 *     storefront. `/product-page/*` was retired from this repo on owner instruction and the
 *     replacement is these pages, so linking there would send a visitor off the domain to the
 *     surface this one exists to replace.
 */
import catalog from './wix-catalog.json';

export interface ShopProduct {
  id: string;
  name: string;
  slug: string;
  /** Wix's own formatted string, e.g. "₹6,999.00". Passed through, never rebuilt. */
  formattedPrice: string;
  /**
   * The decimal string Wix returns, e.g. "6999.00". Used for sorting and for the `price` in the
   * Product schema, where schema.org wants a bare number. NEVER used to charge anyone.
   */
  price: string;
  currency: string;
  inStock: boolean;
  /**
   * The bold opening line of the Wix description. It is the product's own one-line statement of
   * what it does - "Put your location to work.", "Think it through before you decide." - which is
   * exactly what a card in a grid needs and what a meta description should open with.
   */
  tagline: string;
  /** The remaining paragraphs, in order, as plain text. */
  body: string[];
}

interface RawProduct {
  id?: string;
  name?: string;
  slug?: string;
  formattedPrice?: string;
  price?: string;
  currency?: string;
  inStock?: boolean;
  visible?: boolean;
  descriptionHtml?: string;
}

/**
 * Wix description HTML reduced to plain paragraph strings.
 *
 * NOT rendered as HTML. `descriptionHtml` is merchant-authored rich text from a third-party CMS,
 * and putting it through dangerouslySetInnerHTML would make the storefront an XSS surface that
 * depends on Wix's sanitiser rather than ours. Tags are stripped and the text rendered as React
 * children, so the worst a malformed description can do is read badly.
 *
 * `<p>` and `<br>` become paragraph breaks because they are the only structure this copy uses -
 * measured across all seven descriptions, the only other tag present is
 * `<span style="font-weight: 700">`, which marks the opening line. Everything else is dropped
 * rather than approximated. Entities are decoded for the small set that actually appears; a full
 * decoder would be a dependency for no gain.
 *
 * THE COLLAPSE RUNS PER LINE, NOT ONCE OVER THE WHOLE STRING, and that ordering is load-bearing:
 * collapsing whitespace before splitting would eat the separators this function just inserted. A
 * near-identical helper elsewhere in this repo trimmed at every recursion instead and produced
 * "2 tbsptoastedsesame oil" - words fused where a tag boundary had been the only separator.
 *
 * THE SEPARATOR IS A CONTROL CHARACTER AND NOT '\n', which is a correction rather than a style
 * choice. Splitting on '\n' makes a RAW newline in the source a paragraph break, and in HTML it is
 * not - it is whitespace, and should collapse to a space like any other. `<p>one\ntwo</p>` was
 * coming out as two paragraphs instead of "one two". The seven descriptions in the committed
 * snapshot happen to be single-line, so nothing was visibly wrong today; it would have broken the
 * first time the snapshot was refreshed from a Wix editor that wraps its output.
 */
/** U+0001, which cannot appear in Wix rich text and is not whitespace, so \s+ leaves it alone. */
const BREAK = '\u0001';

export function toParagraphs ( html: string ): string[] {
  return html
    // Any BREAK is stripped first, so a control character in the source cannot be mistaken for one
    // this function inserted.
    .replace( new RegExp( BREAK, 'g' ), '' )
    .replace( /<\s*br\s*\/?\s*>/gi, BREAK )
    .replace( /<\/\s*p\s*>/gi, BREAK )
    .replace( /<[^>]+>/g, '' )
    .replace( /&nbsp;/g, ' ' )
    .replace( /&lt;/g, '<' )
    .replace( /&gt;/g, '>' )
    .replace( /&quot;/g, '"' )
    .replace( /&#39;|&apos;/g, "'" )
    // LAST, not first. Decoding &amp; before the others would turn a literal "&amp;lt;" in the
    // source into "<", which is the classic double-decode hole.
    .replace( /&amp;/g, '&' )
    .split( BREAK )
    .map( line => line.replace( /\s+/g, ' ' ).trim() )
    .filter( Boolean );
}

/**
 * Only visible products, and the filter is not cosmetic: `visible: false` in Wix means the
 * merchant has taken the product off the storefront, so publishing it here would contradict the
 * catalogue the business actually runs. A product with no slug is dropped for a harder reason -
 * the slug IS the route, so there would be no page to put it on.
 *
 * Sorted by name, which is the only ordering the snapshot supports. Wix returns no sort weight
 * and every one of the seven carries the same `mainCategoryId`, so any other order would be the
 * order the API happened to answer in - stable until it is not.
 */
export const SHOP_PRODUCTS: ShopProduct[] = ( ( catalog as { products?: RawProduct[] } ).products || [] )
  .filter( raw => raw.visible !== false && !!raw.slug && !!raw.name )
  .map( raw => {
    const paragraphs = toParagraphs( String( raw.descriptionHtml || '' ) );
    return {
      id: String( raw.id || '' ),
      name: String( raw.name || '' ),
      slug: String( raw.slug || '' ),
      formattedPrice: String( raw.formattedPrice || '' ),
      price: String( raw.price || '' ),
      currency: String( raw.currency || 'INR' ),
      inStock: raw.inStock !== false,
      tagline: paragraphs[ 0 ] || '',
      body: paragraphs.slice( 1 ),
    };
  } )
  .sort( ( a, b ) => a.name.localeCompare( b.name ) );

export const shopProductBySlug = ( slug: string ): ShopProduct | null =>
  SHOP_PRODUCTS.find( product => product.slug === slug ) || null;

/** When the snapshot was taken, so a reader can tell how fresh the catalogue is. */
export const CATALOG_FETCHED_AT = String(
  ( catalog as { fetchedAt?: string } ).fetchedAt || '',
);

/** "26 September 2026" - the fetch timestamp as a date a reader can place. */
export const catalogReadOn = (): string => {
  const at = new Date( CATALOG_FETCHED_AT );
  if ( Number.isNaN( at.getTime() ) ) return '';
  // en-GB with an explicit UTC zone: the snapshot timestamp is UTC, and letting this resolve in
  // the visitor's zone would render a different date either side of midnight for the same build,
  // which is a hydration mismatch as well as a wrong answer.
  return at.toLocaleDateString( 'en-GB', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
  } );
};

/**
 * The meta description for a product page: the owner's own sentences, joined in order until the
 * next one would not fit, and NEVER cut mid-sentence.
 *
 * 160 characters is the budget because that is roughly where Google stops rendering. Truncating
 * at a word boundary with an ellipsis was the alternative and it is worse: this copy is written
 * as short, complete paragraphs, so a cut always lands inside the owner's argument. Measured
 * output for all seven, in characters:
 *
 *   File Assist        89     Merchandise      104
 *   Guided Resolution 159     Paperwork         60
 *   Kiosk              54     Referral Partner 110
 *   Viveka             68
 *
 * Four land between 54 and 89 characters, which is short for a description and is the right
 * answer anyway - Google supplements a thin description from the page, and it will not invent a
 * sentence the owner did not write.
 */
export const shopMetaDescription = ( product: ShopProduct ): string => {
  const budget = 160;
  let out = '';
  for ( const paragraph of [ product.tagline, ...product.body ] ) {
    const candidate = out ? out + ' ' + paragraph : paragraph;
    if ( candidate.length > budget ) break;
    out = candidate;
  }
  return out;
};

/**
 * "Kiosk — price and what it includes | WECARE.DIGITAL".
 *
 * The shape is the site's: name, em-dash, a descriptor, then the brand suffix every other title
 * carries. The descriptor is the same on all seven because it is a statement about the PAGE, not
 * about the product - and the alternative, splicing in each product's own tagline, breaks the
 * length bound: Paperwork's is 60 characters, which with the name and suffix runs to 96 against
 * tools/browser/seocheck.js's 75-character ceiling.
 *
 * Measured: 50 characters for Kiosk, 62 for Guided Resolution - the longest of the seven.
 */
export const shopPageTitle = ( product: ShopProduct ): string =>
  product.name + ' — price and what it includes | WECARE.DIGITAL';

/** '/shop/kiosk/' - trailingSlash is on, so the canonical form carries one. */
export const shopProductPath = ( product: ShopProduct ): string =>
  '/shop/' + product.slug + '/';
