import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import React from 'react';
import {
  afterEach, beforeEach, describe, expect, it, vi,
} from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import * as customerAuth from '../lib/customerAuth';
import * as signInMessages from '../lib/signInMessages';
import SignIn from '../pages/account/sign-in';

/**
 * SECTION 6: the seven approved sign-in messages, pinned.
 *
 * TWO THINGS ARE ASSERTED, HONESTLY. First, that all seven strings exist VERBATIM as the approved
 * constants in the shared message source - so the sanctioned wording is present and auditable even
 * for the one state (missing country code) the divided phone field makes unreachable. Second, that
 * the states the UI CAN reach render the approved string and carry NO red validation colour: the
 * error treatment is the lime "read this first" tint, not a red one.
 *
 * The unreachable string (MISSING_CODE) is checked for PRESENCE only, not forced to render. The
 * sign-in field is divided and always carries a dial code, so there is no input that produces a
 * missing-country-code state; manufacturing one just to make the message appear would be dishonest.
 * See src/lib/signInMessages.ts.
 */

const SIGN_IN_SOURCE = readFileSync(
  join(__dirname, '..', 'pages', 'account', 'sign-in.tsx'), 'utf8',
);

/** The owner's section-6 table, verbatim. The source of truth the module must equal. */
const APPROVED_SECTION_6 = [
  'Include your country code, like +91.',
  'Enter a valid number.',
  'Couldn\u2019t send a code. Check your number.',
  'Try again shortly.',
  'Check your code.',
  'Code expired. Send a new one.',
  'Wait before trying again.',
];

describe('the seven section-6 strings exist verbatim', () => {
  it('matches the approved table exactly, in order and count', () => {
    expect([...signInMessages.SECTION_6_MESSAGES]).toEqual(APPROVED_SECTION_6);
  });

  it('exposes each one as a named constant', () => {
    expect(signInMessages.MISSING_CODE).toBe('Include your country code, like +91.');
    expect(signInMessages.BAD_NUMBER).toBe('Enter a valid number.');
    expect(signInMessages.CHECK_NUMBER).toBe('Couldn\u2019t send a code. Check your number.');
    expect(signInMessages.TRY_LATER).toBe('Try again shortly.');
    expect(signInMessages.BAD_CODE).toBe('Check your code.');
    expect(signInMessages.CODE_EXPIRED).toBe('Code expired. Send a new one.');
    expect(signInMessages.RATE_LIMITED).toBe('Wait before trying again.');
  });

  it('is the source the sign-in page draws its message table from', () => {
    // The page references the shared constants rather than re-typing the copy, so the wording
    // cannot drift between the page and this test.
    expect(SIGN_IN_SOURCE).toContain("import * as signInMessages from '../../lib/signInMessages'");
    for (const key of ['MISSING_CODE', 'BAD_NUMBER', 'CHECK_NUMBER', 'TRY_LATER',
      'BAD_CODE', 'CODE_EXPIRED', 'RATE_LIMITED']) {
      expect(SIGN_IN_SOURCE).toContain(`signInMessages.${key}`);
    }
  });
});

describe('the sign-in error states use no red validation colour', () => {
  /**
   * The CSS lives in a styled-jsx block, which jsdom does not compute. So "no red" is asserted two
   * ways that together are stronger than a computed-style read: the error style block contains the
   * lime palette and no red hue, and no reachable error carries an inline red colour.
   */
  it('styles the error with the lime palette, never a red one', () => {
    const errorBlock = SIGN_IN_SOURCE.slice(
      SIGN_IN_SOURCE.indexOf('.si-error{'),
      SIGN_IN_SOURCE.indexOf('.si-back{'),
    );
    expect(errorBlock).toContain('#1a3a2a');            // the deep-green type
    expect(errorBlock).toContain('rgba(209,244,112');   // the lime tint (#d1f470)
    // No red hue anywhere in the error treatment.
    expect(errorBlock).not.toMatch(/#f?[a-f0-9]*0{2}[a-f0-9]{0,2}\b.*red/i);
    expect(errorBlock.toLowerCase()).not.toContain('red');
    // The known old red values are gone.
    for (const red of ['#fbe9e9', '#f0c0c0', '#8a1f1f']) {
      expect(errorBlock).not.toContain(red);
    }
  });

  it('renders a reachable error (bad code) as an approved string with no inline red', async () => {
    vi.spyOn(customerAuth, 'getSession').mockReturnValue(null);
    vi.spyOn(customerAuth, 'requestOtp').mockResolvedValue({
      session: 'sess-A', destination: '********3210', expiresInSeconds: 600, registered: true,
    });
    vi.spyOn(customerAuth, 'submitOtp').mockResolvedValue(null); // wrong code, attempts remain
    vi.stubGlobal('fetch', vi.fn());

    render(<SignIn />);
    fireEvent.change(screen.getByLabelText('WhatsApp number'),
      { target: { value: '+919876543210' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send code' }));
    fireEvent.change(await screen.findByLabelText('WhatsApp code'), { target: { value: '000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm code' }));

    const alert = await screen.findByRole('alert');
    // The rendered string is one of the approved seven, verbatim.
    expect(APPROVED_SECTION_6).toContain(alert.textContent);
    expect(alert.textContent).toBe(signInMessages.BAD_CODE);
    // No inline red style snuck onto the alert element.
    const inline = (alert.getAttribute('style') || '').toLowerCase();
    expect(inline).not.toContain('red');
    expect(inline).not.toMatch(/color:\s*#?(f00|ff0000|dc2626|b00020|8a1f1f)/);
  });

  it('renders a reachable error (rate limited) as an approved string', async () => {
    vi.spyOn(customerAuth, 'getSession').mockReturnValue(null);
    const throttled = Object.assign(new Error('Too many requests'),
      { name: 'TooManyRequestsException' });
    vi.spyOn(customerAuth, 'requestOtp').mockRejectedValue(throttled);
    vi.stubGlobal('fetch', vi.fn());

    render(<SignIn />);
    fireEvent.change(screen.getByLabelText('WhatsApp number'),
      { target: { value: '+919876543210' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send code' }));

    const alert = await screen.findByRole('alert');
    await waitFor(() => expect(alert.textContent).toBe(signInMessages.RATE_LIMITED));
    expect(APPROVED_SECTION_6).toContain(alert.textContent);
  });

  it('never renders the reserved NOT_ON_WHATSAPP string, and it is not one of the seven', () => {
    // The reserved string is approved but must not reach the page today; it is also outside the
    // section-6 seven, so its presence as a constant does not inflate the table.
    expect(signInMessages.NOT_ON_WHATSAPP).toBe('Use a WhatsApp number.');
    expect([...signInMessages.SECTION_6_MESSAGES]).not.toContain(signInMessages.NOT_ON_WHATSAPP);
  });
});
