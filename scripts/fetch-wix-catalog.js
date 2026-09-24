#!/usr/bin/env node
/**
 * Pull the Wix Stores catalog into a committed snapshot at
 * src/content/wix-catalog.json.
 *
 * WHY A SNAPSHOT AND NOT A RUNTIME FETCH. next.config.js sets output:'export', so the
 * public site is pre-generated HTML with no server of ours at runtime. That rules out
 * the two obvious alternatives:
 *
 *   - Fetching from the BROWSER would need the credential in the bundle. A Wix API key
 *     is NOT like a Maps browser key - it is account-scoped (tenant: account) and cannot
 *     be referrer-restricted, so shipping it would hand over the whole Wix account. It
 *     would also be a cross-origin call to wixapis.com with no CORS grant.
 *   - Fetching through our own Lambda at runtime works and already exists
 *     (api.wecare.digital/wix-store/products), but it is authenticated - it answers 401
 *     to the public - and it puts a network hop and a spinner in front of a product list
 *     that changes a few times a month.
 *
 * So the credential stays here, on a developer machine or a CI runner, and the OUTPUT -
 * names, prices, descriptions, which are public information by definition - is committed.
 * The site then renders the catalog with no network call at all.
 *
 * THE SNAPSHOT GOES STALE, and that is the trade-off being accepted. Re-run this after
 * any catalog edit in Wix. It is deliberately NOT wired into `npm run build`: a build
 * that reaches the network is a build that fails when the network or the token does,
 * and nobody wants a deploy blocked by an expired Wix key. A CI job can call it if that
 * changes.
 *
 * IMAGES ARE NOT PULLED. The owner asked for data only, and at the time of writing all
 * seven products carry zero media items anyway.
 *
 * USAGE
 *   WIX_API_KEY='IST...' WIX_SITE_ID='fcd8...' node scripts/fetch-wix-catalog.js
 *
 * Never pass the key on a shared shell's history, and never commit it - .env* is
 * gitignored and scripts/block_inline_secrets.py rejects credential-shaped strings.
 *
 * ENDPOINT CHOICE IS MEASURED. stores-reader/v1/products/query returns 200;
 * stores/v1/products/query returns 428 (Precondition Required) against this site, so the
 * reader path is the one that works. Do not "modernise" it without re-testing.
 */

// ESM, because package.json declares "type": "module" - a require() here dies with
// "require is not defined in ES module scope", which reads like a broken script rather
// than a module-system mismatch. __dirname does not exist in ESM either, hence the
// fileURLToPath dance.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname( fileURLToPath( import.meta.url ) );
const OUT = path.resolve( HERE, '..', 'src', 'content', 'wix-catalog.json' );
const ENDPOINT = 'https://www.wixapis.com/stores-reader/v1/products/query';
const PAGE_SIZE = 100;

function die( msg ) {
  console.error( `fetch-wix-catalog: ${msg}` );
  process.exit( 1 );
}

/**
 * Keep only the fields the site actually renders. Two reasons beyond tidiness: the raw
 * payload is ~68 KB of mostly media and inventory internals for 7 products, and a
 * snapshot that mirrors every upstream field turns every unrelated Wix change into a
 * diff in this repo.
 */
function slim( p ) {
  const priceData = p.priceData || {};
  const formatted = priceData.formatted || {};
  const stock = p.stock || {};
  return {
    id: p.id,
    name: p.name || '',
    slug: p.slug || '',
    // productType is 'physical' for all seven today, which is wrong for the service
    // ones - it makes Wix demand a shipping address at checkout. Recorded as-is rather
    // than corrected here, because the fix belongs in Wix, not in a mirror of Wix.
    productType: p.productType || '',
    visible: p.visible !== false,
    sku: p.sku || '',
    ribbon: p.ribbon || '',
    // Numeric price for arithmetic, formatted for display. Keeping only one of them
    // means either re-deriving currency symbols in the UI or parsing money out of a
    // string, and both go wrong.
    price: typeof priceData.price === 'number' ? priceData.price : null,
    currency: priceData.currency || '',
    formattedPrice: formatted.price || '',
    discountedPrice: typeof priceData.discountedPrice === 'number' ? priceData.discountedPrice : null,
    inStock: stock.inStock !== false,
    // Wix returns description as HTML. It is stored raw and MUST be treated as
    // untrusted when rendered - it is authored in Wix, outside this repo's review.
    descriptionHtml: p.description || '',
    collectionIds: p.collectionIds || [],
    optionCount: ( p.productOptions || [] ).length,
    variantCount: ( p.variants || [] ).length,
    mediaCount: ( ( p.media && p.media.items ) || [] ).length,
  };
}

async function main() {
  const key = process.env.WIX_API_KEY;
  const site = process.env.WIX_SITE_ID;
  if ( !key || !site ) {
    die( 'WIX_API_KEY and WIX_SITE_ID must both be set.\n' +
      '  The existing snapshot is left untouched, so this is safe to skip.' );
  }

  const products = [];
  let offset = 0;
  let total = null;

  // Paginate rather than assuming one page. Seven products fit in one request today;
  // hardcoding that assumption is how a catalog silently truncates at 101.
  for ( let guard = 0; guard < 50; guard++ ) {
    const res = await fetch( ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': key,
        'wix-site-id': site,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify( { query: { paging: { limit: PAGE_SIZE, offset } } } ),
    } );

    if ( !res.ok ) {
      const body = await res.text().catch( () => '' );
      die( `HTTP ${res.status} from Wix. ${body.slice( 0, 200 )}\n` +
        '  401/403 means the key is wrong, expired or lacks Stores read scope.\n' +
        '  428 means you are on stores/v1 - this script uses stores-reader/v1 on purpose.' );
    }

    const data = await res.json();
    const page = data.products || [];
    total = data.totalResults != null ? data.totalResults : total;
    products.push( ...page );
    offset += page.length;
    if ( !page.length || ( total != null && products.length >= total ) ) break;
  }

  const slimmed = products
    .map( slim )
    // Stable order so the committed file does not churn when Wix reorders its response.
    .sort( ( a, b ) => a.slug.localeCompare( b.slug ) );

  const snapshot = {
    // No token, no account id, no site id in the output. The site id is a tenant
    // identifier and there is no reason for it to sit in a public bundle.
    source: 'wix stores-reader/v1',
    fetchedAt: new Date().toISOString(),
    productCount: slimmed.length,
    products: slimmed,
  };

  fs.mkdirSync( path.dirname( OUT ), { recursive: true } );
  fs.writeFileSync( OUT, JSON.stringify( snapshot, null, 2 ) + '\n' );

  console.log( `fetch-wix-catalog: wrote ${slimmed.length} product(s) to ${path.relative( process.cwd(), OUT )}` );
  for ( const p of slimmed ) {
    console.log( `  ${p.slug.padEnd( 20 )} ${p.formattedPrice.padStart( 11 )}  ${p.productType.padEnd( 9 )} ` +
      `opts=${p.optionCount} variants=${p.variantCount} media=${p.mediaCount}${p.visible ? '' : '  (HIDDEN)'}` );
  }
}

main().catch( e => die( e && e.message ? e.message : String( e ) ) );
