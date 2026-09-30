import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import type { GetStaticProps } from 'next';
import PageMeta from '../../components/PageMeta';
import RotatingHero from '../../components/RotatingHero';
import Breadcrumbs from '../../components/Breadcrumbs';
import type { CycleWord } from '../../components/RotatingHero';
import { ORIGIN, ld } from '../../lib/schema';
import { SHOP_PRODUCTS, catalogReadOn, shopProductPath } from '../../content/shop';
import type { ShopProduct } from '../../content/shop';

/**
 * /shop/ - the catalogue index.
 *
 * WHERE THE SEVEN ITEMS COME FROM: src/content/shop.ts, reading the committed snapshot in
 * src/content/wix-catalog.json. That file's docblock carries the whole argument for a snapshot
 * over a live call, and the rule that these prices are for display and must never reach a
 * payment. Read it before changing anything here.
 *
 * THIS IS NOT A CHECKOUT, and the copy says so rather than implying otherwise. Every card and
 * every product page ends at /contact/, because the cart and checkout reads a real storefront
 * needs (amplify/functions/.../wix-store exposes only /products) do not exist yet. A "Buy now"
 * button that opened a contact form would be the worse kind of defect - one that looks finished.
 *
 * THE LAYOUT IS /blog/'s, DELIBERATELY. This is the site's second index page, and the first one
 * already resolved every question this one raises: RotatingHero owns the header offset, the
 * 1300px measure and the gutter; the grid is three columns at 1280px, two at 1024px and one at
 * 767px; cards carry a 3px inline-start spine cycling green, blue and purple, which is the only
 * accent motif this design language has. Inventing a second treatment for a second listing is
 * how the old site ended up with a different footer on every page.
 *
 * WHY THE CARD HEADINGS ARE h2 AND NOT h3. The hero owns the h1 and there is no section heading
 * between it and the grid, so h2 is the next rung with nothing skipped - the same arrangement
 * /blog/ uses for its post cards. They sit at the 22px/700 CARD rung rather than the 40px/700
 * section rung, which is why /shop/ is deliberately absent from tools/browser/typecheck.js: that
 * harness pins the section-h2 rung for the hero-plus-one-section product pages, and /blog/ is
 * absent from it for exactly the same reason.
 */

/**
 * Four verbs, and each one is true of at least one item in the catalogue rather than being
 * chosen for rhythm: order (all seven), start (File Assist, Guided Resolution, Paperwork and
 * Viveka are processes you begin), buy (Merchandise, Kiosk), join (Referral Partner).
 *
 * Tints and dots are the four pairs the Grahak OS hero established. No new colours - the palette
 * is closed, and amber was measured at 2.04:1 before being kept for pill fills only.
 *
 * Lengths are 5, 5, 3 and 4 characters. The pill animates to each word's measured width, so the
 * spread is how far the line's tail travels every 2400ms; RotatingHero's docblock asks for 2-4.
 */
const SHOP_WORDS: CycleWord[] = [
  { word: 'order', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'start', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'buy', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'join', tint: '#ede9fe', dot: '#9849e8' },
];

const TITLE = 'Shop — what we sell, and what it costs | WECARE.DIGITAL';
const DESCRIPTION = 'Every item the WECARE.DIGITAL store lists, with its price and what it '
  + 'includes. Prices are read from the store catalogue and refreshed when it is republished.';

/**
 * THE CATALOGUE ARRIVES AS A PROP, not as a module import read inside the render.
 *
 * getStaticProps below hands it over, which is /blog/index.tsx's arrangement exactly - that route
 * is four lines over blogIndexProps(1) for the same reason. It makes this component a pure
 * function of its props, so a test can render it with an out-of-stock item and see what a visitor
 * would see. Reading SHOP_PRODUCTS directly in the body would leave the !inStock branch below
 * unreachable from any test, since all seven items in the committed snapshot are in stock.
 */
interface ShopIndexProps {
  products: ShopProduct[];
}

const ShopIndex: React.FC<ShopIndexProps> = ( { products } ) => {
  const url = ORIGIN + '/shop/';

  /**
   * AN ItemList, SO THE PAGE SAYS WHAT IT COLLECTS.
   *
   * Emitted as its own script rather than folded into the WebPage graph, because that graph is
   * built by getPublicPageSchema in _app.tsx out of a PUBLIC_PAGE_META entry and a page cannot
   * reach into it - next/head dedupes <script> on `key`, which the sitewide block does not carry.
   * A separate node with its own @id is valid and is how the site already emits #organization and
   * #website. The blog index pages got the same treatment for the same reason.
   *
   * itemListElement carries `url` and `name` only. A nested Product per entry would restate seven
   * products the seven pages already define, at seven @ids, which is the cross-route entity
   * collision this repo has fixed twice.
   */
  const itemList = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    '@id': url + '#itemlist',
    name: 'The WECARE.DIGITAL catalogue',
    numberOfItems: products.length,
    itemListOrder: 'https://schema.org/ItemListOrderAscending',
    itemListElement: products.map( ( product, index ) => ( {
      '@type': 'ListItem',
      position: index + 1,
      name: product.name,
      url: ORIGIN + shopProductPath( product ),
    } ) ),
  };

  return (
    <>
      <PageMeta title={ TITLE } description={ DESCRIPTION } path="/shop/" />
      <Head>
        <script type="application/ld+json" dangerouslySetInnerHTML={ ld( itemList ) } />
      </Head>
      {/* NO badgeLabel. On a product page the badge names the PRODUCT, which is worth saying; here
          it would read "Shop by WECARE.DIGITAL" 109px below the header's own lockup, stating the
          brand twice in the first thing anyone reads. /blog/ omits it for the same reason and
          src/test/BlogDesign.test.tsx pins that decision. */}
      <RotatingHero
        frame="What you can"
        words={ SHOP_WORDS }
        sub="Everything the store lists, with its price and what it actually includes."
        ariaLabel="WECARE.DIGITAL shop"
      >
        <div className="shop-shell">
          <Breadcrumbs items={ [ { label: 'Home', href: '/' }, { label: 'Shop' } ] } />

          {/* THE DATE IS THE HONEST PART. These prices were true when the snapshot was taken, and
              saying when that was is the difference between a reference price and a quote. The
              second sentence is a statement this page can actually keep: nothing is charged here,
              so asking is the only next step there is. */}
          <p className="shop-asof">
            Prices were read from the store catalogue on { catalogReadOn() }. They are shown for
            reference - ask us to confirm the amount before you pay for anything.
          </p>

          <section className="shop-grid" aria-label="Catalogue">
            { products.map( product => (
              <article className="shop-card" key={ product.slug }>
                <div className="shop-copy">
                  <h2 className="shop-name">
                    <Link href={ shopProductPath( product ) }>{ product.name }</Link>
                  </h2>
                  {/* data-wc-no-translate: the price is a currency-formatted number, and the
                      translation pass rewrites text nodes - a translated "₹6,999.00" is a
                      different number in a different grouping convention, which is the one thing
                      on this card that must survive verbatim. The .meta author line on the blog
                      cards carries the same attribute for the same reason. */}
                  <p className="shop-price" data-wc-no-translate="true">{ product.formattedPrice }</p>
                  <p className="shop-tagline">{ product.tagline }</p>
                  {/* RENDERED ONLY WHEN IT IS TRUE, and as of the committed snapshot all seven
                      items are in stock - so this branch paints nothing today. The alternative was
                      a green "In stock" chip on every card, which is seven identical badges
                      carrying no information. src/test/ShopCatalogue.test.ts exercises the branch
                      so it is not untested. */}
                  { !product.inStock && (
                    <p className="shop-oos">Not available right now.</p>
                  ) }
                </div>
              </article>
            ) ) }
          </section>
        </div>

        <style jsx>{`
          /* NO TOP PADDING AND NO MAX-WIDTH: RotatingHero owns both, exactly as .blog-shell
             records. This div sits inside .rh-layout, which already applies the 108px header
             offset, the 1300px measure and the 24px gutter. Restating any of them doubles it.
             The font stack goes too - .rh-shell declares it one level up. */
          .shop-shell{margin:0}

          /* THE AS-OF NOTICE. Same lime-tint-plus-edge treatment as .blog-degraded and the legal
             notice, because it does the same job: something a reader should see before trusting
             the numbers below it. Not a red error - the prices are real, they are just dated. */
          .shop-asof{
            margin:0 0 28px;padding:14px 16px;
            background:rgba(209,244,112,.22);border-left:4px solid #d1f470;border-radius:8px;
            font-size:16px;line-height:1.55;color:rgba(0,0,0,.898);
          }

          /* THE GRID AND THE CARDS ARE /blog/'s, VALUE FOR VALUE. Three columns at 1280px, the
             3px inline-start spine cycling green, blue then purple across the row, the 1px
             e5e7eb hairline on the other three edges, a lime border and a 2px lift on hover with
             the single shadow this language allows. Breakpoints are 1024px and 767px, which is
             where RotatingHero itself breaks. */
          .shop-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}
          .shop-card{
            display:flex;background:#fff;border:1px solid #e5e7eb;
            border-inline-start:3px solid #3da35a;border-radius:14px;overflow:hidden;
            transition:border-color .2s,transform .2s,box-shadow .2s;
          }
          .shop-card:nth-child(3n+2){border-inline-start-color:#2563eb}
          .shop-card:nth-child(3n+3){border-inline-start-color:#9849e8}
          .shop-card:hover{border-color:#d1f470;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          .shop-copy{display:flex;flex-direction:column;flex:1;padding:26px}

          /* The card-heading rung: 22px/700/lh 1.27/-.25px on solid black. Same three numbers as
             .pdp-point-t and the blog card headings, which is what makes the two listings read as
             one site.
             EVERY LINK RULE GOES THROUGH :global(), AND WITHOUT IT NONE OF THEM APPLY. styled-jsx
             adds its scoping class only to lowercase DOM tags it can see in this file, never to a
             capitalised component - it cannot know whether the component forwards className to a
             DOM node. These headings wrap next/link, so the compiled .jsx-xxx a rule would match
             nothing. Measured on the blog pager before the same fix: a.pager-step 69x32, radius 0,
             border 0, transparent - the 44px targets its comment claimed did not exist. */
          .shop-name{font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;margin:0 0 10px}
          .shop-name :global(a){color:#000;text-decoration:none;text-underline-offset:3px}
          .shop-name :global(a:hover){color:#1a3a2a}
          /* Opaque 1a3a2a, not the translucent ring this site shipped on eighteen controls: at
             rgba(26,58,42,.25) it measured 1.51:1 against white and failed WCAG 1.4.11. */
          .shop-name :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}

          /* THE PRICE IS NOT LIME, and that is a rule rather than a preference. Lime means
             actionable on this site, and the one lime surface a page is allowed is spent on its
             call to action - which on a product page is the only thing to press. A price chip
             competing with it for the same signal is the defect .pdp-note documents being fixed.
             So the price takes the card rung in dark green: 1a3a2a on white is about 11:1.
             Tabular figures so seven prices in a column line up on the decimal. */
          .shop-price{
            font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;
            color:#1a3a2a;margin:0 0 12px;font-variant-numeric:tabular-nums;
          }

          /* The one body rung the contract allows: 20px/400/1.4/-.125px at rgba(0,0,0,.898). It
             is the same declaration the hero sub, the product leads and the blog excerpts use.
             Clamped to four lines because the taglines arrive from Wix at whatever length they
             were written - measured across the seven they run 25 to 60 characters, so the clamp
             does not bite today and is here so a longer one cannot set the height of its row. */
          .shop-tagline{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0;
            display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;
          }
          /* margin-top:auto pins it to the bottom of the card, so a row of cards agrees on where
             the notice sits instead of it floating under a short tagline. The dim rung is the
             site's own rgba(0,0,0,.54), not the 6b7280 dashboard token. */
          .shop-oos{margin:16px 0 0;font-size:16px;font-weight:600;line-height:1.4;color:rgba(0,0,0,.54)}

          @media(max-width:1024px){.shop-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
          @media(max-width:767px){
            .shop-grid{grid-template-columns:1fr;gap:18px}
            .shop-copy{padding:22px}
            /* The tagline gets the full measure at one column, so it can run longer before the
               clamp bites. No new font size: same rung. */
            .shop-tagline{-webkit-line-clamp:6}
          }
          @media(prefers-reduced-motion:reduce){
            .shop-card{transition:none}
            .shop-card:hover{transform:none;box-shadow:none}
          }
        `}</style>
      </RotatingHero>
    </>
  );
};

/**
 * The catalogue, read once at build time. See src/content/shop.ts for why it is a committed
 * snapshot rather than a live call - output: 'export' means there is no server to make one from.
 */
export const getStaticProps: GetStaticProps<ShopIndexProps> = async () => ( {
  props: { products: SHOP_PRODUCTS },
} );

export default ShopIndex;
