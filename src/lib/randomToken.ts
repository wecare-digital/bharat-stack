/**
 * A short, unguessable token for client-generated identifiers.
 *
 * WHY THIS EXISTS. `FloatingAgent.tsx` and `InternalChatTab.tsx` both built their
 * conversation key as
 *
 *     `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
 *
 * and CodeQL flagged both as `js/insecure-randomness`. That is not a false positive
 * dressed up as one: the value is sent to the agent backend as the conversation
 * identifier, `Date.now()` is public, and `Math.random()` is a seeded PRNG whose
 * output V8 makes no unpredictability claim about — so the search space is far smaller
 * than the 9 characters suggest, and guessing one lets a visitor address another
 * visitor's session.
 *
 * `crypto.getRandomValues` rather than `crypto.randomUUID`, for two reasons:
 * `randomUUID` requires a secure context and returns a fixed 36-character shape,
 * while this keeps the short id the two call sites already use and works wherever
 * `crypto` exists. Both are in `window.crypto` in every browser this app supports.
 *
 * The fallback is deliberately NOT `Math.random()`. Falling back to the weak source
 * would reintroduce exactly the finding while making it harder to see, so a missing
 * `crypto` throws instead: an id that cannot be generated safely should fail loudly
 * rather than quietly become guessable.
 */

const ALPHABET = 'abcdefghijklmnopqrstuvwxyz0123456789';

export function randomToken ( length = 9 ): string {
  const source = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined;
  if ( !source?.getRandomValues ) {
    throw new Error(
      'randomToken: crypto.getRandomValues is unavailable. Refusing to fall back to ' +
      'Math.random(), which is not unpredictable.'
    );
  }

  const bytes = new Uint8Array( length );
  source.getRandomValues( bytes );

  // Rejection-free mapping is not needed here: 256 % 36 leaves a bias of under 1.4%
  // per character, which does not matter for an identifier whose only requirement is
  // that it cannot be guessed or enumerated. It would matter for a key or a nonce,
  // and this helper is not for those.
  let out = '';
  for ( let i = 0; i < length; i += 1 ) {
    out += ALPHABET[ bytes[ i ] % ALPHABET.length ];
  }
  return out;
}

/**
 * True when `url` is safe to place in an `href`.
 *
 * `js/xss-through-dom` on `calling.tsx`: the IVR URL is typed by an operator and
 * rendered straight into `<a href={ivrUrl}>`. `javascript:alert(1)` in an href
 * executes on click, so a stored value becomes script. Only http and https pass;
 * anything else — `javascript:`, `data:`, `vbscript:`, a bare `//host` — does not.
 */
export function isSafeHttpUrl ( url: string ): boolean {
  if ( !url || typeof url !== 'string' ) return false;
  try {
    const parsed = new URL( url, 'https://wecare.digital' );
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch {
    return false;
  }
}
