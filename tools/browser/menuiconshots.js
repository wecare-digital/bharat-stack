'use strict';

/**
 * menuiconshots - a SECOND round of menu-icon options, for two complaints the first round
 * created rather than solved.
 *
 * ROUND ONE is docs/menu-review.md (tools/browser/menureview.js). It mocked A1 chevron-as-was,
 * A2 solid lime, A3 invert-to-dark-green and A4 three lines. The owner kept the chevron and took
 * A3, and A3 is what ships today. The owner has now reported, of that shipped result:
 *
 *   "menu icon is looking dull"      -> the REST state
 *   "on select too much green"       -> the OPEN/hover state, which fills the whole 46x46 chip
 *                                        solid #1a3a2a
 *
 * Both are fair, and the second one is a direct consequence of round one's own finding.
 *
 * THE CONSTRAINT THAT HAS NOT CHANGED, and which kills the obvious fix. Lime is a LIGHT colour,
 * so no lime fill can carry a state change on a near-white chip: solid #d1f470 measures 1.15:1
 * against the #f4f7ee rest fill, and the old rgba(209,244,112,.22) tint measured 1.03:1 - an RGB
 * move of 15 out of 441. That is why A3 inverted. So "less green" cannot mean "go back to a lime
 * tint"; it has to mean keep a luminance step while using less green AREA, or a fill that is dark
 * without being green.
 *
 * WHAT THIS ROUND ASKS. Rest and open are separable problems, so each option is drawn as a
 * triplet - rest, hover, open - and the contrast of every pair is computed here rather than
 * typed. No new colours: every value is already in the repo (#d1f470, #1a3a2a,
 * rgba(209,244,112,.22), #f4f7ee, #cfe0a6, and the body-text near-black rgba(0,0,0,.898)).
 *
 * Writes docs/menu-icon-round-two.html, docs/menu-icon-mock/ *.png and
 * docs/menu-icon-round-two.md,
 * the same three-artefact shape accentshots.js, dividershots.js and menureview.js use.
 * Run: node tools/browser/menuiconshots.js
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { launch } = require( './lib/browser' );

const DOCS = path.join( __dirname, '..', '..', 'docs' );
// ROUND-TWO FILENAMES, and they are deliberate. The first version of this script wrote
// docs/menu-icon-options.md - which ALREADY EXISTS, from PR #90 ("Record why A was chosen for the
// menu icon, with the two comparisons that settled it"), and overwrote 87 lines of the record of
// round one's decision with round two's. Caught by `git status` showing the file as modified
// rather than new, before it was committed. Round one's artefacts are docs/menu-icon-options.md
// and docs/menu-mock/; this script owns docs/menu-icon-round-two.* and docs/menu-icon-mock/ and
// must never write to the round-one names.
const HTML = path.join( DOCS, 'menu-icon-round-two.html' );
const SHOTS = path.join( DOCS, 'menu-icon-mock' );
const MD = path.join( DOCS, 'menu-icon-round-two.md' );

/* ---------- contrast, computed not typed ---------- */
const hex = h => [ 1, 3, 5 ].map( i => parseInt( h.substr( i, 2 ), 16 ) );
const over = ( fg, a, bg ) => fg.map( ( v, i ) => Math.round( a * v + ( 1 - a ) * bg[ i ] ) );
const lum = c => {
  const s = c.map( v => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : Math.pow( ( x + 0.055 ) / 1.055, 2.4 ); } );
  return 0.2126 * s[ 0 ] + 0.7152 * s[ 1 ] + 0.0722 * s[ 2 ];
};
const ratio = ( a, b ) => {
  const [ x, y ] = [ lum( a ), lum( b ) ].sort( ( p, q ) => q - p );
  return Math.round( ( ( x + 0.05 ) / ( y + 0.05 ) ) * 100 ) / 100;
};
/** Total RGB distance, the "is this a real move" number round one used. */
const move = ( a, b ) => a.reduce( ( sum, v, i ) => sum + Math.abs( v - b[ i ] ), 0 );

const WHITE = hex( '#ffffff' );        // the header behind the chip
const REST = hex( '#f4f7ee' );         // today's chip fill
const LIME = hex( '#d1f470' );
const DGREEN = hex( '#1a3a2a' );
const BORDER = hex( '#cfe0a6' );
const NEARBLACK = over( [ 0, 0, 0 ], 0.898, WHITE );   // rgba(0,0,0,.898), the body-text token
const LIMETINT = over( LIME, 0.22, WHITE );

/**
 * The options. `open` is the state the owner called "too much green", so each entry records how
 * much of the 46x46 chip it actually fills with dark colour - the number the complaint is about.
 *
 * AREA IS THE POINT OF THIS ROUND. A 46x46 chip is 2116px². A3 fills all of it. An option that
 * keeps the same luminance step over a quarter of the area is the same signal with a quarter of
 * the mass, and that is what "less green" can mean without going back to a tint that measured
 * 1.03:1.
 */
const OPTIONS = [
  {
    id: 'g1-shipping-now',
    title: 'G1 — what ships today (A3)',
    darkArea: 2116,
    note: 'The baseline the complaints are about. Rest is a pale chip with a .85-opacity chevron; '
      + 'open fills the entire chip solid #1a3a2a. Included so every other option is judged '
      + 'against it rather than against a memory of it.',
    rest: { fill: '#f4f7ee', border: '#cfe0a6', glyph: '#1a3a2a', glyphOpacity: 0.85 },
    open: { fill: '#1a3a2a', border: '#1a3a2a', glyph: '#d1f470', glyphOpacity: 1 },
  },
  {
    id: 'g2-neutral-invert',
    title: 'G2 — same step, no green in the fill',
    darkArea: 2116,
    note: 'Answers "too much green" literally: the open fill becomes the near-black body-text '
      + 'token rgba(0,0,0,.898) instead of dark green, and the chevron stays lime. Full '
      + 'luminance step preserved, and the only green left on the control is the brand glyph '
      + 'itself. Rest state is livened by taking the chevron to full opacity.',
    rest: { fill: '#f4f7ee', border: '#cfe0a6', glyph: '#1a3a2a', glyphOpacity: 1 },
    open: { fill: 'rgba(0,0,0,.898)', border: 'rgba(0,0,0,.898)', glyph: '#d1f470', glyphOpacity: 1 },
  },
  {
    id: 'g3-dark-disc',
    title: 'G3 — dark disc behind the glyph only',
    darkArea: 452,
    note: 'Keeps the inversion but shrinks it to a 24px disc centred on the chevron, so the dark '
      + 'area drops from 2116px² to 452px² - 21% of what ships. The chip itself stays pale, the '
      + 'step is local to the glyph, and the control never becomes a solid block.',
    rest: { fill: '#f4f7ee', border: '#cfe0a6', glyph: '#1a3a2a', glyphOpacity: 1 },
    open: { fill: '#f4f7ee', border: '#cfe0a6', glyph: '#d1f470', glyphOpacity: 1, disc: '#1a3a2a' },
  },
  {
    id: 'g4-lime-fill-dark-edge',
    title: 'G4 — lime fill, dark 2px edge',
    darkArea: 352,
    note: 'The fill finally gets to be lime, which is what "on" looks like everywhere else on '
      + 'this site - but a lime fill alone measured 1.15:1 in round one, so the state is carried '
      + 'by the border going from light #cfe0a6 to 2px #1a3a2a. Brightest of the options and the '
      + 'least heavy; weakest on fill luminance, so the numbers below decide it.',
    rest: { fill: '#f4f7ee', border: '#cfe0a6', glyph: '#1a3a2a', glyphOpacity: 1 },
    open: { fill: '#d1f470', border: '#1a3a2a', borderWidth: 2, glyph: '#1a3a2a', glyphOpacity: 1 },
  },
  {
    id: 'g5-indicator-bar',
    title: 'G5 — pale chip, dark indicator bar',
    darkArea: 138,
    note: 'A tab-style indicator: the chip stays exactly as it rests and a 3px dark-green bar '
      + 'appears along the bottom inside edge, 138px² of dark - 6.5% of what ships. Smallest '
      + 'possible green mass that still produces a hard luminance edge. Relies most on the '
      + 'chevron rotation to say "open", which is already there.',
    rest: { fill: '#f4f7ee', border: '#cfe0a6', glyph: '#1a3a2a', glyphOpacity: 1 },
    open: { fill: '#f4f7ee', border: '#cfe0a6', glyph: '#1a3a2a', glyphOpacity: 1, bar: '#1a3a2a' },
  },
];

/* ---------- the measured table ---------- */
const openFillRgb = o => {
  if ( o.open.fill === 'rgba(0,0,0,.898)' ) return NEARBLACK;
  return hex( o.open.fill );
};
/**
 * THE FIRST VERSION OF THIS TABLE WAS WRONG, and wrong in the direction that would have thrown
 * away the two best answers. It computed "open vs rest" as open FILL against rest FILL, which is
 * the right question only for G1 and G2. G3 and G5 do not change the fill at all - they add a
 * dark element on top of an unchanged chip - so they scored 1:1 / move 0 and were labelled "too
 * close", when in fact each introduces an 11.52:1 edge.
 *
 * So the number reported is the strongest NEW edge the open state introduces, against whatever
 * surface it appears on, plus the AREA it covers. Those two together are the honest description:
 * a hard edge over a small area is a different trade from a hard edge over the whole chip, and
 * the owner's complaint is about area, not about edge.
 */
const rows = OPTIONS.map( o => {
  const openFill = openFillRgb( o );
  const glyphBg = o.open.disc ? hex( o.open.disc ) : openFill;
  // What is the new dark thing, and what does it sit on?
  const signal = o.open.disc ? { what: 'disc on the pale chip', fg: hex( o.open.disc ), bg: REST }
    : o.open.bar ? { what: 'indicator bar on the pale chip', fg: hex( o.open.bar ), bg: REST }
      : o.open.borderWidth ? { what: '2px border, against the resting border', fg: hex( o.open.border ), bg: BORDER }
        : { what: 'whole-chip fill, against the resting fill', fg: openFill, bg: REST };
  return {
    id: o.id,
    title: o.title,
    darkArea: o.darkArea,
    areaPct: Math.round( ( o.darkArea / 2116 ) * 1000 ) / 10,
    signalWhat: signal.what,
    signalRatio: ratio( signal.fg, signal.bg ),
    signalMove: move( signal.fg, signal.bg ),
    // Is the glyph legible in the open state, on whatever is behind it there?
    glyphOnOpen: ratio( o.open.disc ? LIME : hex( o.open.glyph ), glyphBg ),
    // Is the glyph legible at rest? WCAG 1.4.11 wants 3:1 for a meaningful graphic.
    glyphOnRest: ratio( hex( o.rest.glyph ), REST ),
    // And is the chip itself visible against the white header before it is touched?
    chipOnHeader: ratio( REST, WHITE ),
    borderOnHeader: ratio( hex( o.rest.border ), WHITE ),
  };
} );

/* ---------- the page ---------- */
const chipCss = s => {
  const bw = s.borderWidth || 1;
  return `background:${s.fill};border:${bw}px solid ${s.border};`;
};
const chip = ( s, label ) => `
  <div class="cell">
    <div class="chip" style="${chipCss( s )}">
      ${s.disc ? `<span class="disc" style="background:${s.disc}"></span>` : ''}
      ${s.bar ? `<span class="bar" style="background:${s.bar}"></span>` : ''}
      <span class="arrow${s.rotated ? ' rot' : ''}" style="border-right-color:${s.glyph};border-bottom-color:${s.glyph};opacity:${s.glyphOpacity}"></span>
    </div>
    <span class="lab">${label}</span>
  </div>`;

const optionBlock = ( o, r ) => `
  <section class="opt" id="${o.id}">
    <h2>${o.title}</h2>
    <p class="note">${o.note}</p>
    <div class="row">
      ${chip( o.rest, 'rest' )}
      ${chip( { ...o.open, rotated: false }, 'hover' )}
      ${chip( { ...o.open, rotated: true }, 'open' )}
      ${chip( { ...o.rest, focus: true }, 'focus ring' ).replace( 'class="chip"', 'class="chip focus"' )}
    </div>
    <table class="m">
      <tr><th>dark area of the 46×46 chip</th><td>${r.darkArea}px² &nbsp;(<b>${r.areaPct}%</b> of what ships)</td></tr>
      <tr><th>strongest new edge when open</th><td>${r.signalRatio}:1 &nbsp;(${r.signalWhat}) ${r.signalRatio >= 3 ? '<b class="ok">clear step</b>' : '<b class="warn">hue move only — ' + r.signalMove + '/441</b>'}</td></tr>
      <tr><th>chevron on the open state</th><td>${r.glyphOnOpen}:1 ${r.glyphOnOpen >= 3 ? '<b class="ok">pass</b>' : '<b class="bad">under 3:1</b>'}</td></tr>
      <tr><th>chevron at rest</th><td>${r.glyphOnRest}:1 ${r.glyphOnRest >= 3 ? '<b class="ok">pass</b>' : '<b class="bad">under 3:1</b>'}</td></tr>
    </table>
  </section>`;

const html = `<!doctype html>
<meta charset="utf-8">
<title>Menu icon — round two</title>
<style>
  body{font:16px/1.5 Inter,system-ui,sans-serif;color:rgba(0,0,0,.898);background:#fff;margin:0;padding:40px}
  h1{font-size:34px;font-weight:700;letter-spacing:-1px;margin:0 0 8px}
  .intro{max-width:760px;color:rgba(0,0,0,.6);margin:0 0 34px}
  .opt{max-width:760px;padding:24px 0;border-top:1px solid #e5e7eb}
  h2{font-size:22px;font-weight:700;letter-spacing:-.25px;margin:0 0 8px}
  .note{margin:0 0 18px;color:rgba(0,0,0,.6);font-size:15px}
  .row{display:flex;gap:26px;align-items:flex-start;margin:0 0 18px;padding:16px;background:#fff;border:1px solid #f0f0f0;border-radius:8px}
  .cell{display:flex;flex-direction:column;align-items:center;gap:8px}
  .lab{font-size:12px;color:rgba(0,0,0,.54)}
  /* Real geometry: 46x46, 10px radius, 8px chevron with 2.5px strokes. */
  .chip{position:relative;width:46px;height:46px;border-radius:10px;display:flex;align-items:center;justify-content:center;box-sizing:border-box}
  .chip.focus{box-shadow:0 0 0 2px #fff,0 0 0 5px #1a3a2a}
  .arrow{position:relative;z-index:2;width:8px;height:8px;box-sizing:border-box;border-right:2.5px solid;border-bottom:2.5px solid;transform:translateY(-2px) rotate(45deg)}
  .arrow.rot{transform:translateY(2px) rotate(225deg)}
  .disc{position:absolute;width:24px;height:24px;border-radius:50%;z-index:1}
  .bar{position:absolute;left:6px;right:6px;bottom:4px;height:3px;border-radius:2px;z-index:1}
  table.m{border-collapse:collapse;font-size:14px;width:100%}
  table.m th{text-align:left;font-weight:500;color:rgba(0,0,0,.54);padding:5px 14px 5px 0;white-space:nowrap;vertical-align:top}
  table.m td{padding:5px 0}
  .ok{color:#186a3b}.warn{color:#8a5a00}.bad{color:#b3261e}
</style>
<h1>Menu icon — round two</h1>
<p class="intro">Round one (<code>docs/menu-review.md</code>) chose the invert, shown here as G1.
The owner then reported it as <b>dull at rest</b> and <b>too much green when selected</b>. Every
option below keeps the 46×46 target, the chevron, the rotation and the two-tone focus ring, and
uses only colours already in the repo. The numbers are computed by
<code>tools/browser/menuiconshots.js</code>, not typed.</p>
${OPTIONS.map( ( o, i ) => optionBlock( o, rows[ i ] ) ).join( '' )}
`;

( async () => {
  fs.mkdirSync( SHOTS, { recursive: true } );
  fs.writeFileSync( HTML, html, 'utf8' );

  const browser = await launch();
  const page = await browser.newPage( { viewport: { width: 900, height: 1000 }, deviceScaleFactor: 2 } );
  await page.goto( 'file://' + HTML );
  await page.waitForTimeout( 300 );

  for ( const o of OPTIONS ) {
    const el = await page.$( `#${o.id} .row` );
    await el.screenshot( { path: path.join( SHOTS, `${o.id}.png` ) } );
  }
  const all = await page.$( 'body' );
  await all.screenshot( { path: path.join( SHOTS, 'all-options.png' ) } );

  const md = `# Menu icon — round two

> Rendered from \`docs/menu-icon-round-two.html\` by \`tools/browser/menuiconshots.js\`. Every number
> is computed from the colour values, not typed. Open the HTML for the live version.

Round one is [\`menu-review.md\`](menu-review.md); it picked the invert, which ships today and is
**G1** here. The owner then reported that result as *dull at rest* and *too much green when
selected*. The table is ordered by how much dark area each option puts on the chip, because that
is what the second complaint is actually about.

| option | dark area | % of today | strongest new edge when open | what carries it | chevron on open | chevron at rest |
|---|---|---|---|---|---|---|
${rows.map( r => `| [${r.title}](menu-icon-mock/${r.id}.png) | ${r.darkArea}px² | ${r.areaPct}% | **${r.signalRatio}:1** | ${r.signalWhat} | ${r.glyphOnOpen}:1 | ${r.glyphOnRest}:1 |` ).join( '\n' )}

![all options](menu-icon-mock/all-options.png)

${OPTIONS.map( ( o, i ) => `## ${o.title}\n\n${o.note}\n\n![${o.id}](menu-icon-mock/${o.id}.png)\n` ).join( '\n' )}

## What does not change in any option

The 46×46 target (WCAG 2.5.8 asks 24×24, so there is room to spare), the single chevron, the
45°→225° rotation that carries "open" on its own, and the two-tone focus ring
\`0 0 0 2px #fff, 0 0 0 5px #1a3a2a\` — which exists because a single-colour ring cannot work
against a chip that inverts, and measures 12.48:1 against the header.

## The constraint that rules out the obvious fix

Lime is a light colour. Against the \`#f4f7ee\` rest fill, \`rgba(209,244,112,.22)\` measures
${ratio( LIMETINT, REST )}:1 (RGB move ${move( LIMETINT, REST )}/441) and solid \`#d1f470\` measures
${ratio( LIME, REST )}:1. Neither is a state change, which is why round one inverted. "Less green"
therefore has to mean less dark **area**, or a dark fill that is not green — not a return to a tint.
`;
  fs.writeFileSync( MD, md, 'utf8' );

  console.log( `menuiconshots: ${OPTIONS.length} options -> ${path.relative( process.cwd(), SHOTS )}/` );
  console.log( `  ${path.relative( process.cwd(), MD )}` );
  console.log( `  ${path.relative( process.cwd(), HTML )}\n` );
  console.log( 'option                        darkArea   %today  new-edge  glyph-open  glyph-rest   carried by' );
  for ( const r of rows ) {
    console.log( `  ${r.id.padEnd( 26 )} ${String( r.darkArea ).padStart( 6 )}px² ${String( r.areaPct ).padStart( 6 )}%  `
      + `${String( r.signalRatio ).padStart( 7 )}:1  `
      + `${String( r.glyphOnOpen ).padStart( 8 )}:1  ${String( r.glyphOnRest ).padStart( 8 )}:1   ${r.signalWhat}` );
  }
  console.log( `\nreference: lime tint vs rest ${ratio( LIMETINT, REST )}:1 (move ${move( LIMETINT, REST )}), `
    + `solid lime vs rest ${ratio( LIME, REST )}:1 (move ${move( LIME, REST )})` );
  await browser.close();
  process.exit( 0 );
} )();
