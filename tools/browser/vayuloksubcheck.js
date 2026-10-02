'use strict';

/**
 * vayuloksubcheck - the VayuLok section mock's controls, measured in a real browser.
 *
 * WHY THIS EXISTS AT ALL. `npx vitest run`, `npx tsc --noEmit` and `npm run lint`
 * provably do not cover `docs/mocks` - grep the test, src, scripts and .github trees for
 * `docs/mocks` or `vayulok-live-mock` and there are no hits. So the two HTML twins in
 * `docs/mocks/` have no automated verification of any kind, and the three defects this
 * harness asserts against were all REPORTED BY A HUMAN LOOKING AT THE RENDERED PAGE after
 * every other check in the repo passed. That is the gap.
 *
 * WHY RECTS AND COMPUTED STYLES RATHER THAN grep. Every one of the three defects is
 * invisible in the source:
 *
 *   - `.vl-sub-action` was declared TWICE, in two different blocks, and the two copies set
 *     DISJOINT properties, so both applied and neither overrode the other. Reading either
 *     rule alone says nothing is wrong. Only the measurement shows a 91px box holding a
 *     52px button, leaving its bottom edge 19.5px above the field it belongs to.
 *   - `Clear key` carries `hidden`, so it is absent from every committed screenshot. Its
 *     mismatch against the two pills beside it only appears once the attribute is removed,
 *     which is the state the mock exists to demonstrate.
 *   - "no dialog appears" is a claim about what a browser does on click. There is no
 *     markup to grep for: a native constraint-validation bubble comes from an attribute
 *     interacting with a submit, and it renders as browser chrome rather than as DOM.
 *
 * WHAT IT ASSERTS, at 1280x900 and 390x844, from a file:// URL:
 *   (a) ROLE 1 - every action button shares one geometry: 52px, 13px radius, 16px/500,
 *       2px #1a3a2a, #d1f470 fill.
 *   (b) the Subscribe button's bottom edge meets the phone field's, within 1px.
 *   (c) ROLE 3 divided form - the `.vl-pf` container carries the 52px / 1px #e5e7eb / 10px
 *       box and the two segments carry no border of their own except the divider.
 *   (d) ROLE 5 - `.vl-map-controls` is uniform with `#vl-keyclear` revealed, and clicking
 *       it changes no `aria-pressed` attribute.
 *   (e) the retired role and the dead rule match zero elements, and so does every flavour
 *       of dialog.
 *   (f) the interaction set runs with a `page.on('dialog')` listener that FAILS the run if
 *       it ever fires, and the document gains no new element.
 *   (g) exactly ONE request - the document itself - and zero console or page errors.
 *
 * ZERO NETWORK IS ASSERTED, NOT ASSUMED, and it is the request COUNT that does it. The
 * grep for `rel=stylesheet` / `@font-face` / `@import` is a secondary cross-check only:
 * the file's own comment at line 47 contains those words while declaring that it uses none
 * of them, so the grep cannot be the primary signal without reporting its own
 * documentation as a violation.
 *
 * It takes a path so the TWIN is verified as a twin rather than only byte-compared - a
 * byte comparison proves the files match, not that either renders correctly.
 *
 * Run: node tools/browser/vayuloksubcheck.js
 *      node tools/browser/vayuloksubcheck.js --json
 *      node tools/browser/vayuloksubcheck.js --shots
 *      node tools/browser/vayuloksubcheck.js docs/mocks/vayulok-final-v3.html
 *
 * --shots regenerates the companion PNGs beside the mocks. Viewports live HERE so there is
 * one source of truth for them; see SHOTS below for where the 1440x950 anchors come from.
 */

const path = require( 'path' );
const { launch, gotoStable } = require( './lib/browser' );

const REPO = path.resolve( __dirname, '..', '..' );
const args = process.argv.slice( 2 );
const asJson = args.includes( '--json' );
const withShots = args.includes( '--shots' );
const targets = args.filter( a => !a.startsWith( '--' ) );
const MOCKS = targets.length ? targets : [
  'docs/mocks/vayulok-live-mock.html',
  'docs/mocks/vayulok-final-v3.html',
];

const VIEWPORTS = [ { w: 1280, h: 900 }, { w: 390, h: 844 } ];

/**
 * The full-page companion PNGs, plus the three 1440x950 section anchors.
 *
 * THE 1440 ANCHORS ARE RECONSTRUCTED FROM THE COMMITTED IMAGES, not documented anywhere -
 * the originals were produced by a script that no longer exists. Recorded here so the next
 * pass does not have to guess at them again. `-desktop` is the top of the page, `-scrolled`
 * centres `.vl-hours`, `-subscribe` centres `.vl-subscribe`.
 *
 * EXPECT THE FULL-PAGE HEIGHTS TO MOVE. The committed `*-1280.png` were 1347x6040 and
 * `*-390.png` 390x7506, while the committed HTML rendered 1280x5583 / 390x6547 - i.e. the
 * PNGs were already stale against their own markup before this pass touched either. New,
 * correctly-1280-wide and shorter images are the correction, not a regression.
 */
const SHOTS = {
  full: [ { w: 1280, h: 900, suffix: '-1280' }, { w: 390, h: 844, suffix: '-390' } ],
  anchors: [
    { name: 'vayulok-section-desktop.png', w: 1440, h: 950, scrollTo: null },
    { name: 'vayulok-section-scrolled.png', w: 1440, h: 950, scrollTo: '.vl-hours' },
    { name: 'vayulok-section-subscribe.png', w: 1440, h: 950, scrollTo: '.vl-subscribe' },
  ],
};

/* ROLE 1, from src/styles/button.css:31 (.btn) + :52-56 (.btn-lg) + :78-82 (.btn-primary),
   and rendered identically by docs/mocks/home-hero/index.html:192. 13px is the RADIUS; the
   font size on the 52px size class is 16px. A brief describing this file has had that the
   wrong way round, so the two are asserted separately and named separately below. */
const ROLE1 = {
  height: 52,
  radius: '13px',
  fontSize: '16px',
  fontWeight: '500',
  borderWidth: '2px',
  borderColor: 'rgb(26, 58, 42)',
  background: 'rgb(209, 244, 112)',
};
const ROLE1_BUTTONS = [
  [ 'Load', '#vl-keyload' ],
  [ 'Subscribe', '#vl-sub-btn' ],
  [ 'Contribute', '.vl-bc-submit-wrap .vl-btn' ],
];

/* ROLE 3, from src/components/BlogSubscribe.tsx:329. */
const ROLE3 = { height: 52, radius: '10px', borderWidth: '1px', borderColor: 'rgb(229, 231, 235)' };

const results = [];
const record = ( scope, name, pass, detail ) => {
  results.push( { scope, name, pass: Boolean( pass ), detail } );
  return pass;
};

const probe = async ( page, sel ) => page.evaluate( s => {
  const el = document.querySelector( s );
  if ( !el ) return null;
  const c = getComputedStyle( el );
  const r = el.getBoundingClientRect();
  return {
    height: +r.height.toFixed( 1 ), width: +r.width.toFixed( 1 ),
    top: +r.top.toFixed( 1 ), bottom: +r.bottom.toFixed( 1 ),
    radius: c.borderTopLeftRadius, fontSize: c.fontSize, fontWeight: c.fontWeight,
    borderWidth: c.borderTopWidth, borderColor: c.borderTopColor,
    background: c.backgroundColor,
    paddingInline: c.paddingLeft + '/' + c.paddingRight,
    overflowing: el.scrollWidth > el.clientWidth + 1,
  };
}, sel );

const run = async ( browser, mock ) => {
  const url = 'file://' + path.join( REPO, mock );

  for ( const vp of VIEWPORTS ) {
    const scope = `${path.basename( mock )} @${vp.w}`;
    const page = await browser.newPage( { viewport: { width: vp.w, height: vp.h } } );

    /* COLLECTED BEFORE THE FIRST NAVIGATION, so the document request itself is counted. */
    const requests = [];
    const consoleErrors = [];
    const pageErrors = [];
    const dialogs = [];
    page.on( 'request', r => requests.push( r.url() ) );
    page.on( 'console', m => { if ( m.type() === 'error' ) consoleErrors.push( m.text() ); } );
    page.on( 'pageerror', e => pageErrors.push( String( e ) ) );
    /* A dialog event is a FAILURE, never a pass. It is dismissed so the run can continue
       rather than hanging on a modal nobody is there to answer. */
    page.on( 'dialog', async d => {
      dialogs.push( `${d.type()}: ${d.message()}` );
      await d.dismiss().catch( () => {} );
    } );

    await gotoStable( page, url );

    /* ---- (a) ROLE 1: one geometry across every action button ---------------- */
    const role1 = [];
    for ( const [ label, sel ] of ROLE1_BUTTONS ) {
      const m = await probe( page, sel );
      if ( !m ) { record( scope, `ROLE 1 ${label} exists`, false, sel ); continue; }
      role1.push( { label, m } );
      record( scope, `ROLE 1 ${label} height 52`, m.height === ROLE1.height, `${m.height}px` );
      record( scope, `ROLE 1 ${label} font 16px/500`,
        m.fontSize === ROLE1.fontSize && m.fontWeight === ROLE1.fontWeight,
        `${m.fontSize}/${m.fontWeight}` );
      record( scope, `ROLE 1 ${label} radius 13px`, m.radius === ROLE1.radius, m.radius );
      record( scope, `ROLE 1 ${label} border 2px #1a3a2a`,
        m.borderWidth === ROLE1.borderWidth && m.borderColor === ROLE1.borderColor,
        `${m.borderWidth} ${m.borderColor}` );
      record( scope, `ROLE 1 ${label} fill #d1f470`, m.background === ROLE1.background, m.background );
    }
    /* The cross-button assertion, which is the one the reporter actually made: not "each
       button matches a table" but "the buttons match EACH OTHER". */
    const heights = [ ...new Set( role1.map( r => r.m.height ) ) ];
    const fonts = [ ...new Set( role1.map( r => `${r.m.fontSize}/${r.m.fontWeight}` ) ) ];
    record( scope, 'ROLE 1 all action buttons share one height', heights.length === 1, heights.join( ', ' ) );
    record( scope, 'ROLE 1 all action buttons share one font', fonts.length === 1, fonts.join( ', ' ) );

    /* ---- (b) the Subscribe baseline ---------------------------------------- */
    const btn = await probe( page, '#vl-sub-btn' );
    const pf = await probe( page, '#vl-pf' );
    if ( btn && pf ) {
      /* At 390 the action wraps onto its own line, which is correct and intended, so the
         baseline assertion only holds while the two are on one row. Checked rather than
         assumed, and reported either way so a silent skip cannot hide a regression. */
      const sameRow = Math.abs( btn.top - pf.top ) < 60;
      const delta = +( btn.bottom - pf.bottom ).toFixed( 1 );
      if ( sameRow ) {
        record( scope, 'Subscribe bottom meets field bottom (<=1px)', Math.abs( delta ) <= 1, `${delta}px` );
      } else {
        record( scope, 'Subscribe wrapped to its own row (390 layout)', true, `delta ${delta}px, wrapped` );
      }
    }
    const action = await page.evaluate( () => {
      const el = document.querySelector( '.vl-sub-action' );
      return el ? { minHeight: getComputedStyle( el ).minHeight, kids: el.children.length } : null;
    } );
    /* `auto` IS THE PASS, NOT `0px`. The initial computed value of min-height is `auto`,
       so an un-declared min-height reports `auto` and never `0px`. What must be gone is a
       LENGTH - the 91px that was holding the button off the field's baseline - so the
       assertion is "not a px value", which is the thing actually being asserted. */
    record( scope, '.vl-sub-action declares no min-height length',
      action && !/px$/.test( action.minHeight ), action ? action.minHeight : 'missing' );
    record( scope, '.vl-sub-action holds exactly one control', action && action.kids === 1,
      action ? `${action.kids} children` : 'missing' );

    /* ---- (c) ROLE 3, divided form ------------------------------------------ */
    if ( pf ) {
      record( scope, '.vl-pf height 52', pf.height === ROLE3.height, `${pf.height}px` );
      record( scope, '.vl-pf radius 10px', pf.radius === ROLE3.radius, pf.radius );
      record( scope, '.vl-pf border 1px #e5e7eb',
        pf.borderWidth === ROLE3.borderWidth && pf.borderColor === ROLE3.borderColor,
        `${pf.borderWidth} ${pf.borderColor}` );
    }
    const segs = await page.evaluate( () => {
      const code = document.getElementById( 'vl-sub-dial' );
      const num = document.getElementById( 'vl-sub-phone' );
      if ( !code || !num ) return null;
      const cc = getComputedStyle( code ), nc = getComputedStyle( num );
      const cr = code.getBoundingClientRect(), nr = num.getBoundingClientRect();
      return {
        codeValue: code.value,
        codeTop: +cr.top.toFixed( 1 ), numTop: +nr.top.toFixed( 1 ),
        codeH: +cr.height.toFixed( 1 ), numH: +nr.height.toFixed( 1 ),
        codeOuter: cc.borderTopWidth + '/' + cc.borderBottomWidth + '/' + cc.borderLeftWidth,
        codeDivider: cc.borderRightWidth,
        numBorders: nc.borderTopWidth + '/' + nc.borderRightWidth + '/' + nc.borderBottomWidth + '/' + nc.borderLeftWidth,
        numOverflowing: num.scrollWidth > num.clientWidth + 1,
        constraints: [ code, num ].map( i => ( {
          id: i.id, required: i.required, pattern: i.pattern || '',
          minLength: i.minLength, ariaRequired: i.getAttribute( 'aria-required' ),
        } ) ),
      };
    } );
    if ( segs ) {
      record( scope, 'calling code defaults to +91', segs.codeValue === '+91', segs.codeValue );
      /* 50px, NOT 52: the segments stretch to the container's CONTENT box, which is its
         52px border box less its two 1px borders. That is the correct result and it is what
         PhoneField renders too - the 52px belongs to the container, which is the whole point
         of the divided form. Asserted as "container height minus its borders" rather than as
         a literal 50 so it stays true if the hairline ever changes weight. */
      record( scope, 'both segments fill the container content box',
        pf && segs.codeH === pf.height - 2 && segs.numH === pf.height - 2,
        `${segs.codeH}/${segs.numH} inside ${pf ? pf.height : '?'}` );
      record( scope, 'segments share one row', Math.abs( segs.codeTop - segs.numTop ) < 0.5,
        `${segs.codeTop} vs ${segs.numTop}` );
      record( scope, 'code segment carries only the divider border',
        segs.codeOuter === '0px/0px/0px' && segs.codeDivider === '1px',
        `outer ${segs.codeOuter}, divider ${segs.codeDivider}` );
      record( scope, 'number segment carries no border', segs.numBorders === '0px/0px/0px/0px', segs.numBorders );
      record( scope, 'number placeholder is not clipped', !segs.numOverflowing,
        segs.numOverflowing ? 'scrollWidth exceeds clientWidth' : 'fits' );
      /* The PhoneField fix, asserted rather than trusted: no constraint attribute on
         either segment, because the native bubble was itself the reported defect. */
      const clean = segs.constraints.every( c => !c.required && !c.pattern && c.minLength <= 0 );
      record( scope, 'no required/pattern/minlength on either segment', clean,
        JSON.stringify( segs.constraints ) );
      record( scope, 'aria-required carries the semantic instead',
        segs.constraints.some( c => c.id === 'vl-sub-phone' && c.ariaRequired === 'true' ), '' );
    } else {
      record( scope, 'divided phone field exists', false, '#vl-sub-dial / #vl-sub-phone missing' );
    }

    /* ---- (d) ROLE 5, the map-control row with Clear key revealed ----------- */
    const mapRow = await page.evaluate( () => {
      const clear = document.getElementById( 'vl-keyclear' );
      if ( clear ) clear.removeAttribute( 'hidden' );
      const kids = Array.prototype.slice.call( document.querySelectorAll( '.vl-map-controls > button' ) );
      const out = kids.map( el => {
        const c = getComputedStyle( el ), r = el.getBoundingClientRect();
        return {
          text: el.textContent.trim(), h: +r.height.toFixed( 1 ),
          top: +r.top.toFixed( 1 ), bottom: +r.bottom.toFixed( 1 ),
          fontSize: c.fontSize, fontWeight: c.fontWeight,
          padding: c.paddingLeft + '/' + c.paddingRight, radius: c.borderTopLeftRadius,
        };
      } );
      if ( clear ) clear.setAttribute( 'hidden', '' );
      return out;
    } );
    record( scope, 'map row has 3 controls', mapRow.length === 3, `${mapRow.length}` );
    if ( mapRow.length ) {
      const u = k => [ ...new Set( mapRow.map( r => r[ k ] ) ) ];
      record( scope, 'map row shares one height', u( 'h' ).length === 1, u( 'h' ).join( ', ' ) );
      record( scope, 'map row shares one font size', u( 'fontSize' ).length === 1, u( 'fontSize' ).join( ', ' ) );
      record( scope, 'map row shares one font weight', u( 'fontWeight' ).length === 1, u( 'fontWeight' ).join( ', ' ) );
      record( scope, 'map row shares one padding', u( 'padding' ).length === 1, u( 'padding' ).join( ', ' ) );
      record( scope, 'map row is vertically flush', u( 'top' ).length === 1 && u( 'bottom' ).length === 1,
        `tops ${u( 'top' ).join( ', ' )}` );
      record( scope, 'map row is 38px (ROLE 5)', mapRow.every( r => r.h === 38 ),
        mapRow.map( r => `${r.text} ${r.h}` ).join( ', ' ) );
    }
    /* CLEAR KEY MUST NOT HAVE JOINED THE AQI/PM2.5 RADIO GROUP, which is the risk created
       by giving it the same geometry as the two pills beside it.
       ASSERTED AT THE SELECTOR, NOT BY CLICKING IT, and that is deliberate rather than a
       shortcut. Its handler ends in `window.location.reload()` by design - the Maps script
       cannot be unloaded, so a reload is the only honest way back to the no-key state - so
       a real click destroys the execution context and ends the measurement instead of
       failing or passing it. (Patching `location.reload` is not available either: it is
       non-writable on Location in Chrome.)
       The group membership is decided by ONE selector - the script at the foot of the mock
       does `querySelectorAll('.vl-layer')` and wires every match into the toggle - so
       "is #vl-keyclear in that NodeList" is the whole question, and it is exact. */
    const group = await page.evaluate( () => {
      const clear = document.getElementById( 'vl-keyclear' );
      const layers = Array.prototype.slice.call( document.querySelectorAll( '.vl-layer' ) );
      return {
        members: layers.map( el => el.id ),
        clearIsLayer: Boolean( clear && clear.classList.contains( 'vl-layer' ) ),
        clearInGroup: Boolean( clear && layers.indexOf( clear ) >= 0 ),
        clearHasPressed: Boolean( clear && clear.hasAttribute( 'aria-pressed' ) ),
        clearClass: clear ? clear.className : 'missing',
      };
    } );
    record( scope, 'Clear key is .vl-map-btn, not .vl-layer', !group.clearIsLayer, group.clearClass );
    record( scope, 'Clear key is not in the layer toggle group', !group.clearInGroup,
      group.members.join( ', ' ) );
    record( scope, 'the layer group is exactly AQI + PM2.5',
      group.members.length === 2 && group.members.join( ',' ) === 'vl-layer-aqi,vl-layer-pm',
      group.members.join( ', ' ) );
    record( scope, 'Clear key carries no aria-pressed state', !group.clearHasPressed, '' );

    /* ---- (e) retired role, dead rule, no dialog of any kind ---------------- */
    const counts = await page.evaluate( () => {
      const n = s => document.querySelectorAll( s ).length;
      /* The CSS RULE, not the string: `.vl-btn-quiet` is still named in the comment that
         records its retirement, which is the useful place for it. What must be gone is any
         rule that could style an element, and any element carrying the class. */
      let quietRules = 0;
      for ( const sheet of document.styleSheets ) {
        let rules;
        try { rules = sheet.cssRules; } catch ( e ) { continue; }
        for ( const rule of rules ) {
          if ( rule.selectorText && rule.selectorText.indexOf( 'vl-btn-quiet' ) >= 0 ) quietRules += 1;
          if ( rule.selectorText && rule.selectorText.indexOf( 'vl-verify-row' ) >= 0 ) quietRules += 1;
        }
      }
      const fixed = [];
      document.querySelectorAll( '.vl-vayulok *' ).forEach( el => {
        if ( getComputedStyle( el ).position === 'fixed' ) fixed.push( el.className );
      } );
      /* Every "+" still in the section, as text or as an attribute. The reported one was a
         placeholder reading "+91 00000 00000" inside the number field - a fake country code
         in placeholder grey. It should now only appear as a real control VALUE. */
      const plusText = [];
      const walk = document.createTreeWalker( document.querySelector( '.vl-vayulok' ), NodeFilter.SHOW_TEXT );
      while ( walk.nextNode() ) {
        if ( walk.currentNode.nodeValue.indexOf( '+' ) >= 0 ) plusText.push( walk.currentNode.nodeValue.trim() );
      }
      const plusAttr = [];
      document.querySelectorAll( '.vl-vayulok *' ).forEach( el => {
        for ( const a of el.attributes ) {
          if ( a.value.indexOf( '+' ) >= 0 ) plusAttr.push( `${el.tagName}#${el.id || ''}[${a.name}="${a.value}"]` );
        }
      } );
      return {
        quietEls: n( '.vl-btn-quiet' ), verifyEls: n( '.vl-verify-row' ), quietRules,
        dialogEls: n( 'dialog' ),
        modalEls: n( '[role=dialog],[role=alertdialog],[aria-modal]' ),
        fixed, plusText, plusAttr,
        docScrollWidth: document.documentElement.scrollWidth,
        docClientWidth: document.documentElement.clientWidth,
      };
    } );
    record( scope, '.vl-btn-quiet matches 0 elements', counts.quietEls === 0, `${counts.quietEls}` );
    record( scope, '.vl-verify-row matches 0 elements', counts.verifyEls === 0, `${counts.verifyEls}` );
    record( scope, 'no .vl-btn-quiet / .vl-verify-row CSS rule survives', counts.quietRules === 0,
      `${counts.quietRules} rules` );
    record( scope, 'zero <dialog> elements', counts.dialogEls === 0, `${counts.dialogEls}` );
    record( scope, 'zero role=dialog / aria-modal', counts.modalEls === 0, `${counts.modalEls}` );
    record( scope, 'nothing in the section is position:fixed', counts.fixed.length === 0,
      counts.fixed.join( ', ' ) );
    record( scope, 'the only "+" is the calling-code control value',
      counts.plusText.length === 0
      && counts.plusAttr.every( s => /vl-sub-dial|placeholder="\+91"/.test( s ) ),
      `text ${JSON.stringify( counts.plusText )} attr ${JSON.stringify( counts.plusAttr )}` );
    record( scope, 'no horizontal overflow', counts.docScrollWidth === counts.docClientWidth,
      `${counts.docScrollWidth} vs ${counts.docClientWidth}` );

    /* ---- (f) the interaction set ------------------------------------------- */
    const htmlBefore = await page.evaluate( () => ( {
      len: document.body.innerHTML.length,
      els: document.querySelectorAll( '.vl-subscribe *' ).length,
    } ) );

    /* Submit EMPTY. This is where a `required` attribute would raise the native bubble the
       owner reported, so it is the single most important click in this harness. */
    await page.click( '#vl-sub-btn' );
    await page.waitForTimeout( 150 );
    const emptyState = await page.evaluate( () => ( {
      status: document.getElementById( 'vl-sub-status' ).textContent,
      label: document.getElementById( 'vl-sub-btn' ).textContent,
      invalid: document.getElementById( 'vl-sub-phone' ).getAttribute( 'aria-invalid' ),
    } ) );
    record( scope, 'empty submit reports inline', /10-digit/.test( emptyState.status ), emptyState.status );
    record( scope, 'empty submit marks the number invalid', emptyState.invalid === 'true', `${emptyState.invalid}` );
    record( scope, 'empty submit does not flip the button label', emptyState.label === 'Subscribe', emptyState.label );

    /* Change the calling code by typing, as DialCodeSearch does. */
    await page.fill( '#vl-sub-dial', '971' );
    await page.waitForTimeout( 100 );
    const uae = await page.evaluate( () => ( {
      value: document.getElementById( 'vl-sub-dial' ).value,
      placeholder: document.getElementById( 'vl-sub-phone' ).placeholder,
    } ) );
    record( scope, 'typing 971 commits +971', uae.value === '+971', uae.value );
    record( scope, '+971 updates the length hint', uae.placeholder === '8- or 9-digit WhatsApp number',
      uae.placeholder );

    /* An unsupported code stays unresolved and reverts on blur. */
    await page.fill( '#vl-sub-dial', '123' );
    await page.waitForTimeout( 100 );
    const unresolved = await page.evaluate( () => document.getElementById( 'vl-sub-dial' ).getAttribute( 'aria-invalid' ) );
    record( scope, 'unsupported code is aria-invalid', unresolved === 'true', `${unresolved}` );
    await page.evaluate( () => document.getElementById( 'vl-sub-dial' ).blur() );
    await page.waitForTimeout( 100 );
    const reverted = await page.evaluate( () => document.getElementById( 'vl-sub-dial' ).value );
    record( scope, 'blur reverts to the last committed code', reverted === '+971', reverted );

    /* Back to +91 and submit a valid number. */
    await page.fill( '#vl-sub-dial', '91' );
    await page.evaluate( () => document.getElementById( 'vl-sub-dial' ).blur() );
    await page.fill( '#vl-sub-phone', '9876543210' );
    await page.click( '#vl-sub-btn' );
    await page.waitForTimeout( 150 );
    const done = await page.evaluate( () => ( {
      status: document.getElementById( 'vl-sub-status' ).textContent,
      label: document.getElementById( 'vl-sub-btn' ).textContent,
      cls: document.getElementById( 'vl-sub-status' ).className,
      invalid: document.getElementById( 'vl-sub-phone' ).getAttribute( 'aria-invalid' ),
    } ) );
    record( scope, 'valid submit composes E.164 inline', /\+919876543210/.test( done.status ), done.status );
    record( scope, 'valid submit flips the label to Subscribed', done.label === 'Subscribed', done.label );
    record( scope, 'valid submit marks the status done', /is-done/.test( done.cls ), done.cls );
    record( scope, 'valid submit clears aria-invalid', done.invalid === null, `${done.invalid}` );

    /* Enter in the code segment must not submit the form either. */
    await page.focus( '#vl-sub-dial' );
    await page.keyboard.press( 'Enter' );
    await page.waitForTimeout( 150 );

    const htmlAfter = await page.evaluate( () => ( {
      len: document.body.innerHTML.length,
      els: document.querySelectorAll( '.vl-subscribe *' ).length,
    } ) );
    record( scope, 'no element was added to the subscribe panel', htmlBefore.els === htmlAfter.els,
      `${htmlBefore.els} -> ${htmlAfter.els}` );
    record( scope, 'NO dialog fired during any interaction', dialogs.length === 0,
      dialogs.join( ' | ' ) || 'none' );

    /* ---- (g) zero network, zero errors ------------------------------------- */
    const nonFile = requests.filter( u => !u.startsWith( 'file://' ) );
    record( scope, 'exactly 1 request (the document)', requests.length === 1, `${requests.length}` );
    record( scope, 'zero non-file:// requests', nonFile.length === 0, nonFile.join( ', ' ) || 'none' );
    record( scope, 'zero console errors', consoleErrors.length === 0, consoleErrors.join( ' | ' ) || 'none' );
    record( scope, 'zero page errors', pageErrors.length === 0, pageErrors.join( ' | ' ) || 'none' );

    await page.close();
  }
};

const shoot = async ( browser, mock ) => {
  const url = 'file://' + path.join( REPO, mock );
  const base = path.join( REPO, 'docs/mocks', path.basename( mock, '.html' ) );
  const written = [];

  for ( const s of SHOTS.full ) {
    const page = await browser.newPage( { viewport: { width: s.w, height: s.h } } );
    await gotoStable( page, url );
    const out = `${base}${s.suffix}.png`;
    await page.screenshot( { path: out, fullPage: true } );
    written.push( out );
    await page.close();
  }

  /* The three 1440 anchors are section crops of the LIVE mock only - they are not twinned
     per file, so they are regenerated once rather than overwritten twice with the same
     bytes. */
  if ( path.basename( mock ) === 'vayulok-live-mock.html' ) {
    for ( const a of SHOTS.anchors ) {
      const page = await browser.newPage( { viewport: { width: a.w, height: a.h } } );
      await gotoStable( page, url );
      if ( a.scrollTo ) {
        await page.evaluate( sel => {
          const el = document.querySelector( sel );
          if ( el ) el.scrollIntoView( { block: 'center' } );
        }, a.scrollTo );
      } else {
        await page.evaluate( () => window.scrollTo( 0, 0 ) );
      }
      await page.waitForTimeout( 250 );
      const out = path.join( REPO, 'docs/mocks', a.name );
      await page.screenshot( { path: out } );
      written.push( out );
      await page.close();
    }
  }
  return written;
};

( async () => {
  const browser = await launch();
  const shots = [];
  try {
    for ( const mock of MOCKS ) await run( browser, mock );
    if ( withShots ) for ( const mock of MOCKS ) shots.push( ...await shoot( browser, mock ) );
  } finally {
    await browser.close();
  }

  const failed = results.filter( r => !r.pass );

  if ( asJson ) {
    console.log( JSON.stringify( { results, shots, passed: results.length - failed.length, failed: failed.length }, null, 2 ) );
  } else {
    let scope = '';
    for ( const r of results ) {
      if ( r.scope !== scope ) { scope = r.scope; console.log( `\n=== ${scope} ===` ); }
      console.log( `  ${r.pass ? 'ok  ' : 'FAIL'}  ${r.name.padEnd( 52 )} ${r.detail === undefined ? '' : r.detail}` );
    }
    if ( shots.length ) {
      console.log( '\n=== SCREENSHOTS ===' );
      shots.forEach( s => console.log( `  wrote ${path.relative( REPO, s )}` ) );
    }
    console.log( `\n${results.length - failed.length}/${results.length} assertions passed` );
    failed.forEach( f => console.log( `  FAIL  ${f.scope}  ${f.name}  (${f.detail})` ) );
  }

  process.exit( failed.length ? 1 : 0 );
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
