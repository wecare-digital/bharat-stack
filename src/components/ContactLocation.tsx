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
 * THE API KEY IS NOT IN THIS FILE OR THIS REPO. The supplied HTML hard-coded the same
 * Google key four times, for Maps, Weather, Air Quality and Solar. It is read from
 * NEXT_PUBLIC_GOOGLE_MAPS_KEY instead.
 *
 * Note what NEXT_PUBLIC_ honestly means here: with output:'export' the value is inlined
 * into the built HTML at build time, so it IS publicly visible in the page source. That
 * is unavoidable and normal - any browser that renders a Google map can read the key
 * used to render it. The protection is therefore NOT secrecy, it is a restriction: set
 * an HTTP-referrer allowlist on the key in Google Cloud Console (wecare.digital/*,
 * stack.wecare.digital/*) and enable only the Maps Embed API on it. An unrestricted key
 * in a public page is billable by anyone who copies it.
 *
 * USE A SEPARATE, EMBED-ONLY KEY. Do not reuse the key that also carries Weather, Air
 * Quality and Solar: those are server-side APIs that cannot be referrer-restricted, so
 * publishing that key would expose three paid APIs rather than one.
 *
 * IT DEGRADES INSTEAD OF BREAKING. With no key configured the iframe is not rendered at
 * all - an Embed API iframe without a key paints a Google error page inside our frame,
 * which looks worse than not having a map. The address, plus code, phone, email and a
 * keyless Google Maps link all still work, so the page keeps doing its actual job.
 */

// The verified Google Place for WECARE.DIGITAL. Taken from the owner's own map config,
// and the same id the sitemap-adjacent structured data uses.
const PLACE_ID = 'ChIJQTvOovt3AjoRitCdl0-xHJk';

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

/** Keyless. Any Google Maps client resolves a place_id query without credentials. */
const DIRECTIONS_URL = `https://www.google.com/maps/dir/?api=1&destination=WECARE.DIGITAL&destination_place_id=${PLACE_ID}`;
const PLACE_URL = `https://www.google.com/maps/search/?api=1&query=WECARE.DIGITAL&query_place_id=${PLACE_ID}`;

const ContactLocation: React.FC = () => {
  const mapsKey = ( process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY || '' ).trim();
  const embedUrl = mapsKey
    ? `https://www.google.com/maps/embed/v1/place?key=${encodeURIComponent( mapsKey )}&q=place_id:${PLACE_ID}&zoom=17`
    : '';

  return (
    <section className="cl" aria-labelledby="cl-title">
      <h2 className="cl-h2" id="cl-title">Where to find us</h2>

      <div className="cl-grid">
        <div className="cl-map">
          { embedUrl ? (
            <iframe
              className="cl-frame"
              src={ embedUrl }
              title="Map showing the WECARE.DIGITAL office in Kolkata"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
              allowFullScreen
            />
          ) : (
            /* No key configured. A deliberate, styled panel rather than a broken frame. */
            <a className="cl-fallback" href={ PLACE_URL } target="_blank" rel="noopener noreferrer">
              <span className="cl-fallback-pin" aria-hidden="true" />
              <strong className="cl-fallback-title">Open the map</strong>
              <span className="cl-fallback-sub">Phears Lane, Kolkata — opens in Google Maps</span>
            </a>
          ) }
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

        .cl-fallback{
          position:absolute;inset:0;
          display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;
          padding:24px;text-align:center;text-decoration:none;
          background:rgba(209,244,112,.22);
          transition:background-color .2s;
        }
        .cl-fallback:hover{background:rgba(209,244,112,.34)}
        .cl-fallback:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:-4px}
        /* A pin drawn in CSS rather than shipped as an asset: one div, no request, and it
           cannot 404. The rotated square with one sharp corner is the standard map-pin
           silhouette. */
        .cl-fallback-pin{
          width:22px;height:22px;margin-bottom:6px;
          background:#1a3a2a;border-radius:50% 50% 50% 0;transform:rotate(-45deg);
        }
        .cl-fallback-title{font-size:20px;font-weight:700;letter-spacing:-.25px;color:#1a3a2a}
        .cl-fallback-sub{font-size:15px;line-height:1.45;color:rgba(0,0,0,.54)}

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
          .cl-cta,.cl-fallback{transition:none}
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
