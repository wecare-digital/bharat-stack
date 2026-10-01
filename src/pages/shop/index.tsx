import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import type { GetStaticProps } from 'next';
import PageMeta from '../../components/PageMeta';
import RotatingHero from '../../components/RotatingHero';
import Breadcrumbs from '../../components/Breadcrumbs';
import type { CycleWord } from '../../components/RotatingHero';
import { ORIGIN, ld } from '../../lib/schema';
import { SHOP_PRODUCTS, shopProductPath } from '../../content/shop';
import type { ShopProduct } from '../../content/shop';

/**
 * /shop/ - the catalogue index.
 *
 * The seven items come from src/content/shop.ts, which reads the committed Wix snapshot in
 * src/content/wix-catalog.json. The prices there are for display and must never reach a payment.
 *
 * The layout is /blog/'s: RotatingHero owns the header offset, the 1300px measure and the gutter;
 * the grid is three columns at 1280px, two at 1024px and one at 767px; cards carry a 3px
 * inline-start spine cycling green, blue and purple.
 *
 * The card headings are h2. The hero owns the h1 and there is no section heading between it and the
 * grid, so h2 is the next rung with nothing skipped. They sit at the 22px/700 card rung rather than
 * the 40px/700 section rung, which is why /shop/ is absent from tools/browser/typecheck.js - that
 * harness pins the section rung for hero-plus-one-section pages, and /blog/ is absent for the same
 * reason.
 */

/**
 * Four verbs, each true of at least one item rather than chosen for rhythm: order (all seven),
 * start (File Assist, Guided Resolution, Paperwork, Viveka), buy (Merchandise, Kiosk), join
 * (Referral Partner). Tints and dots are the four pairs the Grahak OS hero established.
 *
 * Lengths are 5, 5, 3 and 4 characters. The pill animates to each word's measured width, so the
 * spread is how far the line's tail travels every 2400ms; RotatingHero asks for 2-4.
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
 * The catalogue arrives as a prop rather than being read inside the render, so this component is a
 * pure function of its props and a test can render it with an out-of-stock item. Reading
 * SHOP_PRODUCTS directly here would leave the !inStock branch unreachable from any test, since all
 * seven items in the committed snapshot are in stock.
 */
interface ShopIndexProps {
  products: ShopProduct[];
}

const ShopIndex: React.FC<ShopIndexProps> = ( { products } ) => {
  const url = ORIGIN + '/shop/';

  /**
   * An ItemList, so the page says what it collects.
   *
   * Emitted as its own script rather than folded into the WebPage graph, because that graph is
   * built by getPublicPageSchema in _app.tsx and a page cannot reach into it - next/head dedupes
   * <script> on `key`, which the sitewide block does not carry. A separate node with its own @id is
   * valid and is how the site already emits #organization and #website.
   *
   * itemListElement carries `url` and `name` only. A nested Product per entry would restate seven
   * products the seven pages already define, at seven @ids.
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
      {/* No badgeLabel: here it would read "Shop by WECARE.DIGITAL" just below the header's own
          lockup, stating the brand twice in the first thing anyone reads. */}
      <RotatingHero
        frame="What you can"
        words={ SHOP_WORDS }
        sub="Everything the store lists, with its price and what it actually includes."
        ariaLabel="WECARE.DIGITAL shop"
      >
        <div className="shop-shell">
          <Breadcrumbs items={ [ { label: 'Home', href: '/' }, { label: 'Shop' } ] } />

          {/* Saying when the snapshot was taken is the difference between a reference price and a
              quote. */}
          <p className="shop-asof">
            Prices here are from the store catalogue. The store confirms the amount when you
            proceed. Live payment is not on yet, so proceeding prepares your order and charges
            you nothing.
          </p>

          <section className="shop-grid" aria-label="Catalogue">
            { products.map( product => (
              <article className="shop-card" key={ product.slug }>
                <div className="shop-copy">
                  <h2 className="shop-name">
                    <Link href={ shopProductPath( product ) }>{ product.name }</Link>
                  </h2>
                  {/* data-wc-no-translate: the translation pass rewrites text nodes, and a
                      translated "₹6,999.00" is a different number in a different grouping
                      convention. */}
                  <p className="shop-price" data-wc-no-translate="true">{ product.formattedPrice }</p>
                  <p className="shop-tagline">{ product.tagline }</p>
                  {/* Rendered only when it is true. All seven items in the committed snapshot are
                      in stock, so this branch paints nothing today; the alternative was a green
                      "In stock" chip on every card, which is seven identical badges carrying no
                      information. */}
                  { !product.inStock && (
                    <p className="shop-oos">Not available right now.</p>
                  ) }
                </div>
              </article>
            ) ) }
          </section>
        </div>

        <style jsx>{`
          /* No top padding and no max-width: RotatingHero owns both. This div sits inside
             .rh-layout, which already applies the 108px/96px header clearance, the 1300px measure
             and the gutter. The font stack goes too - .rh-shell declares it one level up. */
          .shop-shell{margin:0}

          /* The as-of notice takes the lime-tint-plus-edge treatment, because it does the same job
             as .blog-degraded: something a reader should see before trusting the numbers below it.
             Not an error - the prices are real, they are just dated. */
          .shop-asof{
            margin:0 0 28px;padding:14px 16px;
            background:rgba(209,244,112,.22);border-inline-start:4px solid #d1f470;
            border-radius:8px;
            font-size:16px;line-height:1.55;color:rgba(0,0,0,.898);
          }

          /* The grid and the cards are /blog/'s, value for value: three columns at 1280px, the 3px
             inline-start spine cycling green, blue then purple across the row, the 1px #e5e7eb
             hairline on the other three edges, a lime border and a 2px lift on hover with the
             single shadow this language allows. Breakpoints are 1024px and 767px, which is where
             RotatingHero itself breaks. */
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

          /* The card rung: 22px/700/lh1.27/-.25px on solid black, the same three numbers as the
             blog card headings.
             EVERY LINK RULE GOES THROUGH :global(), AND WITHOUT IT NONE OF THEM APPLY. styled-jsx
             adds its scoping class only to lowercase DOM tags it can see in this file, never to a
             capitalised component - it cannot know whether the component forwards className to a
             DOM node. These headings wrap next/link, so the compiled rule would match nothing. */
          .shop-name{font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;margin:0 0 10px}
          .shop-name :global(a){color:#000;text-decoration:none;text-underline-offset:3px}
          .shop-name :global(a:hover){color:#1a3a2a}
          /* Opaque #1a3a2a, not a translucent ring: at rgba(26,58,42,.25) a focus outline measures
             1.51:1 against white and fails WCAG 1.4.11. */
          .shop-name :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}

          /* The price is not lime, and that is a rule rather than a preference: lime means
             actionable, and the one lime surface a page is allowed is spent on its call to action.
             So the price takes the card rung in dark green, about 11:1 on white, with tabular
             figures so a column of prices lines up on the decimal. */
          .shop-price{
            font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;
            color:#1a3a2a;margin:0 0 12px;font-variant-numeric:tabular-nums;
          }

          /* The one body rung the contract allows: 20px/400/1.4/-.125px at rgba(0,0,0,.898).
             Clamped to four lines because the taglines arrive from Wix at whatever length they were
             written - across the seven they run 25 to 60 characters, so the clamp does not bite
             today and is here so a longer one cannot set the height of its row. */
          .shop-tagline{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0;
            display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;
          }
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

/** The catalogue, read once at build time. output: 'export' means there is no server to call. */
export const getStaticProps: GetStaticProps<ShopIndexProps> = async () => ( {
  props: { products: SHOP_PRODUCTS },
} );

export default ShopIndex;
