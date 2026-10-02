import React, { useEffect, useRef } from 'react';
import PageMeta from '../components/PageMeta';
import RotatingHero from '../components/RotatingHero';
import type { CycleWord } from '../components/RotatingHero';

/**
 * /zip — one place for everything about a request, delivery or pickup.
 *
 * SECTION 3 of the customer-experience brief. It sits under the "Request" group in the header
 * (Header.tsx COLUMNS), directly after Orders. The owner's identity for the page is "Zip" and the
 * lead is "Track it. Arrange it. Keep it moving."
 *
 * NOW MATCHES THE HOME PAGE, by owner request. Zip previously used components/PageTopBand — the
 * fixed-statement band — on the reasoning that its heading was the single word "Zip" rather than a
 * rotating phrase. The owner has overridden that: Zip must share the HOME PAGE'S look, including
 * its animated hero and its scroll-reveal closing band, while keeping Zip's own content and its
 * honest "coming soon" treatment for capabilities with no backend.
 *
 * So this page now reuses the SAME two mechanisms the home page animates with, rather than copying
 * their markup or inventing a lookalike:
 *   1. THE ROTATING HERO. components/RotatingHero is the reusable, self-styling version of the
 *      home page's headline pill — identical interval, easings, white entrance shutter and dot
 *      (tools/browser/animcheck.js asserts the family shares one computed transition set). It is
 *      what /shop/, /blog/ and every product page already reuse, and what src/test/BlogDesign
 *      calls "the actual RotatingHero the home page uses". Reusing it is how the "animate as one
 *      family" rule in index.tsx's comments keeps holding. The hero owns the page's single <h1>
 *      and <main>; the page must not add a second of either. The rotation cycles words that are
 *      true of Zip — order / request / delivery / pickup, the three nouns the lead and sub already
 *      name — rather than the home page's marketing audiences.
 *   2. THE SCROLL-REVEAL CLOSING BAND. The home page's closing band reveals once when it scrolls
 *      into view: a lime rule draws itself across and the lines stagger in behind it. That is an
 *      OPT-IN entrance — the CSS ships the final, visible state and JavaScript adds .is-armed only
 *      once it has confirmed it can animate, so no JS, no IntersectionObserver or reduced motion
 *      all leave the band fully readable. This page replicates that exact mechanism (closeRef +
 *      a one-shot IntersectionObserver at threshold 0.18, armed through the node's classList, the
 *      final state shipped as the CSS default), so the degradation and accessibility guarantees
 *      are the same ones the home page proved.
 *
 * SHARED SHELL, NOT A NEW ONE. The Header, Footer and support widget are mounted once in
 * _app.tsx, so this page must not import them. RotatingHero provides the one <main> and the one
 * <h1>; everything else below is this page's own content inside the shared 1300px measure.
 *
 * ROUTING: '/zip' must be in PUBLIC_PAGE_META in _app.tsx (render allowlist + schema), in
 * PUBLIC_EXACT in scripts/generate-sitemap.js (crawl allowlist), and in config/public-pages.json
 * (generated — run scripts/generate-public-pages.js). Miss any and the page serves the staff
 * sign-in shell at HTTP 200. trailingSlash means the URL is /zip/.
 *
 * REAL CAPABILITIES vs NON-TRANSACTING ARCHITECTURE. Only actions backed by a real existing route
 * are rendered as working links:
 *   Track Order        -> /orders/
 *   Track Request      -> /orders/            (orders.tsx tracks "order, delivery, request or booking")
 *   Amend Request      -> /request-amendment/
 *   Send Documents     -> /drop-docs/
 *   Open Vault         -> /vault/
 *   Leave Review       -> /leave-review/
 * There is NO courier / pickup / visit-booking / delivery-tracking backend in this repository
 * (verified: no such handler exists under amplify/functions). So "Book a Visit", "Prescription
 * Pickup", "Book Pickup / Shipment Pickup" and "Check Delivery Status" are rendered as clearly
 * labelled, non-transacting "coming soon" items — a disabled chip with aria-disabled, carrying no
 * href and no action, so nothing looks like a working booking button. The architecture is prepared
 * for a later provider without inventing functionality today. The hero rotating through "pickup"
 * and "delivery" is descriptive of the domain Zip covers, not a claim that either can be
 * transacted here today — the coming-soon section below states plainly which cannot.
 */

// The hero's rotating nouns. Chosen to be TRUE OF ZIP rather than borrowed from the home page's
// audiences: these are the four things the lead and sub already say Zip is about — "a request,
// delivery or pickup" — so the rotation describes the page's own subject. Tints/dots are the four
// per-subject pairs the Grahak OS hero established and the home page reuses verbatim; no new
// colour. Lengths are 5 / 7 / 8 / 6 characters, inside RotatingHero's 2-4-character spread guidance
// once measured, and well under its narrowest-breakpoint fit.
const ZIP_WORDS: CycleWord[] = [
  { word: 'order', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'request', tint: '#ede9fe', dot: '#9849e8' },
  { word: 'delivery', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'pickup', tint: '#fef3c7', dot: '#f0a818' },
];

// The real request routes Zip signposts, each one answering the action beside it. These are the
// same destinations the "Request" group lists, so Zip and the menu cannot drift apart.
const ACTIONS: { label: string; href: string; note: string }[] = [
  { label: 'Track an order', href: '/orders/', note: 'See where an order, delivery, request or booking stands.' },
  { label: 'Track a request', href: '/orders/', note: 'The same place tracks a service request end to end.' },
  { label: 'Amend a request', href: '/request-amendment/', note: 'Change a date, detail or scope on something under way.' },
  { label: 'Send documents', href: '/drop-docs/', note: 'Drop the paperwork a request needs, once.' },
  { label: 'Open your vault', href: '/vault/', note: 'Ask for a copy of a document held against a request.' },
  { label: 'Leave a review', href: '/leave-review/', note: 'Tell us how something went, well or badly.' },
];

// Pickup, visit-booking and live delivery tracking have NO backend here. They are listed so the
// page is honest about what is coming, but each is a disabled, non-transacting affordance — never
// a working-looking button.
const COMING_SOON: { label: string; note: string }[] = [
  { label: 'Book a visit', note: 'Scheduling a visit is not wired up yet.' },
  { label: 'Prescription pickup', note: 'Pickup is not available online yet.' },
  { label: 'Book a pickup', note: 'General courier pickup is not available online yet.' },
  { label: 'Shipment pickup', note: 'Arranging a shipment pickup is not available online yet.' },
  { label: 'Check delivery status', note: 'Live delivery tracking is not wired up yet.' },
];

const ZipPage: React.FC = () => {
  // The scroll-reveal closing band, armed through this node — the SAME mechanism the home page
  // uses. No React state: the reveal is a visual side-effect with no bearing on what React
  // renders, so it is driven by classList on the node itself, which is the case the
  // react-hooks/set-state-in-effect rule exists to steer away from state.
  const closeRef = useRef<HTMLElement | null>( null );

  useEffect( () => {
    const el = closeRef.current;
    if ( !el ) return undefined;

    // THE ANIMATION IS OPT-IN, NOT OPT-OUT, ported from index.tsx's closing band. The CSS ships
    // the FINAL state — everything visible — and this effect adds .is-armed to hide the start
    // state only once it knows it can animate. No JS, no IntersectionObserver, or reduced motion
    // all leave the band fully readable, so the entrance can never be the reason content cannot
    // be read.
    if ( typeof IntersectionObserver === 'undefined' ) return undefined;
    // typeof guard as well as the call: jsdom does not implement matchMedia and throws rather than
    // returning undefined, so a page must not depend on the test setup stubbing it.
    const reduce = typeof window.matchMedia === 'function'
      && window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches;
    if ( reduce ) return undefined;

    el.classList.add( 'is-armed' );

    const io = new IntersectionObserver(
      entries => {
        if ( entries.some( e => e.isIntersecting ) ) {
          el.classList.add( 'is-in' );
          io.disconnect(); // One-shot: it is an entrance, not a scroll effect.
        }
      },
      // 18% visible before it plays, so the reveal is not already finished by the time the section
      // is properly on screen — the same threshold the home page uses.
      { threshold: 0.18 }
    );
    io.observe( el );

    return () => io.disconnect();
  }, [] );

  return (
    <>
      <PageMeta
        title="Zip — WECARE.DIGITAL"
        description="Everything about your request, delivery or pickup in one place: track an order, amend a request, send documents, open your vault or leave a review."
        path="/zip/"
      />
      {/* badgeLabel names the FEATURE above the headline — the documented product-badge use, as on
          every /products/ page — so "Zip" stays the first, prominent, translation-safe word on the
          page while the hero owns the <h1> and the one <main> landmark. */}
      <RotatingHero
        badgeLabel="Zip"
        frame="Everything about your"
        words={ ZIP_WORDS }
        sub="Track it. Arrange it. Keep it moving."
        ariaLabel="Zip"
      >
        <section className="zip-in" aria-label="What you can do from here">
          <h2 className="zip-h2">Everything about your request, delivery or pickup in one place</h2>
          <p className="zip-p">
            Pick the thing you need and we will take you straight to it. Each one below is a page
            that already works — nothing here asks for payment.
          </p>

          <ul className="zip-grid" aria-label="Available actions">
            { ACTIONS.map( action => (
              <li className="zip-card" key={ action.label + action.href }>
                {/* Plain anchor, not next/link: styled-jsx does not scope a capitalised component,
                    so a Link carrying zip-card-link would arrive unstyled. */}
                {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
                <a className="zip-card-link" href={ action.href }>
                  <span className="zip-card-label">{ action.label }</span>
                  <span className="zip-card-note">{ action.note }</span>
                </a>
              </li>
            ) ) }
          </ul>

          <h2 className="zip-h2 zip-h2-spaced">Coming soon</h2>
          <p className="zip-p">
            Visits, pickups and live delivery tracking are not available online yet. We are not
            going to show a button that cannot do anything — these will light up once the service
            behind them is in place.
          </p>

          <ul className="zip-grid zip-grid-muted" aria-label="Not available yet">
            { COMING_SOON.map( item => (
              <li className="zip-card zip-card-soon" key={ item.label }>
                {/* NOT a link and NOT a button: no href, aria-disabled, so assistive technology and
                    the pointer both get that there is nothing to transact here. */}
                <span className="zip-soon" aria-disabled="true">
                  <span className="zip-card-label">{ item.label }</span>
                  <span className="zip-soon-tag">Coming soon</span>
                  <span className="zip-card-note">{ item.note }</span>
                </span>
              </li>
            ) ) }
          </ul>
        </section>

        {/* THE CLOSING BAND, replicating the home page's scroll-reveal treatment. It is a direct
            child of RotatingHero's .rh-layout, so the 96px section gap and the page measure are
            already applied — no margin-top, which on the home page was a measured double-spacing
            bug. The reveal is OPT-IN: everything below ships visible as the CSS default and the
            closeRef effect only hides the start state once it can animate. */}
        <section className="zip-close" aria-labelledby="zip-close-title" ref={ closeRef }>
          <div className="zip-close-panel">
            <p className="zip-close-eyebrow">One place</p>
            <h2 className="zip-close-title" id="zip-close-title">Keep it moving.</h2>
            <p className="zip-close-lead">
              Track it, amend it, or send what it needs — then watch where it stands. One place for
              everything about a request, delivery or pickup, in your language, your way.
            </p>
            <span className="zip-close-rule" aria-hidden="true" />
            <ul className="zip-close-points">
              <li>Go straight to the page that answers you.</li>
              <li>Nothing here asks for payment.</li>
              <li>We say plainly what is not ready yet.</li>
            </ul>
            {/* A PLAIN <a>, and it must stay one: styled-jsx only scopes lowercase DOM tags, so a
                next/link carrying zip-close-cta would render unstyled. Every CTA on the public
                pages is a plain <a> for the same reason. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a className="zip-close-cta" href="/orders/">Track something now</a>
          </div>
        </section>

        <style jsx>{`
          /* zip- prefixed: the globally imported src/styles/*.css declares unscoped rules for
             generic names and styled-jsx does not shield a page from them. */
          .zip-in{max-width:900px}
          /* Section h2 is the contract's 700 rung — HEAVIER than the hero h1's 600, the site's
             deliberate inversion. */
          .zip-h2{
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);margin:0 0 14px;
          }
          .zip-h2-spaced{margin-top:56px}
          /* The one body rung: 20px/400/1.4/-.125px at rgba(0,0,0,.898). */
          .zip-p{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0 0 28px;max-width:640px;
          }
          .zip-grid{
            list-style:none;margin:0;padding:0;display:grid;gap:16px;
            grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
          }
          .zip-grid-muted{margin-top:4px}
          .zip-card{margin:0}
          /* The card treatment: 1px #e5e7eb hairline (static edge), 12px radius, matching the
             catalogue's aside cards. The whole card is the target. */
          .zip-card-link,.zip-soon{
            display:flex;flex-direction:column;gap:6px;height:100%;box-sizing:border-box;
            padding:18px 20px;border:1px solid #e5e7eb;border-radius:12px;
            text-decoration:none;color:inherit;
          }
          .zip-card-link{transition:border-color .2s,transform .2s,box-shadow .2s;background:#fff}
          .zip-card-link:hover{
            border-color:#d1f470;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12);
          }
          .zip-card-link:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}
          .zip-card-label{font-size:18px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#1a3a2a}
          .zip-card-note{font-size:15px;line-height:1.5;color:rgba(0,0,0,.54)}
          /* The non-transacting items read as inert: a dashed edge and a tinted "coming soon" tag,
             no hover lift, no pointer cursor, default cursor so it never looks clickable. */
          .zip-card-soon .zip-soon{
            border-style:dashed;background:rgba(0,0,0,.015);cursor:default;
          }
          .zip-soon-tag{
            align-self:flex-start;font-size:12px;font-weight:700;letter-spacing:.3px;
            text-transform:uppercase;color:#1a3a2a;background:rgba(209,244,112,.35);
            padding:2px 8px;border-radius:999px;
          }

          /* THE CLOSING BAND — the home page's .home-close treatment, kept zip- prefixed.
             A tinted own-surface panel: the same 14px radius and rgba(209,244,112,.22) lime tint
             the rest of the site uses, with a 2px #d1f470 edge — no new colour. */
          .zip-close-panel{
            padding:clamp(28px,4vw,56px);
            border:2px solid #d1f470;border-radius:14px;
            background:rgba(209,244,112,.22);
          }
          .zip-close-eyebrow{
            margin:0 0 14px;font-size:12px;font-weight:700;
            letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a;
          }
          /* Section h2 on the 700 rung — heavier than the hero h1's 600, the site's inversion.
             Same clamp as the other section headings so they read as siblings. */
          .zip-close-title{
            margin:0 0 16px;max-width:19ch;
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);
          }
          .zip-close-lead{
            margin:0;max-width:62ch;
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);
          }

          /* READ THE .is-armed PATTERN BEFORE CHANGING ANY OF THIS. Every rule below ships its
             FINAL, visible state as the default. .is-armed is added by JavaScript only when it has
             confirmed it can animate, and that is what hides the start state; .is-in then plays the
             reveal. The effect is therefore additive, and no JS / no IntersectionObserver /
             reduced motion all leave this section fully readable. */

          /* THE RULE DRAWS ITSELF. transform:scaleX is compositor-only, so it cannot cause layout
             on any frame the way animating width would. transform-origin:left makes it grow from
             the left edge. */
          .zip-close-rule{
            display:block;height:3px;margin:30px 0;background:#d1f470;
            transform-origin:left center;
            transition:transform .62s cubic-bezier(.22,.61,.36,1);
          }
          .zip-close.is-armed .zip-close-rule{transform:scaleX(0)}
          .zip-close.is-armed.is-in .zip-close-rule{transform:scaleX(1)}

          .zip-close-points{margin:0;padding:0;max-width:62ch;list-style:none;display:flex;flex-direction:column;gap:12px}
          .zip-close-points li{
            position:relative;padding-inline-start:26px;
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:rgba(0,0,0,.898);
            transition:opacity .5s ease,transform .5s ease;
          }
          /* A tick drawn with two borders on a rotated box: no asset, cannot 404. The three ticks
             carry the home band's green / blue / purple, in the same top-to-bottom order, so the
             two pages read as a family. */
          .zip-close-points li:nth-child(2)::before{border-left-color:#2563eb;border-bottom-color:#2563eb}
          .zip-close-points li:nth-child(3)::before{border-left-color:#9849e8;border-bottom-color:#9849e8}
          .zip-close-points li::before{
            content:'';position:absolute;inset-inline-start:2px;top:7px;
            width:11px;height:6px;
            border-left:2.5px solid #3da35a;border-bottom:2.5px solid #3da35a;
            transform:rotate(-45deg);
          }
          .zip-close.is-armed .zip-close-points li{opacity:0;transform:translateY(8px)}
          .zip-close.is-armed.is-in .zip-close-points li{opacity:1;transform:none}
          /* Staggered behind the rule, which finishes at .62s. Three 90ms steps read as one
             settling movement rather than three separate events. */
          .zip-close.is-armed.is-in .zip-close-points li:nth-child(1){transition-delay:.34s}
          .zip-close.is-armed.is-in .zip-close-points li:nth-child(2){transition-delay:.43s}
          .zip-close.is-armed.is-in .zip-close-points li:nth-child(3){transition-delay:.52s}

          /* Full-strength lime with #1a3a2a type and a #1a3a2a border — the contract's own-surface
             pairing, and the border is #1a3a2a (not the lime fill) so the control's boundary
             clears WCAG 1.4.11's 3:1 against the pale panel. */
          .zip-close-cta{
            display:inline-flex;align-items:center;min-height:52px;margin-top:32px;
            padding:0 28px;border:2px solid #1a3a2a;border-radius:50px;
            background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
            transition:opacity .5s ease,transform .5s ease,background-color .2s,box-shadow .2s;
          }
          /* opacity:0 (not visibility:hidden) so the control stays in the accessibility tree and
             the tab order; pointer-events:none so a hidden control is not clickable. FOCUS REVEALS
             IT — sequential focus scrolls the band on screen, the :focus rule makes the button
             visible in the same moment, and the observer fires too. */
          .zip-close.is-armed .zip-close-cta{opacity:0;transform:translateY(8px);pointer-events:none}
          .zip-close.is-armed.is-in .zip-close-cta{opacity:1;transform:none;pointer-events:auto;transition-delay:.62s}
          /* After .is-in on purpose: same specificity, so source order decides and focus wins.
             transition:none because a reader who has just tabbed to a control should see it now. */
          .zip-close.is-armed .zip-close-cta:focus{opacity:1;transform:none;pointer-events:auto;transition:none}
          .zip-close-cta:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          .zip-close-cta:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}

          @media(max-width:767px){
            .zip-p{font-size:18px}
            .zip-h2-spaced{margin-top:44px}
            .zip-close-title{max-width:none}
          }

          @media(prefers-reduced-motion:reduce){
            .zip-card-link{transition:none}
            .zip-card-link:hover{transform:none;box-shadow:none}
            /* Belt and braces: the effect already never arms under reduced motion (the JS returns
               before adding .is-armed), so these rules guard the case where the preference changes
               after arming, when the class is already on the node. They kill the movement without
               hiding anything. */
            .zip-close-rule,.zip-close-points li,.zip-close-cta{transition:none}
            .zip-close.is-armed .zip-close-rule{transform:scaleX(1)}
            .zip-close.is-armed .zip-close-points li,
            .zip-close.is-armed .zip-close-cta{opacity:1;transform:none}
            .zip-close.is-armed .zip-close-cta{pointer-events:auto}
            .zip-close-cta:hover{transform:none}
          }
        `}</style>
      </RotatingHero>
    </>
  );
};

export default ZipPage;
