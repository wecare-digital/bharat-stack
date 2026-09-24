/**
 * Phase 7.3 — the flags, and the two module homes they gate.
 *
 * The property that matters most is the DEFAULT. A flag that defaults ON means a missing
 * env var in a new environment silently enables the thing the flag was protecting, which
 * is the opposite of what a safety switch is for. This project already has the inverse
 * lesson written down for `WA_LIVE_SMOKE_TEST`, where switching the flag ON *narrows*
 * sending — absence should fail toward the safe state too.
 *
 * The second property: a flagged-off page must explain itself rather than render a shell
 * of empty panels. An empty chart is indistinguishable from a chart showing zero, and
 * that ambiguity is the defect this whole phase has been removing.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';

vi.mock( 'next/router', () => ( {
  useRouter: () => ( { pathname: '/growth', query: {}, push: vi.fn(), isReady: true } ),
} ) );

import { featureFlags, allFlags } from '../config/featureFlags';
import GrowthPage from '../pages/growth/index';
import CommercePage from '../pages/commerce/index';
import inventory from '../content/integration-registry.json';
import { moduleHomes, getAllNavItems } from '../config/navigation';

const FLAGS_SRC = fs.readFileSync(
  path.resolve( __dirname, '../config/featureFlags.ts' ), 'utf8' );

describe( 'flags default OFF', () => {
  it( 'every flag is false with no env var set', () => {
    for ( const { name, enabled } of allFlags() ) {
      expect( enabled, `${name} must default to false` ).toBe( false );
    }
  } );

  it( 'only an explicit truthy string turns one on', () => {
    // Not a value test on the live flags — a test on the parser, so a future flag
    // cannot be added with looser semantics.
    expect( FLAGS_SRC ).toContain( "[ '1', 'true', 'yes', 'on' ].includes" );
  } );

  it( 'no flag here could be mistaken for a send flag', () => {
    const names = allFlags().map( ( f ) => f.name.toLowerCase() ).join( ' ' );
    for ( const banned of [ 'send', 'live', 'smoke', 'apply', 'routing' ] ) {
      expect( names ).not.toContain( banned );
    }
  } );

  it( 'says plainly that these gate a read-only surface', () => {
    expect( FLAGS_SRC ).toContain( 'read-only UI surface' );
    expect( FLAGS_SRC ).toContain( 'governance.py' );
  } );
} );

describe( 'the Growth home with the flag off', () => {
  it( 'explains why it is off instead of showing empty panels', () => {
    expect( featureFlags.growthModule ).toBe( false );
    render( <GrowthPage embedded /> );
    expect( screen.getByText( /Growth module is switched off/i ) ).toBeTruthy();
    // The reason, not just the state.
    expect( screen.getByText( /no recorded authorised read/i ) ).toBeTruthy();
    expect( screen.getByText( /NEXT_PUBLIC_ENABLE_GROWTH_MODULE/ ) ).toBeTruthy();
  } );

  it( 'still shows the real connection state, which is the useful part', () => {
    render( <GrowthPage embedded /> );
    // Three-state, from the generated registry snapshot — not a tick.
    expect( screen.getAllByText( /Not verified|Not connected/ ).length ).toBeGreaterThan( 0 );
  } );

  it( 'keeps provider names out of the page name and the tab labels', () => {
    render( <GrowthPage embedded /> );
    // The master prompt: "Use provider-neutral page names and confine exact provider
    // labels/IDs to authorized connection details." So the page is "Growth" and the tabs
    // are "Search presence" / "Advertising" — and "Google Ads" DOES appear, inside the
    // connection table, which is the authorised place. The first version of this test
    // asserted the name never appears anywhere and was simply wrong about the rule.
    expect( screen.getByText( 'Growth' ) ).toBeTruthy();
    for ( const tab of [ 'Connections', 'Search presence', 'Advertising' ] ) {
      expect( screen.getByText( tab ) ).toBeTruthy();
    }
    for ( const provider of [ 'Google Ads', 'Meta', 'Bing', 'Wix' ] ) {
      expect( screen.queryByRole( 'tab', { name: new RegExp( provider, 'i' ) } ) ).toBeNull();
    }
  } );
} );

describe( 'the Commerce home with the flag off', () => {
  it( 'gives a different reason from Growth, because it is a different reason', () => {
    expect( featureFlags.commerceModule ).toBe( false );
    render( <CommercePage embedded /> );
    expect( screen.getByText( /Commerce module is switched off/i ) ).toBeTruthy();
    // Off because the storefront is LIVE, not because it is unfinished.
    expect( screen.getByText( /Not because it is unfinished/i ) ).toBeTruthy();
  } );
} );

describe( 'the registry snapshot is real and honest', () => {
  it( 'has all eight providers', () => {
    expect( inventory.providers ).toHaveLength( 8 );
  } );

  it( 'claims nothing as VERIFIED, because nothing has been', () => {
    const verified = inventory.providers.filter(
      ( p: any ) => p.access === 'VERIFIED' );
    expect( verified ).toHaveLength( 0 );
  } );

  it( 'distinguishes a missing credential from an unverified scope', () => {
    const states = new Set( inventory.providers.map( ( p: any ) => p.access ) );
    expect( states.has( 'SCOPE_UNVERIFIED' ) ).toBe( true );
    expect( states.has( 'CREDENTIAL_ABSENT' ) ).toBe( true );
  } );

  it( 'carries an unblock for every provider that is not connected', () => {
    for ( const p of inventory.providers as any[] ) {
      if ( p.access === 'VERIFIED' ) continue;
      expect( p.unblock, `${p.key} has no unblock` ).toBeTruthy();
    }
  } );

  it( 'is timestamped, so a stale snapshot is visible', () => {
    expect( inventory.generatedAt ).toMatch( /^\d{4}-\d{2}-\d{2}T/ );
  } );
} );

describe( 'both homes are reachable', () => {
  it( 'are declared as module homes at their own routes', () => {
    const growth = moduleHomes.find( ( m ) => m.id === 'growth' );
    const commerce = moduleHomes.find( ( m ) => m.id === 'commerce' );
    expect( growth?.path ).toBe( '/growth' );
    expect( commerce?.path ).toBe( '/commerce' );
  } );

  it( 'appear in the navigation the command palette is built from', () => {
    const paths = getAllNavItems().map( ( i ) => i.path );
    // A flagged-off page that explains itself beats a 404, so it stays findable.
    expect( paths ).toContain( '/growth' );
    expect( paths ).toContain( '/commerce' );
  } );
} );
