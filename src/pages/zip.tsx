import React from 'react';
import PageMeta from '../components/PageMeta';
import PageTopBand from '../components/PageTopBand';

/**
 * /zip — one place for everything about a request, delivery or pickup.
 *
 * SECTION 3 of the customer-experience brief. It sits under the "Request" group in the header
 * (Header.tsx COLUMNS), directly after Orders. The owner's heading is "Zip" and the lead is
 * "Track it. Arrange it. Keep it moving."
 *
 * SHARED SHELL, NOT A NEW ONE. The Header, Footer and support widget are mounted once in
 * _app.tsx, so this page must not import them. The top band is components/PageTopBand — the same
 * fixed-statement band /cart/ uses — which owns the one <h1>, the 108px/96px header clearance, the
 * 1300px measure and the entrance animation. PageTopBand is chosen over RotatingHero because the
 * heading is a fixed word ("Zip"), not a rotating phrase: the sibling marketing page /orders/ uses
 * RotatingHero because its headline cycles order/delivery/request/booking, which Zip does not.
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
 * for a later provider without inventing functionality today.
 */

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

const ZipPage: React.FC = () => (
  <>
    <PageMeta
      title="Zip — WECARE.DIGITAL"
      description="Everything about your request, delivery or pickup in one place: track an order, amend a request, send documents, open your vault or leave a review."
      path="/zip/"
    />
    <PageTopBand
      heading="Zip"
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
          @media(max-width:767px){
            .zip-p{font-size:18px}
            .zip-h2-spaced{margin-top:44px}
          }
          @media(prefers-reduced-motion:reduce){
            .zip-card-link{transition:none}
            .zip-card-link:hover{transform:none;box-shadow:none}
          }
        `}</style>
      </section>
    </PageTopBand>
  </>
);

export default ZipPage;
