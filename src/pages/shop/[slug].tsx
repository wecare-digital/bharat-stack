import React, { useCallback, useState } from 'react';
import Link from 'next/link';
import type { GetStaticPaths, GetStaticProps } from 'next';
import ShopProductHead from '../../components/ShopProductHead';
import Breadcrumbs from '../../components/Breadcrumbs';
import { SHOP_PRODUCTS, shopProductBySlug, catalogReadOn } from '../../content/shop';
import type { ShopProduct } from '../../content/shop';
import { addItem } from '../../lib/cart';

/**
 * /shop/<slug>/ - one page per catalogue item.
 *
 * SEVEN PRERENDERED PAGES, ONE FILE. getStaticPaths enumerates the snapshot, so the set of pages
 * is the set of visible products and cannot drift from it. `fallback: false` because
 * next.config.js sets output: 'export' - there is no server to render an eighth slug, and a
 * request for one gets the export's 404 behaviour, which is the honest answer.
 *
 * THE HEAD IS OWNED BY components/ShopProductHead.tsx, not by PageMeta and the sitewide block in
 * _app.tsx. Read that file's docblock for why: PUBLIC_PAGE_META is keyed on router.pathname, which
 * for a dynamic route is the literal string '/shop/[slug]', so every URL computed from it -
 * canonical, og:url, the WebPage @id - would name a page that does not exist. '/shop/[slug]' is in
 * the isContentPublic chain instead, exactly as /post/[slug] and the four blog index routes are.
 *
 * NO ROTATING HERO, and that is the one place this page departs from its siblings. RotatingHero
 * needs a frame plus four cycle words held within a few characters of each other; inventing four
 * per product, times seven, would be marketing copy the owner never wrote, on pages whose entire
 * content is the owner's own words. So this page states its own top band - and therefore owns the
 * header clearance that .rh-shell would otherwise have handled. See the note on .shopd below,
 * because getting that wrong is a defect this site has already shipped once.
 *
 * NO IMAGE. The snapshot reports mediaCount 0 on all seven products, so there is nothing to show.
 * A grey placeholder frame is a promise that a picture exists.
 *
 * THE CALL TO ACTION IS ADD-TO-CART, and it is the page's single LIME surface - lime means
 * actionable on this site and a page gets one. It adds the product's catalogue REFERENCE and a
 * quantity to the browser cart (src/lib/cart.ts) and points at /cart/, which is the authenticated
 * Cart V2 -> checkout path. The button never charges anything: an order in this system exists only
 * after a payment has been verified server-side (amplify/functions/shared/order_creation.py), and
 * live payment initiation is off by default (amplify/functions/ecommerce/checkout/handler.py), so
 * proceeding prepares an order without taking money. The boundary note below says exactly that - it
 * no longer claims "this page is not a checkout", because a cart path now exists, but it stays
 * truthful that payment is not live yet. The wiring is product-agnostic: it drives off the
 * product's id/slug and a quantity, with no per-product behaviour, because the seven items are
 * dummy placeholders today.
 */

interface ShopProductPageProps {
  product: ShopProduct;
}

const ShopProductPage: React.FC<ShopProductPageProps> = ( { product } ) => {
  // "added" flips once the item is in the cart, turning the CTA into a link to the cart rather
  // than re-adding on every press. Client-only state; the settled markup is the add button, so a
  // no-JS load still shows a coherent, honest page.
  const [ added, setAdded ] = useState<boolean>( false );

  const onAdd = useCallback( (): void => {
    addItem( product, 1 );
    setAdded( true );
  }, [ product ] );

  return (
  <>
    <ShopProductHead product={ product } />
    <main className="shopd" aria-label={ product.name }>
      {/* TWO BANDS, AND THE SHAPE IS BORROWED RATHER THAN INVENTED. Every other page in this
          family is div.rh-hero followed by section.pdp inside one container, and
          tools/browser/sectioncheck.js reports them as exactly two bands. Written as a flat run of
          paragraphs this page reported FOURTEEN - one per <p> - because there was nothing telling
          the reader, or the harness, that the name and the price are one thing and the description
          is another. The identity block and the argument are two bands here for the same reason
          they are on the other fourteen routes. */}
      <div className="shopd-in">
        <div className="shopd-head">
          <Breadcrumbs items={ [
            { label: 'Home', href: '/' },
            { label: 'Shop', href: '/shop/' },
            { label: product.name },
          ] } />

          <h1 className="shopd-h1">{ product.name }</h1>

          {/* data-wc-no-translate for the same reason as the card price: the translation pass
              rewrites text nodes, and a translated "₹24,999.00" is a different number in a
              different grouping convention. */}
          <p className="shopd-price" data-wc-no-translate="true">{ product.formattedPrice }</p>

          { !product.inStock && (
            <p className="shopd-oos" role="status">Not available right now.</p>
          ) }
        </div>

        {/* aria-label, because this is an unlabelled region otherwise - the page's only heading is
            the h1 above it, in the other band. section.pdp names itself exactly this way on the
            fourteen pages ProductPage renders. */}
        <section className="shopd-about" aria-label={ `About ${product.name}` }>
          {/* THE PRODUCT'S OWN WORDS, AS TEXT AND NEVER AS HTML. toParagraphs in
              src/content/shop.ts strips the tags rather than trusting them: this is
              merchant-authored rich text from a third-party CMS, and dangerouslySetInnerHTML would
              make the storefront an XSS surface that depends on Wix's sanitiser instead of ours.
              The first paragraph is the tagline - bold in Wix - and takes the lead rung. */}
          <p className="shopd-lead">{ product.tagline }</p>
          { product.body.map( ( paragraph, index ) => (
            <p className="shopd-p" key={ `p-${index}` }>{ paragraph }</p>
          ) ) }

          {/* THE PAGE'S SINGLE LIME SURFACE: add to cart, then a link on to /cart/. It is a
              button before the item is added (a client action) and a link once it is, so a shopper
              is never stranded. :global() wraps the next/link case because styled-jsx cannot scope
              a capitalised component - see the .shopd-cta rule below. */}
          { added
            ? (
              <Link className="shopd-cta" href="/cart/">Go to your cart</Link>
            )
            : (
              <button className="shopd-cta shopd-cta-btn" type="button" onClick={ onAdd }>
                Add { product.name } to cart
              </button>
            ) }

          {/* THE BOUNDARY STATEMENT, in the hairline box rather than a lime one - .shopd-note
              records the whole argument: lime means actionable on this site and the page's single
              lime surface is already spent on the CTA above. It no longer claims "this page is not
              a checkout" now that a cart path exists, but it stays truthful: the store confirms the
              amount, live payment is not being accepted yet, and proceeding prepares your order
              without charging you. */}
          <p className="shopd-note">
            The price above was read from the store catalogue on { catalogReadOn() }; the store
            confirms the amount when you check out. Live payment is not being accepted yet, so
            adding to your cart and proceeding prepares your order without charging you - nothing is
            taken until a payment has been verified.
          </p>

          <p className="shopd-back"><Link href="/shop/">All items in the shop</Link></p>
        </section>
      </div>

      <style jsx>{`
        /* THE HEADER CLEARANCE IS THE WHOLE REASON THIS BLOCK IS CAREFUL.
           Header is position:fixed and 108px tall, dropping to 96px below 768px. A page whose top
           padding does not match BOTH heights paints its own first line underneath it. /llm/
           shipped exactly that - an inline padding:'48px 20px 80px', and a style attribute cannot
           carry a media query, so it could not express the two-height clearance; its first line
           sat at y=48 with the header's bottom at y=108. tools/browser/pageaudit.js now checks it
           with elementFromPoint at the text's own centre, which is why it is a probe rather than a
           rect comparison.
           Every number here is .rh-shell's and .rh-layout's, because a page that does not use
           RotatingHero must still agree with the fourteen that do: 108px offset, 1300px measure,
           24px gutter, 80px/96px band padding, min-height calc(100vh - 69px), and the font stack
           declared rather than inherited - the public pages render in Inter only because an
           Amplify stylesheet happens to set it on body, and --font-sans has no Inter in it. */
        .shopd{
          min-height:calc(100vh - 69px);
          padding-top:108px;
          box-sizing:border-box;
          background:#fff;
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          color:#1a1a1a;
        }
        .shopd-in{
          width:100%;max-width:1300px;margin:0 auto;
          padding:80px 24px 96px;box-sizing:border-box;
        }

        /* The hero h1 rung, verbatim from .rh-head: clamp(36px,4.3vw,60px) at 600 - LIGHTER than
           the 700 section level, which is this site's deliberate inversion and is not to be
           "corrected". Tracking in em rather than px, because a fixed px value against a fluid
           clamp changes the optical tightness with the viewport - measured at -2.22% to -6.11% of
           the font size before that was fixed, a 2.75x spread.
           NO 400px/340px FONT STEPS. RotatingHero carries them because its headline sits inside an
           animated pill whose padding pushed "amend a request" 11px past a 320px measure. The
           longest name here is "Guided Resolution", whose longest word is "Resolution" - it wraps
           freely and has no pill around it, so there is nothing to step down for. Measured at
           320px and 280px by pageaudit: 0 overflow. */
        .shopd-h1{
          font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;
          letter-spacing:-0.04em;color:rgba(0,0,0,.95);margin:24px 0 0;max-width:900px;
        }

        /* The price takes the card rung - 22px/700/lh 1.27/-.25px - in dark green rather than
           lime, for the reason .shop-price on the listing records: lime means actionable and the
           page's one lime surface is the button. 1a3a2a on white is about 11:1. */
        .shopd-price{
          font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;
          color:#1a3a2a;margin:18px 0 0;font-variant-numeric:tabular-nums;
        }
        .shopd-oos{margin:12px 0 0;font-size:16px;font-weight:600;line-height:1.4;color:rgba(0,0,0,.54)}

        /* The gap between the two bands lives HERE, on the band, rather than on the paragraph
           inside it. It was the lead's 28px top margin, which reached the band above only by
           collapsing through this element's top edge - correct today and silently gone the moment
           anyone gives this section a border or a padding. */
        .shopd-about{margin-top:28px}

        /* The lead runs at the body level but slightly tighter, because it is the product's
           one-line statement of itself rather than a point being made - .pdp-lead's rung exactly.
           700px is .pdp's measure: at 20px the 1300px band would run past 110 characters a line,
           well beyond the 45-75 the rest of the site holds to. */
        .shopd-lead{
          font-size:20px;font-weight:400;line-height:1.45;letter-spacing:-.125px;
          color:rgba(0,0,0,.898);margin:0;max-width:700px;
        }
        /* The single body rung the contract allows, identical to .pdp-p and the blog excerpts. */
        .shopd-p{
          font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
          color:rgba(0,0,0,.898);margin:18px 0 0;max-width:700px;
        }

        /* .pdp-cta, value for value: full-strength #d1f470 with #1a3a2a type, which is the
           contract's own-surface pairing, and a 2px border because the hairline rule is that 1px
           means a static edge and 2px means a hoverable one.
           :global() IS MANDATORY HERE. This is next/link, and styled-jsx adds its scoping class
           only to lowercase DOM tags it can see in this file - a capitalised component never gets
           it, because styled-jsx cannot know whether the component forwards className to a DOM
           node. Without :global() the compiled .jsx-xxx.shopd-cta rule matches nothing and the
           button renders as bare blue underlined text. Measured on the blog pager before the
           identical fix: a.pager-step 69x32, radius 0, border 0, transparent. */
        .shopd-in :global(.shopd-cta){
          display:inline-flex;align-items:center;min-height:52px;margin-top:34px;
          padding:0 26px;border:2px solid #d1f470;border-radius:50px;
          background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
          font-family:inherit;line-height:normal;cursor:pointer;
          transition:background-color .2s,transform .2s,box-shadow .2s;
        }
        .shopd-in :global(.shopd-cta:hover){background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
        .shopd-in :global(.shopd-cta:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px}

        /* Static 1px hairline in e5e7eb, per the rule: 1px static, 2px hoverable. */
        .shopd-note{
          margin:34px 0 0;padding:16px 18px;border:1px solid #e5e7eb;border-radius:12px;
          font-size:16px;line-height:1.55;color:rgba(0,0,0,.54);max-width:700px;
        }

        .shopd-back{margin:28px 0 0;font-size:16px;line-height:1.55}
        .shopd-back :global(a){color:#1a3a2a;font-weight:600;text-underline-offset:3px}
        .shopd-back :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}

        @media(max-width:767px){
          /* BOTH numbers move together, which is the point of the note at the top of this block:
             96px clearance for the 96px header, and .rh-layout's narrow band padding. */
          .shopd{min-height:calc(100vh - 85px);padding-top:96px}
          .shopd-in{padding:48px 16px 64px}
          .shopd-h1{line-height:1.1}
          .shopd-lead{font-size:18px}
          .shopd-p{font-size:18px}
        }
        @media(prefers-reduced-motion:reduce){
          .shopd-in :global(.shopd-cta){transition:none}
          .shopd-in :global(.shopd-cta:hover){transform:none;box-shadow:none}
        }
      `}</style>
    </main>
  </>
  );
};

export const getStaticPaths: GetStaticPaths = async () => ( {
  paths: SHOP_PRODUCTS.map( product => ( { params: { slug: product.slug } } ) ),
  // output: 'export' - there is no server, so an unknown slug cannot be rendered on demand.
  fallback: false,
} );

export const getStaticProps: GetStaticProps<ShopProductPageProps> = async ( { params } ) => {
  const product = shopProductBySlug( String( params?.slug || '' ) );
  // notFound rather than a thrown error: getStaticPaths only produces slugs that resolve, so this
  // branch is unreachable in a normal build - but returning notFound means a snapshot edited to
  // remove a product while a stale path list is cached produces a 404 rather than a build crash.
  if ( !product ) return { notFound: true };
  return { props: { product } };
};

export default ShopProductPage;
