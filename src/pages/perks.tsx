import React from 'react';
import PageMeta from '../components/PageMeta';
import PageTopBand from '../components/PageTopBand';

/**
 * /perks — gift cards, rewards and offers in one place.
 *
 * SECTION 4 of the customer-experience brief, and the repaired destination for the several
 * systems that link customers to a gift-card URL. The owner's headline is "A little extra, made
 * for you." The page carries three sections with the owner's copy: Gift Cards, Offers and Rewards.
 *
 * THE GIFT-CARD AUDIT. There was no page at /gift-card (it 404'd), yet active CTAs pointed at
 * https://wecare.digital/gift-card from the WhatsApp inbound handler, the AI response handler and
 * the SEO-tools route table. Rather than add a second thin route, the real destination is the Gift
 * Cards section of THIS page, reached at /perks/#gift-cards; those active CTAs are repointed to
 * https://wecare.digital/perks/ and the SEO entry is moved to /perks. No distinct /gift-card route
 * is created, so nothing new has to be registered beyond /perks.
 *
 * NO THIRD-PARTY PROVIDER NAME. "Gift Up", "GiftUp" and any vendor name are absent from this page
 * on purpose — the brief forbids surfacing one in customer-facing UI.
 *
 * NON-TRANSACTING BY DESIGN. There is no gift-card, rewards or offers backend in this repository
 * (verified: no handler under amplify/functions exposes one, and cart_v2 currently rejects
 * gift-card payment entirely). So "Buy a gift card", "Redeem a gift card", "Check balance" and the
 * Rewards section are rendered as clearly non-transacting "coming soon" affordances — inert
 * elements with aria-disabled, no href and no action. No points, balances, reward history,
 * redemption eligibility or invented offers appear anywhere. Offers honestly states that there are
 * no live offers to show yet rather than inventing any.
 *
 * SHARED SHELL. Header, Footer and the support widget come from _app.tsx and are not imported
 * here; the top band is components/PageTopBand, the same fixed-statement band /cart/ and /zip/ use.
 *
 * ROUTING: '/perks' is registered in PUBLIC_PAGE_META (_app.tsx), PUBLIC_EXACT
 * (scripts/generate-sitemap.js) and config/public-pages.json (generated, group 'perks').
 * trailingSlash means the URL is /perks/.
 */

// Gift-card actions — all non-transacting until a provider seam is bound server-side.
const GIFT_CARD_ACTIONS = [ 'Buy a gift card', 'Redeem a gift card', 'Check balance' ];

const PerksPage: React.FC = () => (
  <>
    <PageMeta
      title="Perks — WECARE.DIGITAL"
      description="Gifts, rewards and offers in one place. Choose a WECARE.DIGITAL gift card, explore offers to apply at checkout, and more reasons to come back."
      path="/perks/"
    />
    <PageTopBand
      heading="A little extra, made for you."
      sub="Gifts, rewards and offers in one place."
      ariaLabel="Perks"
    >
      <section className="pk-in" aria-label="Perks">
        {/* GIFT CARDS. The repaired /gift-card destination lives here; the anchor id matches the
            header link /perks/#gift-cards and the CTAs repointed in the backend handlers. */}
        <section className="pk-sec" id="gift-cards" aria-labelledby="pk-gift-h">
          <h2 className="pk-h2" id="pk-gift-h">Give them something they&rsquo;ll actually use.</h2>
          <p className="pk-p">
            Choose a WECARE.DIGITAL gift card and let them decide what comes next.
          </p>
          {/* The buy / redeem / check-balance controls are non-transacting: no gift-card provider
              is wired up, so showing a working-looking button would be a false promise. Each is an
              inert chip, not a link or a button. */}
          <ul className="pk-chips" aria-label="Gift card options (not available yet)">
            { GIFT_CARD_ACTIONS.map( label => (
              <li className="pk-chip-item" key={ label }>
                <span className="pk-chip" aria-disabled="true">
                  <span className="pk-chip-label">{ label }</span>
                  <span className="pk-chip-tag">Coming soon</span>
                </span>
              </li>
            ) ) }
          </ul>
          <p className="pk-note">
            Gift cards are not on sale online yet. When they are, this is where you will buy,
            redeem and check the balance on one.
          </p>
          {/* TODO: once gift cards go live, link the published gift-card terms here. Legal copy
              lives in src/content/legal and is out of scope for this change — do not inline
              clauses on this page. */}
        </section>

        {/* OFFERS. Only real/current offers may be shown; none are wired, so the page says so
            plainly rather than inventing any. */}
        <section className="pk-sec" id="offers" aria-labelledby="pk-offers-h">
          <h2 className="pk-h2" id="pk-offers-h">Something extra</h2>
          <p className="pk-p">
            Explore available offers and apply eligible coupons during checkout.
          </p>
          <p className="pk-note">
            There are no live offers to show right now. Current offers will appear here, and any
            eligible coupon is applied at checkout — we will not list an offer we cannot honour.
          </p>
        </section>

        {/* REWARDS. No rewards backend exists, so there are no points, balances, history or
            eligibility — just an honest, non-transacting placeholder. */}
        <section className="pk-sec" id="rewards" aria-labelledby="pk-rewards-h">
          <h2 className="pk-h2" id="pk-rewards-h">More reasons to come back</h2>
          <p className="pk-p">
            A rewards programme is on the way. We would rather build it properly than show you a
            points balance that is not real.
          </p>
          <p className="pk-note" aria-disabled="true">
            <span className="pk-chip-tag pk-chip-tag-inline">Coming soon</span>
            Rewards are not available yet — there are no points, balances or history to show.
          </p>
        </section>

        <style jsx>{`
          /* pk- prefixed to stay clear of the globally imported unscoped CSS. */
          .pk-in{max-width:900px}
          .pk-sec{margin:0 0 56px}
          .pk-sec:last-of-type{margin-bottom:0}
          /* Section h2 is the 700 rung, heavier than the band's 600 h1 — the site's inversion. */
          .pk-h2{
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);margin:0 0 14px;
          }
          /* The single body rung. */
          .pk-p{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0 0 18px;max-width:640px;
          }
          /* The dim aside rung used for honesty notes — the catalogue's 1px #e5e7eb hairline,
             12px radius, rgba(0,0,0,.54) type, so it reads as a "read this before you trust what
             is above" aside. */
          .pk-note{
            margin:0;padding:16px 18px;border:1px solid #e5e7eb;border-radius:12px;
            font-size:16px;line-height:1.55;color:rgba(0,0,0,.54);max-width:640px;
          }
          .pk-chips{list-style:none;margin:0 0 18px;padding:0;display:flex;flex-wrap:wrap;gap:12px}
          .pk-chip-item{margin:0}
          /* Non-transacting chip: dashed edge, default cursor, no hover — never looks clickable. */
          .pk-chip{
            display:inline-flex;align-items:center;gap:10px;cursor:default;
            padding:12px 16px;border:1px dashed #e5e7eb;border-radius:999px;
            background:rgba(0,0,0,.015);
          }
          .pk-chip-label{font-size:16px;font-weight:700;color:#1a3a2a}
          .pk-chip-tag{
            font-size:12px;font-weight:700;letter-spacing:.3px;text-transform:uppercase;
            color:#1a3a2a;background:rgba(209,244,112,.35);padding:2px 8px;border-radius:999px;
          }
          .pk-chip-tag-inline{margin-right:10px}
          @media(max-width:767px){
            .pk-p{font-size:18px}
            .pk-sec{margin-bottom:44px}
          }
        `}</style>
      </section>
    </PageTopBand>
  </>
);

export default PerksPage;
