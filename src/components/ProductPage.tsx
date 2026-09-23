import React from 'react';
import Head from 'next/head';
import RotatingHero from './RotatingHero';
import type { ProductDef } from '../content/products';

/**
 * One layout for every product page. Copy comes from src/content/products.ts.
 *
 * SELF-STYLING, like BrandBadge, RotatingHero, WorkflowTerminal and LegalDocument:
 * styled-jsx cannot scope a composite component from its parent, so this owns every rule
 * it needs and the route file owns nothing but which product to render.
 *
 * Classes are pdp- prefixed. The globally imported src/styles/*.css declares unscoped rules
 * for generic names and styled-jsx does not shield a page from them.
 *
 * TYPE COMES OFF THE DESIGN CONTRACT and matches bharat-rx.tsx exactly, because these pages
 * sit beside it in the same menu column and any difference would read as an accident:
 * section h2 on the 700 rung (heavier than the hero h1's 600, which is the site's deliberate
 * inversion), card headings at 22px/700/-.25px, and the single body level at
 * 20px/400/1.4/-.125px.
 *
 * THE NOTE IS A HAIRLINE BOX, NOT A LIME ONE. Several of these products are regulated or
 * easily misread - Dastavez is not a law firm, Clear Closure does not act for either party,
 * Open Possibility is not therapy, Elsewhere cannot promise a visa. Those have to be read,
 * but lime on this site means "actionable", and the single lime surface on the page is
 * already spent on the call to action. A boundary statement competing with the CTA for the
 * same signal would be a worse outcome than a quiet one that is actually legible.
 */

interface ProductPageProps {
  product: ProductDef;
}

const SITE = 'https://wecare.digital';

const ProductPage: React.FC<ProductPageProps> = ( { product } ) => (
  <>
    <Head>
      <title>{ product.title }</title>
      <meta name="description" content={ product.description } />
      {/* key="canonical" so this replaces the shared one from _app.tsx rather than adding a
          second - two canonicals on a page is the defect that was already fixed once here. */}
      <link rel="canonical" key="canonical" href={ `${SITE}/${product.slug}/` } />
    </Head>
    <RotatingHero
      ariaLabel={ product.name }
      badgeLabel={ `${product.name} by WECARE.DIGITAL` }
      frame={ product.frame }
      words={ product.words }
      sub={ product.sub }
    >
      <section className="pdp" aria-label={ `About ${product.name}` }>
        <h2 className="pdp-h2">{ product.sectionHeading }</h2>
        <p className="pdp-lead">{ product.lead }</p>

        <ul className="pdp-points">
          { product.points.map( ( point, i ) => (
            <li className="pdp-point" key={ point.heading }>
              <span className="pdp-point-n">{ i + 1 }</span>
              <div>
                <strong className="pdp-point-t">{ point.heading }</strong>
                <p className="pdp-p">{ point.body }</p>
              </div>
            </li>
          ) ) }
        </ul>

        <a className="pdp-cta" href={ product.ctaHref }>{ product.ctaLabel }</a>

        { product.note && <p className="pdp-note">{ product.note }</p> }

        <style jsx>{`
          .pdp{max-width:700px}
          .pdp-h2{
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);margin:0 0 22px;
          }
          /* The lead runs at the body level but slightly tighter, because it is a paragraph
             of context rather than a point being made. */
          .pdp-lead{font-size:20px;font-weight:400;line-height:1.45;letter-spacing:-.125px;color:rgba(0,0,0,.898);margin:0 0 34px}

          .pdp-points{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:20px}
          .pdp-point{display:flex;gap:16px;align-items:flex-start}
          /* The .22 lime tint: the contract's quiet treatment, right for a counter that
             labels rather than acts. Full-strength lime is reserved for the CTA below. */
          .pdp-point-n{
            flex:0 0 auto;width:34px;height:34px;border-radius:50%;
            display:grid;place-items:center;
            background:rgba(209,244,112,.22);color:#1a3a2a;
            font-size:15px;font-weight:700;
          }
          .pdp-point-t{display:block;margin:5px 0 6px;font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#000}
          .pdp-p{font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:rgba(0,0,0,.898);margin:0}

          /* Full-strength #d1f470 with #1a3a2a type - the contract's own-surface pairing -
             and 2px because the hairline rule is that 2px means hoverable. */
          .pdp-cta{
            display:inline-flex;align-items:center;min-height:52px;margin-top:30px;
            padding:0 26px;border:2px solid #d1f470;border-radius:50px;
            background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
            transition:background-color .2s,transform .2s,box-shadow .2s;
          }
          .pdp-cta:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          .pdp-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}

          /* Static 1px hairline, per the rule: 1px static, 2px hoverable. */
          .pdp-note{
            margin:34px 0 0;padding:16px 18px;border:1px solid #e5e7eb;border-radius:12px;
            font-size:16px;line-height:1.55;color:rgba(0,0,0,.54);
          }

          @media(max-width:767px){
            .pdp-lead{font-size:18px}
            .pdp-p{font-size:18px}
            .pdp-point-t{font-size:20px}
          }
        `}</style>
      </section>
    </RotatingHero>
  </>
);

export default ProductPage;
