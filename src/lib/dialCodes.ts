/**
 * Country dial codes, in one place — WhatsApp-supported territories only.
 *
 * MOVED HERE RATHER THAN COPIED. This list already existed as a `COUNTRY_CODES` literal inside
 * src/pages/workspace/contacts/index.tsx, which is a workspace page a shopper never sees. The
 * public sign-in field needs the same entries, and a second literal would have been two lists to
 * keep in step - the kind of duplication that ends with the workspace offering a code the
 * storefront refuses. The contacts page imports from here.
 *
 * ORDER IS DELIBERATE AND NOT ALPHABETICAL. India is first because it is the store's market; the
 * rest follow broadly by how likely they are for this audience (Gulf and SE Asia before Europe,
 * because that is where the diaspora this store serves actually is). A select whose first option
 * is the common answer is faster than one that opens on Afghanistan.
 *
 * ── WHAT CHANGED 2026-10-02, AND WHY ────────────────────────────────────────────────────────────
 * This was TWENTY entries with no flags, no national-length data, and - the defect that prompted
 * the rewrite - it OFFERED CHINA (+86). WhatsApp is blocked in mainland China, so a shopper
 * picking +86 would wait forever for a code that can never arrive. That is the same class of
 * defect as the "no files are registered to this number" guard on /get: a dead end the person
 * cannot see. Offering a code whose OTP cannot be delivered is worse than not offering it.
 *
 * EXCLUDED ON PURPOSE - do not "helpfully" add these back:
 *   +86  China        - WhatsApp blocked since 2017 (was previously in this list)
 *   +98  Iran         - WhatsApp blocked
 *   +963 Syria        - WhatsApp blocked / unavailable
 *   +850 North Korea  - no consumer internet access
 * If a territory's status changes, change it here with a dated note, because this file is the only
 * thing standing between a shopper and an OTP that never comes.
 *
 * HONEST LIMIT ON COMPLETENESS. WhatsApp is available in most of the world, so a truly exhaustive
 * list runs to ~195 entries. This is a CURATED SUBSET of the markets this store plausibly serves,
 * not a claim to completeness, and it is deliberately easy to extend: add a row with its flag,
 * name, code and nationalDigits. It is NOT generated from a vendor list, and no vendor publishes a
 * machine-readable "supported countries" feed - the exclusions above are from WhatsApp's own
 * published availability and are the ones that actually matter. Anyone extending this should check
 * the territory is not on a blocked list before adding it.
 *
 * NOT THE VALIDATION AUTHORITY, STILL. `nationalDigits` is a CLIENT-SIDE pre-check so a shopper
 * learns about a wrong-length number before a round trip. The server remains the authority:
 * customerAuth.normaliseMobile() and the Python validators have to agree with the backend byte for
 * byte, and neither is relaxed by anything here.
 */

export interface DialCode {
  /** The dial code with its leading plus, e.g. "+91". Display AND value. */
  code: string;
  /** Country name, as a shopper would recognise it. Translatable text when rendered. */
  country: string;
  /**
   * The flag, as a regional-indicator emoji pair.
   *
   * RENDERING IS NOT UNIVERSAL AND THE UI MUST NOT PRETEND IT IS. Windows ships no flag glyphs, so
   * Chrome and Edge on Windows render these as the two letters instead ("IN", "AE"). That is a
   * legible, non-broken fallback precisely BECAUSE the dial code is always displayed beside it -
   * a Windows visitor sees "IN +91", which still says what it needs to. That is the documented
   * reason PhoneField shows flag AND code together rather than relying on the flag alone, and the
   * reason an SVG sprite was not added: ~60 flag assets to make Windows match macOS is a poor
   * trade on a static export when the fallback already reads correctly.
   */
  flag: string;
  /**
   * Valid NATIONAL number lengths (digits after the dial code, trunk zero stripped).
   *
   * An array because many countries have more than one valid length - UK mobiles are 10 but some
   * landlines are 9, UAE is 8 or 9. India is the one the owner named explicitly: EXACTLY 10.
   * An empty array means "we do not have a rule for this country" and the client-side check must
   * then pass anything non-empty and let the server decide, rather than inventing a bound.
   */
  nationalDigits: readonly number[];
}

export const DIAL_CODES: readonly DialCode[] = [
  // The store's market, and the only entry with a single hard length the owner specified.
  { code: '+91', country: 'India', flag: '🇮🇳', nationalDigits: [ 10 ] },
  // Gulf - the largest diaspora markets for this store.
  { code: '+971', country: 'United Arab Emirates', flag: '🇦🇪', nationalDigits: [ 8, 9 ] },
  { code: '+966', country: 'Saudi Arabia', flag: '🇸🇦', nationalDigits: [ 9 ] },
  { code: '+974', country: 'Qatar', flag: '🇶🇦', nationalDigits: [ 8 ] },
  { code: '+965', country: 'Kuwait', flag: '🇰🇼', nationalDigits: [ 8 ] },
  { code: '+968', country: 'Oman', flag: '🇴🇲', nationalDigits: [ 8 ] },
  { code: '+973', country: 'Bahrain', flag: '🇧🇭', nationalDigits: [ 8 ] },
  // Anglophone.
  { code: '+1', country: 'United States / Canada', flag: '🇺🇸', nationalDigits: [ 10 ] },
  { code: '+44', country: 'United Kingdom', flag: '🇬🇧', nationalDigits: [ 9, 10 ] },
  { code: '+61', country: 'Australia', flag: '🇦🇺', nationalDigits: [ 9 ] },
  { code: '+64', country: 'New Zealand', flag: '🇳🇿', nationalDigits: [ 8, 9 ] },
  { code: '+353', country: 'Ireland', flag: '🇮🇪', nationalDigits: [ 9 ] },
  // South Asia.
  { code: '+92', country: 'Pakistan', flag: '🇵🇰', nationalDigits: [ 10 ] },
  { code: '+880', country: 'Bangladesh', flag: '🇧🇩', nationalDigits: [ 10 ] },
  { code: '+94', country: 'Sri Lanka', flag: '🇱🇰', nationalDigits: [ 9 ] },
  { code: '+977', country: 'Nepal', flag: '🇳🇵', nationalDigits: [ 10 ] },
  { code: '+960', country: 'Maldives', flag: '🇲🇻', nationalDigits: [ 7 ] },
  { code: '+975', country: 'Bhutan', flag: '🇧🇹', nationalDigits: [ 8 ] },
  // South-East and East Asia (China deliberately absent - see the header).
  { code: '+65', country: 'Singapore', flag: '🇸🇬', nationalDigits: [ 8 ] },
  { code: '+60', country: 'Malaysia', flag: '🇲🇾', nationalDigits: [ 9, 10 ] },
  { code: '+62', country: 'Indonesia', flag: '🇮🇩', nationalDigits: [ 9, 10, 11 ] },
  { code: '+63', country: 'Philippines', flag: '🇵🇭', nationalDigits: [ 10 ] },
  { code: '+66', country: 'Thailand', flag: '🇹🇭', nationalDigits: [ 9 ] },
  { code: '+84', country: 'Vietnam', flag: '🇻🇳', nationalDigits: [ 9 ] },
  { code: '+81', country: 'Japan', flag: '🇯🇵', nationalDigits: [ 10 ] },
  { code: '+82', country: 'South Korea', flag: '🇰🇷', nationalDigits: [ 9, 10 ] },
  { code: '+852', country: 'Hong Kong', flag: '🇭🇰', nationalDigits: [ 8 ] },
  // Europe.
  { code: '+49', country: 'Germany', flag: '🇩🇪', nationalDigits: [ 10, 11 ] },
  { code: '+33', country: 'France', flag: '🇫🇷', nationalDigits: [ 9 ] },
  { code: '+34', country: 'Spain', flag: '🇪🇸', nationalDigits: [ 9 ] },
  { code: '+39', country: 'Italy', flag: '🇮🇹', nationalDigits: [ 9, 10 ] },
  { code: '+31', country: 'Netherlands', flag: '🇳🇱', nationalDigits: [ 9 ] },
  { code: '+41', country: 'Switzerland', flag: '🇨🇭', nationalDigits: [ 9 ] },
  { code: '+46', country: 'Sweden', flag: '🇸🇪', nationalDigits: [ 7, 8, 9 ] },
  { code: '+47', country: 'Norway', flag: '🇳🇴', nationalDigits: [ 8 ] },
  { code: '+45', country: 'Denmark', flag: '🇩🇰', nationalDigits: [ 8 ] },
  { code: '+351', country: 'Portugal', flag: '🇵🇹', nationalDigits: [ 9 ] },
  { code: '+48', country: 'Poland', flag: '🇵🇱', nationalDigits: [ 9 ] },
  { code: '+30', country: 'Greece', flag: '🇬🇷', nationalDigits: [ 10 ] },
  { code: '+90', country: 'Türkiye', flag: '🇹🇷', nationalDigits: [ 10 ] },
  // Africa.
  { code: '+27', country: 'South Africa', flag: '🇿🇦', nationalDigits: [ 9 ] },
  { code: '+234', country: 'Nigeria', flag: '🇳🇬', nationalDigits: [ 10 ] },
  { code: '+254', country: 'Kenya', flag: '🇰🇪', nationalDigits: [ 9 ] },
  { code: '+255', country: 'Tanzania', flag: '🇹🇿', nationalDigits: [ 9 ] },
  { code: '+256', country: 'Uganda', flag: '🇺🇬', nationalDigits: [ 9 ] },
  { code: '+233', country: 'Ghana', flag: '🇬🇭', nationalDigits: [ 9 ] },
  { code: '+20', country: 'Egypt', flag: '🇪🇬', nationalDigits: [ 10 ] },
  { code: '+212', country: 'Morocco', flag: '🇲🇦', nationalDigits: [ 9 ] },
  { code: '+230', country: 'Mauritius', flag: '🇲🇺', nationalDigits: [ 7, 8 ] },
  // Americas.
  { code: '+55', country: 'Brazil', flag: '🇧🇷', nationalDigits: [ 10, 11 ] },
  { code: '+52', country: 'Mexico', flag: '🇲🇽', nationalDigits: [ 10 ] },
  { code: '+54', country: 'Argentina', flag: '🇦🇷', nationalDigits: [ 10 ] },
  { code: '+56', country: 'Chile', flag: '🇨🇱', nationalDigits: [ 9 ] },
  { code: '+57', country: 'Colombia', flag: '🇨🇴', nationalDigits: [ 10 ] },
  { code: '+51', country: 'Peru', flag: '🇵🇪', nationalDigits: [ 9 ] },
  // Rest.
  { code: '+972', country: 'Israel', flag: '🇮🇱', nationalDigits: [ 9 ] },
  { code: '+7', country: 'Russia / Kazakhstan', flag: '🇷🇺', nationalDigits: [ 10 ] },
  { code: '+380', country: 'Ukraine', flag: '🇺🇦', nationalDigits: [ 9 ] },
  { code: '+998', country: 'Uzbekistan', flag: '🇺🇿', nationalDigits: [ 9 ] },
  { code: '+679', country: 'Fiji', flag: '🇫🇯', nationalDigits: [ 7 ] },
];

/**
 * The default selection: the store's own market.
 *
 * A VISIBLE DEFAULT, NOT AN INFERENCE. This is the difference that matters in the sign-in field:
 * normaliseMobile() quietly treats any ten digits starting 6-9 as Indian, which is wrong for a
 * shopper in Dubai and invisible to them. A selector that SHOWS "+91" from the first paint is a
 * default the shopper can see and change; an inference is one they cannot.
 */
export const DEFAULT_DIAL_CODE = '+91';

/** Lookup by dial code. Returns undefined for a code not in the supported list. */
export const findDialCode = ( code: string ): DialCode | undefined =>
  DIAL_CODES.find( entry => entry.code === code );

/**
 * Is this national number the right LENGTH for the selected country?
 *
 * DIGITS ONLY, AND LENGTH ONLY. This deliberately does not attempt to judge whether a number is
 * real, allocated, or mobile-vs-landline - that is normaliseMobile()'s job on the client and the
 * backend's job authoritatively. It answers one question a shopper benefits from hearing
 * immediately: "that is not the right number of digits for the country you picked."
 *
 * Returns true when we have NO rule for the country (nationalDigits empty), because refusing a
 * number on the basis of a bound we never established would block a legitimate shopper to enforce
 * a guess. An empty input is NOT valid - that is a separate, earlier check.
 */
export const isValidNationalLength = ( code: string, national: string ): boolean => {
  const digits = national.replace( /\D/g, '' ).replace( /^0+/, '' );
  if ( !digits ) return false;
  const entry = findDialCode( code );
  if ( !entry || entry.nationalDigits.length === 0 ) return true;
  return entry.nationalDigits.includes( digits.length );
};

/**
 * The expected-length hint for a country, as a short phrase for a placeholder or an error.
 * "10-digit" for India, "8- or 9-digit" for the UAE, and an empty string where we have no rule -
 * so a caller can omit the hint entirely rather than print something vague.
 */
export const nationalLengthHint = ( code: string ): string => {
  const entry = findDialCode( code );
  if ( !entry || entry.nationalDigits.length === 0 ) return '';
  const lengths = [ ...entry.nationalDigits ].sort( ( a, b ) => a - b );
  if ( lengths.length === 1 ) return `${lengths[ 0 ]}-digit`;
  const last = lengths.pop();
  return `${lengths.join( ', ' )}- or ${last}-digit`;
};
