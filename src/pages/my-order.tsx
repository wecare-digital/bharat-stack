import React from 'react';
import PageMeta from '../components/PageMeta';
import RotatingHero, { type CycleWord } from '../components/RotatingHero';

/**
 * /my-order — where a customer checks what they have already asked for.
 *
 * ROUTING: '/my-order' must be in the EXACT-MATCH allowlist in _app.tsx or this renders
 * an empty body with HTTP 200 - a 404 that does not look like one. trailingSlash means
 * the URL is /my-order/.
 *
 * THIS REPLACED "Request Tracking" IN THE MENU rather than sitting beside it. The two are
 * the same function under different names, and a menu that offers both sends the same
 * visitor to two places to answer one question. If both are genuinely wanted - say
 * "My Order" for purchases and "Request Tracking" for service requests - that is a real
 * distinction and the row should come back, but it needs different destinations to be
 * worth the space.
 *
 * NOT YET WIRED TO ANY DATA. There is no order-lookup endpoint on the public site, and a
 * page that asks for an order number and then cannot answer would be worse than an
 * honest signpost. So this is the hero plus a route to the Selfservice portal, which is
 * where order state actually lives today. The moment an endpoint exists, the lookup form
 * belongs here.
 */

// "Track your order / delivery / request / booking" - all four complete the frame and
// all are 5 to 8 characters, so the pill barely travels. Tints and dots reused verbatim
// from the Grahak OS hero; no new colours.
const CYCLE_WORDS: CycleWord[] = [
  { word: 'order', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'delivery', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'request', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'booking', tint: '#ede9fe', dot: '#9849e8' },
];

const SELFSERVICE = 'https://www.wecare.digital/selfservice';

const MyOrderPage: React.FC = () => (
  <>
    <PageMeta
      title="My Order — WECARE.DIGITAL"
      description="Check the status of an order, delivery, request or booking with WECARE.DIGITAL, and find what to do if something needs changing."
      path="/my-order/"
    />
    <RotatingHero
      ariaLabel="My order"
      badgeLabel="Selfservice — WECARE.DIGITAL"
      frame="Track your"
      words={ CYCLE_WORDS }
      sub="Every order and request is tracked end to end, with one place to check where things stand."
    >
      <section className="mo" aria-label="Check an order">
        <h2 className="mo-h2">Check where something stands</h2>
        <p className="mo-p">
          Order and request status lives in the Selfservice portal. Open it with the
          reference from your confirmation message and it will show the current stage,
          what happens next, and who to contact if something needs changing.
        </p>
        <a className="mo-cta" href={ SELFSERVICE }>Open Selfservice</a>

        <h2 className="mo-h2 mo-h2-spaced">If something needs changing</h2>
        <p className="mo-p">
          Amendments, cancellations and refunds are handled through the same portal. What
          is possible depends on how far along the order is - the detail is in section 14
          of our{ ' ' }
          {/* Plain anchor, not next/link, for the reason Footer.tsx documents: styled-jsx
              does not scope composite components, so a Link carrying mo-link would arrive
              with no styling at all. */}
          { /* eslint-disable-next-line @next/next/no-html-link-for-pages */ }
          <a className="mo-link" href="/terms/">Terms of Service</a>, which covers
          cancellations, refunds and rescheduling.
        </p>
        <p className="mo-p">
          If you cannot find the reference, or the status looks wrong, reach us on{ ' ' }
          <a className="mo-link" href="tel:+919330994400">+91 9330994400</a> or{ ' ' }
          <a className="mo-link" href="mailto:one@wecare.digital">one@wecare.digital</a>.
        </p>

        <style jsx>{`
          /* mo- prefixed. The globally imported src/styles/*.css declares unscoped rules
             for generic names and styled-jsx does not shield a page from them. */
          .mo{max-width:700px}
          /* Section h2 is the contract's 700 rung - HEAVIER than the hero h1's 600. That
             inversion is intentional across the whole site. */
          .mo-h2{
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);margin:0 0 14px;
          }
          .mo-h2-spaced{margin-top:44px}
          /* The one body level: 20px/400/1.4/-.125px at rgba(0,0,0,.898). */
          .mo-p{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0 0 14px;
          }
          /* Full-strength lime with #1a3a2a type: the contract's treatment for our own
             surfaces at full voice, the same pair as BrandBadge and .msg.sent. This is
             the page's single call to action, so it is the one place that earns it.
             2px border because it is hoverable - the hairline rule is that 2px means
             interactive and 1px means static. */
          .mo-cta{
            display:inline-flex;align-items:center;min-height:52px;margin-top:6px;
            padding:0 26px;border:2px solid #d1f470;border-radius:50px;
            background:#d1f470;color:#1a3a2a;
            font-size:17px;font-weight:600;text-decoration:none;
            transition:background-color .2s,border-color .2s,transform .2s,box-shadow .2s;
          }
          .mo-cta:hover{
            background:#fff;border-color:#d1f470;
            transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12);
          }
          .mo-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
          .mo-link{color:#1a3a2a;font-weight:600;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px}
          .mo-link:hover{background:rgba(209,244,112,.22)}
          @media(max-width:767px){
            .mo-p{font-size:18px}
            .mo-h2-spaced{margin-top:36px}
          }
        `}</style>
      </section>
    </RotatingHero>
  </>
);

export default MyOrderPage;
