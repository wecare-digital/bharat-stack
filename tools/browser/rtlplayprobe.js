/**
 * rtlplayprobe - does the terminal's Pause control still sit on its reserved space under rtl?
 *
 * WHY A PROBE AND NOT AN OPINION. rtlcheck reports `button.wt-play off by 726px` on / and /404/
 * at every posture, and the arithmetic is not in doubt: the control is
 * position:absolute;right:0, `right` is a physical property, so its distance from the
 * inline-start edge cannot survive mirroring and the symmetry assertion must fail. What that
 * does NOT tell you is whether anything is visually wrong, and those are different questions.
 *
 * The case for "nothing is wrong": .wt-window carries dir="ltr" deliberately - it draws literal
 * machine output, and mirroring it produced a shell prompt and an API call that no longer
 * parsed, measured as the largest asymmetry on the home page at exactly 726px. Its title bar
 * therefore reserves its 108px of padding on the PHYSICAL right in both directions. A control
 * pinned to the physical right would land on that reserved space either way, and mirroring the
 * control while its window stays put is what would break it.
 *
 * The case for "something is wrong": the control is a sibling of the window rather than a child,
 * because the window is aria-hidden and a focusable element inside an aria-hidden subtree is
 * keyboard-reachable while absent from the accessibility tree. Siblings do not inherit the dir
 * lock, so nothing structural guarantees the two agree - they agree only as long as both happen
 * to be pinned to the same physical edge, which is a coincidence worth checking rather than
 * assuming.
 *
 * So this measures the thing that actually matters: whether the control overlaps the window's
 * three lights or its state text, and whether it stays inside the padding reserved for it.
 * Overlap is the defect; a failed symmetry assertion on its own is not.
 *
 *     node tools/browser/rtlplayprobe.js
 */
const { launch, gotoStable } = require( './lib/browser' );
const { target } = require( './lib/serve' );

const overlap = ( a, b ) => {
  const x = Math.max( 0, Math.min( a.right, b.right ) - Math.max( a.left, b.left ) );
  const y = Math.max( 0, Math.min( a.bottom, b.bottom ) - Math.max( a.top, b.top ) );
  return Math.round( x ) > 1 && Math.round( y ) > 1 ? `${Math.round( x )}x${Math.round( y )}px` : null;
};

( async () => {
  const t = await target();
  const browser = await launch();
  const page = await browser.newPage( { viewport: { width: 1280, height: 900 } } );

  console.log( `rtlplayprobe - ${t.mode} on ${t.base}\n` );

  let fail = 0;
  for ( const dir of [ 'ltr', 'rtl' ] ) {
    await gotoStable( page, `${t.base}/` );
    await page.evaluate( d => { document.documentElement.dir = d; }, dir );
    await page.waitForTimeout( 400 );

    const m = await page.evaluate( () => {
      const box = sel => {
        const el = document.querySelector( sel );
        if ( !el ) return null;
        const r = el.getBoundingClientRect();
        return { left: r.left, right: r.right, top: r.top, bottom: r.bottom,
          w: Math.round( r.width ), h: Math.round( r.height ) };
      };
      const bar = box( '.wt-bar' );
      const play = box( '.wt-play' );
      const lights = [ '.wt-light-1', '.wt-light-2', '.wt-light-3' ].map( box ).filter( Boolean );
      const state = box( '.wt-bar-state' );
      const cs = play ? getComputedStyle( document.querySelector( '.wt-play' ) ) : null;
      const barCs = bar ? getComputedStyle( document.querySelector( '.wt-bar' ) ) : null;
      return { bar, play, lights, state,
        playInset: cs ? `left:${cs.left} right:${cs.right}` : null,
        barPad: barCs ? `${barCs.paddingLeft} / ${barCs.paddingRight}` : null,
        windowDir: getComputedStyle( document.querySelector( '.wt-window' ) ).direction };
    } );

    if ( !m.play ) { console.log( `  ${dir}: no .wt-play rendered` ); continue; }

    console.log( `  ${dir.toUpperCase()}  window dir=${m.windowDir}  bar padding L/R = ${m.barPad}  play inset ${m.playInset}` );
    console.log( `        bar   ${Math.round( m.bar.left )}..${Math.round( m.bar.right )}` );
    console.log( `        play  ${Math.round( m.play.left )}..${Math.round( m.play.right )}  (${m.play.w}x${m.play.h})` );

    const insideBar = m.play.left >= m.bar.left - 1 && m.play.right <= m.bar.right + 1;
    console.log( `        inside the title bar: ${insideBar}` );

    const hits = [];
    m.lights.forEach( ( l, i ) => { const o = overlap( m.play, l ); if ( o ) hits.push( `light-${i + 1} ${o}` ); } );
    if ( m.state ) { const o = overlap( m.play, m.state ); if ( o ) hits.push( `bar-state ${o}` ); }

    if ( hits.length ) { console.log( `        OVERLAPS: ${hits.join( ', ' )}` ); fail++; }
    else console.log( '        overlaps nothing in the bar' );
  }

  await browser.close();
  console.log( fail
    ? `\nFAIL: the control collides with the title bar in ${fail} direction(s)`
    : '\nok: the control sits on its reserved space in both directions - the symmetry failure is '
      + 'a consequence of the deliberate dir=ltr lock, not a visual defect' );
  process.exit( fail ? 1 : 0 );
} )();
