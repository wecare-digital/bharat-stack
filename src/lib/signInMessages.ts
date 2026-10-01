/**
 * The owner's section-6 sign-in message table, verbatim and in ONE place.
 *
 * WHY A SHARED SOURCE. These seven strings are approved copy: field-associated, non-enumerating,
 * and in the homepage palette with no red validation state. The sign-in page shows them; a test
 * asserts they exist verbatim and that the reachable ones render without a red computed colour.
 * Keeping them in a single module makes the approved wording auditable from both the page and the
 * test, so a drift in either cannot pass unnoticed.
 *
 * ON MISSING_CODE, WHICH IS PRESENT BUT NOT WIRED TO A REACHABLE STATE. "Include your country code,
 * like +91." is the approved wording for a missing country code. The sign-in field is DIVIDED
 * (PhoneField, from #175): its leading segment always carries a dial code, so the state this
 * message describes cannot occur through the UI - there is no input that produces it. The string is
 * kept here, exported and auditable, so the approved wording is present and the next person who
 * wires a code-entry control that CAN be left blank finds the sanctioned copy rather than inventing
 * one. It is deliberately NOT forced into a reachable code path just to make it render; doing so
 * would be a message no real state earns.
 *
 * ON NOT_ON_WHATSAPP, SIMILARLY RESERVED. "Use a WhatsApp number." is approved but must not render
 * today: the only send-failure signal the backend offers (502 send_failed) also covers a transient
 * Meta outage, so asserting the number is not on WhatsApp would be a confident wrong answer about
 * our own outage. It is kept here for when a provider recipient-not-found signal exists.
 *
 * NON-ENUMERATION. None of these distinguish a registered number from an unknown one - the same
 * string is shown for the same failure either way, so the sign-in door cannot be used to discover
 * who is a customer.
 */

/** Missing country code. Approved wording; see the note above on why it is not wired to a state. */
export const MISSING_CODE = 'Include your country code, like +91.';
/** Invalid number or format. */
export const BAD_NUMBER = 'Enter a valid number.';
/** Generic delivery failure, or unknown WhatsApp availability. */
export const CHECK_NUMBER = 'Couldn\u2019t send a code. Check your number.';
/** Provider temporary outage - our side, so it does not send the shopper to edit anything. */
export const TRY_LATER = 'Try again shortly.';
/** Invalid code, attempts remaining. */
export const BAD_CODE = 'Check your code.';
/** The challenge is no longer answerable. */
export const CODE_EXPIRED = 'Code expired. Send a new one.';
/** Send or guess limit reached. */
export const RATE_LIMITED = 'Wait before trying again.';
/** Reserved for provider evidence this page does not yet receive. See the note above. */
export const NOT_ON_WHATSAPP = 'Use a WhatsApp number.';

/**
 * The seven section-6 strings, in the owner's order. Exactly these seven, verbatim: the test asserts
 * the array equals the approved list so neither wording nor count can drift.
 */
export const SECTION_6_MESSAGES = [
  MISSING_CODE,
  BAD_NUMBER,
  CHECK_NUMBER,
  TRY_LATER,
  BAD_CODE,
  CODE_EXPIRED,
  RATE_LIMITED,
] as const;
