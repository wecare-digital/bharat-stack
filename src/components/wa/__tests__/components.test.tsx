import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge, QualityBadge, HealthStatusBadge } from '../badges';
import { MaskedPhone, maskTail, SecretField } from '../masked';
import { MetaErrorPanel } from '../MetaErrorPanel';
import { ValidationErrorList, WarningList } from '../lists';
import { FeatureFlagBadge } from '../badges';
import { buildCurl } from '../inputs';

describe( 'badges', () => {
    it( 'renders status text', () => {
        render( <StatusBadge status="APPROVED" /> );
        expect( screen.getByText( 'APPROVED' ) ).toBeInTheDocument();
    } );
    it( 'renders quality + health labels', () => {
        render( <><QualityBadge score="GREEN" /><HealthStatusBadge health="BLOCKED" /></> );
        expect( screen.getByText( /Quality: GREEN/ ) ).toBeInTheDocument();
        expect( screen.getByText( /Health: BLOCKED/ ) ).toBeInTheDocument();
    } );
    it( 'feature flag on/off', () => {
        render( <><FeatureFlagBadge name="WAF" enabled={ false } /></> );
        expect( screen.getByText( 'WAF: OFF' ) ).toBeInTheDocument();
    } );
} );

describe( 'masking', () => {
    it( 'maskTail keeps last 4', () => {
        expect( maskTail( '919900112233', 4 ) ).toBe( '91****2233' );
        expect( maskTail( 'abc' ) ).toBe( '***' );
    } );
    it( 'MaskedPhone hides by default', () => {
        render( <MaskedPhone value="919900112233" /> );
        expect( screen.getByText( '91****2233' ) ).toBeInTheDocument();
        expect( screen.queryByText( '919900112233' ) ).toBeNull();
    } );
    it( 'SecretField never shows raw value without reveal', () => {
        render( <SecretField label="Token" value="supersecret" /> );
        expect( screen.queryByText( 'supersecret' ) ).toBeNull();
    } );
} );

describe( 'MetaErrorPanel', () => {
    it( 'shows message, code and fbtrace_id', () => {
        render( <MetaErrorPanel error={ { error: { message: 'Bad param', code: 100, fbtrace_id: 'AbC123' } } } /> );
        expect( screen.getByText( 'Bad param' ) ).toBeInTheDocument();
        expect( screen.getByText( /code: 100/ ) ).toBeInTheDocument();
        expect( screen.getByText( 'AbC123' ) ).toBeInTheDocument();
    } );
} );

describe( 'validation lists', () => {
    it( 'renders errors and nothing when empty', () => {
        const { container, rerender } = render( <ValidationErrorList errors={ [ 'bad body', { message: 'bad btn', line_start: 3 } ] } /> );
        expect( screen.getByText( /bad body/ ) ).toBeInTheDocument();
        expect( screen.getByText( /bad btn \(line 3\)/ ) ).toBeInTheDocument();
        rerender( <ValidationErrorList errors={ [] } /> );
        expect( container.textContent ).toBe( '' );
    } );
    it( 'renders warnings', () => {
        render( <WarningList warnings={ [ '4+ buttons' ] } /> );
        expect( screen.getByText( /4\+ buttons/ ) ).toBeInTheDocument();
    } );
} );

describe( 'buildCurl', () => {
    it( 'builds a curl with masked token placeholder', () => {
        const cmd = buildCurl( { method: 'POST', url: 'https://x/y', body: { a: 1 } } );
        expect( cmd ).toContain( "curl -X POST 'https://x/y'" );
        expect( cmd ).toContain( 'Bearer $ACCESS_TOKEN' );
        expect( cmd ).toContain( '"a":1' );
    } );
} );
