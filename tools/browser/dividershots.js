'use strict';

/**
 * dividershots - renders docs/divider-review.html to PNGs, including motion filmstrips.
 *
 * WHY THIS EXISTS. The HTML mock is the better artefact - the animations actually run in it -
 * but it could not be opened. GitHub serves raw files as text/plain, so a committed .html
 * shows as source, and the third-party proxy that fixes that (raw.githack) did not work for
 * the owner. A review artefact nobody can open is not a review artefact.
 *
 * PNGs embedded in Markdown render natively on GitHub with no proxy, no login and no
 * content-type problem. So this produces those, from the SAME file, so the two cannot drift.
 *
 * HOW A STILL IMAGE SHOWS AN ANIMATION. Not by faking intermediate values: the four columns of
 * each filmstrip are four real copies of the component, ARMED AT STAGGERED TIMES and then
 * captured in a single screenshot. Column 4 was armed 700ms before the shutter, column 1 just
 * before it - so every column is a genuine frame of the real transition, with the real easing
 * and the real 90ms inter-bar delay. Nothing is simulated, which matters because the whole
 * question is whether the stagger is legible.
 *
 * Writes: docs/divider-mock/*.png and docs/divider-review.md
 * Run: node tools/browser/dividershots.js   (after dividerreview.js)
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { launch } = require( './lib/browser' );

const DOCS = path.join( __dirname, '..', '..', 'docs' );
const MOCK = path.join( DOCS, 'divider-review.html' );
const SHOTS = path.join( DOCS, 'divider-mock' );
const MD = path.join( DOCS, 'divider-review.md' );

/** Milliseconds before the shutter that each filmstrip column was armed. */
const FILMSTRIP = [ 40, 190, 330, 760 ];

const OPTIONS = [
  { id: 'a', sel: '#opt-a', file: 'a-current.png', animated: false },
  { id: 'b', sel: '#opt-b', file: 'b-three-colours.png', animated: false },
  { id: 'c', sel: '#opt-c', file: 'c-colours-draw.png', animated: true },
  { id: 'd', sel: '#opt-d', file: 'd-lime-draw.png', animated: true },
];

( async () => {
  if ( !fs.existsSync( MOCK ) ) {
    console.error( `No mock at ${MOCK} - run node tools/browser/dividerreview.js first.` );
    process.exit( 1 );
  }
  fs.mkdirSync( SHOTS, { recursive: true } );

  const browser = await launch();
  const page = await browser.newPage( { viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 } );

  /* ---- 1. each option at rest, cropped to its own card ---- */
  for ( const opt of OPTIONS ) {
    await page.goto( 'file://' + MOCK, { waitUntil: 'load' } );
    await page.waitForTimeout( 1400 ); // let every reveal finish
    const card = await page.$( opt.sel );
    await card.screenshot( { path: path.join( SHOTS, opt.file ) } );
    console.log( `  ${opt.file}` );
  }

  /* ---- 2. filmstrips: four real frames of one transition, in one shot ---- */
  for ( const opt of OPTIONS.filter( o => o.animated ) ) {
    await page.goto( 'file://' + MOCK, { waitUntil: 'load' } );
    await page.waitForTimeout( 600 );

    const strip = await page.evaluateHandle( ( { sel, offsets } ) => {
      const source = document.querySelector( `${sel} .beats` );
      const host = document.createElement( 'div' );
      host.id = 'filmstrip';
      host.style.cssText = 'display:flex;gap:18px;padding:20px;background:#fff;align-items:flex-start';
      for ( const ms of offsets ) {
        const col = document.createElement( 'div' );
        col.style.cssText = 'flex:1;min-width:0';
        const label = document.createElement( 'div' );
        label.textContent = ms >= 700 ? 'settled' : `${ms} ms`;
        label.style.cssText = 'font:600 11px Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:rgba(0,0,0,.42);margin:0 0 10px';
        const copy = source.cloneNode( true );
        copy.classList.remove( 'is-in' );
        copy.classList.add( 'is-armed' );
        col.append( label, copy );
        host.append( col );
      }
      document.body.prepend( host );
      return host;
    }, { sel: opt.sel, offsets: FILMSTRIP } );

    /*
     * Arm the LATEST column first and the earliest last, so that at the moment of the
     * screenshot each column has been running for its own labelled duration. Every column is
     * therefore a real frame of the real transition rather than a value someone chose.
     */
    const order = [ ...FILMSTRIP ].sort( ( a, b ) => b - a );
    let elapsed = 0;
    for ( const ms of order ) {
      const wait = order[ 0 ] - ms - elapsed;
      if ( wait > 0 ) { await page.waitForTimeout( wait ); elapsed += wait; }
      await page.evaluate( ( { index } ) => {
        const col = document.querySelectorAll( '#filmstrip .beats' )[ index ];
        void col.offsetHeight;
        col.classList.add( 'is-in' );
      }, { index: FILMSTRIP.indexOf( ms ) } );
    }

    const file = opt.file.replace( '.png', '-filmstrip.png' );
    await ( await page.$( '#filmstrip' ) ).screenshot( { path: path.join( SHOTS, file ) } );
    console.log( `  ${file}` );
    await strip.dispose();
  }

  /* ---- 3. the footer tagline, 6px against 14px, same technique ---- */
  await page.goto( 'file://' + MOCK, { waitUntil: 'load' } );
  await page.waitForTimeout( 600 );
  await page.evaluate( ( { offsets } ) => {
    const host = document.createElement( 'div' );
    host.id = 'ftstrip';
    host.style.cssText = 'display:flex;gap:16px;padding:20px;background:#fff';
    for ( const variant of [ 'six', 'fourteen' ] ) {
      const source = document.querySelector( `.ft.${variant}` );
      const group = document.createElement( 'div' );
      group.style.cssText = 'flex:1;border:1px solid #e5e7eb;border-radius:12px;padding:14px';
      const head = document.createElement( 'div' );
      head.textContent = variant === 'six' ? '6px / 520ms — what you could not see' : '14px / 560ms — live now';
      head.style.cssText = 'font:700 12px Inter,sans-serif;color:#1a3a2a;margin:0 0 12px';
      group.append( head );
      const row = document.createElement( 'div' );
      row.style.cssText = 'display:flex;gap:12px';
      for ( const ms of offsets ) {
        const col = document.createElement( 'div' );
        col.style.cssText = 'flex:1;min-width:0';
        const label = document.createElement( 'div' );
        label.textContent = ms >= 700 ? 'settled' : `${ms}ms`;
        label.style.cssText = 'font:600 10px Inter,sans-serif;letter-spacing:.05em;text-transform:uppercase;color:rgba(0,0,0,.42);margin:0 0 8px';
        const copy = source.cloneNode( true );
        copy.classList.remove( 'is-in' );
        copy.classList.add( 'is-armed' );
        col.append( label, copy );
        row.append( col );
      }
      group.append( row );
      host.append( group );
    }
    document.body.prepend( host );
  }, { offsets: FILMSTRIP } );

  const ftOrder = [ ...FILMSTRIP ].sort( ( a, b ) => b - a );
  let ftElapsed = 0;
  for ( const ms of ftOrder ) {
    const wait = ftOrder[ 0 ] - ms - ftElapsed;
    if ( wait > 0 ) { await page.waitForTimeout( wait ); ftElapsed += wait; }
    await page.evaluate( ( { index, count } ) => {
      const all = document.querySelectorAll( '#ftstrip .ft' );
      // Same column index in BOTH variants, so the two are compared at equal elapsed time.
      for ( let v = 0; v < 2; v++ ) {
        const el = all[ v * count + index ];
        void el.offsetHeight;
        el.classList.add( 'is-in' );
      }
    }, { index: FILMSTRIP.indexOf( ms ), count: FILMSTRIP.length } );
  }
  await ( await page.$( '#ftstrip' ) ).screenshot( { path: path.join( SHOTS, 'footer-6-vs-14-filmstrip.png' ) } );
  console.log( '  footer-6-vs-14-filmstrip.png' );

  await browser.close();

  /* ---- 4. the Markdown that GitHub can actually render ---- */
  const md = `# Band 2's three dividers, and the footer entrance

> **Why this file exists as Markdown.** \`docs/divider-review.html\` is the better artefact —
> the animations run in it, with a Replay button — but GitHub serves raw \`.html\` as
> \`text/plain\`, so it shows as source rather than rendering, and the proxy that works around
> that did not open. These PNGs are rendered **from that same file** by
> \`tools/browser/dividershots.js\`, so the two cannot drift. GitHub renders them inline with no
> proxy and no login.
>
> The four-column strips are **not simulated**. Each column is a real copy of the component
> armed at a staggered time and captured in a single screenshot, so every column is a genuine
> frame of the real transition with the real easing and the real 90 ms inter-bar delay.

## The question, and what it is really about

Should the three lime rules in band 2 stay one colour or become three, with animation?

It is not a CSS question. The five tint/dot pairs in this repo are documented as
*"a per-subject system that sits outside the brand palette by design"*, and they are used where
each item names a **different subject** — the rotating words in three separate heroes. So
colour-coding a list is this site saying *these are different kinds of thing*.

The source already answers whether that is true here. The section had **four** beats; the
fourth — "It remembers the context" — was deleted for saying the same thing as the first, and
the docblock records why: **"Three claims, one idea."**

---

## A — as it ships today

![Option A](divider-mock/a-current.png)

Three parts of one idea. No order implied, no hierarchy.

**The argument against:** since the bars were equalised to 118 px in #77 they are identical in
colour, thickness **and** height. That flatness is the report.

## B — three colours, as asked

![Option B](divider-mock/b-three-colours.png)

Three different **kinds** of thing — which is what this palette means everywhere else.

**The argument against:** contradicts "Three claims, one idea", and the deletion of the fourth
beat that the phrase was written to explain.

## C — three colours + staggered draw

![Option C](divider-mock/c-colours-draw.png)

![Option C in motion](divider-mock/c-colours-draw-filmstrip.png)

**The argument against:** carries B's problem and adds a second signal on top. Motion already
says *sequence*; colour saying *different subjects* at the same time tells the reader two
different stories about one list.

## D — one lime + staggered draw  ·  **recommended**

![Option D](divider-mock/d-lime-draw.png)

![Option D in motion](divider-mock/d-lime-draw-filmstrip.png)

Three parts of one idea, read in order. The sequence comes from the motion; the single hue
keeps them one thing.

**Why this one.** The flatness you are reacting to is real and it is my doing — equalising the
bars removed the last thing that differed between them. Motion restores the difference without
making a claim: it says **order**, which the list has, rather than **category**, which it does
not. If you want colour anyway, take **B** over **C**.

---

## Cost of each option

| Option | New colour values | Needs JS | Reduced motion | Contrast risk |
|---|---|---|---|---|
| **A** today | none | no | n/a | none |
| **B** three colours | none — reuses three existing subject hues | no | n/a | none, all ≥3:1 on white at 3px |
| **C** colours + draw | none | yes, to arm | bars visible, no draw | none |
| **D** lime + draw | none | yes, to arm | bars visible, no draw | none |

"Needs JS to arm" is the pattern the footer dash and the hero pill already use: the stylesheet
ships the **finished** state, and JavaScript adds \`.is-armed\` to hide the start state only once
it has confirmed it can animate. No JS, or \`prefers-reduced-motion\`, leaves three visible lime
bars — exactly what ships today.

---

## The footer tagline

Already live on \`stack\` at 14 px, merged in #78. You reported it as "not showing" twice while
it was 6 px, and you were right — \`footerprobe.js\` found the reveal playing perfectly (34
hidden frames, 48 mid-fade, finishing at opacity 1) travelling **6 px over 520 ms**, about
11 px/s, on a 15 px line beside a 56 px dash moving nine times faster.

![Footer, 6px against 14px](divider-mock/footer-6-vs-14-filmstrip.png)

14 px is a little over half this line's 24 px line box, so the movement registers without
reading as a jump. \`footerprobe.js\` now **asserts** travel ≥ 12 px, because every frame-level
check was already green at 6 px and so could not be the guard.

---

**Tell me a letter — A, B, C or D — and I will ship it with a probe that asserts the stagger,
the same way the footer one asserts the travel.**
`;

  fs.writeFileSync( MD, md );
  const total = fs.readdirSync( SHOTS ).reduce( ( sum, f ) => sum + fs.statSync( path.join( SHOTS, f ) ).size, 0 );
  console.log( `\n  ${MD}` );
  console.log( `  ${fs.readdirSync( SHOTS ).length} PNGs, ${Math.round( total / 1024 )} kB total\n` );
} )();
