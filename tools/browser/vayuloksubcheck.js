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
 * WHAT THIS PASS ADDED, and why each needed a browser rather than a reading:
 *
 *   - THE INLINE SUBSCRIBE FORM WAS REPLACED BY A WhatsApp DEEP LINK. A deletion is a
 *     claim about absence, and grep cannot settle it here: this file's stylesheet and
 *     script both keep RETIREMENT NOTES that still name `.vl-pf`, `.vl-sub-action`,
 *     `VL_DIAL_CODES` and the rest, deliberately, because those notes are what stop the
 *     defects recurring. So absence is measured three ways - zero elements, zero CSS
 *     RULES, and zero live identifiers in a comment-stripped script - because any one of
 *     the three can pass while another leaks.
 *   - THE NEW ANCHOR IS A MEMBER OF ROLE 1, not a lookalike. Asserted pairwise against
 *     the Contribute button, one assertion per property, plus "exactly ONE rule declares
 *     .vl-btn" - which is the direct guard against the `.vl-sub-action` history below.
 *   - THE LOCATION SEARCH HAD NO IMPLEMENTATION AT ALL. Not a broken handler: MEASURED in
 *     Chromium, typing into `#vl-search` produced ZERO MutationObserver records, the
 *     document held zero `[role=option]` and zero `<datalist>`, the id appeared nowhere
 *     in the inline script, and the element count under `.vl-vayulok` was 473 before and
 *     473 after. An inert control is invisible to every static check in the repo and to
 *     every screenshot; only driving it and measuring what moves catches it.
 *
 * WHAT IT ASSERTS, at 1280x900 and 390x844, from a file:// URL:
 *   (a) ROLE 1 - every action button shares one geometry: 52px, 13px radius, 16px/500,
 *       2px #1a3a2a, #d1f470 fill. 'Subscribe on WhatsApp' is in this set.
 *   (b') the subscribe form is GONE - no elements, no CSS rules, no dial-code JS.
 *   (c') the WhatsApp anchor: exact href, target=_blank, rel noopener+noreferrer, one
 *       client rect (it does not wrap), not underlined, keyboard focusable - and every
 *       ROLE 1 property EQUAL to Contribute's, from one shared `.vl-btn` rule.
 *   (d) ROLE 5 - `.vl-map-controls` is uniform with `#vl-keyclear` revealed, and clicking
 *       it changes no `aria-pressed` attribute.
 *   (e) the retired role and the dead rule match zero elements, and so does every flavour
 *       of dialog; zero `<link>`, no http(s) `src`, and EXACTLY ONE remote reference in
 *       the whole section - the wa.me href.
 *   (f) the interaction set runs with a `page.on('dialog')` listener that FAILS the run if
 *       it ever fires.
 *   (h) the place search, driven: it opens, it returns matching rows, it matches on the
 *       ADDRESS as well as the name, the list is on screen and unclipped, ROLE 7 rows
 *       share a content box, the active row is visibly distinct from its neighbour,
 *       Arrow keys move and CLAMP, Enter and click both commit and update four nodes,
 *       Escape closes without undoing, a no-match line is not selectable, and nothing
 *       overflows with the list open.
 *   (g) exactly ONE request - the document itself - and zero console or page errors.
 *
 * (b) AND (c) WERE RETIRED, their numbers left vacant rather than closing the gap, for
 * the same reason the mock's ROLE numbers are never reused: they are cited from outside
 * this file. See the note where they used to run.
 *
 * ZERO NETWORK IS ASSERTED, NOT ASSUMED, and it is the request COUNT that does it. The
 * grep for `rel=stylesheet` / `@font-face` / `@import` is a secondary cross-check only:
 * the file's own comment at line 47 contains those words while declaring that it uses none
 * of them, so the grep cannot be the primary signal without reporting its own
 * documentation as a violation.
 *
 * THE wa.me HREF IS NOT A NETWORK REQUEST, and the distinction is the whole reason the
 * request count stays at 1. It is a navigation TARGET in an `href`: nothing fetches it on
 * load, and the suite proves that by counting requests rather than by trusting the claim.
 * It does mean the repo-level grep for `href="http` now reports 1 hit on each mock
 * instead of 0, so that single hit is pinned in the DOM as well - `(e)` asserts that
 * EXACTLY ONE attribute under `.vl-vayulok` is remote and that it is this anchor's href
 * with this exact URL, which is stricter than a count because it names what is allowed.
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

const fs = require( 'fs' );
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
    /* REPURPOSED IN THIS PASS: this used to centre `.vl-hours`, which the full-page
       `-1280` shot already covers. It now shows THE SEARCH RESULTS LIST OPEN, because the
       location search is wired behaviour that no committed image evidenced - a reviewer
       could not see from any PNG that typing produces a list, only read that it should.
       `type` drives the real handler through the real input; `mumbai` is the query the
       assertions above use, and it matches 2 places on their ADDRESS rather than their
       name, which is the non-obvious half of the matcher. */
    { name: 'vayulok-section-scrolled.png', w: 1440, h: 950, scrollTo: '.vl-search', type: { sel: '#vl-search', text: 'mumbai' } },
    /* ANCHORED ON #vl-sub-wa, NOT ON .vl-subscribe. The lime panel this used to centre was
       deleted when the mock was matched to the live page, and a scrollTo whose selector
       matches nothing silently does not scroll - so this shot would have quietly captured
       the top of the page while still being named "subscribe". */
    { name: 'vayulok-section-subscribe.png', w: 1440, h: 950, scrollTo: '#vl-sub-wa' },
    /* ADDED IN THIS PASS. `-footer` centres the Share row, which puts the whole ported
       stack in one frame: the lime Subscribe pill, a hairline, the CONTRIBUTE eyebrow and
       its paragraph, the amount chips, the Contribute pill, a second hairline, then SHARE
       and its three circles. That is the frame to check against the owner's screenshot,
       because it is the only one that shows all three ported blocks and both dividers. */
    { name: 'vayulok-section-footer.png', w: 1440, h: 950, scrollTo: '.vl-share' },
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
/* ROLE 1 NOW HAS EXACTLY ONE MEMBER, AND THAT IS THE ASSERTION, NOT A GAP.
   'Subscribe on WhatsApp' and 'Contribute' were both in this list, on the claim that they
   were members of ROLE 1 rather than lookalikes. That claim was WRONG ABOUT THE REAL SITE:
   the shipped controls are 999px pills (.blog-wa-subscribe at src/pages/post/[slug].tsx:772
   and .pill/.pill-action at src/components/PillButton.tsx:202), not 13px-radius .btn-lg
   controls. They are now ROLE 8 and ROLE 9 and are asserted against the SHIPPED values
   below. 'Load' is the only member left - it is mock furniture inside .vl-keygate, mirrors
   no shipped blog control, and .vl-keygate is left untouched by instruction.
   So the two old cross-control assertions ("all action buttons share one height/font") are
   vacuous over a one-element list and are replaced by an explicit count, so that a later
   pass reads a decision rather than an omission and does not re-flatten the pills back in. */
const ROLE1_BUTTONS = [
  [ 'Load', '#vl-keyload' ],
];
const WA_HREF = 'https://wa.me/message/BEA3HNW3LNM3A1';
const WA_NAME = 'Subscribe on WhatsApp';

/* ROLE 8 - the ported .blog-wa-subscribe, from src/pages/post/[slug].tsx:772-782.
   EVERY VALUE HERE IS THE SHIPPED DECLARATION, read off that block:
   padding:12px 20px; border-radius:999px; background:#d1f470; color:#1a3a2a;
   font-weight:700; font-size:17px; text-decoration:none; and NO border at all.
   borderWidth is '0px' ON PURPOSE - the shipped anchor declares no border, and asserting
   2px here (as the retired ROLE 1 block did) is what made the port look wrong.
   height is NOT pinned: 47px is MEASURED (12px padding twice plus a 17px/700 line box)
   rather than declared, so it moves with the font fallback. It is asserted as >= 44, the
   AAA 2.5.5 target-size bar the rest of this page holds, with 47 recorded in the detail. */
const ROLE8 = {
  minHeight: 44,
  radius: '999px',
  fontSize: '17px',
  fontWeight: '700',
  borderWidth: '0px',
  background: 'rgb(209, 244, 112)',
  color: 'rgb(26, 58, 42)',
  paddingBlock: '12px/12px',
  paddingInline: '20px/20px',
};

/* ROLE 9 - the ported .pill/.pill-action, from src/components/PillButton.tsx:202-224.
   min-height:52px IS declared, so unlike ROLE 8 the height is pinned.
   THE TYPE IS READ OFF .vl-pill-action, NEVER OFF .vl-pill, and that is the trap this
   table exists to document: .vl-pill is a <button>, so the pill box itself computes the
   UA's 13.33px/400 Arial. Asserting fontSize on the pill measures the UA default and
   reports a correct port as broken. lineHeight 20.4px is 1.2 x 17px. */
const ROLE9 = {
  height: 52,
  radius: '999px',
  borderWidth: '2px',
  borderColor: 'rgb(26, 58, 42)',
  background: 'rgb(209, 244, 112)',
  paddingInline: '28px/28px',
  actionFontSize: '17px',
  actionFontWeight: '700',
  actionLineHeight: '20.4px',
};

/* ROLE 10 - the ported .share-btn, from the styled-jsx in src/components/ShareLinks.tsx:175-198.
   width/height 44px EXACTLY (not a minimum - a circle has to be square to be round, and 44px
   is the WCAG 2.5.8 floor), border-radius 50%, 2px #e5e7eb, #fff; .is-primary swaps to the
   lime fill with the #1a3a2a edge. The icons are sized 19x19 by .share-btn svg at :202.
   NOTE THE SOURCE: this is styled-jsx INSIDE the component, NOT src/styles/inner-pages.css.
   The .share-btn in inner-pages.css:1947-1968 is scoped under .pay-page/.pay-link-page and is
   a 13px-radius white button with !important - a different control. Nothing here comes from it. */
const ROLE10 = {
  size: 44,
  radius: '50%',
  borderWidth: '2px',
  restBorder: 'rgb(229, 231, 235)',
  restFill: 'rgb(255, 255, 255)',
  primaryFill: 'rgb(209, 244, 112)',
  primaryBorder: 'rgb(26, 58, 42)',
  icon: 19,
};

/* The four amount chips, as rendered faces and as radio values. Kept as one table so the
   positive assertion ("these four, in this order") and the negative one ("none of the
   retired numbers survive") cannot drift apart.
   THE NEGATIVE SET MUST BE CHECKED IN THE DOM, NOT BY GREP: `999px` appears ~10 times in
   the stylesheet and `600` appears ~9 times as font weights and PIN codes, so `grep 99` and
   `grep 600` both match the file for reasons that have nothing to do with an amount. */
const RETIRED_AMOUNTS = [ '99', '249', '499' ];

/* THE WHATSAPP GLYPH, READ OUT OF THE SHIPPED COMPONENT AT RUN TIME.
   The brief's requirement is that the path be copied VERBATIM, so this asserts exactly
   that rather than approximating it with a length floor: the harness reads
   src/pages/post/[slug].tsx, lifts the one `d` beginning M17.47, and compares the mock's
   path to it character for character. A retyped, truncated or re-minified path fails.
   Reading src/ here is READ-ONLY and is the point - it makes the mock's fidelity to the
   real component a checked fact instead of a claim in a comment. It is also the only
   assertion in this file that would notice the SHIPPED icon changing. */
const readShippedWaPath = () => {
  const file = path.join( REPO, 'src', 'pages', 'post', '[slug].tsx' );
  const m = /d="(M17\.47[^"]*)"/.exec( fs.readFileSync( file, 'utf8' ) );
  return m ? m[ 1 ] : null;
};
const SHIPPED_WA_PATH = readShippedWaPath();

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
    /* ROLE 1 IS DOWN TO ONE MEMBER BY DESIGN - see the ROLE1_BUTTONS note. The old
       "they match EACH OTHER" pair is gone because it is trivially true of one element.
       This counts instead, and it counts the DOM rather than the table: if a later pass
       puts .vl-btn back on the subscribe anchor or the contribute submit, this fails. */
    record( scope, 'ROLE 1 has exactly one member (Load), by design',
      role1.length === 1 && role1[ 0 ].label === 'Load', role1.map( r => r.label ).join( ', ' ) || 'none' );
    const strayRole1 = await page.evaluate( () => Array.prototype.slice
      .call( document.querySelectorAll( '.vl-vayulok .vl-btn' ) )
      .map( el => el.id || el.className )
      .filter( n => n !== 'vl-keyload' ) );
    record( scope, 'no ported control was left on .vl-btn', strayRole1.length === 0,
      strayRole1.join( ', ' ) || 'none' );

    /* ---- (b) AND (c) WERE RETIRED WITH THE INLINE SUBSCRIBE FORM -----------
       (b) asserted that `#vl-sub-btn`'s bottom edge met `#vl-pf`'s within 1px, and that
       `.vl-sub-action` declared no min-height LENGTH and held exactly one control. (c)
       asserted the ROLE 3 divided form: `.vl-pf`'s 52px / 10px / 1px #e5e7eb box, both
       segments filling its content box, the divider living only on the leading segment,
       and no required/pattern/minlength on either input.

       All of it measured elements that no longer exist. Subscribing moved to a WhatsApp
       deep link, so the form, the divided calling-code field, the submit button and the
       status line were deleted from the mock; there is no 91px box left to catch and no
       segment left to measure. The replacement is a single ROLE 1 anchor, which is
       asserted in (a) alongside Load and Contribute, plus the deletion proofs and the
       Contribute-parity block below. src/components/PhoneField.tsx remains the source if
       a divided field is ever needed again.

       Letting these fail against the new markup would have reported the intended change
       as a regression, which is why they are removed rather than left to rot. */

    /* ---- (b') THE FORM IS ACTUALLY GONE ------------------------------------
       A deletion is a claim about ABSENCE, which grep cannot settle on its own: a
       selector can survive in a comment (several do, deliberately, as retirement notes)
       while matching nothing, and a rule can survive with no elements. So absence is
       measured three ways - no elements, no CSS RULES, and no live identifiers in the
       script - because any one of the three could pass while another leaked. */
    const gone = await page.evaluate( () => {
      const n = s => document.querySelectorAll( s ).length;
      /* CSS rules, not source text. `.vl-pf` and friends are still NAMED in the
         stylesheet's retirement comments, which is the useful place for them; what must
         be gone is any rule that could style an element. */
      const deadSelectors = [ 'vl-pf', 'vl-cell', 'vl-sub-fields', 'vl-sub-action', 'vl-sub-status' ];
      let deadRules = [];
      for ( const sheet of document.styleSheets ) {
        let rules;
        try { rules = sheet.cssRules; } catch ( e ) { continue; }
        for ( const rule of rules ) {
          if ( !rule.selectorText ) continue;
          for ( const dead of deadSelectors ) {
            if ( rule.selectorText.indexOf( dead ) >= 0 ) deadRules.push( rule.selectorText );
          }
        }
      }
      /* The ported dial-code code, as live JS identifiers. Same reasoning: the names
         survive in the script's own retirement comment, so the probe strips comments
         before looking rather than reporting the documentation as a violation. */
      const scriptText = Array.prototype.slice.call( document.querySelectorAll( 'script' ) )
        .map( s => s.textContent ).join( '\n' )
        .replace( /\/\*[\s\S]*?\*\//g, '' )
        .replace( /^\s*\/\/.*$/gm, '' );
      const deadJs = [ 'VL_DIAL_CODES', 'VL_DEFAULT_DIAL', 'vlNormaliseDial', 'vlFindDial',
        'vlLengthHint', 'vlValidLength', 'DialCodeSearch', 'phoneField' ]
        .filter( name => scriptText.indexOf( name ) >= 0 );
      return {
        ids: n( '#vl-sub-form' ) + n( '#vl-sub-btn' ) + n( '#vl-sub-dial' )
          + n( '#vl-sub-phone' ) + n( '#vl-pf' ),
        classes: n( '.vl-sub-status' ) + n( '.vl-sub-action' ) + n( '.vl-cell' ) + n( '.vl-sub-fields' ),
        formBits: n( '.vl-subscribe form, .vl-subscribe input, .vl-subscribe button' ),
        deadRules, deadJs,
      };
    } );
    record( scope, 'subscribe form ids match 0 elements', gone.ids === 0, `${gone.ids}` );
    record( scope, 'subscribe form classes match 0 elements', gone.classes === 0, `${gone.classes}` );
    record( scope, 'no form/input/button left in the panel', gone.formBits === 0, `${gone.formBits}` );
    record( scope, 'no dead subscribe-form CSS rule survives', gone.deadRules.length === 0,
      gone.deadRules.join( ', ' ) || 'none' );
    record( scope, 'no dial-code JS identifier survives', gone.deadJs.length === 0,
      gone.deadJs.join( ', ' ) || 'none' );

    /* ---- (c') THE WHATSAPP ANCHOR -----------------------------------------
       NEVER CLICKED, and that is deliberate rather than a gap. target=_blank on a real
       external href would open a popup and begin a live navigation, which would both
       break the zero-request assertion in (g) and leave a page the run cannot control.
       The claim being made is "this is a correctly-formed, reachable link to exactly
       this URL", and href + target + rel + focusability is the whole of it. */
    const wa = await page.evaluate( () => {
      const a = document.getElementById( 'vl-sub-wa' );
      if ( !a ) return null;
      const c = getComputedStyle( a );
      return {
        tag: a.tagName,
        href: a.getAttribute( 'href' ),
        target: a.getAttribute( 'target' ),
        rel: a.getAttribute( 'rel' ) || '',
        text: a.textContent.trim(),
        rects: a.getClientRects().length,
        decoration: c.textDecorationLine,
        ariaLabel: a.getAttribute( 'aria-label' ) || '',
        spanText: a.querySelector( 'span' ) ? a.querySelector( 'span' ).textContent.trim() : '',
        /* THE GLYPH IS AN INLINE SVG AND IT IS THE FIRST CHILD, mirroring the shipped
           markup (icon then label). A <img> or a background-image here would be an
           external request and would break the zero-network claim. */
        firstChildTag: a.firstElementChild ? a.firstElementChild.tagName.toLowerCase() : '',
        svgCount: a.querySelectorAll( 'svg' ).length,
        pathFill: a.querySelector( 'svg path' ) ? a.querySelector( 'svg path' ).getAttribute( 'fill' ) : null,
        pathD: a.querySelector( 'svg path' ) ? ( a.querySelector( 'svg path' ).getAttribute( 'd' ) || '' ) : '',
        /* ROLE 8 computed values, for the side-by-side against [slug].tsx:772-782. */
        height: +a.getBoundingClientRect().height.toFixed( 1 ),
        radius: c.borderTopLeftRadius,
        fontSize: c.fontSize,
        fontWeight: c.fontWeight,
        borderWidth: c.borderTopWidth,
        background: c.backgroundColor,
        color: c.color,
        paddingBlock: c.paddingTop + '/' + c.paddingBottom,
        paddingInline: c.paddingLeft + '/' + c.paddingRight,
      };
    } );
    if ( !wa ) {
      record( scope, 'WhatsApp anchor exists', false, '#vl-sub-wa missing' );
    } else {
      record( scope, 'WhatsApp anchor is an <a>', wa.tag === 'A', wa.tag );
      record( scope, 'href is EXACTLY the wa.me deep link', wa.href === WA_HREF, `${wa.href}` );
      record( scope, 'anchor opens in a new tab', wa.target === '_blank', `${wa.target}` );
      record( scope, 'rel carries noopener and noreferrer',
        /noopener/.test( wa.rel ) && /noreferrer/.test( wa.rel ), wa.rel || 'empty' );
      record( scope, 'label names WhatsApp', /WhatsApp/.test( wa.text ), wa.text );
      /* THE ACCESSIBLE NAME IS THE SHIPPED aria-label, and the visible <span> carries the
         same string. That duplication is what [slug].tsx:517+522 does; it is mild WCAG
         2.5.3 redundancy rather than a violation, because the name CONTAINS the visible
         label, and it is asserted rather than "fixed" so the mock keeps mirroring shipped
         markup. */
      record( scope, `accessible name is EXACTLY "${WA_NAME}"`, wa.ariaLabel === WA_NAME,
        wa.ariaLabel || 'none' );
      record( scope, 'visible span label matches the accessible name', wa.spanText === WA_NAME,
        wa.spanText || 'none' );
      /* ONE client rect = one line box = the label did not wrap. This is the 390px
         claim: a wrapped anchor would report two rects and a taller box. */
      record( scope, 'label does not wrap (1 client rect)', wa.rects === 1, `${wa.rects} rects` );
      record( scope, 'anchor is not underlined', wa.decoration === 'none', wa.decoration );
      await page.focus( '#vl-sub-wa' );
      const focused = await page.evaluate( () => document.activeElement.id );
      record( scope, 'anchor is keyboard focusable', focused === 'vl-sub-wa', focused || 'none' );

      /* The glyph: inline, first, filled with currentColor, and the real path rather than
         a stub. The shipped `d` is ~1180 chars, so a length floor catches a retyped or
         truncated path without pinning the whole string twice in this repo. */
      record( scope, 'glyph is an INLINE <svg>, first child', wa.firstChildTag === 'svg', wa.firstChildTag || 'none' );
      record( scope, 'exactly one <svg> in the anchor', wa.svgCount === 1, `${wa.svgCount}` );
      record( scope, 'glyph path is fill="currentColor"', wa.pathFill === 'currentColor', String( wa.pathFill ) );
      record( scope, 'shipped glyph path was readable from [slug].tsx',
        Boolean( SHIPPED_WA_PATH ), SHIPPED_WA_PATH ? `${SHIPPED_WA_PATH.length} chars` : 'NOT FOUND' );
      record( scope, 'glyph path is VERBATIM the shipped path',
        Boolean( SHIPPED_WA_PATH ) && wa.pathD === SHIPPED_WA_PATH,
        wa.pathD === SHIPPED_WA_PATH ? `identical, ${wa.pathD.length} chars`
          : `mock ${wa.pathD.length} vs shipped ${SHIPPED_WA_PATH ? SHIPPED_WA_PATH.length : 0}` );

      /* ---- ROLE 8, PROPERTY BY PROPERTY AGAINST THE SHIPPED DECLARATIONS ----
         One assertion per property so a failure names what drifted. */
      record( scope, `ROLE 8 height >= 44 (measured ${wa.height})`, wa.height >= ROLE8.minHeight, `${wa.height}px` );
      record( scope, 'ROLE 8 radius 999px', wa.radius === ROLE8.radius, wa.radius );
      record( scope, 'ROLE 8 font 17px/700',
        wa.fontSize === ROLE8.fontSize && wa.fontWeight === ROLE8.fontWeight,
        `${wa.fontSize}/${wa.fontWeight}` );
      record( scope, 'ROLE 8 has NO border (shipped value)', wa.borderWidth === ROLE8.borderWidth, wa.borderWidth );
      record( scope, 'ROLE 8 fill #d1f470', wa.background === ROLE8.background, wa.background );
      record( scope, 'ROLE 8 type #1a3a2a', wa.color === ROLE8.color, wa.color );
      record( scope, 'ROLE 8 padding-block 12px', wa.paddingBlock === ROLE8.paddingBlock, wa.paddingBlock );
      record( scope, 'ROLE 8 padding-inline 20px', wa.paddingInline === ROLE8.paddingInline, wa.paddingInline );
    }

    /* ---- (c'') THE PAIRWISE WHATSAPP-vs-CONTRIBUTE PARITY BLOCK IS RETIRED ----
       It asserted, property by property, that the subscribe anchor and the Contribute
       submit were geometrically IDENTICAL - same height, radius, font, border, padding.
       They are not identical on the real site and were never meant to be: the shipped
       subscribe is .blog-wa-subscribe (47px measured, no border, 12px/20px padding) and
       the shipped Contribute is .pill (52px declared, 2px #1a3a2a, 0/28px padding). The
       block was asserting a shape the real site does not have, so passing it REQUIRED the
       mock to be wrong. It is replaced by the per-role blocks above and below, each
       measured against its own shipped source. */

    /* ---- ROLE 9: the Contribute pill, vs PillButton.tsx:202-224 -------------- */
    const pill = await page.evaluate( () => {
      const el = document.querySelector( '.vl-bc-submit-wrap .vl-pill' );
      if ( !el ) return null;
      const c = getComputedStyle( el );
      const span = el.querySelector( '.vl-pill-action' );
      const sc = span ? getComputedStyle( span ) : null;
      return {
        tag: el.tagName,
        type: el.getAttribute( 'type' ),
        height: +el.getBoundingClientRect().height.toFixed( 1 ),
        radius: c.borderTopLeftRadius,
        borderWidth: c.borderTopWidth,
        borderColor: c.borderTopColor,
        background: c.backgroundColor,
        paddingInline: c.paddingLeft + '/' + c.paddingRight,
        paddingBlock: c.paddingTop + '/' + c.paddingBottom,
        /* READ OFF THE PILL ITSELF ONLY TO PROVE THE TRAP IS REAL - a <button> with no
           font declaration computes the UA's 13.33px Arial, which is why the type is
           asserted on the span below and never here. */
        pillFontSize: c.fontSize,
        label: span ? span.textContent.trim() : '',
        actionFontSize: sc ? sc.fontSize : '',
        actionFontWeight: sc ? sc.fontWeight : '',
        actionLineHeight: sc ? sc.lineHeight : '',
        actionColor: sc ? sc.color : '',
      };
    } );
    if ( !pill ) {
      record( scope, 'ROLE 9 Contribute pill exists', false, '.vl-bc-submit-wrap .vl-pill missing' );
    } else {
      record( scope, 'ROLE 9 is a submit <button>', pill.tag === 'BUTTON' && pill.type === 'submit',
        `${pill.tag} type=${pill.type}` );
      record( scope, 'ROLE 9 label is "Contribute"', pill.label === 'Contribute', pill.label || 'none' );
      record( scope, 'ROLE 9 height 52 (declared min-height)', pill.height === ROLE9.height, `${pill.height}px` );
      record( scope, 'ROLE 9 radius 999px', pill.radius === ROLE9.radius, pill.radius );
      record( scope, 'ROLE 9 border 2px #1a3a2a',
        pill.borderWidth === ROLE9.borderWidth && pill.borderColor === ROLE9.borderColor,
        `${pill.borderWidth} ${pill.borderColor}` );
      record( scope, 'ROLE 9 fill #d1f470', pill.background === ROLE9.background, pill.background );
      record( scope, 'ROLE 9 padding-inline 28px', pill.paddingInline === ROLE9.paddingInline, pill.paddingInline );
      record( scope, 'ROLE 9 padding-block 0', pill.paddingBlock === '0px/0px', pill.paddingBlock );
      /* The type, on the SPAN. */
      record( scope, 'ROLE 9 label font 17px/700 (on .vl-pill-action)',
        pill.actionFontSize === ROLE9.actionFontSize && pill.actionFontWeight === ROLE9.actionFontWeight,
        `${pill.actionFontSize}/${pill.actionFontWeight}` );
      record( scope, 'ROLE 9 label line-height 20.4px (1.2 x 17)',
        pill.actionLineHeight === ROLE9.actionLineHeight, pill.actionLineHeight );
      record( scope, 'ROLE 9 label colour #1a3a2a', pill.actionColor === 'rgb(26, 58, 42)', pill.actionColor );
      /* AND THE TRAP ITSELF, asserted so it stays documented by execution: the pill box
         does NOT carry the 17px. If a future pass "simplifies" by moving the font onto
         .vl-pill, this flips and the comment above stops being a guess. */
      record( scope, 'ROLE 9 pill box does NOT carry the label type (UA font)',
        pill.pillFontSize !== ROLE9.actionFontSize, `pill ${pill.pillFontSize} vs span ${pill.actionFontSize}` );
    }

    /* ---- ROLE 10: the three share controls, vs ShareLinks.tsx:175-202 --------
       THE ROW IS HARD-CLASSED is-native is-clip in the mock, because the shipped CSS
       hides .share-native/.share-copy until a useEffect feature-detects navigator.share
       and navigator.clipboard. Both being visible is therefore the state a browser with
       both APIs renders - and the non-zero client rects asserted below are what proves the
       hard-classing actually reveals them rather than leaving display:none in force. */
    const share = await page.evaluate( () => {
      const row = document.querySelector( '.vl-share-row' );
      if ( !row ) return null;
      const btns = Array.prototype.slice.call( row.querySelectorAll( '.vl-share-btn' ) );
      const read = el => {
        const c = getComputedStyle( el );
        const r = el.getBoundingClientRect();
        const svg = el.querySelector( 'svg' );
        const sc = svg ? getComputedStyle( svg ) : null;
        /* The drawn icons are stroked and must compute fill:none - without the
           path:not([fill]) rule the native-share circles render as black discs. */
        const drawn = el.querySelector( 'svg circle, svg line, svg polyline' );
        const dc = drawn ? getComputedStyle( drawn ) : null;
        return {
          tag: el.tagName,
          type: el.getAttribute( 'type' ),
          name: el.getAttribute( 'aria-label' ) || '',
          cls: el.className,
          w: +r.width.toFixed( 1 ), h: +r.height.toFixed( 1 ),
          top: +r.top.toFixed( 1 ), bottom: +r.bottom.toFixed( 1 ),
          radius: c.borderTopLeftRadius,
          borderWidth: c.borderTopWidth,
          borderColor: c.borderTopColor,
          background: c.backgroundColor,
          color: c.color,
          svgCount: el.querySelectorAll( 'svg' ).length,
          iconW: sc ? sc.width : '', iconH: sc ? sc.height : '',
          drawnFill: dc ? dc.fill : '', drawnStroke: dc ? dc.stroke : '',
          tip: el.querySelector( '.vl-share-tip' ) ? el.querySelector( '.vl-share-tip' ).textContent.trim() : '',
          rects: el.getClientRects().length,
        };
      };
      const label = row.querySelector( '.vl-share-label' );
      const status = row.querySelector( '.vl-share-status' );
      const sr = status ? status.getBoundingClientRect() : null;
      return {
        btns: btns.map( read ),
        children: Array.prototype.slice.call( row.children ).map( el => el.className ),
        label: label ? { text: label.textContent.trim(), transform: getComputedStyle( label ).textTransform } : null,
        status: status ? {
          role: status.getAttribute( 'role' ),
          live: status.getAttribute( 'aria-live' ),
          w: +sr.width.toFixed( 1 ), h: +sr.height.toFixed( 1 ),
          text: status.textContent.trim(),
        } : null,
      };
    } );
    if ( !share ) {
      record( scope, 'ROLE 10 share row exists', false, '.vl-share-row missing' );
    } else {
      record( scope, 'share row holds label + 3 buttons + status', share.children.length === 5,
        `${share.children.length} children` );
      record( scope, 'exactly 3 .vl-share-btn controls', share.btns.length === 3, `${share.btns.length}` );
      record( scope, 'SHARE label renders uppercase',
        Boolean( share.label ) && share.label.transform === 'uppercase',
        share.label ? `${share.label.text} / ${share.label.transform}` : 'none' );
      record( scope, 'SHARE label text is "Share"',
        Boolean( share.label ) && share.label.text === 'Share', share.label ? share.label.text : 'none' );

      for ( const b of share.btns ) {
        const which = b.tip || b.name;
        record( scope, `ROLE 10 ${which} is a <button type=button>`,
          b.tag === 'BUTTON' && b.type === 'button', `${b.tag} type=${b.type}` );
        record( scope, `ROLE 10 ${which} has an accessible name`, b.name.length > 0, b.name || 'EMPTY' );
        record( scope, `ROLE 10 ${which} is 44x44`, b.w === ROLE10.size && b.h === ROLE10.size, `${b.w}x${b.h}` );
        record( scope, `ROLE 10 ${which} radius 50%`, b.radius === ROLE10.radius, b.radius );
        record( scope, `ROLE 10 ${which} border 2px`, b.borderWidth === ROLE10.borderWidth, b.borderWidth );
        record( scope, `ROLE 10 ${which} holds exactly one inline <svg>`, b.svgCount === 1, `${b.svgCount}` );
        record( scope, `ROLE 10 ${which} icon is 19x19`,
          b.iconW === `${ROLE10.icon}px` && b.iconH === `${ROLE10.icon}px`, `${b.iconW} x ${b.iconH}` );
        /* is-native/is-clip really did reveal it: display:none yields ZERO client rects. */
        record( scope, `ROLE 10 ${which} is actually visible (not display:none)`, b.rects > 0, `${b.rects} rects` );
      }
      /* ONE ROW, ONE ROLE: the three circles are flush, so none of them is a lookalike
         sitting a pixel off the others. */
      const tops = [ ...new Set( share.btns.map( b => b.top ) ) ];
      const bots = [ ...new Set( share.btns.map( b => b.bottom ) ) ];
      record( scope, 'ROLE 10 row is vertically flush', tops.length === 1 && bots.length === 1,
        `tops ${tops.join( ', ' )} / bottoms ${bots.join( ', ' )}` );

      /* THE PRIMARY IS THE WHATSAPP ONE, and it is the ONLY lime one. Asserted as a
         difference as well as against the literals, so "all three styled the same"
         cannot pass. */
      const primary = share.btns.filter( b => /is-primary/.test( b.cls ) );
      record( scope, 'exactly ONE .is-primary share control', primary.length === 1, `${primary.length}` );
      if ( primary.length === 1 ) {
        record( scope, 'the primary is the WhatsApp control', /WhatsApp/.test( primary[ 0 ].name ),
          primary[ 0 ].name );
        record( scope, 'primary fill is lime #d1f470', primary[ 0 ].background === ROLE10.primaryFill,
          primary[ 0 ].background );
        record( scope, 'primary border is #1a3a2a', primary[ 0 ].borderColor === ROLE10.primaryBorder,
          primary[ 0 ].borderColor );
      }
      const secondary = share.btns.filter( b => !/is-primary/.test( b.cls ) );
      record( scope, 'the other two share controls are white', secondary.length === 2
        && secondary.every( b => b.background === ROLE10.restFill ),
        secondary.map( b => b.background ).join( ', ' ) );
      record( scope, 'the other two carry the light-grey edge', secondary.length === 2
        && secondary.every( b => b.borderColor === ROLE10.restBorder ),
        secondary.map( b => b.borderColor ).join( ', ' ) );
      record( scope, 'primary fill DIFFERS from the other two',
        primary.length === 1 && secondary.every( b => b.background !== primary[ 0 ].background ), '' );

      /* The stroked icons must not be filled - this is the rule whose absence turns the
         native-share mark into three black discs. */
      const drawnBtns = share.btns.filter( b => b.drawnFill );
      record( scope, 'drawn icons compute fill:none', drawnBtns.length > 0
        && drawnBtns.every( b => b.drawnFill === 'none' ),
        drawnBtns.map( b => b.drawnFill ).join( ', ' ) || 'no drawn icon found' );
      record( scope, 'drawn icons stroke with the button colour', drawnBtns.length > 0
        && drawnBtns.every( b => b.drawnStroke === b.color ),
        drawnBtns.map( b => `${b.drawnStroke} vs ${b.color}` ).join( ' | ' ) || 'none' );

      /* THE LIVE REGION. Empty and inert here - nothing copies, so nothing writes to it -
         but still a 1x1 clipped status node rather than display:none. */
      record( scope, 'share status is a polite live region',
        Boolean( share.status ) && share.status.role === 'status' && share.status.live === 'polite',
        share.status ? `role=${share.status.role} aria-live=${share.status.live}` : 'missing' );
      record( scope, 'share status is visually clipped to 1x1',
        Boolean( share.status ) && share.status.w <= 1 && share.status.h <= 1,
        share.status ? `${share.status.w}x${share.status.h}` : 'missing' );
      record( scope, 'share status is empty (inert, nothing writes to it)',
        Boolean( share.status ) && share.status.text === '', share.status ? share.status.text : 'missing' );

      /* All three keyboard-focusable: an icon-only control that cannot be reached is
         worse for a keyboard reader than for anyone else. */
      const sel = [ '.vl-share-btn.is-primary', '.vl-share-btn.vl-share-native', '.vl-share-btn.vl-share-copy' ];
      for ( const s of sel ) {
        await page.focus( s );
        const ok = await page.evaluate( q => document.activeElement === document.querySelector( q ), s );
        record( scope, `ROLE 10 ${s} is keyboard focusable`, ok, ok ? 'focused' : 'not focused' );
      }
    }

    /* ---- THE FOUR AMOUNT CHIPS, AND THE RETIRED NUMBERS -----------------------
       Asserted in the DOM rather than by grep: `999px` and `600` both appear in this
       file for reasons unrelated to an amount (radii, font weights, PIN codes), so a
       text search for them is noise. See RETIRED_AMOUNTS. */
    const amounts = await page.evaluate( () => {
      const faces = Array.prototype.slice.call( document.querySelectorAll( '.vl-bc-choice-face' ) );
      const radios = Array.prototype.slice.call( document.querySelectorAll( '.vl-bc-radio' ) );
      const checked = radios.filter( r => r.checked );
      const readFace = el => {
        const c = getComputedStyle( el );
        return {
          text: el.textContent.trim(),
          background: c.backgroundColor,
          borderColor: c.borderTopColor,
          radius: c.borderTopLeftRadius,
          fontSize: c.fontSize,
          fontWeight: c.fontWeight,
          h: +el.getBoundingClientRect().height.toFixed( 1 ),
        };
      };
      return {
        faces: faces.map( readFace ),
        values: radios.map( r => r.value ),
        checkedCount: checked.length,
        checkedValue: checked.length === 1 ? checked[ 0 ].value : null,
        checkedFace: checked.length === 1 && checked[ 0 ].nextElementSibling
          ? readFace( checked[ 0 ].nextElementSibling ) : null,
        uncheckedFace: ( () => {
          const u = radios.filter( r => !r.checked )[ 0 ];
          return u && u.nextElementSibling ? readFace( u.nextElementSibling ) : null;
        } )(),
      };
    } );
    record( scope, 'exactly 4 amount chips', amounts.faces.length === 4, `${amounts.faces.length}` );
    record( scope, 'exactly 4 amount radios', amounts.values.length === 4, `${amounts.values.length}` );
    record( scope, 'exactly one amount is checked', amounts.checkedCount === 1, `${amounts.checkedCount}` );
    record( scope, 'the last chip is "Other"',
      amounts.faces.length === 4 && amounts.faces[ 3 ].text === 'Other',
      amounts.faces.length ? amounts.faces[ 3 ].text : 'none' );
    /* THE NEGATIVE CLAIM: none of the mock's old invented amounts survives, as a face
       text or as a radio value. */
    const facesText = amounts.faces.map( f => f.text );
    for ( const n of RETIRED_AMOUNTS ) {
      record( scope, `retired amount ${n} appears in NO chip face`,
        !facesText.some( t => new RegExp( `(^|[^0-9])${n}([^0-9]|$)` ).test( t ) ),
        facesText.join( ' ' ) );
      record( scope, `retired amount ${n} appears in NO radio value`,
        !amounts.values.includes( n ), amounts.values.join( ', ' ) );
    }
    /* THE SELECTED CHIP IS LIME WITH A DARK EDGE AND THE UNSELECTED ONES ARE NOT.
       Asserted as a DIFFERENCE as well as against the literals, so "all four styled the
       same" cannot pass by matching one of them. */
    if ( amounts.checkedFace && amounts.uncheckedFace ) {
      record( scope, 'selected chip fill is lime #d1f470',
        amounts.checkedFace.background === 'rgb(209, 244, 112)', amounts.checkedFace.background );
      record( scope, 'selected chip border is #1a3a2a',
        amounts.checkedFace.borderColor === 'rgb(26, 58, 42)', amounts.checkedFace.borderColor );
      record( scope, 'unselected chip fill is white',
        amounts.uncheckedFace.background === 'rgb(255, 255, 255)', amounts.uncheckedFace.background );
      record( scope, 'unselected chip border is #e5e7eb',
        amounts.uncheckedFace.borderColor === 'rgb(229, 231, 235)', amounts.uncheckedFace.borderColor );
      record( scope, 'selected chip LOOKS different from an unselected one',
        amounts.checkedFace.background !== amounts.uncheckedFace.background
        && amounts.checkedFace.borderColor !== amounts.uncheckedFace.borderColor,
        `${amounts.checkedFace.background} vs ${amounts.uncheckedFace.background}` );
    } else {
      record( scope, 'a checked and an unchecked chip are both measurable', false, 'one is missing' );
    }
    /* ROLE 4 geometry, vs BlogContribution.tsx:275-280. */
    for ( const f of amounts.faces ) {
      record( scope, `ROLE 4 chip ${f.text} is 999px / 15px-700`,
        f.radius === '999px' && f.fontSize === '15px' && f.fontWeight === '700',
        `${f.radius} ${f.fontSize}/${f.fontWeight}` );
    }

    /* ---- THE CONTRIBUTE EYEBROW -------------------------------------------
       The DOM text is the WORD "Contribute", never "Contribution"; the UPPERCASING is
       CSS, ported from BlogContribution.tsx:260-263, and the two are different things.
       What the owner rejected was the word, not the casing. */
    const eyebrow = await page.evaluate( () => {
      const el = document.querySelector( '.vl-bc-title' );
      if ( !el ) return null;
      const c = getComputedStyle( el );
      return { text: el.textContent.trim(), transform: c.textTransform, fontSize: c.fontSize, fontWeight: c.fontWeight };
    } );
    if ( !eyebrow ) {
      record( scope, 'contribute eyebrow exists', false, '.vl-bc-title missing' );
    } else {
      record( scope, 'eyebrow DOM text is the word "Contribute"', eyebrow.text === 'Contribute', eyebrow.text );
      /* THE WORD vs THE CASING. The DOM text asserted above is the word the owner chose;
         this asserts the CSS casing the shipped component declares, which renders it as
         CONTRIBUTE. The two assertions together are the point: if someone "fixes" the
         casing by editing the markup to CONTRIBUTE, the first one fails. */
      record( scope, 'eyebrow renders uppercase (BlogContribution.tsx:260-263)',
        eyebrow.transform === 'uppercase', eyebrow.transform );
      record( scope, 'eyebrow DOM text is NOT the rejected word "Contribution"',
        !/Contribution/.test( eyebrow.text ), eyebrow.text );
      record( scope, 'eyebrow is 12px/700 (the eyebrow rung)',
        eyebrow.fontSize === '12px' && eyebrow.fontWeight === '700',
        `${eyebrow.fontSize}/${eyebrow.fontWeight}` );
    }

    /* ---- THE TWO DIVIDERS, AND THE SECTION RHYTHM THAT DRAWS THEM ----------
       Subscribe / Contribute / Share are .vl-section siblings in .vl-app-left, and
       `.vl-app-left > .vl-section` carries the hairline. So the dividers are the existing
       rhythm, not new rules - and that is what this asserts: the 2nd and 3rd sections each
       carry a 1px hairline above them, and the first does not. */
    const rhythm = await page.evaluate( () => {
      const secs = Array.prototype.slice.call( document.querySelectorAll( '.vl-app-left > .vl-section' ) );
      return secs.map( el => {
        const c = getComputedStyle( el );
        return {
          cls: el.className,
          borderTopWidth: c.borderTopWidth,
          borderTopColor: c.borderTopColor,
          paddingTop: c.paddingTop,
          marginTop: c.marginTop,
        };
      } );
    } );
    record( scope, 'left column holds exactly 3 ported sections', rhythm.length === 3,
      rhythm.map( r => r.cls ).join( ' | ' ) );
    /* THE SECTIONS ARE IN SCREENSHOT ORDER: Subscribe, then Contribute, then Share. */
    record( scope, 'the 3 sections are in screenshot order (subscribe, contribute, share)',
      rhythm.length === 3
      && !/vl-contribute|vl-share/.test( rhythm[ 0 ].cls )
      && /vl-contribute/.test( rhythm[ 1 ].cls )
      && /vl-share/.test( rhythm[ 2 ].cls ),
      rhythm.map( r => r.cls ).join( ' -> ' ) );
    /* EVERY .vl-section IN THIS COLUMN CARRIES THE HAIRLINE, so three sections yield TWO
       dividers BETWEEN them (above Contribute and above Share) plus the one above
       Subscribe that separates the stack from the content higher up the column. The brief
       asks for two dividers between the three blocks, and that is what the 2nd and 3rd
       hairlines are; counting all three hairlines and expecting 2 is the off-by-one to
       avoid here. */
    const hairlines = rhythm.filter( r => r.borderTopWidth === '1px' );
    record( scope, 'all 3 sections carry the 1px section hairline', hairlines.length === 3,
      `${hairlines.length}` );
    const between = rhythm.slice( 1 );
    record( scope, 'exactly 2 dividers sit BETWEEN the 3 blocks',
      between.length === 2 && between.every( r => r.borderTopWidth === '1px' ),
      between.map( r => `${r.cls.split( ' ' ).pop()}:${r.borderTopWidth}` ).join( ', ' ) );
    record( scope, 'the dividers are the --hair colour',
      between.length === 2 && between.every( r => r.borderTopColor === 'rgb(229, 231, 235)' ),
      between.map( r => r.borderTopColor ).join( ', ' ) );
    /* .vl-contribute declared padding-top:24px and was FULLY SHADOWED by
       `.vl-app-left > .vl-section` (two classes beats one), which declares 40px. So the
       rule was dead, and whether it is deleted or kept the computed value is 40px - this
       is the measurement that proves removing it moves nothing. */
    /* THE SPACING IS THE SHIPPED SPACING, asserted against the source rather than
       against this mock's old invented 56px/40px. Both shipped blocks - `.bc` at
       BlogContribution.tsx:253-254 and `.post-share` at [slug].tsx:787 - declare
       `margin-top:44px;padding-top:24px;border-top:1px solid #e5e7eb`. */
    record( scope, 'every ported section uses the shipped 24px padding-top',
      rhythm.every( r => r.paddingTop === '24px' ),
      rhythm.map( r => r.paddingTop ).join( ', ' ) );
    record( scope, 'every ported section uses the shipped 44px margin-top',
      rhythm.every( r => r.marginTop === '44px' ),
      rhythm.map( r => r.marginTop ).join( ', ' ) );
    /* ONE RULE DRAWS ALL THREE, so they cannot drift: identical separator geometry
       across the stack is asserted as a set-size of 1, not as three equal literals. */
    const sepShapes = [ ...new Set( rhythm.map( r => `${r.borderTopWidth} ${r.borderTopColor} ${r.paddingTop} ${r.marginTop}` ) ) ];
    record( scope, 'all 3 separators are geometrically identical', sepShapes.length === 1,
      sepShapes.join( ' | ' ) );

    /* THE SHARED-CLASS PROOF, and it is the guard against this file's own history: the
       shape must come from ONE rule both controls match, not from two rules that happen
       to agree today. `.vl-sub-action` was once declared twice with disjoint properties
       and both applied, which is why "exactly one rule whose selector IS .vl-btn" is
       asserted as a number rather than assumed from reading the stylesheet. */
    const shared = await page.evaluate( () => {
      let exact = 0;
      for ( const sheet of document.styleSheets ) {
        let rules;
        try { rules = sheet.cssRules; } catch ( e ) { continue; }
        for ( const rule of rules ) {
          if ( rule.selectorText && rule.selectorText.trim() === '.vl-btn' ) exact += 1;
        }
      }
      /* SCOPED TO THE SECTION, NOT TO .vl-subscribe. The lime panel was deleted when the
         mock was matched to the live page, so a `.vl-subscribe ...` query now matches
         nothing and reported "none" - which passed as "no stray controls" for the wrong
         reason while actually proving the probe had gone blind. The claim being made is
         that the subscribe REGION still holds exactly one interactive control, so it is
         anchored to the anchor's own section. */
      const subSection = document.querySelector( '#vl-sub-wa' )
        ? document.querySelector( '#vl-sub-wa' ).closest( 'section' ) : null;
      const controls = subSection
        ? Array.prototype.slice.call( subSection.querySelectorAll( 'a, button, input, select, textarea' ) )
        : [];
      return {
        exact,
        panelControls: controls.map( el => el.id || el.tagName ),
      };
    } );
    /* STILL ASSERTED, AND STILL FOR THE ORIGINAL REASON: a shape must come from ONE rule,
       not from two rules that happen to agree today. `.vl-sub-action` was once declared
       TWICE with disjoint properties and both applied, which is why this is counted rather
       than assumed from reading the stylesheet. ROLE 1 now has one member, but the
       single-rule guarantee is what stops the next role from splitting in two. */
    record( scope, 'exactly ONE rule declares .vl-btn', shared.exact === 1, `${shared.exact} rules` );
    record( scope, 'subscribe section holds exactly one control (the anchor)',
      shared.panelControls.length === 1 && shared.panelControls[ 0 ] === 'vl-sub-wa',
      shared.panelControls.join( ', ' ) || 'NONE FOUND - probe may be blind' );

    /* ---- THE SUBSCRIBE PANEL AND HEADING ARE GONE ---------------------------
       The owner compared the mock against the live post page and found the one
       remaining mismatch here: the mock wrapped the anchor in a lime-tinted panel with
       an eyebrow and an h2, and the real page has neither - the anchor follows the tags
       </nav> directly on the plain page background. These assert the removal in the DOM
       AND in the stylesheet, because a dead rule left behind is how this file's
       duplicate-declaration defects have started before. */
    const panelGone = await page.evaluate( () => {
      const deadSelectors = [ '.vl-subscribe', '.vl-sub-head', '.vl-sub-title' ];
      let rules = 0;
      const found = [];
      for ( const sheet of document.styleSheets ) {
        let list;
        try { list = sheet.cssRules; } catch ( e ) { continue; }
        const walk = rs => {
          for ( const r of rs ) {
            if ( r.cssRules ) { walk( r.cssRules ); continue; }
            if ( !r.selectorText ) continue;
            for ( const d of deadSelectors ) {
              if ( r.selectorText.split( ',' ).some( s => s.trim().startsWith( d ) ) ) {
                rules += 1; found.push( r.selectorText.trim() );
              }
            }
          }
        };
        walk( list );
      }
      const sec = document.querySelector( '#vl-sub-wa' ) ? document.querySelector( '#vl-sub-wa' ).closest( 'section' ) : null;
      const labelledBy = sec ? sec.getAttribute( 'aria-labelledby' ) : null;
      return {
        els: document.querySelectorAll( '.vl-subscribe, .vl-sub-head, .vl-sub-title' ).length,
        rules, found,
        /* .vl-eyebrow MUST SURVIVE: it has a second, live user ("Health advisory"). */
        eyebrows: document.querySelectorAll( '.vl-eyebrow' ).length,
        eyebrowTexts: Array.prototype.slice.call( document.querySelectorAll( '.vl-eyebrow' ) ).map( e => e.textContent.trim() ),
        headingText: document.body.innerText.includes( 'Get air-quality alerts for your place' ),
        /* The anchor must be a DIRECT child of its section - no wrapper left behind. */
        anchorParentIsSection: document.querySelector( '#vl-sub-wa' )
          ? document.querySelector( '#vl-sub-wa' ).parentElement.tagName === 'SECTION' : false,
        sectionLabel: sec ? sec.getAttribute( 'aria-label' ) : null,
        labelledBy,
        /* A dangling aria-labelledby is worse than none: it reads as wired but names
           nothing. If the attribute is present at all, its target must exist. */
        labelledByResolves: labelledBy ? Boolean( document.getElementById( labelledBy ) ) : true,
        /* The panel's fill must be gone - the anchor now sits on the page background. */
        sectionBg: sec ? getComputedStyle( sec ).backgroundColor : null,
        sectionBorder: sec ? getComputedStyle( sec ).borderLeftWidth : null,
      };
    } );
    record( scope, 'the lime subscribe panel/head/title match 0 elements', panelGone.els === 0, `${panelGone.els}` );
    record( scope, 'no .vl-subscribe / .vl-sub-head / .vl-sub-title CSS rule survives',
      panelGone.rules === 0, panelGone.found.join( ', ' ) || 'none' );
    record( scope, 'the "Get air-quality alerts" heading is gone', !panelGone.headingText,
      panelGone.headingText ? 'STILL PRESENT' : 'absent' );
    record( scope, 'the subscribe anchor is a direct child of its section',
      panelGone.anchorParentIsSection, panelGone.anchorParentIsSection ? 'section' : 'still wrapped' );
    record( scope, 'the subscribe section has no panel fill',
      panelGone.sectionBg === 'rgba(0, 0, 0, 0)', String( panelGone.sectionBg ) );
    record( scope, 'the subscribe section has no panel border',
      panelGone.sectionBorder === '0px', String( panelGone.sectionBorder ) );
    /* THE ARIA FIX, not just the deletion. */
    record( scope, 'no DANGLING aria-labelledby on the subscribe section',
      panelGone.labelledByResolves,
      panelGone.labelledBy ? `points at #${panelGone.labelledBy}` : 'attribute absent' );
    record( scope, 'the subscribe section is still named', panelGone.sectionLabel === WA_NAME,
      panelGone.sectionLabel || 'UNNAMED' );
    /* AND THE SELECTOR THAT MUST NOT HAVE BEEN SWEPT UP WITH THEM. */
    record( scope, '.vl-eyebrow survives for its other live user',
      panelGone.eyebrows >= 1, panelGone.eyebrowTexts.join( ' | ' ) || 'none left' );
    record( scope, 'the "VayuLok alerts" eyebrow specifically is gone',
      !panelGone.eyebrowTexts.includes( 'VayuLok alerts' ), panelGone.eyebrowTexts.join( ' | ' ) );

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
         placeholder reading "+91 00000 00000" inside the number field - a fake country
         code in placeholder grey. It was then replaced by a real calling-code control
         whose VALUE was legitimately "+91", which was the one permitted "+". That control
         is now gone too, and the wa.me URL contains no "+", so the correct expectation is
         ZERO - no "+" of any kind anywhere in the section. */
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
      /* THE ZERO-NETWORK GREP, DONE IN THE DOM INSTEAD. The brief's
         `grep -c 'rel="stylesheet"\|<link \|src="http\|href="http'` had to move off 0,
         because the wa.me anchor is one legitimate href="http...". Asserting it in the
         DOM is stricter than adjusting the grep's expected count: it names WHICH
         attribute is allowed to be remote rather than just counting hits, so a second
         remote reference cannot hide behind the allowance. */
      const links = n( 'link' );
      const srcHttp = [];
      const httpAttrs = [];
      document.querySelectorAll( '.vl-vayulok *' ).forEach( el => {
        for ( const a of el.attributes ) {
          if ( /^https?:/.test( a.value ) ) httpAttrs.push( `${el.tagName}#${el.id || ''}[${a.name}="${a.value}"]` );
        }
      } );
      document.querySelectorAll( '[src]' ).forEach( el => {
        if ( /^https?:/.test( el.getAttribute( 'src' ) ) ) srcHttp.push( el.tagName );
      } );
      return {
        quietEls: n( '.vl-btn-quiet' ), verifyEls: n( '.vl-verify-row' ), quietRules,
        dialogEls: n( 'dialog' ),
        modalEls: n( '[role=dialog],[role=alertdialog],[aria-modal]' ),
        fixed, plusText, plusAttr, links, srcHttp, httpAttrs,
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
    record( scope, 'no "+" survives in the section',
      counts.plusText.length === 0 && counts.plusAttr.length === 0,
      `text ${JSON.stringify( counts.plusText )} attr ${JSON.stringify( counts.plusAttr )}` );
    record( scope, 'zero <link> elements', counts.links === 0, `${counts.links}` );
    record( scope, 'no element has an http(s) src', counts.srcHttp.length === 0,
      counts.srcHttp.join( ', ' ) || 'none' );
    record( scope, 'exactly ONE remote reference, the wa.me href',
      counts.httpAttrs.length === 1 && counts.httpAttrs[ 0 ] === `A#vl-sub-wa[href="${WA_HREF}"]`,
      counts.httpAttrs.join( ', ' ) || 'none' );
    record( scope, 'no horizontal overflow', counts.docScrollWidth === counts.docClientWidth,
      `${counts.docScrollWidth} vs ${counts.docClientWidth}` );

    /* ---- (f) the interaction set ------------------------------------------- */
    /* THE SUBSCRIBE-FORM INTERACTIONS WERE RETIRED HERE, with the form itself. Twelve
       assertions drove `#vl-sub-dial` / `#vl-sub-phone` / `#vl-sub-btn` through the
       DialCodeSearch model and the inline submit: empty submit reporting into
       `.vl-sub-status` without raising the native bubble, typing `971` committing `+971`
       and refreshing the length hint, an unsupported code going aria-invalid and
       reverting on blur, a valid submit composing E.164 and flipping the label to
       `Subscribed`, and the panel gaining no element through any of it. None of those
       controls exist now. The search interactions in (h) are what exercise this page.

       `NO dialog fired` IS KEPT AND IS NOT TIED TO THE FORM. It is the assertion the
       owner's original report turned on - a browser validation bubble is chrome, not DOM,
       so it can only be caught by listening - and it now covers every interaction the
       harness performs, including the whole of the search path in (h). */
    /* ---- (h) THE PLACE SEARCH ----------------------------------------------
       THIS BLOCK IS THE WHOLE REASON TASK 3 COUNTS AS VERIFIED. The field was inert
       decoration - measured, not inferred: typing produced ZERO MutationObserver
       records, there were zero [role=option] and zero <datalist> in the document, and
       `vl-search` appeared nowhere in the inline script. Every other check in the repo
       passed while a visible control did nothing at all. The only thing that catches
       that class of gap is driving the control and measuring what moves, which is what
       follows. Run at BOTH viewports, because "it works at 1280" was never the claim. */
    const rest = await page.evaluate( () => {
      const i = document.getElementById( 'vl-search' );
      const l = document.getElementById( 'vl-search-results' );
      return {
        role: i && i.getAttribute( 'role' ),
        controls: i && i.getAttribute( 'aria-controls' ),
        autocomplete: i && i.getAttribute( 'aria-autocomplete' ),
        expanded: i && i.getAttribute( 'aria-expanded' ),
        listRole: l && l.getAttribute( 'role' ),
        listRects: l ? l.getClientRects().length : -1,
      };
    } );
    record( scope, 'search input is a combobox', rest.role === 'combobox', `${rest.role}` );
    record( scope, 'combobox points at the listbox', rest.controls === 'vl-search-results', `${rest.controls}` );
    record( scope, 'combobox declares aria-autocomplete=list', rest.autocomplete === 'list', `${rest.autocomplete}` );
    record( scope, 'list is closed at rest', rest.expanded === 'false', `${rest.expanded}` );
    record( scope, 'results container is a listbox', rest.listRole === 'listbox', `${rest.listRole}` );
    record( scope, 'results container renders nothing at rest', rest.listRects === 0, `${rest.listRects} rects` );

    /* THE GUARD, AND IT IS NOT CEREMONY. Everything below DRIVES the control - it
       types, presses keys and clicks rows - so if the results surface is missing the
       probes dereference null and the click waits for a selector that will never
       exist, and the run dies with a TypeError instead of reporting. A harness that
       throws tells you it broke; one that records tells you WHAT broke. Measured
       against the pre-fix file, the un-guarded version crashed on the first probe and
       reported nothing at all, which is exactly the failure mode this file exists to
       avoid - so a missing search surface is recorded as a FAILED assertion naming
       the thing that is absent, and the suite still reaches (g). */
    if ( rest.role !== 'combobox' || rest.listRole !== 'listbox' ) {
      record( scope, 'the search has a results surface to drive', false,
        `input role ${rest.role}, list role ${rest.listRole} - search interactions NOT run` );
    } else {
      /* TYPE A REAL QUERY. 'mumbai' matches on the ADDRESS of two rows whose names
         ('Bandra West', 'Andheri East') do not contain the string - so this also proves
         the match runs over the address, not just the name. */
      await page.click( '#vl-search' );
      await page.type( '#vl-search', 'mumbai', { delay: 30 } );
      await page.waitForTimeout( 150 );
      const open = await page.evaluate( () => {
        const i = document.getElementById( 'vl-search' );
        const l = document.getElementById( 'vl-search-results' );
        const rows = Array.prototype.slice.call( l.querySelectorAll( '[role="option"]' ) );
        const r = l.getBoundingClientRect();
        return {
          expanded: i.getAttribute( 'aria-expanded' ),
          count: rows.length,
          addrs: rows.map( el => el.querySelector( '.vl-search-option-addr' ).textContent ),
          heights: rows.map( el => +el.getBoundingClientRect().height.toFixed( 1 ) ),
          contentHeights: rows.map( el => el.clientHeight ),
          radius: getComputedStyle( l ).borderTopLeftRadius,
          borderWidth: getComputedStyle( l ).borderTopWidth,
          borderColor: getComputedStyle( l ).borderTopColor,
          listH: +r.height.toFixed( 1 ), listRight: +r.right.toFixed( 1 ), listBottom: +r.bottom.toFixed( 1 ),
          clientWidth: document.documentElement.clientWidth,
          activeDesc: i.getAttribute( 'aria-activedescendant' ),
          bg0: rows[ 0 ] && getComputedStyle( rows[ 0 ] ).backgroundColor,
          bg1: rows[ 1 ] && getComputedStyle( rows[ 1 ] ).backgroundColor,
          sel0: rows[ 0 ] && rows[ 0 ].getAttribute( 'aria-selected' ),
          id0: rows[ 0 ] && rows[ 0 ].id,
        };
      } );
      record( scope, 'typing opens the list', open.expanded === 'true', `${open.expanded}` );
      record( scope, 'a query returns a NON-EMPTY result list', open.count > 0, `${open.count} options` );
      record( scope, 'mumbai matches exactly 2 places', open.count === 2, `${open.count}` );
      record( scope, 'every match is in Mumbai (matched on address)',
        open.addrs.length > 0 && open.addrs.every( a => /Mumbai/i.test( a ) ), open.addrs.join( ' | ' ) );
      /* ON SCREEN, NOT MERELY IN THE DOM. The README's rule is that a could-not-tell is a
         failure, so the list's own rect is checked against the viewport - a list rendered
         at zero height, or off the right edge at 390, would otherwise pass as "present". */
      record( scope, 'list has real height', open.listH > 0, `${open.listH}px` );
      record( scope, 'list is not clipped horizontally', open.listRight <= open.clientWidth,
        `right ${open.listRight} vs ${open.clientWidth}` );
      record( scope, 'list is on screen vertically', open.listBottom > 0, `bottom ${open.listBottom}` );
      /* ROLE 7 geometry. 44px is the repo's chosen AAA 2.5.5 target-size bar.

         THE CONTENT BOX IS WHAT MUST MATCH, NOT THE BORDER BOX, and this assertion was
         written the wrong way round first and failed - usefully. MEASURED: row 1 is 60.98
         and row 2 is 61.98, while both clientHeights are 61. The 1px is the
         `.vl-search-option + .vl-search-option` divider, which only the second and
         subsequent rows carry, exactly as the flush hairline rows elsewhere in this file
         work. So "every row is the same height" is false by 1px BY DESIGN, and the real
         claim is that every row's content box is identical and the only variation is the
         divider. Asserting the border box would have forced either a fake uniformity or a
         deleted divider to make a wrong assertion pass. */
      record( scope, 'ROLE 7 rows share one content-box height',
        [ ...new Set( open.contentHeights ) ].length === 1, open.contentHeights.join( ', ' ) );
      record( scope, 'ROLE 7 border boxes vary only by the 1px divider',
        Math.max( ...open.heights ) - Math.min( ...open.heights ) <= 1, open.heights.join( ', ' ) );
      record( scope, 'ROLE 7 rows clear the 44px target bar', open.heights.every( h => h >= 44 ),
        open.heights.join( ', ' ) );
      record( scope, 'list radius is --r-field (10px)', open.radius === ROLE3.radius, open.radius );
      record( scope, 'list border is 1px #e5e7eb',
        open.borderWidth === ROLE3.borderWidth && open.borderColor === ROLE3.borderColor,
        `${open.borderWidth} ${open.borderColor}` );
      /* THE ACTIVE STATE IS VISIBLE, asserted as a colour DIFFERENCE between the active
         row and its neighbour rather than against a hardcoded lime - a state nobody can
         see is not a state, and comparing the two rows catches "both rows styled the
         same" which an equality check against #d1f470 would not. */
      record( scope, 'first row is active on open', open.sel0 === 'true', `${open.sel0}` );
      record( scope, 'aria-activedescendant names the active row', open.activeDesc === open.id0,
        `${open.activeDesc}` );
      record( scope, 'the active row is visibly distinct', open.bg0 !== open.bg1,
        `${open.bg0} vs ${open.bg1}` );

      /* ARROW KEYS. Down moves, Up returns, and a further Up CLAMPS at the top rather
         than wrapping to the bottom - SearchModal.tsx:149-153 is the model. */
      await page.keyboard.press( 'ArrowDown' );
      await page.waitForTimeout( 80 );
      const down = await page.evaluate( () => {
        const rows = document.querySelectorAll( '#vl-search-results [role="option"]' );
        return {
          activeDesc: document.getElementById( 'vl-search' ).getAttribute( 'aria-activedescendant' ),
          sel1: rows[ 1 ].getAttribute( 'aria-selected' ),
          id1: rows[ 1 ].id,
          bg1: getComputedStyle( rows[ 1 ] ).backgroundColor,
          bg0: getComputedStyle( rows[ 0 ] ).backgroundColor,
        };
      } );
      record( scope, 'ArrowDown moves aria-selected to row 2', down.sel1 === 'true', `${down.sel1}` );
      record( scope, 'ArrowDown moves aria-activedescendant', down.activeDesc === down.id1, `${down.activeDesc}` );
      record( scope, 'the active fill moved with it', down.bg1 !== down.bg0, `${down.bg1} vs ${down.bg0}` );
      await page.keyboard.press( 'ArrowUp' );
      await page.keyboard.press( 'ArrowUp' );
      await page.waitForTimeout( 80 );
      const clamped = await page.evaluate( () => {
        const rows = document.querySelectorAll( '#vl-search-results [role="option"]' );
        return {
          sel0: rows[ 0 ].getAttribute( 'aria-selected' ),
          activeDesc: document.getElementById( 'vl-search' ).getAttribute( 'aria-activedescendant' ),
          id0: rows[ 0 ].id,
        };
      } );
      record( scope, 'ArrowUp returns to row 1 and CLAMPS there',
        clamped.sel0 === 'true' && clamped.activeDesc === clamped.id0, `${clamped.activeDesc}` );

      /* ENTER COMMITS AND THE PAGE VISIBLY CHANGES. Compared against the strings CAPTURED
         from the active row, never against a hardcoded city, so the assertion survives an
         edit to VL_PLACES. */
      const chosen = await page.evaluate( () => {
        const row = document.querySelector( '#vl-search-results [aria-selected="true"]' );
        return {
          name: row.querySelector( '.vl-search-option-name' ).textContent,
          addr: row.querySelector( '.vl-search-option-addr' ).textContent,
        };
      } );
      await page.keyboard.press( 'Enter' );
      await page.waitForTimeout( 150 );
      const committed = await page.evaluate( () => {
        const l = document.getElementById( 'vl-search-results' );
        const t = s => { const el = document.querySelector( s ); return el ? el.textContent : null; };
        return {
          expanded: document.getElementById( 'vl-search' ).getAttribute( 'aria-expanded' ),
          rects: l.getClientRects().length,
          value: document.getElementById( 'vl-search' ).value,
          place: t( '.vl-place' ), addr: t( '.vl-place-addr' ),
          cardH: t( '.vl-map-preview .vl-card-h' ), small: t( '.vl-map-preview .vl-small' ),
        };
      } );
      record( scope, 'Enter closes the list', committed.expanded === 'false' && committed.rects === 0,
        `expanded ${committed.expanded}, ${committed.rects} rects` );
      record( scope, 'Enter writes the choice into the field', committed.value === chosen.name,
        `${committed.value}` );
      record( scope, 'selection updates the section heading', committed.place === chosen.name,
        `${committed.place}` );
      record( scope, 'selection updates the heading address', committed.addr === chosen.addr,
        `${committed.addr}` );
      record( scope, 'selection updates the map preview name', committed.cardH === chosen.name,
        `${committed.cardH}` );
      record( scope, 'selection updates the map preview address', committed.small === chosen.addr,
        `${committed.small}` );

      /* ESCAPE closes and leaves the committed selection alone. */
      await page.fill( '#vl-search', '' );
      await page.type( '#vl-search', 'beng', { delay: 30 } );
      await page.waitForTimeout( 150 );
      const beforeEsc = await page.evaluate( () => document.getElementById( 'vl-search' ).getAttribute( 'aria-expanded' ) );
      record( scope, 'a second query re-opens the list', beforeEsc === 'true', `${beforeEsc}` );
      await page.keyboard.press( 'Escape' );
      await page.waitForTimeout( 100 );
      const afterEsc = await page.evaluate( () => ( {
        expanded: document.getElementById( 'vl-search' ).getAttribute( 'aria-expanded' ),
        rects: document.getElementById( 'vl-search-results' ).getClientRects().length,
        place: document.querySelector( '.vl-place' ).textContent,
      } ) );
      record( scope, 'Escape closes the list', afterEsc.expanded === 'false' && afterEsc.rects === 0,
        `expanded ${afterEsc.expanded}` );
      record( scope, 'Escape does not undo the committed selection', afterEsc.place === chosen.name,
        `${afterEsc.place}` );

      /* NO MATCH reports a line that is NOT an option - it must not be selectable and must
         not be counted by the keyboard model. */
      await page.fill( '#vl-search', '' );
      await page.type( '#vl-search', 'zzzz', { delay: 20 } );
      await page.waitForTimeout( 150 );
      const noMatch = await page.evaluate( () => {
        const l = document.getElementById( 'vl-search-results' );
        const empty = l.querySelectorAll( '.vl-search-empty' );
        return {
          options: l.querySelectorAll( '[role="option"]' ).length,
          empties: empty.length,
          emptyRole: empty[ 0 ] ? empty[ 0 ].getAttribute( 'role' ) : 'missing',
        };
      } );
      record( scope, 'no-match renders zero options', noMatch.options === 0, `${noMatch.options}` );
      record( scope, 'no-match renders exactly one empty line', noMatch.empties === 1, `${noMatch.empties}` );
      record( scope, 'the empty line is not an option', noMatch.emptyRole === null, `${noMatch.emptyRole}` );

      /* THE MOUSE PATH reaches the same four nodes as the keyboard path. */
      await page.fill( '#vl-search', '' );
      await page.type( '#vl-search', 'kochi', { delay: 30 } );
      await page.waitForTimeout( 150 );
      const mouseChoice = await page.evaluate( () => {
        const row = document.querySelector( '#vl-search-results [role="option"]' );
        return {
          name: row.querySelector( '.vl-search-option-name' ).textContent,
          addr: row.querySelector( '.vl-search-option-addr' ).textContent,
        };
      } );
      await page.click( '#vl-search-results [role="option"]' );
      await page.waitForTimeout( 150 );
      const clicked = await page.evaluate( () => {
        const t = s => { const el = document.querySelector( s ); return el ? el.textContent : null; };
        return {
          place: t( '.vl-place' ), addr: t( '.vl-place-addr' ),
          cardH: t( '.vl-map-preview .vl-card-h' ), small: t( '.vl-map-preview .vl-small' ),
        };
      } );
      record( scope, 'clicking a row updates all four nodes',
        clicked.place === mouseChoice.name && clicked.addr === mouseChoice.addr
        && clicked.cardH === mouseChoice.name && clicked.small === mouseChoice.addr,
        `${clicked.place} / ${clicked.addr}` );

      /* RE-ASSERTED WITH A LIST OPEN, at both widths: an absolutely-positioned overlay is
         exactly the kind of thing that can push a document wider than its viewport.
         THE fill('') IS LOAD-BEARING. Without it this typed onto the end of the value the
         click above had just committed ('Panampilly Nagar'), giving
         'Panampilly Nagarnagar', which matches nothing - so the overflow assertion passed
         against a CLOSED list and proved nothing. That is why the companion assertion
         below counts the options: a geometry check on an empty overlay is a vacuous pass,
         and it is caught here by measuring that there was something to measure. */
      await page.fill( '#vl-search', '' );
      await page.type( '#vl-search', 'nagar', { delay: 20 } );
      await page.waitForTimeout( 150 );
      const openOverflow = await page.evaluate( () => ( {
        sw: document.documentElement.scrollWidth,
        cw: document.documentElement.clientWidth,
        options: document.querySelectorAll( '#vl-search-results [role="option"]' ).length,
      } ) );
      record( scope, 'no horizontal overflow with the list OPEN',
        openOverflow.sw === openOverflow.cw, `${openOverflow.sw} vs ${openOverflow.cw}` );
      record( scope, 'the open list has options to overflow with', openOverflow.options > 0,
        `${openOverflow.options}` );
    }

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
      /* Typed through the real input so the real handler opens the real list - a shot of
         a list forced open by setting a class would evidence nothing. */
      if ( a.type ) {
        await page.click( a.type.sel );
        await page.type( a.type.sel, a.type.text, { delay: 30 } );
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
