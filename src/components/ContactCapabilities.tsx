import React from 'react';

/**
 * The capability strip under the map on /contact/.
 *
 * SELF-STYLING, like the other composite components here: styled-jsx cannot scope a
 * composite component from its parent.
 *
 * WHY THIS EXISTS RATHER THAN THE WHOLE APP. The owner's arrival map carries air
 * quality, weather, solar, currency, world time, translation with spoken audio, Street
 * View and a West Bengal discovery rail. Embedding all of it on a contact page would
 * import a second design system and bury the address. Naming it instead does the more
 * useful job: a visitor working out how to reach an office learns, at the moment they
 * are already being helped, that the help is something we built. That is the point the
 * owner asked for - present the stack as a feature, not as a widget.
 *
 * EVERY FIGURE HERE IS TAKEN FROM THE RUNNING CODE, not estimated:
 *   - Weather and air quality refresh on a 15-minute interval (15 * 60 * 1000).
 *   - The forecast request asks for 10 days and pages until it has them.
 *   - Solar reports max panel count, best yearly DC output and a carbon-offset factor.
 *   - Currency resolves any listed currency against INR from a live reference provider.
 *   - Time resolves the selected place's own zone and compares it to IST.
 *   - Translation advertises 194 machine-translation languages plus Cloud text-to-speech.
 *   - Street View widens its search to 2,500 m before it gives up (STREET_MAX_RADIUS_METERS).
 * If any of those change in the app, change them here too - a specific number that has
 * quietly gone stale is worse than no number.
 *
 * NO NEW COLOURS AND NO ICON REQUESTS. Each glyph is an inline stroked SVG on
 * currentColor, the same approach the translate icon and the workflow panel use, so
 * there is nothing to 404 and nothing to recolour.
 */

interface Capability {
  name: string;
  detail: string;
  icon: React.ReactNode;
}

// Stroke-only paths on a 24px box, inheriting currentColor. Kept deliberately plain:
// these sit at 22px and detail is lost at that size.
const CAPABILITIES: Capability[] = [
  {
    name: 'Air quality',
    detail: 'Live AQI with the dominant pollutant and health guidance, refreshed every 15 minutes alongside weather and a 10-day forecast.',
    icon: <><path d="M4 9h9a3 3 0 1 0-3-3" /><path d="M4 14h13a3 3 0 1 1-3 3" /><path d="M4 19h6" /></>,
  },
  {
    name: 'Solar potential',
    detail: 'Roof capacity in kW, how many panels fit, best-case yearly output and the carbon that offsets — for any building on the map.',
    icon: <><circle cx="12" cy="12" r="4" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" /></>,
  },
  {
    name: 'Currency',
    detail: 'Any listed currency against the rupee, from a live reference provider rather than a figure typed in once and forgotten.',
    icon: <><path d="M7 5h8M7 10h8M13 5c0 5-6 4-6 4l6 10" /></>,
  },
  {
    name: 'Local time',
    detail: 'The selected place resolves its own time zone and offset, so you see their clock next to ours — and what time you would actually arrive.',
    icon: <><circle cx="12" cy="12" r="8" /><path d="M12 8v4.5l3 1.8" /></>,
  },
  {
    name: 'Translation',
    detail: '194 languages, with the translated line spoken aloud through cloud speech — useful when the last hundred metres need asking about.',
    icon: <><path d="M4 6h9M8.5 6v1c0 3.3-2 6-4.5 7" /><path d="M6 11c1.4 2 3.5 3.3 6 4" /><path d="m12.5 19 3.5-9 3.5 9M14 16.5h4.5" /></>,
  },
  {
    name: 'Street View',
    detail: 'See the entrance before you travel. If there is no panorama at the door it widens the search to 2,500 m and tells you how far off it is.',
    icon: <><path d="M4 18V8.5l5-2 6 2 5-2V16" /><path d="M9 6.5V17M15 8.5V19" /></>,
  },
  {
    name: 'West Bengal discovery',
    detail: 'A curated rail of places across the state — heritage, parks, railways, temples — that keeps loading as you scroll rather than ending at six.',
    icon: <><path d="M12 21s7-5.4 7-11a7 7 0 1 0-14 0c0 5.6 7 11 7 11Z" /><circle cx="12" cy="10" r="2.5" /></>,
  },
];

const ContactCapabilities: React.FC = () => (
  <section className="cc" aria-labelledby="cc-title">
    <p className="cc-eyebrow">Built and run by us</p>
    <h2 className="cc-h2" id="cc-title">The map that gets you here does rather more than that</h2>
    <p className="cc-lead">
      Everything below is ours — the same platform we build for customers, pointed at our
      own front door. It is the shortest honest answer to what we actually do.
    </p>

    <ul className="cc-grid">
      { CAPABILITIES.map( item => (
        <li className="cc-item" key={ item.name }>
          <span className="cc-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">{ item.icon }</svg>
          </span>
          <div className="cc-copy">
            <strong className="cc-name">{ item.name }</strong>
            <span className="cc-detail">{ item.detail }</span>
          </div>
        </li>
      ) ) }
    </ul>

    <style jsx>{`
      /* cc- prefixed. The globally imported src/styles/*.css declares unscoped rules for
         generic names and styled-jsx does not shield a page from them. */
      .cc{max-width:1000px;margin-top:72px}

      .cc-eyebrow{
        margin:0 0 12px;font-size:12px;font-weight:700;
        letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a;
      }
      /* Section h2 on the contract's 700 rung, heavier than the hero h1's 600 - the
         inversion this site uses everywhere. Same clamp as the other section headings so
         this reads as their sibling rather than a new level. */
      .cc-h2{
        max-width:760px;margin:0 0 16px;
        font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
        letter-spacing:-1.2px;color:rgba(0,0,0,.95);
      }
      /* The single body level the contract allows: 20px/400/1.4/-.125px. */
      .cc-lead{
        max-width:640px;margin:0 0 36px;
        font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:rgba(0,0,0,.898);
      }

      /* auto-fit with a 300px floor rather than a fixed count: seven items divide badly
         into two, three or four, and letting them reflow avoids an orphan row of one at
         an awkward width. align-items:start so a short card does not stretch to match a
         tall neighbour. */
      .cc-grid{
        margin:0;padding:0;list-style:none;
        display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
        gap:18px 28px;align-items:start;
      }
      /* Hairline separator above each item instead of a card border. Seven bordered boxes
         would read as seven buttons; a rule reads as a list, which is what this is.
         1px because it is static - 2px on this site means you can interact with it. */
      .cc-item{
        display:flex;gap:14px;align-items:flex-start;
        padding-top:18px;border-top:1px solid #e5e7eb;
      }

      /* The .22 lime tint: the contract's quiet treatment, correct for a label rather
         than an action. Full-strength lime stays on the one call to action above. */
      .cc-icon{
        flex:0 0 auto;width:40px;height:40px;border-radius:12px;
        display:grid;place-items:center;
        background:rgba(209,244,112,.22);color:#1a3a2a;
      }
      /* fill:none + stroke on currentColor is what lets one icon set inherit the colour
         of whatever it sits in, with no per-icon overrides. */
      .cc-icon svg{
        width:22px;height:22px;fill:none;stroke:currentColor;
        stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;
      }

      .cc-copy{min-width:0;display:flex;flex-direction:column;gap:5px}
      /* Card-heading rung: 22px/700/-.25px, same as the product page points. */
      .cc-name{font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#000}
      /* Detail drops to the 17px reading size used for long prose elsewhere - at 20px
         seven paragraphs of it would outweigh the lead that introduces them. */
      .cc-detail{font-size:17px;font-weight:400;line-height:1.55;letter-spacing:-.05px;color:rgba(0,0,0,.54)}

      @media(max-width:899px){
        .cc{margin-top:56px}
        .cc-lead{font-size:18px;margin-bottom:28px}
        .cc-grid{grid-template-columns:1fr;gap:0}
        .cc-name{font-size:20px}
        .cc-detail{font-size:16.5px}
        /* Slightly tighter rhythm once they are a single stacked column. */
        .cc-item{padding-top:16px;margin-bottom:16px}
      }
    `}</style>
  </section>
);

export default ContactCapabilities;
