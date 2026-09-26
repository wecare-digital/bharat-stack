// Build the two PNG boards the owner actually reads: .home-flow as it ships, and
// .home-flow with fixes 1 and 2 applied. Nothing here touches src/ - the "after"
// state is produced by injecting the exact declarations the edit would add, at
// matching specificity, and then MEASURING the result to prove the injection took.
//
// Run from mock/home-flow/tools/ with the repo built (NODE_ENV=production npm run build).
const { launch, gotoStable } = require( '../../../tools/browser/lib/browser' );
const { target } = require( '../../../tools/browser/lib/serve' );
const fs = require( 'fs' );
const path = require( 'path' );

const OUT = path.resolve( __dirname, 'out-board' );

// iPad portrait. The worst-affected real device, and inside the 768-1024 band that
// gets the narrow layout and the desktop panel height at the same time.
const VP = { width: 820, height: 1180 };

// The two edits, written as they would be written in the source, with the selector
// doubled so the injected rule matches styled-jsx's own .home-flow-copy.jsx-xxx
// specificity and wins on source order instead of on !important.
const FIX1 = cap => `@media(max-width:1024px){.home-flow-copy.home-flow-copy{max-width:${cap}px}}`;
const FIX2 = `@media(max-width:1024px){.wt-window.wt-window{height:min(560px,calc(100vh - 180px));border-radius:12px}}`;

// Same characters-per-line method as flowmeasure.cjs, so the captions on these
// boards are the same numbers the deep-check reported.
const PROBE = `
  ( () => {
    function cpl( el ) {
      if ( !el ) return null;
      const text = ( el.textContent || '' ).trim();
      if ( !text ) return null;
      const cs = getComputedStyle( el );
      const probe = document.createElement( 'span' );
      probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;font:' +
        cs.font + ';letter-spacing:' + cs.letterSpacing;
      probe.textContent = text;
      document.body.appendChild( probe );
      const advance = probe.getBoundingClientRect().width / text.length;
      probe.remove();
      return Math.round( el.getBoundingClientRect().width / advance );
    }
    const q = s => document.querySelector( s );
    const copy = q( '.home-flow-copy' );
    const wt = q( '.wt-window' );
    const flow = q( '.home-flow' );
    return {
      copyW: Math.round( copy.getBoundingClientRect().width ),
      copyMaxW: getComputedStyle( copy ).maxWidth,
      leadCpl: cpl( q( '.home-flow-lead' ) ),
      beatCpl: cpl( q( '.home-flow-list li span' ) ),
      panelH: wt ? Math.round( wt.getBoundingClientRect().height ) : null,
      panelW: wt ? Math.round( wt.getBoundingClientRect().width ) : null,
      flowW: Math.round( flow.getBoundingClientRect().width ),
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      // Is the transcript parked at the bottom of its scroller? A shorter panel means
      // more of the stream is scrolled out of sight, and the component only scrolls to
      // the bottom when its own state changes. If the height changed AFTER that ran,
      // the last line sits cut off behind the footer bar - which would be a defect in
      // the harness, not in the fix, and it has to be told apart from a real clip.
      scroll: ( () => {
        const sp = q( '.wt-space' );
        if ( !sp ) return null;
        const max = sp.scrollHeight - sp.clientHeight;
        return { top: Math.round( sp.scrollTop ), max: Math.round( max ),
          atBottom: max - sp.scrollTop <= 2 };
      } )(),
    };
  } )()
`;

async function shoot( browser, t, { name, css } ) {
  const ctx = await browser.newContext( {
    viewport: VP,
    deviceScaleFactor: 2,          // retina, so the copy is legible when chat scales it down
    serviceWorkers: 'block',       // public/sw.js intercepts requests otherwise
    reducedMotion: 'reduce',       // freeze the terminal: every shot shows the same frame
  } );
  // The stylesheet goes in BEFORE first layout, not after load. addStyleTag after
  // load reproduces the declaration but not the ORDER: the terminal scrolls its
  // transcript to the bottom when it mounts, so a panel that shrinks from 650px to
  // 560px afterwards is left scrolled short and the last line renders cut off. That
  // is exactly what the first run of this board showed, and it is not what the real
  // edit does - in the real edit the panel is 560px from the first frame. Deferring
  // to DOMContentLoaded also keeps the rule AFTER styled-jsx's own inlined <style>
  // tags in the head, so source order still decides the tie.
  if ( css ) {
    await ctx.addInitScript( sheet => {
      const inject = () => {
        const s = document.createElement( 'style' );
        s.textContent = sheet;
        document.head.appendChild( s );
      };
      if ( document.readyState === 'loading' ) {
        document.addEventListener( 'DOMContentLoaded', inject );
      } else { inject(); }
    }, css );
  }
  const page = await ctx.newPage();
  await gotoStable( page, `${t.base}/` );
  await page.waitForTimeout( 1200 );
  const m = await page.evaluate( PROBE );
  const el = await page.$( '.home-flow' );
  const file = path.join( OUT, `${name}.png` );
  await el.screenshot( { path: file } );
  await ctx.close();
  return { name, file, ...m };
}

// One board = a caption strip, a list of findings, and the real screenshot beneath.
// Built as HTML and photographed, because that is the only way to get labelled
// arrows onto a picture without drawing them by hand.
function boardHtml( { kind, title, subtitle, findings, shots } ) {
  const accent = kind === 'before' ? '#c0281c' : '#15803d';
  const chip = kind === 'before' ? 'AS IT SHIPS TODAY' : 'WITH THE FIX APPLIED';
  const cards = shots.map( s => `
    <figure class="card">
      <figcaption class="cap">
        <span class="capname">${s.label}</span>
        ${s.note ? `<span class="capnote">${s.note}</span>` : ''}
      </figcaption>
      <img src="${path.basename( s.file )}" width="${VP.width}">
    </figure>` ).join( '' );

  return `<!doctype html><meta charset="utf-8">
<style>
  *{box-sizing:border-box}
  body{margin:0;background:#f4f4f2;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;
       padding:36px;width:${VP.width * shots.length + 72 + 28 * ( shots.length - 1 )}px}
  .chip{display:inline-block;background:${accent};color:#fff;font-size:15px;font-weight:700;
        letter-spacing:.08em;padding:7px 14px;border-radius:5px}
  h1{font-size:34px;font-weight:700;letter-spacing:-.03em;line-height:1.14;margin:16px 0 6px;color:#111}
  .sub{font-size:19px;line-height:1.45;color:#444;margin:0 0 20px;max-width:900px}
  ul.find{margin:0 0 26px;padding:0;list-style:none;display:flex;flex-direction:column;gap:9px;max-width:1100px}
  ul.find li{font-size:18px;line-height:1.4;color:#1a1a1a;padding-left:30px;position:relative}
  ul.find li:before{content:'';position:absolute;left:0;top:7px;width:16px;height:16px;
                    border-radius:50%;background:${accent}}
  .row{display:flex;gap:28px;align-items:flex-start}
  .card{margin:0;background:#fff;border:1px solid #dcdcd8;border-radius:10px;overflow:hidden;
        box-shadow:0 2px 14px rgba(0,0,0,.07)}
  .cap{padding:12px 16px;border-bottom:1px solid #ececes;background:#fafaf8;display:flex;
       flex-direction:column;gap:3px}
  .capname{font-size:17px;font-weight:700;color:#111;letter-spacing:-.01em}
  .capnote{font-size:15px;color:${accent};font-weight:600}
  img{display:block}
  .foot{font-size:15px;line-height:1.45;color:#6b6b66;margin:20px 0 0;max-width:1100px}
</style>
<div class="chip">${chip}</div>
<h1>${title}</h1>
<p class="sub">${subtitle}</p>
<ul class="find">${findings.map( f => `<li>${f}</li>` ).join( '' )}</ul>
<div class="row">${cards}</div>
<p class="foot">The few empty squares inside the black panel are a missing emoji font in the
screenshot tool, not a fault on the page. The green circle at the bottom right is the
WhatsApp button, which is on every page.</p>`;
}

async function board( browser, spec, outName ) {
  const ctx = await browser.newContext( { viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 1 } );
  const page = await ctx.newPage();
  // Written to disk and loaded over file:// rather than setContent: a page created
  // from setContent has an about:blank origin and silently never loads file:// images,
  // which showed up as a waitForFunction timeout rather than as a broken <img>.
  const html = path.join( OUT, `${outName}.html` );
  fs.writeFileSync( html, boardHtml( spec ) );
  await page.goto( `file://${html}` );
  await page.waitForFunction( () => [ ...document.images ].every( i => i.complete && i.naturalWidth > 0 ) );
  await page.waitForTimeout( 300 );
  const out = path.resolve( __dirname, '..', outName );
  await page.screenshot( { path: out, fullPage: true } );
  await ctx.close();
  return out;
}

( async () => {
  fs.mkdirSync( OUT, { recursive: true } );
  const t = await target();
  const browser = await launch();

  const before = await shoot( browser, t, { name: 'shot-before', css: null } );
  const a680 = await shoot( browser, t, { name: 'shot-after-680', css: FIX1( 680 ) + FIX2 } );
  const a560 = await shoot( browser, t, { name: 'shot-after-560', css: FIX1( 560 ) + FIX2 } );

  // Prove the injection did what the edit would do, rather than assuming it.
  const checks = [
    [ 'before: copy has no cap', before.copyMaxW === 'none' ],
    [ 'before: panel is the desktop 650px', before.panelH === 650 ],
    [ 'before: panel spans the whole measure', before.panelW === before.flowW ],
    [ 'before: lines are over 75 chars', before.leadCpl > 75 && before.beatCpl > 75 ],
    [ 'after680: cap took', a680.copyMaxW === '680px' ],
    [ 'after680: panel stepped to 560px', a680.panelH === 560 ],
    [ 'after560: cap took', a560.copyMaxW === '560px' ],
    [ 'after560: panel stepped to 560px', a560.panelH === 560 ],
    [ 'after560: lines are inside 45-75', a560.leadCpl <= 75 && a560.beatCpl <= 75 ],
    [ 'no state overflows horizontally',
      [ before, a680, a560 ].every( s => s.overflow <= 0 ) ],
    // The shorter panel must not leave the transcript hanging half-hidden behind the
    // footer bar. Every state has to be parked at the bottom of its own scroller.
    [ 'every state has the transcript scrolled to the bottom',
      [ before, a680, a560 ].every( s => s.scroll && s.scroll.atBottom ) ],
  ];
  let bad = 0;
  console.log( '\n  assertions' );
  for ( const [ label, ok ] of checks ) {
    if ( !ok ) bad++;
    console.log( `   ${ok ? 'PASS' : 'FAIL'}  ${label}` );
  }

  console.log( '\n  state          copy box  cap      lead CPL  beat CPL  panel' );
  for ( const s of [ before, a680, a560 ] ) {
    console.log( '  ', s.name.replace( 'shot-', '' ).padEnd( 13 ),
      String( s.copyW + 'px' ).padEnd( 9 ), String( s.copyMaxW ).padEnd( 8 ),
      String( s.leadCpl ).padEnd( 9 ), String( s.beatCpl ).padEnd( 9 ),
      `${s.panelW}x${s.panelH}` );
  }

  const b1 = await board( browser, {
    kind: 'before',
    title: 'iPad portrait, 820px wide &mdash; the home page block below the hero',
    subtitle: 'This is the real page, photographed at the width of an iPad held upright. ' +
      'Two things are wrong with it, and both come from a number rather than from the design.',
    findings: [
      `The text runs <b>${before.beatCpl} characters per line</b>. Comfortable reading is 45&ndash;75. ` +
        'The column has no width limit at all once the layout stops being two columns.',
      `The black panel is <b>${before.panelH}px tall and ${before.panelW}px wide</b> &mdash; the full ` +
        'measure, with nothing beside it. That is the desktop size on a tablet layout.',
    ],
    shots: [ { file: before.file, label: 'Now', note: `${before.beatCpl} characters per line  ·  panel ${before.panelW} × ${before.panelH}px` } ],
  }, 'board-1-before.png' );

  const b2 = await board( browser, {
    kind: 'after',
    title: 'The same width, with the two fixes',
    subtitle: 'The text column gets a width limit, and the panel gets the shorter height it ' +
      'already uses on phones. Desktop is untouched &mdash; both changes live inside the ' +
      'existing narrow-screen block. The two pictures differ only in the width limit: ' +
      '680px was the number proposed, 560px is the number this page already uses for the ' +
      'paragraph under the headline.',
    findings: [
      `<b>680px</b> brings the line down to <b>${a680.beatCpl} characters</b> &mdash; much better, ` +
        'but still above the 75 the rule of thumb sets.',
      `<b>560px</b> brings it to <b>${a560.beatCpl} characters</b>, inside 45&ndash;75, and reuses a ` +
        'width already on this page rather than inventing one.',
      `The panel is <b>${a560.panelH}px</b> in both, down from ${before.panelH}px &mdash; the same ` +
        'height a phone already gets today.',
    ],
    shots: [
      { file: a680.file, label: 'Option A — limit 680px', note: `${a680.beatCpl} characters per line  ·  panel ${a680.panelW} × ${a680.panelH}px` },
      { file: a560.file, label: 'Option B — limit 560px', note: `${a560.beatCpl} characters per line  ·  panel ${a560.panelW} × ${a560.panelH}px` },
    ],
  }, 'board-2-after.png' );

  await browser.close();
  await t.close();
  console.log( `\n  boards\n   ${b1}\n   ${b2}` );
  if ( bad ) { console.log( `\n  ${bad} ASSERTION(S) FAILED` ); process.exit( 1 ); }
  console.log( '\n  all assertions pass' );
} )();
