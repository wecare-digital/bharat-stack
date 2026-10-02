import React, { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import PhoneField from '../components/PhoneField';
import { isValidNationalLength } from '../lib/dialCodes';

const Harness = () => {
  const [ dialCode, setDialCode ] = useState( '+91' );
  const [ number, setNumber ] = useState( '' );
  return (
    <PhoneField
      id="phone"
      dialCode={ dialCode }
      onDialCodeChange={ setDialCode }
      number={ number }
      onNumberChange={ setNumber }
    />
  );
};

describe( 'PhoneField searchable calling code', () => {
  it( 'uses a search input instead of a native country select', () => {
    const { container } = render( <Harness /> );
    expect( container.querySelector( 'select.pf-code' ) ).toBeNull();
    const code = screen.getByRole( 'searchbox', { name: 'Calling code' } ) as HTMLInputElement;
    expect( code.value ).toBe( '+91' );
  } );

  it( 'accepts digits with or without plus and resolves only supported codes', () => {
    render( <Harness /> );
    const code = screen.getByRole( 'searchbox', { name: 'Calling code' } ) as HTMLInputElement;

    fireEvent.change( code, { target: { value: '971' } } );
    expect( code.value ).toBe( '+971' );

    fireEvent.change( code, { target: { value: '+44' } } );
    expect( code.value ).toBe( '+44' );
  } );

  it( 'does not commit an unsupported code and restores the last valid code on blur', () => {
    render( <Harness /> );
    const code = screen.getByRole( 'searchbox', { name: 'Calling code' } ) as HTMLInputElement;

    fireEvent.change( code, { target: { value: '999' } } );
    expect( code.value ).toBe( '+999' );
    expect( code.getAttribute( 'aria-invalid' ) ).toBe( 'true' );

    fireEvent.blur( code );
    expect( code.value ).toBe( '+91' );
  } );

  it( 'shows no country names in the control', () => {
    const { container } = render( <Harness /> );
    expect( container.textContent ).not.toMatch( /India|United Arab Emirates|United Kingdom/ );
  } );

  it( 'keeps the explicit India ten-digit national validation rule', () => {
    expect( isValidNationalLength( '+91', '9876543210' ) ).toBe( true );
    expect( isValidNationalLength( '+91', '987654321' ) ).toBe( false );
    expect( isValidNationalLength( '+91', '98765432101' ) ).toBe( false );
  } );
} );
