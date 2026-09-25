/**
 * Locking and unlocking page scroll, for overlays that must not let the page move behind
 * them.
 *
 * WHY THIS EXISTS RATHER THAN `document.body.style.overflow = 'hidden'` AT EACH CALL SITE.
 *
 * That one-liner is the usual way to do this and it was correct here right up until the
 * scroll container moved. Layout.css used to put `height: 100%` and `overflow-y: auto` on
 * html AND body, which made BODY the element the page scrolled inside - so setting
 * `overflow: hidden` on body genuinely froze the page. That was two nested scrollers and a
 * bug in its own right: on a 320px phone the footer was pushed off the top of the screen
 * with 623px of blank space below it. Fixing it made the DOCUMENT the scroller again.
 *
 * At which point `body { overflow: hidden }` stops locking anything. It would have failed
 * silently - the overlay opens, looks right, and the page keeps scrolling behind it - and
 * the cause would have been three files away from the symptom. Both call sites are now
 * here so the pairing is written down once.
 *
 * BOTH ELEMENTS ARE SET, deliberately. html is the scroller today; body was yesterday.
 * Setting both costs nothing, works under either arrangement, and means a future change to
 * the scroll container cannot quietly break every overlay in the product again.
 *
 * WHAT THIS DOES NOT DO: compensate for the scrollbar. Hiding overflow on a desktop page
 * that had a visible scrollbar reclaims its width and shifts the layout sideways by a few
 * pixels. That is not addressed because this codebase styles scrollbars to 5px and
 * overlay-style on the platforms that support it, so the shift is not perceptible - and the
 * usual fix, padding the locked element by the scrollbar width, introduces its own jump on
 * the platforms where scrollbars are already overlaid.
 */

type Styled = { style: { overflow: string } } | null;

const targets = (): Styled[] =>
  typeof document === 'undefined' ? [] : [ document.documentElement, document.body ];

/** Freeze page scroll. Safe to call when already locked. */
export function lockScroll (): void {
  for ( const el of targets() ) {
    if ( el ) el.style.overflow = 'hidden';
  }
}

/**
 * Release page scroll.
 *
 * Clears the inline value rather than writing a literal back, so each element returns to
 * whatever the stylesheet says - html to `overflow-x: hidden` from Layout.css, body to
 * nothing. Writing `overflow = 'auto'` or `'visible'` instead would overwrite the
 * stylesheet permanently: on body, `overflow-x: visible` with the rest of the cascade is
 * how body became a second scroll container in the first place.
 */
export function unlockScroll (): void {
  for ( const el of targets() ) {
    if ( el ) el.style.overflow = '';
  }
}
