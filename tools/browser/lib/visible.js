'use strict';

/**
 * One visibility predicate, installed into the page as `window.__visible`.
 *
 * WHY THIS EXISTS. Seven suites in this directory each grew their own "is it visible"
 * test and no two agree. Collected before this file was written:
 *
 *   pageaudit.js:118     r.width > 0 && r.height > 0
 *   contactcheck.js:214  rect + visibility + display + opacity
 *   devicecheck.js:88    rect + visibility + opacity
 *   sectioncheck.js:67   height + display + visibility
 *   hometree.js:79       (height && width) || position === 'absolute'
 *   closeprobe.js:236    display + visibility + opacity + height
 *
 * The weakest of those is a real defect, not a stylistic difference. `width > 0 &&
 * height > 0` is NOT visibility: an element inside a collapsed panel still has a box.
 * Measured on /grahak-os/, a check written that way reported **28** focusable elements
 * where **7** are reachable - the other 21 are links inside the closed nav panel. Used to
 * assert "every focusable control has a focus ring", it fails on 21 controls a visitor
 * cannot reach, and the honest result looks like a regression in the page.
 *
 * That is the README's own rule biting: decide what the measurement is actually
 * measuring before believing its verdict. A disagreement between suites means at most
 * one of them is right, and nobody can tell which from the output.
 *
 * WHAT IT CHECKS, and why each clause is needed rather than tidy:
 *
 *   - a non-empty box                 - zero-size elements paint nothing
 *   - visibility / display / opacity  - the element's own removal from paint
 *   - content-visibility: hidden      - skips rendering while keeping a box
 *   - offsetParent === null           - catches an ANCESTOR with display:none, which
 *                                       leaves the element's own computed display intact.
 *                                       Exempted for position:fixed, whose offsetParent
 *                                       is legitimately null.
 *   - an ancestor walk for opacity    - opacity does NOT inherit. An ancestor at
 *                                       opacity:0 renders nothing while every descendant
 *                                       still computes opacity:1. This is the clause the
 *                                       .anim defect on /grahak-os/ lived behind, so it
 *                                       is the one most worth keeping.
 *
 * WHAT IT DOES NOT CATCH, stated rather than implied:
 *
 *   - clipping. `max-height:0;overflow:hidden` on an ancestor leaves a child with a
 *     full-size rect that paints nowhere. Detecting it needs a rect intersection against
 *     every scroll/clip ancestor, which is a different and more expensive check.
 *   - occlusion. Something painted on top of the element. Use elementFromPoint for that,
 *     scrolling the target into view first - see the note in the README.
 *   - off-screen position. An element scrolled out of view is still visible in this
 *     sense. Compare rects against the viewport when that is what you mean.
 *
 * So `__visible` means "this element participates in paint", not "a visitor can see it
 * right now". Where a suite needs the stronger claim it should say so at the call site.
 */

/**
 * The predicate, as source. It is injected rather than imported because the suites pass
 * functions to page.evaluate, which serialises them - a require() here would not survive
 * the boundary.
 */
const VISIBLE_SOURCE = `
window.__visible = function ( el ) {
  if ( !el || el.nodeType !== 1 ) return false;

  var r = el.getBoundingClientRect();
  if ( r.width <= 0 || r.height <= 0 ) return false;
  if ( el.getClientRects().length === 0 ) return false;

  var s = getComputedStyle( el );
  if ( s.display === 'none' ) return false;
  if ( s.visibility === 'hidden' || s.visibility === 'collapse' ) return false;
  if ( parseFloat( s.opacity ) === 0 ) return false;
  if ( s.contentVisibility === 'hidden' ) return false;

  // An ancestor with display:none leaves this element's own computed display alone.
  // position:fixed has a null offsetParent while being perfectly visible.
  if ( el.offsetParent === null && s.position !== 'fixed' ) return false;

  // opacity and content-visibility do not inherit, so they need the walk. visibility
  // does inherit, but a descendant can set it back to visible, so it is re-checked.
  for ( var n = el.parentElement; n && n !== document.documentElement; n = n.parentElement ) {
    var cs = getComputedStyle( n );
    if ( cs.display === 'none' ) return false;
    if ( cs.visibility === 'hidden' && s.visibility !== 'visible' ) return false;
    if ( parseFloat( cs.opacity ) === 0 ) return false;
    if ( cs.contentVisibility === 'hidden' ) return false;
  }

  return true;
};
`;

/**
 * Define `window.__visible` for every navigation on this page.
 *
 * addInitScript rather than an evaluate after goto: it runs before the document's own
 * scripts and re-runs on each navigation, so a suite that visits 180 routes installs it
 * once. Call it after newPage() and before the first goto.
 *
 * @param {import('playwright-core').Page|import('playwright-core').BrowserContext} pageOrContext
 */
async function installVisible ( pageOrContext ) {
  await pageOrContext.addInitScript( VISIBLE_SOURCE );
}

module.exports = { VISIBLE_SOURCE, installVisible };
