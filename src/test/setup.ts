import '@testing-library/jest-dom/vitest';

/**
 * jsdom does not implement window.matchMedia, and calling it throws
 * "window.matchMedia is not a function" rather than returning undefined.
 *
 * Any component that gates animation on (prefers-reduced-motion: reduce) therefore
 * crashes on mount under test. That is a jsdom gap, not a bug in the page: the API
 * is universally available in real browsers. It stayed hidden because the VayuLok
 * page, which has gated its headline rotation this way from the start, has no test
 * of its own - the Home page rotation was the first one to be asserted on.
 *
 * Defaults to matches:false, i.e. "motion is allowed", so tests exercise the
 * animated path. A test that needs the reduced-motion branch should override this
 * per-test with vi.spyOn(window, 'matchMedia').
 */
if ( typeof window !== 'undefined' && typeof window.matchMedia !== 'function' )
{
  Object.defineProperty( window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: ( query: string ): MediaQueryList => ( {
      media: query,
      matches: false,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      // Deprecated pair, still called by some libraries.
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    } as unknown as MediaQueryList ),
  } );
}
