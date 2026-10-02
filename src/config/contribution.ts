/**
 * BLOG CONTRIBUTION AMOUNTS, IN ONE PLACE - the Section 5 "Support this work" presets and the
 * bounds a custom amount is checked against, with a single definition so no amount is re-typed.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * The brief for the voluntary-contribution section on every blog post asks for suggested amounts
 * of 49, 99 and 199 rupees plus an "Other" custom option, and asks that those presets be "centrally
 * configurable rather than duplicating hard-coded amounts throughout the codebase". src/config/share.ts
 * is the precedent for that shape: one config module imported where needed, with a test
 * (ShareMeta.test.tsx there, BlogContribution.test.tsx here) holding the rendered values equal to
 * the ones declared here so the two cannot drift. Everything that renders or validates a
 * contribution amount - the BlogContribution component and its tests - reads THIS module. Nothing
 * re-states 49/99/199, 4900/9900/19900, 'INR', or the bounds anywhere else.
 *
 * CANONICAL UNIT IS INTEGER PAISE, NEVER RUPEES-AS-FLOAT
 * -----------------------------------------------------
 * The backend money core (amplify/functions/shared/lambda_utils/ecommerce/money.py and
 * checkout_pricing.py) is integer paise with Decimal rounding and refuses fractional paise; a
 * contribution request has to speak the same unit so the two halves cannot disagree about what
 * "99 rupees" means. So the presets are declared in paise - ₹49 = 4900 paise - and the only place
 * rupees appear is the display label, derived from paise by integer division, never the other way
 * round. A browser must never send a rupee float that the server then has to round.
 *
 * THE SERVER IS THE AUTHORITY ON THE ALLOWED RANGE - this is the load-bearing security note.
 * ------------------------------------------------------------------------------------------
 * The bounds below (CONTRIBUTION_MIN_PAISE / CONTRIBUTION_MAX_PAISE) exist for ONE purpose: a
 * quick, honest UX convenience so a reader typing a custom amount gets immediate feedback instead
 * of a round trip. They are NOT the trusted range. FEAT-004's BLOG_CONTRIBUTION backend
 * re-validates every amount server-side against its own authoritative bounds and mints the gateway
 * order from the server-decided value; the browser value is only a REQUEST. If this file and the
 * server ever disagree, the server wins and the client is simply offering a worse-but-safe hint.
 * Never treat a value that passed this client check as "approved to charge".
 */

/** The only currency contributions are taken in. ISO 4217, matching the Razorpay/Wix money core. */
export const CONTRIBUTION_CURRENCY = 'INR' as const;

/**
 * The suggested preset amounts, in INTEGER PAISE, in the order the brief lists them: ₹49, ₹99,
 * ₹199. Declared in paise because paise is the canonical unit (see the header note); the rupee
 * labels below are derived from these, so there is one source and the label can never claim a
 * different amount than the value sent.
 */
export const CONTRIBUTION_PRESETS_PAISE: readonly number[] = [ 4900, 9900, 19900 ] as const;

/**
 * CUSTOM-AMOUNT BOUNDS, in integer paise. A custom contribution must be at least ₹10 and at most
 * ₹1,00,000 (one lakh). These are the CLIENT-SIDE hint range only - FEAT-004's server re-validates
 * authoritatively and is the real gate (see the header note). The minimum keeps a contribution
 * above the convenience-fee floor; the maximum keeps a stray keystroke from proposing a six-figure
 * charge. Both are read by BlogContribution's validation and by its test, never re-typed.
 */
export const CONTRIBUTION_MIN_PAISE = 1000; // ₹10
export const CONTRIBUTION_MAX_PAISE = 10_000_000; // ₹1,00,000

/** One hundred paise to the rupee. Named so no magic 100 appears in the conversion helpers. */
export const PAISE_PER_RUPEE = 100;

/**
 * The rupee value of a paise amount, as an integer, for a DISPLAY label only. Preset amounts are
 * whole rupees by construction (4900/9900/19900), so this is exact for them. It is deliberately a
 * floor rather than a rounding: a label is never the authority on what is charged, and a custom
 * amount's trusted value stays in paise.
 */
export const paiseToRupees = ( paise: number ): number => Math.floor( paise / PAISE_PER_RUPEE );

/**
 * Convert a rupee amount a reader typed into integer paise. Returns null for anything that is not
 * a finite, non-negative number of whole-or-two-decimal rupees - the server re-checks regardless,
 * but a non-numeric or fractional-paise entry should never even be sent.
 *
 * Accepts up to two decimal places (so ₹49.50 -> 4950 paise) and rejects more, because a third
 * decimal is a sub-paise amount the money core refuses. Uses rounding on the scaled integer rather
 * than float multiplication to avoid 0.1-style representation drift.
 */
export const rupeesToPaise = ( rupees: number | string ): number | null => {
  const text = String( rupees ).trim();
  if ( text === '' ) return null;
  // A plain decimal number with at most two fractional digits, no sign, no exponent, no thousands
  // separators. Anything else is not a rupee amount a reader should be sending.
  if ( !/^\d+(\.\d{1,2})?$/.test( text ) ) return null;
  const value = Number( text );
  if ( !Number.isFinite( value ) ) return null;
  return Math.round( value * PAISE_PER_RUPEE );
};

/**
 * Is a paise amount within the client-side hint bounds? A UX convenience ONLY - the server is the
 * authority (see header). Rejects non-integers (fractional paise), NaN, and anything outside
 * [CONTRIBUTION_MIN_PAISE, CONTRIBUTION_MAX_PAISE].
 */
export const isAllowedContributionPaise = ( paise: number ): boolean =>
  Number.isInteger( paise )
  && paise >= CONTRIBUTION_MIN_PAISE
  && paise <= CONTRIBUTION_MAX_PAISE;

/** The purpose tag the backend keys a blog contribution under. Mirrors FEAT-004's BLOG_CONTRIBUTION. */
export const CONTRIBUTION_PURPOSE = 'BLOG_CONTRIBUTION' as const;
