import React from 'react';

/**
 * The capability strip on the home page.
 *
 * MOVED OFF /contact/ at the owner's request, and renamed with it - this was
 * ContactCapabilities.tsx with a cc- prefix, which would have been a lie in its new home.
 * The class prefix is pcap- rather than cap-, because grahak-os/index.tsx still discusses
 * a .cap-icon in a comment and a prefix that reads as "already taken" invites collisions.
 *
 * SELF-STYLING, like the other composite components here: styled-jsx cannot scope a
 * composite component from its parent.
 *
 * NO margin-top. It is a direct child of .home-layout, which is a flex column with
 * gap:96px, so the section rhythm is already owned by the parent. The version of
 * .home-close that carried its own margin-top:96px on top of that gap measured 192px
 * between sections instead of 96px - the two are additive, and only one of them should
 * exist.
 *
 * THE HEADLINE HAD TO CHANGE, and this is the one edit to the owner's supplied copy.
 * On the contact page it read "The map that gets you here does rather more than that",
 * which worked because a map was directly above it. There is no map on the home page, so
 * that sentence pointed at nothing. The lead's own closing line was the strongest thing
 * in the block, so it was promoted to the heading, and the lead now says where the
 * capabilities can actually be seen running. Every one of the seven items below is
 * verbatim as supplied.
 *
 * WHY NAME THEM RATHER THAN EMBED THEM. The owner's arrival map carries air quality,
 * weather, solar, currency, world time, translation with spoken audio, Street View and a
 * West Bengal discovery rail. Embedding all of it would import a second design system.
 * Naming it presents the stack as a capability rather than a widget, which is the point.
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

const PlatformCapabilities: React.FC = () => (
  <section className="pcap" aria-labelledby="pcap-title">
    <p className="pcap-eyebrow">Built and run by us</p>
    <h2 className="pcap-h2" id="pcap-title">The shortest honest answer to what we do</h2>
    <p className="pcap-lead">
      Everything below is ours — the same platform we build for customers, pointed at our
      own front door. You can watch all of it running on{ ' ' }
      <a className="pcap-link" href="/contact/">our contact page</a>.
    </p>

    <ul className="pcap-grid">
      { CAPABILITIES.map( item => (
        <li className="pcap-item" key={ item.name }>
          <span className="pcap-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">{ item.icon }</svg>
          </span>
          <div className="pcap-copy">
            <strong className="pcap-name">{ item.name }</strong>
            <span className="pcap-detail">{ item.detail }</span>
          </div>
        </li>
      ) ) }
    </ul>

    <style jsx>{`
      /* pcap- prefixed. The globally imported src/styles/*.css declares unscoped rules for
         generic names and styled-jsx does not shield a page from them. */
      /* max-width:1000px, not the layout's full 1300px: seven two-line details set at the
         full measure would run past a comfortable reading length. */
      .pcap{max-width:1000px}

      .pcap-eyebrow{
        margin:0 0 12px;font-size:12px;font-weight:700;
        letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a;
      }
      /* Section h2 on the contract's 700 rung, heavier than the hero h1's 600 - the
         inversion this site uses everywhere. Same clamp as the other section headings so
         this reads as their sibling rather than a new level. */
      .pcap-h2{
        max-width:760px;margin:0 0 16px;
        font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
        letter-spacing:-1.2px;color:rgba(0,0,0,.95);
      }
      /* The single body level the contract allows: 20px/400/1.4/-.125px. */
      .pcap-lead{
        max-width:640px;margin:0 0 36px;
        font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:rgba(0,0,0,.898);
      }
      /* A plain <a>, like every other link on the public pages: next/link would not receive
         styled-jsx's scoping class, so this rule would silently stop matching. */
      .pcap-link{color:#1a3a2a;font-weight:600;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px}
      .pcap-link:hover{background:rgba(209,244,112,.22)}
      .pcap-link:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:2px}

      /* auto-fit with a 300px floor rather than a fixed column count. To be accurate about
         what this does and does not buy: seven is prime, so a trailing short row is
         unavoidable at any column count (3+3+1 here at full width, 2+2+2+1 at mid). What
         auto-fit avoids is a fixed count that becomes wrong at some viewport - the columns
         follow the available width instead of being asserted. align-items:start so a short
         item does not stretch to match a tall neighbour. */
      .pcap-grid{
        margin:0;padding:0;list-style:none;
        display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
        gap:18px 28px;align-items:start;
      }
      /* Hairline separator above each item instead of a card border. Seven bordered boxes
         would read as seven buttons; a rule reads as a list, which is what this is.
         1px because it is static - 2px on this site means you can interact with it. */
      .pcap-item{
        display:flex;gap:14px;align-items:flex-start;
        padding-top:18px;border-top:1px solid #e5e7eb;
      }

      /* The .22 lime tint: the contract's quiet treatment, correct for a label rather
         than an action. Full-strength lime stays on the page's one call to action. */
      .pcap-icon{
        flex:0 0 auto;width:40px;height:40px;border-radius:12px;
        display:grid;place-items:center;
        background:rgba(209,244,112,.22);color:#1a3a2a;
      }
      /* fill:none + stroke on currentColor is what lets one icon set inherit the colour
         of whatever it sits in, with no per-icon overrides. */
      .pcap-icon svg{
        width:22px;height:22px;fill:none;stroke:currentColor;
        stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;
      }

      .pcap-copy{min-width:0;display:flex;flex-direction:column;gap:5px}
      /* Card-heading rung: 22px/700/-.25px, same as the product page points. */
      .pcap-name{font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#000}
      /* Detail drops to the 17px reading size used for long prose elsewhere - at 20px
         seven paragraphs of it would outweigh the lead that introduces them. */
      .pcap-detail{font-size:17px;font-weight:400;line-height:1.55;letter-spacing:-.05px;color:rgba(0,0,0,.54)}

      @media(max-width:899px){
        .pcap-lead{font-size:18px;margin-bottom:28px}
        .pcap-grid{grid-template-columns:1fr;gap:0}
        .pcap-name{font-size:20px}
        .pcap-detail{font-size:16.5px}
        /* Slightly tighter rhythm once they are a single stacked column. */
        .pcap-item{padding-top:16px;margin-bottom:16px}
      }
    `}</style>
  </section>
);

export default PlatformCapabilities;
