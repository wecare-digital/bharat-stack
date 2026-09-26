'use strict';

/**
 * homemock - renders hero-CTA variants for review BEFORE any source change.
 *
 * WHY IT PATCHES THE REAL PAGE INSTEAD OF DRAWING A MOCKUP. A hand-written mock HTML
 * file would get the fonts, the clamp() headline, the 108px header offset and the fold
 * position all slightly wrong, and those are exactly the things being judged. This loads
 * the actual static export, injects the proposed element and stylesheet into it, measures,
 * and screenshots. What you see is the real page with one block added.
 *
 * NOTHING IN src/ IS TOUCHED. The injection lives in this file only.
 *
 * COPY IS PLACEHOLDER, AND DELIBERATELY BORROWED RATHER THAN INVENTED. Every label below
 * already exists on the site - "Submit a request" is the header nav item and one of the
 * five rotating phrases on /contact/; "Sign in" describes /access, which is the login
 * entry that redirects to /dashboard. No new positioning language is proposed here,
 * because the handoff records that the owner writes this page's copy personally.
 *
 * THE PRICE IS DERIVED, NEVER TYPED. Read from src/content/wix-catalog.json at render
 * time, so the mock cannot show a number the catalogue does not contain.
 *
 * ON THE TYPE LADDER, which is the one real design argument in here. index.tsx holds that
 * the page has ONE body level (20px/400/1.4/-.125px) and that the hero sub-line is
 * deliberately a single sentence, because "a second would put two body blocks on a page
 * that has no section rhythm yet". So a price rendered as body copy is either a second
 * body block (against that note) or a new rung at 17px (the drift the file has already
 * corrected twice). Variants B and D therefore put the price on the CONTROL row at the
 * CTA's own 17px/600, beside the button rather than beneath it - a control label, not
 * body copy. That is the choice to accept or reject.
 *
 * Run: node tools/browser/homemock.js   (needs out/ - see README.md)
 * Writes: docs/mockups/home-hero-20260926/*.png
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

const OUT = path.join( __dirname, '..', '..', 'docs', 'mockups', 'home-hero-20260926' );

// ---- the derived price floor -------------------------------------------------
const catalog = JSON.parse(
  fs.readFileSync( path.join( __dirname, '..', '..', 'src', 'content', 'wix-catalog.json' ), 'utf8' )
);
const items = Array.isArray( catalog ) ? catalog : ( catalog.products || catalog.items || [] );
const prices = items.map( p => Number( p.price ) ).filter( n => Number.isFinite( n ) && n > 0 );
const FLOOR = Math.min( ...prices );
const FLOOR_TXT = `₹${FLOOR.toLocaleString( 'en-IN' )}`;

// ---- the injected stylesheet ------------------------------------------------
// Mirrors .home-close-cta's treatment exactly (lime #d1f470 on #1a3a2a, 2px border,
// 50px radius, 17px/600) so the hero CTA reads as the same control as the closing one,
// at the same size. min-height 52px is the closing CTA's own value and clears 44px.
const CSS = `
  .mock-cta-row{
    display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin:32px 0 0;
  }
  .mock-cta{
    display:inline-flex;align-items:center;min-height:52px;
    padding:0 28px;border:2px solid #d1f470;border-radius:50px;
    background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
    transition:background-color .2s,box-shadow .2s,transform .2s;
  }
  .mock-cta:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
  .mock-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
  /* Secondary: no new colour. Same #1a3a2a type, lime dropped to a hairline-safe 2px
     outline on white, which is the site's static-border weight. */
  .mock-cta-2{
    display:inline-flex;align-items:center;min-height:52px;
    padding:0 24px;border:2px solid rgba(26,58,42,.22);border-radius:50px;
    background:#fff;color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
  }
  .mock-cta-2:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
  /* Price as a CONTROL-ROW label at the CTA's own size, not a second body block. */
  .mock-price{font-size:17px;font-weight:400;color:rgba(0,0,0,.54);letter-spacing:-.125px}
  .mock-price b{font-weight:600;color:#1a3a2a}
  @media(max-width:767px){
    .mock-cta-row{gap:12px;margin-top:28px}
    .mock-cta,.mock-cta-2{width:100%;justify-content:center}
    .mock-price{width:100%}
  }
`;

// Each variant returns the HTML for the row appended inside .home-hero, after .home-sub.
// Appending there rather than anywhere else is what puts it next in the natural tab
// order, immediately after the text it follows - no tabindex needed.
const VARIANTS = [
  {
    id: 'A-control',
    title: 'A — control, exactly as shipped',
    note: 'No change. The reference for every measurement below.',
    html: null,
  },
  {
    id: 'B-single-contact',
    title: 'B — one primary CTA, to /contact/',
    note: 'The minimum that closes the finding. "Submit a request" is existing site '
      + 'language (header nav item, and one of the five rotating phrases on /contact/).',
    html: `<div class="mock-cta-row">
      <a class="mock-cta" href="/contact/">Submit a request</a>
    </div>`,
  },
  {
    id: 'C-single-price',
    title: `C — primary CTA + derived price on the control row (${FLOOR_TXT})`,
    note: `Price read from wix-catalog.json at render time: floor ${FLOOR_TXT}. Sits on the `
      + 'control row at 17px, NOT as a second body block. Gives the closing band\'s '
      + '"Know the price before you commit" something above the fold to stand on.',
    html: `<div class="mock-cta-row">
      <a class="mock-cta" href="/contact/">Submit a request</a>
      <span class="mock-price">from <b>${FLOOR_TXT}</b></span>
    </div>`,
  },
  {
    id: 'D-two-actions',
    title: 'D — primary to /contact/, secondary to /access',
    note: 'Separates the new visitor from the returning one. /access is the login entry '
      + 'that redirects to /dashboard, and nothing above the fold currently points there.',
    html: `<div class="mock-cta-row">
      <a class="mock-cta" href="/contact/">Submit a request</a>
      <a class="mock-cta-2" href="/access">Sign in</a>
    </div>`,
  },
  {
    id: 'E-everything',
    title: `E — both actions + price (${FLOOR_TXT})`,
    note: 'Shown so the crowding is visible rather than argued about. Three elements on '
      + 'one row at 390px wraps to three stacked rows.',
    html: `<div class="mock-cta-row">
      <a class="mock-cta" href="/contact/">Submit a request</a>
      <a class="mock-cta-2" href="/access">Sign in</a>
      <span class="mock-price">from <b>${FLOOR_TXT}</b></span>
    </div>`,
  },
  {
    id: 'F-duplication-trap',
    title: 'F — the shortcut, shown so it can be rejected on sight',
    note: 'Reuses the closing band\'s exact string "Tell us what you need" and its exact '
      + 'destination. One page, one sentence, twice - the same defect the brand-badge '
      + 'removal reasoned its way out of. Included as evidence, not as a candidate.',
    html: `<div class="mock-cta-row">
      <a class="mock-cta" href="/contact/">Tell us what you need</a>
    </div>`,
  },
];

const VIEWPORTS = [
  { name: 'desktop-1280x900', width: 1280, height: 900 },
  { name: 'phone-390x844', width: 390, height: 844 },
];

const apply = ( css, html ) => {
  const s = document.createElement( 'style' );
  s.textContent = css;
  document.head.appendChild( s );
  if ( !html ) return;
  const hero = document.querySelector( '.home-hero' );
  const sub = document.querySelector( '.home-sub' );
  if ( !hero || !sub ) throw new Error( 'hero or sub-line not found' );
  const wrap = document.createElement( 'div' );
  wrap.innerHTML = html.trim();
  hero.appendChild( wrap.firstElementChild );
};

const measure = () => {
  const vh = window.innerHeight;
  const h1 = document.querySelector( '.home-head' );
  const hero = document.querySelector( '.home-hero' );
  const sub = document.querySelector( '.home-sub' );
  const flow = document.querySelector( '.home-flow' );
  const cta = document.querySelector( '.mock-cta' );
  const r = el => ( el ? el.getBoundingClientRect() : null );
  const box = r( cta );
  return {
    h1Height: Math.round( r( h1 ).height ),
    heroHeight: Math.round( r( hero ).height ),
    subBottom: Math.round( r( sub ).bottom ),
    flowTop: flow ? Math.round( r( flow ).top ) : null,
    ctaHeight: box ? Math.round( box.height ) : null,
    ctaTop: box ? Math.round( box.top ) : null,
    ctaBottom: box ? Math.round( box.bottom ) : null,
    ctaAboveFold: box ? box.bottom <= vh : null,
    fold: vh,
  };
};

( async () => {
  fs.mkdirSync( OUT, { recursive: true } );
  const t = await target();
  const browser = await launch();
  const url = `${t.base}/`;
  const rows = [];

  try {
    console.log( `homemock - ${t.base}/  ->  ${path.relative( process.cwd(), OUT )}` );
    console.log( `catalogue: ${items.length} products, floor ${FLOOR_TXT}\n` );

    for ( const v of VARIANTS ) {
      for ( const vp of VIEWPORTS ) {
        const ctx = await browser.newContext( {
          viewport: { width: vp.width, height: vp.height },
          deviceScaleFactor: 2,
        } );
        const page = await ctx.newPage();
        await gotoStable( page, url );
        await page.evaluate( ( [ css, html ] ) => {
          const s = document.createElement( 'style' );
          s.textContent = css;
          document.head.appendChild( s );
          if ( !html ) return;
          const hero = document.querySelector( '.home-hero' );
          const wrap = document.createElement( 'div' );
          wrap.innerHTML = html.trim();
          hero.appendChild( wrap.firstElementChild );
        }, [ CSS, v.html ] );
        await page.waitForTimeout( 1200 );

        const m = await page.evaluate( measure );
        const file = `${v.id}__${vp.name}.png`;
        await page.screenshot( { path: path.join( OUT, file ) } );

        // Tab order, so focus position is reviewed alongside the picture.
        const stops = [];
        for ( let i = 0; i < 5; i++ ) {
          await page.keyboard.press( 'Tab' );
          stops.push( await page.evaluate( () => {
            const el = document.activeElement;
            if ( !el || el === document.body ) return '(body)';
            const cls = ( el.className || '' ).toString().split( /\s+/ )
              .filter( c => !c.startsWith( 'jsx-' ) ).join( '.' );
            const invisible = +getComputedStyle( el ).opacity === 0;
            return `${el.tagName.toLowerCase()}${cls ? '.' + cls : ''}`
              + `${invisible ? '(invisible)' : ''}`;
          } ) );
        }

        rows.push( { variant: v.id, vp: vp.name, ...m, tab: stops } );
        console.log(
          `  ${file.padEnd( 44 )} h1 ${m.h1Height}px  hero ${m.heroHeight}px  `
          + `flowTop ${m.flowTop}  ${m.ctaHeight ? `cta ${m.ctaHeight}px @${m.ctaTop} aboveFold=${m.ctaAboveFold}` : 'no cta'}`
        );
        await ctx.close();
      }
    }

    // ---- the two defect "before" shots, so the fixes have a picture too ----
    {
      const ctx = await browser.newContext( {
        viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, javaScriptEnabled: false,
      } );
      const page = await ctx.newPage();
      await page.goto( url, { waitUntil: 'load' } );
      await page.waitForTimeout( 500 );
      await page.screenshot( { path: path.join( OUT, 'defect-H2__js-disabled-1280x900.png' ) } );
      console.log( '  defect-H2__js-disabled-1280x900.png            the h1 with no JS' );
      await ctx.close();
    }
    {
      const ctx = await browser.newContext( {
        viewport: { width: 480, height: 900 }, deviceScaleFactor: 2, reducedMotion: 'reduce',
      } );
      const page = await ctx.newPage();
      await gotoStable( page, url );
      await page.waitForTimeout( 800 );
      await page.setViewportSize( { width: 1280, height: 900 } );
      await page.waitForTimeout( 800 );
      await page.screenshot( { path: path.join( OUT, 'defect-H3__reduced-motion-resize-clip-1280x900.png' ) } );
      console.log( '  defect-H3__reduced-motion-resize-clip-...png   the clipped word' );
      await ctx.close();
    }

    fs.writeFileSync( path.join( OUT, 'measurements.json' ), JSON.stringify( { floor: FLOOR, rows }, null, 2 ) );
    console.log( `\n${rows.length} renders + 2 defect shots -> ${path.relative( process.cwd(), OUT )}` );
  } finally {
    await browser.close();
    if ( t.close ) await t.close();
  }
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
