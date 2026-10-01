/**
 * Country dial codes, in one place.
 *
 * MOVED HERE RATHER THAN COPIED. This exact list already existed as a `COUNTRY_CODES` literal
 * inside src/pages/workspace/contacts/index.tsx, which is a workspace page a shopper never sees.
 * The public sign-in field needs the same twenty entries, and a second literal would have been two
 * lists to keep in step - the kind of duplication that ends with the workspace offering a code the
 * storefront refuses. The contacts page now imports from here.
 *
 * ORDER IS DELIBERATE AND NOT ALPHABETICAL. India is first because it is the store's market, and
 * the rest follow the order the contacts page already used. A select whose first option is the
 * common answer is faster than one that opens on Australia.
 *
 * NOT A VALIDATION SOURCE. Nothing here decides whether a number is real - that is
 * customerAuth.normaliseMobile(), which has to agree with the backend byte for byte. These are the
 * prefixes a shopper can pick from, nothing more.
 */

export interface DialCode {
  /** The dial code with its leading plus, e.g. "+91". Display AND value. */
  code: string;
  /** Country name, as a shopper would recognise it. Translatable text when rendered. */
  country: string;
}

export const DIAL_CODES: readonly DialCode[] = [
  { code: '+91', country: 'India' }, { code: '+1', country: 'USA/Canada' }, { code: '+44', country: 'UK' },
  { code: '+61', country: 'Australia' }, { code: '+971', country: 'UAE' }, { code: '+966', country: 'Saudi Arabia' },
  { code: '+65', country: 'Singapore' }, { code: '+60', country: 'Malaysia' }, { code: '+49', country: 'Germany' },
  { code: '+33', country: 'France' }, { code: '+81', country: 'Japan' }, { code: '+86', country: 'China' },
  { code: '+82', country: 'South Korea' }, { code: '+55', country: 'Brazil' }, { code: '+27', country: 'South Africa' },
  { code: '+234', country: 'Nigeria' }, { code: '+254', country: 'Kenya' }, { code: '+62', country: 'Indonesia' },
  { code: '+63', country: 'Philippines' }, { code: '+7', country: 'Russia' },
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
