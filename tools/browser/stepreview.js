'use strict';

/**
 * STEPREVIEW - the workflow terminal's step colours, five ways, at 1:1.
 *
 * WHY THIS EXISTS. The per-service dot hues shipped and the owner reported "the text is
 * still lime green". That report was correct, and the reason was invisible from the diff:
 * `.wt-name.is-complete` is gated on `step.complete`, true for exactly ONE of the eight
 * steps, so the rule recoloured a single line - lime to green, two greens - while all
 * eight `.wt-svc` pills stayed lime. Three rounds of description did not settle it, so
 * this renders the options instead of arguing about them.
 *
 * THE FIVE PANELS:
 *   0 today      pill lime x8, names white x7 + green on step 8   (what ships now)
 *   1 pill only  pill takes its service's hue, names untouched
 *   2 A          pill hued, ALL names white - hue stays decorative, max readability
 *   3 B          pill hued, ALL names take their own hue at >=4.5:1  (AA)
 *   4 C          pill hued, ALL names take their own hue at >=7:1    (AAA, pastel)
 *
 * Panel 1 is in here on purpose. The pill change and the name change are two separate
 * decisions and the owner asked for them in two separate messages; showing the pill
 * isolated is the only way to judge it without the name variant confounding it.
 *
 * RENDERS TO PNG, NOT HTML, and that is not a preference. A committed .html is served by
 * GitHub as text/plain and the owner sees source instead of a picture - it has cost this
 * project three round-trips already. The .md and the PNGs are what get reviewed.
 *
 * THE TICK IS AN INLINE SVG HERE, standing in for the text glyph the component renders.
 * This sandbox has 82 fonts, all Noto Sans, none with symbol coverage, so a literal U+2713
 * renders as a tofu box - which would be a sandbox artefact masquerading as a design
 * defect in a document whose whole job is to show the owner what a reader sees. The shape
 * is the same; only the delivery differs, and option A's case rests on the tick being
 * visible, so it has to actually appear.
 *
 * Run: node tools/browser/stepreview.js
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { launch } = require( './lib/browser' );

const DOCS = path.join( __dirname, '..', '..', 'docs' );
const HTML = path.join( DOCS, 'step-review.html' );
const SHOTS = path.join( DOCS, 'step-mock' );
const MD = path.join( DOCS, 'step-review.md' );

/* ---------- contrast ---------- */
const rgbOf = h => [ 1, 3, 5 ].map( i => parseInt( h.substr( i, 2 ), 16 ) );
const lum = h => {
  const c = rgbOf( h ).map( v => v / 255 )
    .map( v => ( v <= 0.03928 ? v / 12.92 : Math.pow( ( v + 0.055 ) / 1.055, 2.4 ) ) );
  return 0.2126 * c[ 0 ] + 0.7152 * c[ 1 ] + 0.0722 * c[ 2 ];
};
const ratio = ( a, b ) => {
  const [ hi, lo ] = [ lum( a ), lum( b ) ].sort( ( x, y ) => y - x );
  return ( ( hi + 0.05 ) / ( lo + 0.05 ) ).toFixed( 2 );
};
const tint = ( h, a ) => '#' + rgbOf( h ).map( v => Math.round( v * a ).toString( 16 ).padStart( 2, '0' ) ).join( '' );

/* ---------- the real step data, trimmed to what a colour decision needs ---------- */
const STEPS = [
  { svc: 'gateway', name: 'Request accepted', time: '12ms', hue: 'blue' },
  { svc: 'auth', name: 'Account resolved', time: '31ms', hue: 'purple' },
  { svc: 'contacts', name: 'Customer looked up', time: '18ms', hue: 'amber' },
  { svc: 'messaging', name: 'Four services pick it up at once', time: '46ms', hue: 'lime' },
  { svc: 'commerce', name: 'Order and catalog updated', time: '54ms', hue: 'green' },
  { svc: 'billing', name: 'Usage metered', time: '9ms', hue: 'blue' },
  { svc: 'queue', name: 'A provider failed, nobody noticed', time: '1.2s', hue: 'amber' },
  { svc: 'platform', name: 'All services healthy', time: '2.1s', hue: 'green', complete: true },
];

/* dot = the shipped hue. ink = lifted past 4.5:1 on the pill's own tinted ground AND on
 * #000, so ONE value serves both the pill and the name. aaa = lifted past 7:1 on #000. */
const HUES = {
  blue: { dot: '#2563eb', ink: '#3d74ed', aaa: '#6993f1' },
  purple: { dot: '#9849e8', ink: '#9f56ea', aaa: '#b57cee' },
  amber: { dot: '#f0a818', ink: '#f0a818', aaa: '#f0a818' },
  lime: { dot: '#d1f470', ink: '#d1f470', aaa: '#d1f470' },
  green: { dot: '#3da35a', ink: '#3da35a', aaa: '#47a862' },
};

const LIME = '#d1f470';

const VARIANTS = [
  {
    id: 'today', label: 'TODAY — what ships now',
    note: 'Pill lime on all eight. Names white on seven, green on step 8 — the only row whose data says complete. This is the one-line change that was reported as "not showing".',
    pill: () => LIME, pillBg: () => LIME, name: s => ( s.complete ? HUES[ s.hue ].dot : '#ffffff' ),
  },
  {
    id: 'pill-only', label: 'PILL ONLY — pill takes its service hue, names untouched',
    note: 'The change you asked for three times, shown on its own. The pill holds the service name, which is exactly what the dot hue encodes, so lime there had stopped meaning anything.',
    pill: s => HUES[ s.hue ].ink, pillBg: s => HUES[ s.hue ].dot, name: s => ( s.complete ? HUES[ s.hue ].ink : '#ffffff' ),
  },
  {
    id: 'a', label: 'A — pill hued, ALL names white',
    note: 'Hue stays decorative and lives only on the dot and the chip. Every name reads at 21:1, the highest on the panel. The tick alone carries "complete", and step 8 stops being the one dim row.',
    pill: s => HUES[ s.hue ].ink, pillBg: s => HUES[ s.hue ].dot, name: () => '#ffffff',
  },
  {
    id: 'b', label: 'B — pill hued, ALL names take their own hue (AA, ≥4.5:1)',
    note: 'Eight coloured names instead of one, so the change is finally visible. Blue and purple lift 11% and 7% toward white to clear the floor; amber, lime and green are untouched.',
    pill: s => HUES[ s.hue ].ink, pillBg: s => HUES[ s.hue ].dot, name: s => HUES[ s.hue ].ink,
  },
  {
    id: 'c', label: 'C — pill hued, ALL names at AAA (≥7:1)',
    note: 'Same as B with a bigger lift on blue, purple and green. Rendered side by side it is very nearly indistinguishable from B, so the extra contrast margin buys almost nothing visible — and it inherits B\'s problem below.',
    pill: s => HUES[ s.hue ].ink, pillBg: s => HUES[ s.hue ].dot, name: s => HUES[ s.hue ].aaa,
  },
];

const TICK = c => `<svg class="tick" viewBox="0 0 12 12" aria-hidden="true"><path d="M1.5 6.5 L4.5 9.5 L10.5 2.5" fill="none" stroke="${c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const panel = v => {
  const rows = STEPS.map( ( s, i ) => {
    const dot = HUES[ s.hue ].dot;
    const pillInk = v.pill( s );
    const pillHue = v.pillBg( s );
    const nameCol = v.name( s );
    const done = i < STEPS.length; // every rendered step is done or running; all static here
    return `
      <div class="step">
        <span class="dot" style="background:${dot};border-color:${dot}"></span>
        <div class="head">
          <span class="svc" style="color:${pillInk};background:rgba(${rgbOf( pillHue ).join( ',' )},.14);border-color:rgba(${rgbOf( pillHue ).join( ',' )},.34)">${s.svc}</span>
          <span class="name" style="color:${nameCol}">${s.complete ? TICK( nameCol ) : ''}${s.name}</span>
          <span class="time">${s.time}</span>
        </div>
      </div>`;
  } ).join( '' );

  return `
  <section class="variant" id="v-${v.id}">
    <h2>${v.label}</h2>
    <p class="note">${v.note}</p>
    <div class="panel">
      <div class="bar"><span class="l l1"></span><span class="l l2"></span><span class="l l3"></span><span class="bt">platform / production</span></div>
      <div class="body">
        <div class="req"><span class="caret">&rsaquo;</span> One customer places an order. Watch what runs behind it.</div>
        ${rows}
      </div>
    </div>
  </section>`;
};

const page = `<!doctype html><meta charset="utf-8"><title>step colours — five ways</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;padding:34px;background:#f6f7f4;font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans",sans-serif;color:#1a3a2a}
  h1{font-size:21px;margin:0 0 6px}
  .sub{margin:0 0 30px;font-size:14px;color:rgba(0,0,0,.6);max-width:760px;line-height:1.55}
  .variant{margin:0 0 34px}
  .variant h2{font-size:14px;letter-spacing:.05em;text-transform:uppercase;margin:0 0 6px;color:#1a3a2a}
  .note{margin:0 0 12px;font-size:13.5px;line-height:1.55;color:rgba(0,0,0,.66);max-width:760px}
  .panel{width:720px;border-radius:12px;overflow:hidden;border:1px solid #d8dcd2;background:#000}
  .bar{display:flex;align-items:center;gap:7px;padding:9px 13px;background:#3b271a}
  .l{width:10px;height:10px;border-radius:50%}
  .l1{background:#f0a818}.l2{background:#3da35a}.l3{background:#2563eb}
  .bt{margin-left:8px;font-size:11.5px;color:rgba(255,255,255,.62);font-family:ui-monospace,"SFMono-Regular",Menlo,monospace}
  .body{padding:16px 18px 18px}
  .req{font-size:13px;color:rgba(255,255,255,.72);margin:0 0 16px;font-family:ui-monospace,"SFMono-Regular",Menlo,monospace}
  .caret{color:#d1f470}
  .step{position:relative;padding:0 0 15px 24px}
  .step:last-child{padding-bottom:0}
  .dot{position:absolute;left:0;top:4px;width:12px;height:12px;border-radius:50%;border:2px solid;z-index:2}
  .head{min-height:20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .svc{padding:2px 7px;border-radius:4px;border:1px solid;font-size:11.5px;letter-spacing:.02em;font-family:ui-monospace,"SFMono-Regular",Menlo,monospace}
  .name{font-size:15px;font-weight:600;display:inline-flex;align-items:center;gap:5px}
  .tick{width:12px;height:12px;flex:0 0 auto}
  .time{font-size:12px;color:rgba(255,255,255,.46);font-family:ui-monospace,"SFMono-Regular",Menlo,monospace}
</style>
<h1>Workflow terminal — step colours, five ways</h1>
<p class="sub">Same eight steps, same dots, same type. Only the pill colour and the name colour change. The tick is drawn as an SVG here because this sandbox has no font with symbol coverage; the component renders a text glyph of the same shape.</p>
${VARIANTS.map( panel ).join( '' )}`;

async function main() {
  fs.mkdirSync( SHOTS, { recursive: true } );
  fs.writeFileSync( HTML, page );

  const browser = await launch();
  try {
    const context = await browser.newContext( { viewport: { width: 860, height: 900 }, deviceScaleFactor: 2 } );
    const p = await context.newPage();
    await p.goto( 'file://' + HTML, { waitUntil: 'load' } );
    await p.waitForTimeout( 300 );

    for ( const v of VARIANTS ) {
      const el = await p.$( `#v-${v.id} .panel` );
      await el.screenshot( { path: path.join( SHOTS, `${v.id}.png` ) } );
      console.log( `  wrote docs/step-mock/${v.id}.png` );
    }
    await p.screenshot( { path: path.join( SHOTS, 'all.png' ), fullPage: true } );
    console.log( '  wrote docs/step-mock/all.png' );
    await context.close();
  } finally {
    await browser.close();
  }

  /* ---------- the measurement table, computed not asserted ---------- */
  const rows = STEPS.map( ( s, i ) => {
    const h = HUES[ s.hue ];
    const pillBg = tint( h.dot, 0.14 );
    return `| ${i + 1} | \`${s.svc}\` | ${s.hue} \`${h.dot}\` | \`${h.ink}\` on \`${pillBg}\` = **${ratio( h.ink, pillBg )}:1** | \`${h.ink}\` = **${ratio( h.ink, '#000000' )}:1** | \`${h.aaa}\` = **${ratio( h.aaa, '#000000' )}:1** |`;
  } ).join( '\n' );

  const md = `# Workflow terminal — step colours, five ways

> ## DECIDED: **A**
>
> Owner picked **A** after seeing the five panels rendered. Shipped: hue lives on the dot and
> the chip, every step name holds \`#fff\` at 21:1, and the tick keeps its step's \`--ink\`.
>
> The deciding argument was only visible once the options were pictures. **On a sentence, a hue
> stops reading as an identifier and starts reading as a severity** — B put step 7, *"A provider
> failed, nobody noticed"*, in amber, which reads as a warning badge when the whole point of the
> line is that the failure was absorbed. This is the same reasoning already recorded in the
> component for excluding red from the dot palette.
>
> I had recommended **B** from the contrast figures alone, and the figures could not show this.
> The mock changed the answer — which is the argument for rendering options rather than
> describing them.
>
> This document is kept rather than deleted: it is the record of what was compared and why the
> recommendation was reversed.

The per-service dot hues shipped, and the report back was **"the dot colour changed, but the text colour is still lime green"**. That report was accurate. The reason was not visible in the diff.

\`.wt-name.is-complete\` is gated on \`step.complete\`, which is \`true\` for **exactly one of the eight steps**. So the rule recoloured a single line — lime \`#d1f470\` to green \`#3da35a\`, two greens, 16.89:1 down to 6.58:1 — while all eight \`.wt-svc\` pills stayed lime. The lime in the report was the pills.

Probed against the production export, \`tools/browser/replaycheck.js\`:

| # | service | dot | pill text | name text |
|---|---|---|---|---|
${STEPS.map( ( s, i ) => `| ${i + 1} | \`${s.svc}\` | ${s.hue} \`${HUES[ s.hue ].dot}\` | lime \`#d1f470\` | ${s.complete ? `green \`${HUES[ s.hue ].dot}\`` : 'white `#ffffff`'} |` ).join( '\n' )}

---

## The five panels

${VARIANTS.map( v => `### ${v.label}\n\n${v.note}\n\n![${v.id}](step-mock/${v.id}.png)\n` ).join( '\n' )}

---

## Measured

Pill text sits on its own hue at 14% over black. Name text sits on the panel body, \`#000\`. Pill type is 11.5px and name type is 15px/600 — both count as normal text for WCAG, so the floor is **4.5:1** for AA and **7:1** for AAA.

| # | service | dot hue | pill ink on its chip | name at AA (B) | name at AAA (C) |
|---|---|---|---|---|---|
${rows}

### Why blue and purple need lifting at all

| hue | raw | on \`#000\` | verdict as text |
|---|---|---|---|
| lime | \`#d1f470\` | 16.89:1 | passes AAA |
| amber | \`#f0a818\` | 10.32:1 | passes AAA |
| green | \`#3da35a\` | 6.58:1 | passes AA, misses AAA |
| purple | \`#9849e8\` | 4.45:1 | **fails AA** |
| blue | \`#2563eb\` | 4.06:1 | **fails AA** |

This is also a **latent bug in what currently ships**, not only a question about the mock. The committed comment beside \`.wt-name.is-complete\` claims the lowest of the five is "blue at 4.06:1. Well clear of 4.5:1 for 15px/600 text". 4.06 is not clear of 4.5 — it is below it. Nothing is visibly broken today only because step 8, the single complete step, happens to be green. Mark step 1 or 6 complete and the panel ships failing text.

### The hues stay distinguishable

Closest pair after lifting is blue against purple at **131** RGB distance of a possible 765. Every other pair is 194 or more. And each lifted ink stays close enough to its own dot to read as the same colour — blue moves **43**.

---

## What each option costs

**A** — one hue per row, carried by the dot and the chip. Names all white at 21:1, the most readable text on the panel. "Complete" is carried by the tick and by the footer's *running* / *complete* wording, so nothing is lost that colour was uniquely saying. Step 8 stops being the only dim row.

**B** — colours eight names instead of one, so the change is unmistakable. Costs the panel's primary text: a name drops from 21:1 to as low as 4.51:1.

**C** — B with a bigger lift. Rendered at size it is very nearly indistinguishable from B, so it pays a palette cost for a margin nobody can see.

---

## I am revising my own recommendation, and the mock is the reason

I recommended **B** before rendering it, on the argument that it was the only option that made the change visible. Looking at it, B has a problem the numbers could not show:

**On a sentence, a hue stops reading as an identifier and starts reading as a severity.**

- Row 7, *"A provider failed, nobody noticed"*, renders in **amber**. Amber on a sentence about a failure reads as a warning badge. The whole point of that line is that the failure was absorbed and nothing needed attention.
- Row 6, *"Usage metered"*, renders in **blue**, which reads as an info notice.

This is precisely the reasoning already recorded in this component for **excluding red** from the dot palette — red on "A provider failed" would read as an alarm about the thing being described. That argument applies with more force to a full sentence than to a 12px dot, and B puts the hue on the sentence.

The pill does not have this problem, and the difference is worth being precise about: a chip containing the single word \`queue\` is self-evidently an identifier, so colouring it reinforces identity. A chip cannot be mistaken for a severity because it is not a claim about anything. The sentence beside it can.

**So: A.** It resolves the original report completely — there is no lime text left anywhere in the panel, every row's hue is visible on its dot *and* its chip, and the change lands on all eight rows instead of one. It keeps the panel's primary text at 21:1, and it removes the current defect where step 8 is the only dim row. Colour ends up carrying exactly one meaning, *which service*, in the two places that are unambiguously labels.

None of the five panels changes what colour *means*: hue says **which service**, while motion, the tick and the footer wording say **whether it ran**. WCAG 1.4.1 stays unengaged throughout. A is the only one where hue never lands on a sentence.

---

Regenerate: \`node tools/browser/stepreview.js\`
`;

  fs.writeFileSync( MD, md );
  console.log( '  wrote docs/step-review.md' );

  // The .html is a build intermediate, not a deliverable - GitHub serves it as text/plain.
  fs.unlinkSync( HTML );
  console.log( '  removed the intermediate .html (GitHub serves it as text/plain)' );
}

main().catch( e => { console.error( e ); process.exit( 1 ); } );
