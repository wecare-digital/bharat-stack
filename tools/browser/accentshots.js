'use strict';

/**
 * accentshots - renders docs/accent-review.html to PNGs plus a Markdown wrapper.
 *
 * Same reason as dividershots.js: GitHub serves raw .html as text/plain, so a committed HTML
 * mock displays as source, and the proxy that fixes that did not open. Markdown with PNGs
 * renders natively, with no proxy and no login. Generated FROM the HTML so the two cannot drift.
 *
 * Writes: docs/accent-mock/*.png and docs/accent-review.md
 * Run: node tools/browser/accentshots.js   (after accentreview.js)
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { launch } = require( './lib/browser' );

const DOCS = path.join( __dirname, '..', '..', 'docs' );
const MOCK = path.join( DOCS, 'accent-review.html' );
const SHOTS = path.join( DOCS, 'accent-mock' );
const MD = path.join( DOCS, 'accent-review.md' );

/** Cards in document order, named for the file they become. */
const CARDS = [
  'footer-1a-14px', 'footer-1b-words', 'footer-1c-22px', 'footer-1d-green-bharat',
  'ticks-2a-one-green', 'ticks-2b-beat-colours', 'ticks-2c-amber-fails', 'ticks-2d-drawing',
  'dots-3a-now', 'dots-3b-as-asked', 'dots-3c-lightened-pulse', 'dots-3d-no-new-colours',
];

/** ms before the shutter each filmstrip column was armed. */
const STRIP = [ 40, 190, 340, 780 ];

( async () => {
  if ( !fs.existsSync( MOCK ) ) {
    console.error( `No mock at ${MOCK} - run node tools/browser/accentreview.js first.` );
    process.exit( 1 );
  }
  fs.mkdirSync( SHOTS, { recursive: true } );

  const browser = await launch();
  const page = await browser.newPage( { viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2 } );

  /* ---- every card at rest ---- */
  await page.goto( 'file://' + MOCK, { waitUntil: 'load' } );
  await page.waitForTimeout( 1600 );
  const cards = await page.$$( '.card' );
  if ( cards.length !== CARDS.length ) {
    console.warn( `  note: ${cards.length} cards found, ${CARDS.length} names - check the order` );
  }
  for ( let i = 0; i < Math.min( cards.length, CARDS.length ); i++ ) {
    await cards[ i ].screenshot( { path: path.join( SHOTS, `${CARDS[ i ]}.png` ) } );
    console.log( `  ${CARDS[ i ]}.png` );
  }

  /* ---- the contrast table, which is the argument ---- */
  const table = await page.$( 'table' );
  await table.screenshot( { path: path.join( SHOTS, 'contrast-table.png' ) } );
  console.log( '  contrast-table.png' );

  /**
   * FILMSTRIPS for the animated options. Four real copies armed at staggered times and caught
   * in one screenshot, so each column is a genuine frame of the real transition rather than an
   * interpolated guess - the same technique dividershots uses, and the reason is the same: the
   * question is whether the motion is legible, and a simulated curve answers it for you.
   */
  const strips = [
    { name: 'footer-1b-words-filmstrip', sel: '.ft.words', label: 'word by word' },
    { name: 'footer-1a-14px-filmstrip', sel: '.ft.v14:not(.accent)', label: '14px rise' },
    { name: 'ticks-2d-drawing-filmstrip', sel: '.pts.draw', label: 'ticks drawing' },
  ];

  for ( const strip of strips ) {
    await page.goto( 'file://' + MOCK, { waitUntil: 'load' } );
    await page.waitForTimeout( 700 );

    await page.evaluate( ( { sel, offsets, isTicks } ) => {
      const source = document.querySelector( sel );
      const host = document.createElement( 'div' );
      host.id = 'strip';
      host.style.cssText = 'display:flex;gap:16px;padding:22px;background:#fff;align-items:flex-start';
      for ( const ms of offsets ) {
        const col = document.createElement( 'div' );
        col.style.cssText = 'flex:1;min-width:0';
        const label = document.createElement( 'div' );
        label.textContent = ms >= 700 ? 'settled' : `${ms} ms`;
        label.style.cssText = 'font:600 11px Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:rgba(0,0,0,.42);margin:0 0 10px';
        const copy = source.cloneNode( true );
        copy.classList.remove( 'is-in' );
        copy.classList.add( 'is-armed' );
        const wrap = document.createElement( 'div' );
        // Ticks need their panel back, or they float on white and read wrong.
        if ( isTicks ) {
          wrap.style.cssText = 'background:rgba(209,244,112,.22);border:2px solid #d1f470;border-radius:12px;padding:16px';
        }
        wrap.append( copy );
        col.append( label, wrap );
        host.append( col );
      }
      document.body.prepend( host );
    }, { sel: strip.sel, offsets: STRIP, isTicks: strip.sel.includes( 'pts' ) } );

    const order = [ ...STRIP ].sort( ( a, b ) => b - a );
    let elapsed = 0;
    for ( const ms of order ) {
      const wait = order[ 0 ] - ms - elapsed;
      if ( wait > 0 ) { await page.waitForTimeout( wait ); elapsed += wait; }
      await page.evaluate( ( { index, sel } ) => {
        const el = document.querySelectorAll( `#strip ${sel.includes( 'pts' ) ? '.pts' : '.ft'}` )[ index ];
        void el.offsetHeight;
        el.classList.add( 'is-in' );
      }, { index: STRIP.indexOf( ms ), sel: strip.sel } );
    }
    await ( await page.$( '#strip' ) ).screenshot( { path: path.join( SHOTS, `${strip.name}.png` ) } );
    console.log( `  ${strip.name}.png` );
  }

  await browser.close();

  const md = `# Three accent questions — footer, band 3 ticks, terminal dots

> Rendered from \`docs/accent-review.html\` by \`tools/browser/accentshots.js\`, because GitHub
> serves raw \`.html\` as \`text/plain\` and shows it as source. The HTML version has the
> animations running live with Replay buttons; these PNGs render here with no proxy.
>
> The filmstrips are **four real copies** armed at staggered times and caught in one
> screenshot — every column is a genuine frame of the real transition, not an interpolated guess.

You asked for all three as one thing: *three colours, with animation.* The measurement says
they are **not** one thing.

## The one number that decides it

![Contrast on both backgrounds](accent-mock/contrast-table.png)

The three elements sit on three different backgrounds — footer \`#ffffff\`, band 3 panel
\`#f5fde0\` (lime \`.22\` over white), terminal bar \`#3b271a\`. A mid-tone hue cannot clear 3:1
on both a near-white panel and a dark brown bar: too light for one, too dark for the other.

**Only green \`#3da35a\` clears 3:1 on both** — 3.04:1 and 4.42:1.

So "the same three colours everywhere" is not available. Two specifics:

| | |
|---|---|
| **amber \`#f0a818\`** | **1.94:1** on the band 3 panel — worse than on white, because the panel is itself yellow-green |
| **purple \`#9849e8\`** | **2.99:1** on the terminal bar — a mid-tone on dark brown |

---

# 1 · Footer tagline

Already live since #78: 14 px rise over 560 ms. You were right that 6 px was invisible — the
probe found it playing perfectly at ~11 px/s.

| ![1A](accent-mock/footer-1a-14px.png) | ![1B](accent-mock/footer-1b-words.png) |
|---|---|
| ![1C](accent-mock/footer-1c-22px.png) | ![1D](accent-mock/footer-1d-green-bharat.png) |

**1A in motion:**

![1A filmstrip](accent-mock/footer-1a-14px-filmstrip.png)

**1B, word by word — five words 60 ms apart:**

![1B filmstrip](accent-mock/footer-1b-words-filmstrip.png)

**1B's real cost:** this line is translated, and a translated sentence has a different word
count — so the spans must be generated from rendered text at runtime, not hardcoded, or other
languages break.

---

# 2 · Band 3's three ticks

Currently all three are \`#1a3a2a\` at 11.89:1. Matching the beats works — **but not with amber.**

| ![2A](accent-mock/ticks-2a-one-green.png) | ![2B](accent-mock/ticks-2b-beat-colours.png) |
|---|---|
| ![2C](accent-mock/ticks-2c-amber-fails.png) | ![2D](accent-mock/ticks-2d-drawing.png) |

Look at the first tick in **2C** — on a yellow-green panel the amber mark nearly disappears
while the other two are solid. Not a guideline violation (the text is complete without the
ticks); it just does not read as three colours, it reads as two ticks and a smudge.

**2B** uses the exact three hex values band 2 already ships — green / blue / purple, all above
3:1, no new colour anywhere.

**2D, ticks drawing in:**

![2D filmstrip](accent-mock/ticks-2d-drawing-filmstrip.png)

---

# 3 · The three dots before "platform / production"

> ### This one reverses an instruction of yours that is in the code
>
> \`WorkflowTerminal.tsx\`, verbatim: *"LIME AND NEUTRALS ONLY, on instruction. The window
> lights were red/amber/lime borrowed from macOS; the first two are the only warm hues on the
> page and they pulled the eye to chrome rather than to content."*
>
> The same file warns that colour here *"competes with the lime step dots that mark actual
> state"* — inside the panel, lime dots mean **this service ran**. Three coloured dots on the
> window frame mean nothing, and would be the most colourful thing in a panel whose only real
> signal is lime.
>
> You may well want to reverse it. It should just be on purpose.

| ![3A](accent-mock/dots-3a-now.png) | ![3B](accent-mock/dots-3b-as-asked.png) |
|---|---|
| ![3C](accent-mock/dots-3c-lightened-pulse.png) | ![3D](accent-mock/dots-3d-no-new-colours.png) |

**A correction I owe you on 3B.** I first wrote that purple "sits almost on top of" the bar at
2.99:1. Look at it — it is perfectly visible. A WCAG ratio measures **luminance only**, and a
saturated purple against dark brown differs strongly in hue and chroma, which the metric does
not count. The number is marginal; the appearance is fine. So **3B has no contrast problem** —
only the recorded-instruction problem.

**3C** makes the colours work by lightening them for a dark bar — but costs **two new colour
values** that exist nowhere in the repo, plus an endless pulse in a panel whose terminal
deliberately plays *once and stops* (the WCAG 2.2.2 argument that killed the loop applies here).

**3D** is amber / green / lime — no new colours, all legible. It is also almost exactly the
macOS set that was removed, with green in place of red.

---

# What I would do

**1 → 1A, unchanged.** Live, measured, and 1B's translation cost is real. If 14 px still reads
too quiet, take **1D** — colour on "Bharat" survives no-JS *and* reduced motion, which motion
cannot.

**2 → 2B.** Matching the beats is a good instinct and costs nothing: the hex values are already
on the page and all three clear 3:1. Not 2C. I would skip 2D — this band already staggers these
exact three items at 340/430/520 ms, so a second stagger inside each is motion for its own sake.

**3 → 3A, keep it** — and *not* for contrast reasons, which I got wrong above and corrected. The
dots are \`aria-hidden\` window chrome carrying no meaning, and the panel's whole argument is that
*lime means something happened*. Three coloured dots make the frame louder than the content —
your own recorded instruction, in that file, in those words.

If you want colour there anyway, **3B** is the one I would take now: no new colour values and it
looks right. Not 3C (two new hexes plus an endless pulse), not 3D (walks back into the macOS set
you removed).

---

**Tell me per item — e.g. "1A, 2B, 3A" — and I will ship it with probes asserting the contrast
on the real composited backgrounds.**
`;

  fs.writeFileSync( MD, md );
  const total = fs.readdirSync( SHOTS ).reduce( ( s, f ) => s + fs.statSync( path.join( SHOTS, f ) ).size, 0 );
  console.log( `\n  ${MD}` );
  console.log( `  ${fs.readdirSync( SHOTS ).length} PNGs, ${Math.round( total / 1024 )} kB\n` );
} )();
