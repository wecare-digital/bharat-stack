'use strict';

/**
 * Verification harness for docs/mocks/vayulok-app-mock.html.
 *
 * This is a TASK ARTIFACT, not part of the mock and not part of the site build.
 *
 * It proves the one thing that matters most about that file: it makes ZERO network
 * requests. Grep alone cannot prove that — a URL can be assembled at runtime, and a
 * value present in source can be overridden — so the real gate is an OFFLINE browser
 * context that records every request the page attempts. A `file://` navigation records
 * exactly one request (the document itself); any <script src>, remote font or remote
 * image would show up as a second request or as a `requestfailed`.
 *
 * The static grep gate is kept as a second, independent check, because it catches a
 * key or a URL sitting in a comment where the browser would never fetch it.
 *
 * CHROMIUM IS RESOLVED THROUGH tools/browser/lib/browser.js AND NEVER HARDCODED.
 * That module scans for the installed revision; a pinned path dies on the next
 * sandbox reset, which is the failure it exists to prevent.
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { launch, gotoStable, resolveChrome } = require(
  '/projects/sandbox/wecare-digital/tools/browser/lib/browser.js'
);

const REPO = '/projects/sandbox/wecare-digital';
const MOCK = path.join( REPO, 'docs/mocks/vayulok-app-mock.html' );
const FILE_URL = 'file://' + MOCK;

const VIEWPORTS = [
  { label: '1280', width: 1280, height: 900, png: 'docs/mocks/vayulok-app-mock-1280.png' },
  { label: '390', width: 390, height: 844, png: 'docs/mocks/vayulok-app-mock-390.png' },
];

const failures = [];
function check( name, ok, detail ) {
  if ( ok ) {
    console.log( `  PASS  ${name}${detail ? ' — ' + detail : ''}` );
  } else {
    console.log( `  FAIL  ${name}${detail ? ' — ' + detail : ''}` );
    failures.push( name + ( detail ? ': ' + detail : '' ) );
  }
}

/* ------------------------------------------------------------------ static gate */

function staticGate() {
  console.log( '\n== STATIC GATE (source grep) ==' );
  const src = fs.readFileSync( MOCK, 'utf8' );

  // Anything here is either a live key, a remote resource, or a way to fetch one.
  const forbidden = [
    'AIzaSy', 'googleapis', 'fonts.g', 'http://', 'https://', 'google-maps-key',
    '<script src', 'fetch(', 'XMLHttpRequest', '@font-face', 'setInterval', 'setTimeout',
  ];
  for ( const needle of forbidden ) {
    const n = src.split( needle ).length - 1;
    check( `no occurrence of ${JSON.stringify( needle )}`, n === 0, `found ${n}` );
  }

  // Drifted token values that must never come back.
  for ( const drift of [ 'd0f070', '183828' ] ) {
    const n = src.split( drift ).length - 1;
    check( `no drifted token ${drift}`, n === 0, `found ${n}` );
  }

  // The real tokens must actually be present.
  for ( const token of [ 'd1f470', '1a3a2a' ] ) {
    const n = src.split( token ).length - 1;
    check( `brand token ${token} present`, n >= 1, `found ${n}` );
  }

  // D5: no xmlns anywhere, because its value would be a URL.
  const xmlns = src.split( 'xmlns' ).length - 1;
  check( 'no xmlns attribute on any svg', xmlns === 0, `found ${xmlns}` );
}

/* ---------------------------------------------------------------- browser gate */

async function run() {
  const chrome = resolveChrome();
  console.log( `Chromium: ${chrome}` );
  staticGate();

  const browser = await launch();
  let totalRequests = 0;

  try {
    for ( const vp of VIEWPORTS ) {
      console.log( `\n== BROWSER GATE @ ${vp.label} (${vp.width}x${vp.height}) ==` );

      const context = await browser.newContext( {
        offline: true,
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 1,
      } );

      const requests = [];
      const requestFailed = [];
      context.on( 'request', r => requests.push( r.url() ) );
      context.on( 'requestfailed', r => requestFailed.push( r.url() ) );

      const page = await context.newPage();
      const consoleErrors = [];
      const pageErrors = [];
      page.on( 'console', m => { if ( m.type() === 'error' ) consoleErrors.push( m.text() ); } );
      page.on( 'pageerror', e => pageErrors.push( String( e && e.message || e ) ) );

      await gotoStable( page, FILE_URL );

      /* --- the headline assertion: zero network ------------------------------- */
      totalRequests += requests.length;
      check(
        `exactly one request (the document itself), i.e. ZERO network requests`,
        requests.length === 1 && requests[ 0 ] === FILE_URL,
        `${requests.length} request(s): ${JSON.stringify( requests )}`
      );
      check( 'no failed requests', requestFailed.length === 0, JSON.stringify( requestFailed ) );

      /* --- no console errors -------------------------------------------------- */
      check( 'no console errors', consoleErrors.length === 0, JSON.stringify( consoleErrors ) );
      check( 'no page errors', pageErrors.length === 0, JSON.stringify( pageErrors ) );

      /* --- rendered tokens, not source strings -------------------------------- */
      const styles = await page.evaluate( () => {
        const cs = sel => {
          const el = document.querySelector( sel );
          return el ? getComputedStyle( el ) : null;
        };
        const tab = cs( '#vk-tab-air' );
        const layer = cs( '#vk-layer-aqi' );
        const best = cs( '#vk-best-outside' );
        const adv = cs( '#vk-advisory' );
        const dot = cs( '#vk-aqi-dot' );
        const panel = cs( '.vk-panel' );
        return {
          tabBg: tab && tab.backgroundColor, tabFg: tab && tab.color,
          layerBg: layer && layer.backgroundColor, layerFg: layer && layer.color,
          bestBg: best && best.backgroundColor,
          advBg: adv && adv.backgroundColor,
          dotBg: dot && dot.backgroundColor,
          font: panel && panel.fontFamily,
        };
      } );

      check( 'active tab fills lime #d1f470', styles.tabBg === 'rgb(209, 244, 112)', styles.tabBg );
      check( 'active tab type is green #1a3a2a', styles.tabFg === 'rgb(26, 58, 42)', styles.tabFg );
      check( 'pressed layer button fills lime', styles.layerBg === 'rgb(209, 244, 112)', styles.layerBg );
      check( 'pressed layer button type is green', styles.layerFg === 'rgb(26, 58, 42)', styles.layerFg );
      check( '"Best outside" card is green #1a3a2a', styles.bestBg === 'rgb(26, 58, 42)', styles.bestBg );
      check( 'advisory ground is the pale lime .22', styles.advBg === 'rgba(209, 244, 112, 0.22)', styles.advBg );
      check( 'AQI dot is amber #f0a818', styles.dotBg === 'rgb(240, 168, 24)', styles.dotBg );
      check( 'font stack begins Inter', /^Inter/.test( styles.font || '' ), styles.font );

      /* --- layout ------------------------------------------------------------- */
      const layout = await page.evaluate( () => {
        const r = sel => document.querySelector( sel ).getBoundingClientRect();
        const el = sel => document.querySelector( sel );
        return {
          innerHeight: window.innerHeight,
          scrollHeight: document.scrollingElement.scrollHeight,
          panelRect: { top: r( '.vk-panel' ).top, width: r( '.vk-panel' ).width },
          stageRect: { top: r( '.vk-stage' ).top, height: r( '.vk-stage' ).height },
          panelScrolls: el( '.vk-panel' ).scrollHeight > el( '.vk-panel' ).clientHeight,
          factRailScrolls: el( '#vk-fact-rail' ).scrollWidth > el( '#vk-fact-rail' ).clientWidth,
          hourRailScrolls: el( '#vk-hour-rail' ).scrollWidth > el( '#vk-hour-rail' ).clientWidth,
        };
      } );

      check(
        'page itself does not scroll (shell is 100dvh)',
        Math.abs( layout.scrollHeight - layout.innerHeight ) <= 2,
        `scrollHeight ${layout.scrollHeight} vs innerHeight ${layout.innerHeight}`
      );
      check( 'left panel scrolls internally', layout.panelScrolls === true );
      check( 'fact rail scrolls horizontally', layout.factRailScrolls === true );
      check( 'hour rail scrolls horizontally', layout.hourRailScrolls === true );

      /* --- stage overlays: visible, inside the stage, and not colliding -----
         The first 390 render had the attribution block clipped off the top of
         the stage and the legend buried under the preview card, which the
         token and scroll assertions above all passed straight through. So
         geometry is asserted directly: every VISIBLE overlay must sit inside
         the stage box, and no two may intersect by more than a hairline. */
      const overlays = await page.evaluate( () => {
        const sels = [ '.vk-layers', '.vk-map-cap', '.vk-legend', '.vk-attrib', '.vk-preview' ];
        const stage = document.querySelector( '.vk-stage' ).getBoundingClientRect();
        const items = sels.map( s => {
          const el = document.querySelector( s );
          const cs = getComputedStyle( el );
          const r = el.getBoundingClientRect();
          return {
            sel: s,
            visible: cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0,
            top: r.top, bottom: r.bottom, left: r.left, right: r.right,
          };
        } );
        const foot = document.querySelector( '#vk-panel-foot' );
        const footCs = getComputedStyle( foot );
        return {
          stage,
          items,
          footVisible: footCs.display !== 'none' && foot.getBoundingClientRect().height > 0,
        };
      } );

      const visible = overlays.items.filter( o => o.visible );
      const outside = visible.filter( o =>
        o.top < overlays.stage.top - 1 || o.bottom > overlays.stage.bottom + 1
        || o.left < overlays.stage.left - 1 || o.right > overlays.stage.right + 1
      );
      check(
        'every visible stage overlay sits inside the stage (nothing clipped)',
        outside.length === 0,
        outside.map( o => o.sel ).join( ', ' )
      );

      const collisions = [];
      for ( let i = 0; i < visible.length; i++ ) {
        for ( let j = i + 1; j < visible.length; j++ ) {
          const a = visible[ i ], b = visible[ j ];
          const ox = Math.min( a.right, b.right ) - Math.max( a.left, b.left );
          const oy = Math.min( a.bottom, b.bottom ) - Math.max( a.top, b.top );
          if ( ox > 1 && oy > 1 ) collisions.push( `${a.sel} x ${b.sel}` );
        }
      }
      check( 'no two stage overlays overlap', collisions.length === 0, collisions.join( ', ' ) );

      // Attribution must be reachable at EVERY width. At 390 the stage block is
      // suppressed by design, so the panel foot is what carries it there.
      check( 'panel-foot attribution is present and visible', overlays.footVisible === true );
      if ( vp.label === '390' ) {
        check(
          'stage attribution is suppressed at 390 (panel foot carries it)',
          overlays.items.find( o => o.sel === '.vk-attrib' ).visible === false
        );
      } else {
        check(
          'stage attribution is visible at 1280',
          overlays.items.find( o => o.sel === '.vk-attrib' ).visible === true
        );
      }

      if ( vp.label === '1280' ) {
        check(
          'panel width within minmax(405,455)',
          layout.panelRect.width >= 405 && layout.panelRect.width <= 455,
          `${layout.panelRect.width}px`
        );
      } else {
        check(
          'map stage stacks above the panel',
          layout.stageRect.top < layout.panelRect.top,
          `stage ${layout.stageRect.top} < panel ${layout.panelRect.top}`
        );
        const ratio = layout.stageRect.height / layout.innerHeight;
        check(
          'map stage is ~42% of viewport height',
          Math.abs( ratio - 0.42 ) <= 0.03,
          `${( ratio * 100 ).toFixed( 1 )}%`
        );
      }

      /* --- behaviour: the two toggles ---------------------------------------- */
      if ( vp.label === '1280' ) {
        await page.click( '#vk-tab-weather' );
        const afterTab = await page.evaluate( () => ( {
          airHidden: document.getElementById( 'vk-panel-air' ).hidden,
          weatherHidden: document.getElementById( 'vk-panel-weather' ).hidden,
          airSel: document.getElementById( 'vk-tab-air' ).getAttribute( 'aria-selected' ),
          weatherSel: document.getElementById( 'vk-tab-weather' ).getAttribute( 'aria-selected' ),
          weatherBg: getComputedStyle( document.getElementById( 'vk-tab-weather' ) ).backgroundColor,
        } ) );
        check(
          'tab toggle swaps panels and aria-selected',
          afterTab.airHidden === true && afterTab.weatherHidden === false
            && afterTab.airSel === 'false' && afterTab.weatherSel === 'true'
            && afterTab.weatherBg === 'rgb(209, 244, 112)',
          JSON.stringify( afterTab )
        );

        await page.click( '#vk-layer-pm' );
        const afterLayer = await page.evaluate( () => ( {
          pmPressed: document.getElementById( 'vk-layer-pm' ).getAttribute( 'aria-pressed' ),
          aqiPressed: document.getElementById( 'vk-layer-aqi' ).getAttribute( 'aria-pressed' ),
          pmBg: getComputedStyle( document.getElementById( 'vk-layer-pm' ) ).backgroundColor,
        } ) );
        check(
          'layer toggle swaps aria-pressed and the lime fill',
          afterLayer.pmPressed === 'true' && afterLayer.aqiPressed === 'false'
            && afterLayer.pmBg === 'rgb(209, 244, 112)',
          JSON.stringify( afterLayer )
        );

        // Restore the specified default state BEFORE screenshotting, so the
        // committed PNG shows Air active and AQI pressed.
        await page.click( '#vk-tab-air' );
        await page.click( '#vk-layer-aqi' );
        const restored = await page.evaluate( () => ( {
          airSel: document.getElementById( 'vk-tab-air' ).getAttribute( 'aria-selected' ),
          aqiPressed: document.getElementById( 'vk-layer-aqi' ).getAttribute( 'aria-pressed' ),
        } ) );
        check(
          'default state restored before screenshot',
          restored.airSel === 'true' && restored.aqiPressed === 'true',
          JSON.stringify( restored )
        );
      }

      /* Clicking a tab scrolls it into view, which left the first 1280 capture
         starting halfway down the panel. Reset so the committed PNG opens on
         the place section the way the file does. */
      const panelScrollTop = await page.evaluate( () => {
        const p = document.querySelector( '.vk-panel' );
        p.scrollTop = 0;
        return p.scrollTop;
      } );
      check( 'panel reset to the top before screenshot', panelScrollTop === 0, String( panelScrollTop ) );

      /* The pollutant bars are spans inside spans, and an inline box ignores
         width — they rendered at zero width while every colour assertion
         passed. Measure that they actually paint. */
      const bars = await page.evaluate( () => {
        const widths = [ ...document.querySelectorAll( '#vk-panel-air .vk-bar' ) ]
          .map( el => el.getBoundingClientRect().width );
        const chart = [ ...document.querySelectorAll( '#vk-chart span' ) ]
          .map( el => el.getBoundingClientRect().height );
        return { widths, minWidth: Math.min( ...widths ), chartMin: Math.min( ...chart ), bars: widths.length, chartBars: chart.length };
      } );
      check( 'six pollutant bars, all painting a non-zero width',
        bars.bars === 6 && bars.minWidth > 0, JSON.stringify( bars.widths.map( w => Math.round( w ) ) ) );
      check( 'twenty-four history bars, all painting a non-zero height',
        bars.chartBars === 24 && bars.chartMin > 0, `min ${bars.chartMin.toFixed( 1 )}px` );

      /* --- screenshot --------------------------------------------------------- */
      const out = path.join( REPO, vp.png );
      await page.screenshot( { path: out, fullPage: true } );
      const size = fs.statSync( out ).size;
      check( `screenshot written ${vp.png}`, size > 0, `${size} bytes` );

      // Re-assert after everything, including the clicks: still no network.
      check(
        'still zero network requests after interaction',
        requests.length === 1,
        `${requests.length} request(s)`
      );

      await context.close();
    }
  } finally {
    await browser.close();
  }

  console.log( `\nTOTAL REQUESTS RECORDED ACROSS BOTH VIEWPORTS: ${totalRequests} (both are the file:// document itself)` );

  if ( failures.length ) {
    console.error( `\nFAILED (${failures.length}):` );
    failures.forEach( f => console.error( '  - ' + f ) );
    process.exit( 1 );
  }
  console.log( '\nPASS — zero network requests, no console errors, tokens and layout verified.' );
}

run().catch( err => {
  console.error( '\nHARNESS ERROR:', err && err.stack || err );
  process.exit( 1 );
} );
