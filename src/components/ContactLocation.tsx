import React from 'react';

/**
 * The map and address block on /contact/.
 *
 * SELF-STYLING, like BrandBadge, RotatingHero, WorkflowTerminal, LegalDocument and
 * ProductPage: styled-jsx cannot scope a composite component from its parent.
 *
 * WHAT THIS IS NOT. The owner supplied a complete standalone map application - roughly
 * 6,000 lines carrying weather, air quality, solar, currency conversion, world time,
 * translation with Cloud TTS, Street View, a nearby-places rail and a West Bengal
 * carousel. None of that is here, for two reasons. It is a different product, not a
 * contact panel; and it ships its own design system - Material tokens
 * (--md-sys-color-*), Wix Madefor type, a 13px radius scale, #111 ink - which directly
 * contradicts this site's contract. Porting it would have imported a second visual
 * language onto a marketing page. What the owner asked for was the map in OUR design,
 * followed by the address, and that is what this is.
 *
 * NO API KEY, AND THEREFORE NO KEY IN THE PAGE SOURCE. This used to build a Maps Embed
 * API url (maps/embed/v1/place) from NEXT_PUBLIC_GOOGLE_MAPS_KEY, which had two problems.
 * The owner asked for the map to render INLINE with no redirection out to Google, and the
 * keyed version could not: with no key configured it rendered a panel that linked to
 * Google instead of a map, because an Embed API iframe without a key paints a Google
 * error page inside our frame. And NEXT_PUBLIC_ with output:'export' inlines the value
 * into the built HTML, so the key was going to be publicly readable in the page source
 * and would have needed referrer-locking and its own embed-only key to stay un-abusable.
 *
 * It now uses the legacy keyless endpoint - maps?q=...&output=embed - which needs no
 * credential, no billing account and no rotation. The map always renders. Nobody is sent
 * to Google to see where we are.
 *
 * THE TRADE-OFF, STATED: that endpoint is long-lived and very widely used but it is NOT
 * formally documented by Google, so it carries no compatibility promise the way the Embed
 * API does. If it is ever withdrawn the frame goes blank and the address block below it
 * keeps working. /projects/pwtest/mapprobe.js is the canary - it asserts the frame paints
 * street-level tiles AND names Kolkata, so a silent regression is caught rather than
 * discovered by a visitor.
 *
 * THE QUERY FORM IS MEASURED, NOT GUESSED. Four forms were tested in a real framed
 * browser. place_id: syntax LOOKS right and returns HTTP 200 with a full set of map
 * tiles, but this endpoint does not parse it and silently renders the entire planet. The
 * plain-text business query below is the only one that resolves our actual Google
 * Business listing, so the pin is labelled WECARE.DIGITAL and carries the verified
 * address. Do not "tidy" this into a place_id.
 */

// The verified Google Place for WECARE.DIGITAL. Still used for the keyless deep links
// below, where place_id IS honoured - it is only the embed endpoint that ignores it.
const PLACE_ID = 'ChIJQTvOovt3AjoRitCdl0-xHJk';

/**
 * The exact query string measured to resolve our business listing on the keyless embed.
 * Mirrored in /projects/pwtest/mapprobe.js as SHIPPED_QUERY.
 */
const MAP_QUERY = 'WECARE.DIGITAL, Phears Lane, Kolkata 700012';

/** z=17 is building level: the lane is named and the block is legible without panning. */
const EMBED_URL = `https://maps.google.com/maps?q=${encodeURIComponent( MAP_QUERY )}&z=17&output=embed`;

const ADDRESS_LINES = [
  'The W.B.S.I.D.C. Building',
  'Unit 1/20, 81/2/7 Phears Lane',
  'Kolkata, West Bengal 700012',
  'India',
];

/** Google's short code for the entrance. Works on its own in Google Maps search. */
const PLUS_CODE = 'H9C4+MMP';
const PHONE_DISPLAY = '+91 93309 94400';
const PHONE_HREF = '+919330994400';
const EMAIL = 'one@wecare.digital';

/**
 * Keyless deep link for turn-by-turn directions. The /maps/dir/ endpoint DOES honour
 * place_id (unlike the embed endpoint above), so this pins the exact verified premises
 * rather than a geocoded guess at the street.
 *
 * This is the one link in the section that leaves the site, and it is deliberate: it is an
 * explicit "Get directions" button a visitor chooses to press, not the map being replaced
 * by a redirect. Seeing where we are costs no navigation; routing to us needs a maps app.
 */
const DIRECTIONS_URL = `https://www.google.com/maps/dir/?api=1&destination=WECARE.DIGITAL&destination_place_id=${PLACE_ID}`;

const ContactLocation: React.FC = () => {
  return (
    <section className="cl" aria-labelledby="cl-title">
      <h2 className="cl-h2" id="cl-title">Where to find us</h2>

      <div className="cl-grid">
        {/* UNCONDITIONAL. There is no key branch and no link-out placeholder any more:
            the map itself is the thing the owner asked to see on the page, so it renders
            for every visitor on every load. */}
        <div className="cl-map">
          <iframe
            className="cl-frame"
            src={ EMBED_URL }
            title="Map showing the WECARE.DIGITAL office on Phears Lane, Kolkata"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            allowFullScreen
          />
        </div>

        <div className="cl-copy">
          <p className="cl-label">Address</p>
          {/* itemProp-free, but marked up as a real address element so assistive tech
              and crawlers read it as one. */}
          <address className="cl-address">
            { ADDRESS_LINES.map( line => <span key={ line }>{ line }</span> ) }
          </address>

          <p className="cl-label">Plus code</p>
          <p className="cl-value"><code className="cl-code">{ PLUS_CODE }</code></p>

          <p className="cl-label">Phone</p>
          <p className="cl-value"><a className="cl-link" href={ `tel:${PHONE_HREF}` }>{ PHONE_DISPLAY }</a></p>

          <p className="cl-label">Email</p>
          <p className="cl-value"><a className="cl-link" href={ `mailto:${EMAIL}` }>{ EMAIL }</a></p>

          <a className="cl-cta" href={ DIRECTIONS_URL } target="_blank" rel="noopener noreferrer">
            Get directions
          </a>
        </div>
      </div>

      <style jsx>{`
        /* cl- prefixed. The globally imported src/styles/*.css declares unscoped rules
           for generic names and styled-jsx does not shield a page from them. */
        .cl{max-width:1000px;margin-top:64px}
        /* Section h2 on the contract's 700 rung - heavier than the hero h1's 600, which
           is the inversion this whole site uses. Same clamp as the other section
           headings so they read as siblings. */
        .cl-h2{
          font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
          letter-spacing:-1.2px;color:rgba(0,0,0,.95);margin:0 0 24px;
        }

        /* Map left, details right. The map is 1fr and the copy column a fixed 300px for
           the same reason the Home terminal band is built that way: an address block
           reflows cleanly at any width, a map just gets less useful. */
        .cl-grid{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:28px;align-items:start}

        /* THE LIME EDGE IS THE WHOLE POINT of the treatment the owner asked for. The
           supplied app framed its map in #111 ink on a 13px radius; this uses our own
           14px radius and puts a 2px lime border on it - 2px because the hairline rule
           on this site is 1px static, 2px interactive, and a map you can pan is
           interactive. The tinted backdrop shows through while the iframe loads, so the
           frame never flashes white. */
        .cl-map{
          position:relative;overflow:hidden;
          border:2px solid #d1f470;border-radius:14px;
          background:rgba(209,244,112,.22);
          aspect-ratio:4/3;
        }
        /* display:block kills the inline-element baseline gap under the iframe, which
           otherwise shows as a few pixels of tint along the bottom edge. */
        .cl-frame{display:block;width:100%;height:100%;border:0}

        .cl-copy{min-width:0}
        .cl-label{
          margin:0 0 6px;font-size:12px;font-weight:700;
          letter-spacing:.08em;text-transform:uppercase;color:rgba(0,0,0,.54);
        }
        .cl-label:not(:first-child){margin-top:20px}

        /* font-style:normal because browsers italicise <address> by default, and an
           italic postal address reads as a quotation. */
        .cl-address{margin:0;font-style:normal;display:flex;flex-direction:column;gap:2px}
        .cl-address span{font-size:17px;font-weight:400;line-height:1.5;letter-spacing:-.05px;color:rgba(0,0,0,.898)}
        .cl-value{margin:0;font-size:17px;line-height:1.5;color:rgba(0,0,0,.898)}

        /* The plus code is a code, so it is set as one - tabular mono keeps the glyphs
           from shifting and signals that it is meant to be copied verbatim. */
        .cl-code{
          font-family:'SF Mono',Monaco,Consolas,monospace;font-size:16px;
          padding:3px 8px;border-radius:6px;
          background:rgba(209,244,112,.22);color:#1a3a2a;
        }

        .cl-link{color:#1a3a2a;font-weight:600;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px}
        .cl-link:hover{background:rgba(209,244,112,.22)}

        /* Full-strength lime with #1a3a2a type: the contract's own-surface pairing, and
           the single actionable surface in this section. */
        .cl-cta{
          display:inline-flex;align-items:center;min-height:52px;margin-top:28px;
          padding:0 26px;border:2px solid #d1f470;border-radius:50px;
          background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
          transition:background-color .2s,transform .2s,box-shadow .2s;
        }
        .cl-cta:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
        .cl-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}

        @media(prefers-reduced-motion:reduce){
          .cl-cta{transition:none}
          .cl-cta:hover{transform:none}
        }

        @media(max-width:899px){
          /* One column, and the map goes shorter and wider - 16/9 rather than 4/3 - so it
             does not eat the whole screen above the address on a phone. */
          .cl-grid{grid-template-columns:1fr;gap:24px}
          .cl-map{aspect-ratio:16/9}
          .cl{margin-top:48px}
        }
      `}</style>
    </section>
  );
};

export default ContactLocation;
