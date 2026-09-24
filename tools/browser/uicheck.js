'use strict';

/**
 * uicheck - the header lockup, and the pair of floating widgets.
 *
 * THREE THINGS THAT ONLY RENDERED GEOMETRY CAN ANSWER.
 *
 * 1. THE BRAND LOCKUP. The logo is an <img> with a fixed height; the wordmark beside it
 *    is two lines whose height is font-size x line-height x 2. Two unrelated formulas,
 *    so they agree only by coincidence. The delta is REPORTED, not asserted - the logo
 *    being slightly taller than the wordmark is normal lockup practice and is currently
 *    a deliberate choice. What IS asserted is that the wordmark is optically centred
 *    against the logo, because an off-centre lockup is a defect under any sizing.
 *
 * 2. THE TWO FLOATING WIDGETS, which live in different places entirely:
 *      .wc-langbar        this repo, src/components/LanguageBar.tsx
 *      #wecarewa-widget   NOT in this repo - injected by wecare-wa-widget.js, served
 *                         from app.wecare.digital, loaded via next/script lazyOnload
 *    Neither file can see the other, so "are they the same size and lined up" is
 *    unanswerable from source. This measures both.
 *
 * 3. THE PANEL MAY NOT OVERLAP THE EXTERNAL BUTTON IN X. That button carries
 *    z-index 2147483647, the maximum 32-bit integer, so nothing can ever be stacked
 *    above it - an overlapping panel gets a WhatsApp circle punched through it. Since
 *    the trigger now deliberately shares the button's column, this is the assertion
 *    that stops that alignment from breaking the panel.
 *
 * WHY NOT THE HOME PAGE. LanguageBar returns null when the path is '/', and also when
 * fewer than two languages load. So on '/' there is exactly one floating widget and
 * nothing to align. This runs against /contact/ instead.
 *
 * THE LANGUAGE API IS STUBBED. LanguageBar fetches api.wecare.digital, which sends no
 * Access-Control-Allow-Origin for 127.0.0.1, so against a local origin the fetch fails,
 * langs stays empty and the component renders NOTHING. Measuring without the stub
 * reports zero widgets, which is indistinguishable from a bug - and an earlier revision
 * of this file quietly skipped the assertion in that case, which is the kind of silent
 * pass this suite exists to prevent. Absence is now a FAILURE.
 *
 *   node tools/browser/uicheck.js
 *   BASE=http://localhost:3000 node tools/browser/uicheck.js
 */

const { launch, gotoStable } = require( './lib/browser' );
const { target } = require( './lib/serve' );

const ROUTE = '/contact/';

/**
 * The external button's geometry, read directly out of wecare-wa-widget.js rather than
 * guessed. Used for two purposes: to stub the widget when the external script does not
 * load, and as a canary - if the real script loads and disagrees with these numbers, the
 * alignment in LanguageBar.tsx was derived from a stale reading and needs redoing.
 */
const WA = {
  desktop: { box: 64, icon: 56, right: 16, bottom: 120 },
  mobile: { box: 60, icon: 52, right: 14, bottom: 80 },
  breakpoint: 767,
};

const VIEWPORTS = [
  { width: 1440, height: 900, label: 'desktop 1440', wa: WA.desktop },
  { width: 1024, height: 800, label: 'tablet 1024', wa: WA.desktop },
  { width: 700, height: 900, label: 'narrow 700', wa: WA.mobile },
  { width: 390, height: 844, label: 'phone 390', wa: WA.mobile },
];

const results = [];
let failures = 0;

function record( ok, name, detail ) {
  results.push( { ok, name } );
  if ( !ok ) failures++;
  console.log( `  ${ok ? 'ok  ' : 'FAIL'} ${name}${detail ? ` - ${detail}` : ''}` );
}

/**
 * The exact shapes LanguageBar parses, taken from the component rather than invented:
 * /languages yields `{ languages: [{ code, name }] }` and /voices yields
 * `{ voices: [{ languageCode, additionalLanguageCodes }] }`. An earlier version of this
 * stub returned `{ label, native }` keys, which produced a valid 200 the component then
 * discarded - the widget stayed absent and the harness blamed the page.
 */
const LANGS = [
  { code: 'en', name: 'English' },
  { code: 'hi', name: 'Hindi' },
  { code: 'bn', name: 'Bengali' },
];
const VOICES = [
  { languageCode: 'en-IN', additionalLanguageCodes: [ 'en-US' ] },
  { languageCode: 'hi-IN' },
];

async function stubLanguageApi( page ) {
  await page.route( /api\.wecare\.digital\/site-language\/(languages|voices)/, route => {
    const isVoices = /\/voices/.test( route.request().url() );
    route.fulfill( {
      status: 200,
      contentType: 'application/json',
      headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify( isVoices ? { voices: VOICES } : { languages: LANGS } ),
    } );
  } );
}

/** Ensure the external button exists, stubbing it if its script did not load. */
async function ensureWaWidget( page, geo ) {
  const present = await page.$( '#wecarewa-widget' );
  if ( present ) return 'real';
  await page.evaluate( g => {
    const style = document.createElement( 'style' );
    style.textContent = `
      #wecarewa-widget{position:fixed;right:${g.right}px;bottom:${g.bottom}px;z-index:2147483647;
        width:${g.box}px;height:${g.box}px;display:flex;align-items:center;justify-content:center}
      #wecarewa-widget img{width:${g.icon}px;height:${g.icon}px;display:block}`;
    document.head.appendChild( style );
    const d = document.createElement( 'div' );
    d.id = 'wecarewa-widget';
    d.setAttribute( 'data-stubbed', 'true' );
    const a = document.createElement( 'a' );
    a.href = 'https://wa.me/message/APDM5HUWH26SG1';
    a.setAttribute( 'aria-label', 'Chat with us on WhatsApp' );
    const img = document.createElement( 'img' );
    // 1x1 transparent gif, so nothing is fetched over the network.
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    a.appendChild( img ); d.appendChild( a ); document.body.appendChild( d );
  }, geo );
  return 'stubbed';
}

async function measureLockup( page ) {
  return page.evaluate( () => {
    const lockup = document.querySelector( '.brand-lockup' );
    if ( !lockup ) return { error: 'no .brand-lockup' };
    const img = lockup.querySelector( 'img' );
    const copy = lockup.querySelector( '.brand-copy' );
    if ( !img || !copy ) return { error: `missing parts (img=${!!img} copy=${!!copy})` };
    const r = el => { const b = el.getBoundingClientRect(); return {
      top: Math.round( b.top * 100 ) / 100, bottom: Math.round( b.bottom * 100 ) / 100,
      h: Math.round( b.height * 100 ) / 100, w: Math.round( b.width * 100 ) / 100 }; };
    const i = r( img ), c = r( copy );
    return {
      img: i, copy: c,
      fontSize: getComputedStyle( copy.firstElementChild ).fontSize,
      delta: Math.round( ( i.h - c.h ) * 100 ) / 100,
      // Space above and below the wordmark relative to the logo box. Equal = centred.
      spaceAbove: Math.round( ( c.top - i.top ) * 100 ) / 100,
      spaceBelow: Math.round( ( i.bottom - c.bottom ) * 100 ) / 100,
    };
  } );
}

/** Visible circle of each widget, plus the panel box once opened. */
async function measureWidgets( page ) {
  return page.evaluate( () => {
    const vw = window.innerWidth, vh = window.innerHeight;
    const box = el => { const b = el.getBoundingClientRect(); return {
      w: Math.round( b.width ), h: Math.round( b.height ),
      left: Math.round( b.left ), right: Math.round( b.right ),
      fromRight: Math.round( vw - b.right ), fromBottom: Math.round( vh - b.bottom ),
      centerX: Math.round( b.left + b.width / 2 ),
      centerXFromRight: Math.round( vw - ( b.left + b.width / 2 ) ),
      top: Math.round( b.top ), bottomEdge: Math.round( b.bottom ),
    }; };

    const trigger = document.querySelector( '.language-trigger' );
    const waWrap = document.querySelector( '#wecarewa-widget' );
    const waIcon = waWrap && waWrap.querySelector( 'img' );
    const panel = document.querySelector( '.wc-langbar .panel' );

    return {
      trigger: trigger ? box( trigger ) : null,
      waIcon: waIcon ? box( waIcon ) : null,
      waWrap: waWrap ? box( waWrap ) : null,
      panel: panel ? box( panel ) : null,
      stubbed: waWrap ? waWrap.getAttribute( 'data-stubbed' ) === 'true' : null,
    };
  } );
}

async function main() {
  const t = await target();
  const browser = await launch();
  console.log( `uicheck - ${t.mode === 'BASE' ? `BASE ${t.base}` : `static export (out/) on ${t.base}`}` );
  console.log( `route ${ROUTE} (LanguageBar returns null on '/', so the pair cannot be measured there)\n` );

  try {
    for ( const vp of VIEWPORTS ) {
      const context = await browser.newContext( { viewport: { width: vp.width, height: vp.height } } );
      const page = await context.newPage();
      await stubLanguageApi( page );
      await gotoStable( page, t.base + ROUTE );

      console.log( `${vp.label}` );

      const lk = await measureLockup( page );
      if ( lk.error ) {
        record( false, `${vp.label}: lockup measurable`, lk.error );
      } else {
        console.log( `  lockup: logo ${lk.img.w}x${lk.img.h}, wordmark ${lk.copy.w}x${lk.copy.h} @${lk.fontSize} -> logo taller by ${lk.delta}px (reported, not a failure)` );
        record( Math.abs( lk.spaceAbove - lk.spaceBelow ) <= 0.5,
          `${vp.label}: wordmark optically centred against the logo`,
          `${lk.spaceAbove}px above / ${lk.spaceBelow}px below` );
      }

      // The trigger is client-rendered after the (stubbed) fetch resolves.
      let haveTrigger = true;
      try {
        await page.waitForSelector( '.language-trigger', { timeout: 15000 } );
      } catch {
        haveTrigger = false;
        record( false, `${vp.label}: language widget rendered`,
          'no .language-trigger - the API stub did not satisfy LanguageBar, or fewer than 2 languages parsed' );
      }

      if ( haveTrigger ) {
        const source = await ensureWaWidget( page, vp.wa );
        await page.waitForTimeout( 200 );
        const m = await measureWidgets( page );

        if ( source === 'stubbed' ) {
          console.log( `  (external #wecarewa-widget did not load here; stubbed from wecare-wa-widget.js geometry: ${vp.wa.box}px box / ${vp.wa.icon}px icon at right:${vp.wa.right} bottom:${vp.wa.bottom})` );
        } else {
          // Canary: the real script loaded, so check it still matches what the CSS assumed.
          record( m.waIcon.w === vp.wa.icon,
            `${vp.label}: external button still ${vp.wa.icon}px as LanguageBar assumes`,
            `measured ${m.waIcon.w}px - if this changed, redo the offsets in LanguageBar.tsx` );
        }

        console.log( `  lang trigger  ${m.trigger.w}x${m.trigger.h}  centre ${m.trigger.centerXFromRight}px from right  bottom ${m.trigger.fromBottom}px` );
        console.log( `  wa icon       ${m.waIcon.w}x${m.waIcon.h}  centre ${m.waIcon.centerXFromRight}px from right  bottom ${m.waIcon.fromBottom}px` );

        record( m.trigger.w === m.waIcon.w && m.trigger.h === m.waIcon.h,
          `${vp.label}: both widgets are the same visible size`,
          `${m.trigger.w}x${m.trigger.h} vs ${m.waIcon.w}x${m.waIcon.h}` );

        record( m.trigger.centerXFromRight === m.waIcon.centerXFromRight,
          `${vp.label}: both widgets share a vertical centre line`,
          `${m.trigger.centerXFromRight}px vs ${m.waIcon.centerXFromRight}px from the right edge` );

        // Gap between the two circles, measured on whichever sits higher.
        const gap = m.trigger.top > m.waIcon.bottomEdge
          ? m.trigger.top - m.waIcon.bottomEdge
          : m.waIcon.top - m.trigger.bottomEdge;
        record( gap >= 12 && gap <= 20, `${vp.label}: even gap between the two circles`, `${gap}px` );

        // Open the panel and prove it cannot collide with the un-coverable button.
        await page.click( '.language-trigger' );
        await page.waitForTimeout( 300 );
        const open = await measureWidgets( page );
        if ( !open.panel ) {
          record( false, `${vp.label}: panel measurable when open`, 'no .panel found' );
        } else {
          const xOverlap = Math.min( open.panel.right, open.waWrap.right ) - Math.max( open.panel.left, open.waWrap.left );
          console.log( `  panel ${open.panel.w}px wide, right edge ${open.panel.fromRight}px from viewport; wa box x ${open.waWrap.left}..${open.waWrap.right}` );
          record( xOverlap <= 0,
            `${vp.label}: open panel clears the external button in x (it cannot be covered)`,
            xOverlap <= 0 ? `${Math.abs( xOverlap )}px clearance` : `OVERLAPS by ${xOverlap}px - the WhatsApp circle will punch through` );
          record( open.panel.left >= 8, `${vp.label}: open panel stays on screen`, `left edge at ${open.panel.left}px` );
        }
      }

      await context.close();
      console.log( '' );
    }
  } finally {
    await browser.close();
    await t.close();
  }

  console.log( `${results.length - failures}/${results.length} assertions passed` );
  if ( failures ) { console.log( `${failures} FAILED` ); process.exit( 1 ); }
}

main().catch( err => { console.error( err ); process.exit( 1 ); } );
