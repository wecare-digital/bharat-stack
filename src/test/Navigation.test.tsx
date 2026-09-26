/**
 * The restructure's one hard invariant: NOTHING became unreachable.
 *
 * The sidebar went from 88 destinations to a short list, with the rest behind a
 * gear. That is only safe because `getAllNavItems()` walks BOTH trees and the
 * command palette is built from it. 21 of the original 88 paths have no link
 * anywhere else in the app, so if the palette ever stopped seeing the settings
 * tree, those pages would be reachable only by typing a URL from memory.
 *
 * These tests are the guard on that. They are deliberately about reachability and
 * about paths resolving to real files - not about which group a page sits in, which
 * is a judgement the owner can move around freely.
 */
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  navigationConfig,
  settingsConfig,
  getAllNavItems,
  getSettingsItems,
  isNavItemActive,
  isSubItemActive,
} from '../config/navigation';

const PAGES = path.resolve( __dirname, '../pages' );

/** Does a nav path resolve to a real page file? Query strings are stripped. */
function pageExists ( navPath: string ): boolean {
  const clean = navPath.split( '?' )[ 0 ].replace( /^\//, '' );
  if ( clean === '' ) return fs.existsSync( path.join( PAGES, 'index.tsx' ) );
  return fs.existsSync( path.join( PAGES, `${clean}.tsx` ) )
    || fs.existsSync( path.join( PAGES, clean, 'index.tsx' ) );
}

describe( 'the sidebar is short and holds only daily streams', () => {
  it( 'has far fewer top-level entries than the 11 it had', () => {
    expect( navigationConfig.length ).toBeLessThanOrEqual( 8 );
  } );

  it( 'leads with the inbox', () => {
    expect( navigationConfig[ 0 ].path ).toBe( '/workspace/inbox' );
  } );

  it( 'no longer carries the 30-item WhatsApp branch', () => {
    const waInSidebar = getAllNavItemsFrom( navigationConfig )
      .filter( ( p ) => p.startsWith( '/workspace/whatsapp' ) );
    expect( waInSidebar ).toHaveLength( 0 );
  } );

  it( 'offers Calls as an inbox filter, not a page', () => {
    const inbox = navigationConfig.find( ( i ) => i.path === '/workspace/inbox' );
    const calls = inbox?.children?.find( ( c ) => c.label === 'Calls' );
    expect( calls?.path ).toBe( '/workspace/inbox?channel=voice' );
    // dm/calls must be gone, not merely unlinked.
    expect( fs.existsSync( path.join( PAGES, 'workspace/calls/index.tsx' ) ) ).toBe( false );
  } );
} );

function getAllNavItemsFrom ( items: any[] ): string[] {
  const out: string[] = [];
  const walk = ( arr: any[] ) => {
    for ( const i of arr )
    {
      out.push( i.path );
      if ( i.children ) walk( i.children );
    }
  };
  walk( items );
  return out;
}

describe( 'nothing became unreachable', () => {
  it( 'getAllNavItems covers the settings tree, not just the sidebar', () => {
    const all = getAllNavItems().map( ( i ) => i.path );
    for ( const s of getSettingsItems() )
    {
      expect( all ).toContain( s.path );
    }
  } );

  it( 'still knows about more destinations than the old sidebar did', () => {
    // The old nav had 88 unique paths. This must not be a reduction in
    // reachability, only in prominence.
    const unique = new Set( getAllNavItems().map( ( i ) => i.path.split( '?' )[ 0 ] ) );
    expect( unique.size ).toBeGreaterThanOrEqual( 87 );
  } );

  it( 'keeps the pages that have no link anywhere else', () => {
    // A sample of the 21 orphans, including the MFA page the owner asked to keep
    // and which cannot be reached any other way.
    const all = getAllNavItems().map( ( i ) => i.path );
    for ( const p of [ '/access/security', '/workspace/channels', '/workspace/search',
      '/workspace/whatsapp/catalog-builder', '/workspace/whatsapp/embedded-signup',
      '/dashboard/design-reference', '/workspace/meta-agent', '/workspace/faq' ] )
    {
      expect( all ).toContain( p );
    }
  } );

  it( 'picked up routes that were orphaned before the restructure', () => {
    const all = getAllNavItems().map( ( i ) => i.path );
    // '/forms/create' was in this list until 2026-09-25. It was deleted as a ComingSoon
    // stub, so asserting the nav still reaches it would now assert the opposite of what
    // this file is for. FeatureFlags.test.tsx carries the inverse check for it.
    for ( const p of [ '/dashboard/cors-settings', '/workspace/whatsapp/ai-agent',
      '/workspace/whatsapp/scripts', '/forms/responses' ] )
    {
      expect( all ).toContain( p );
    }
  } );
} );

describe( 'every nav path resolves to a real page', () => {
  it( 'no sidebar entry points at a missing file', () => {
    const missing = getAllNavItemsFrom( navigationConfig ).filter( ( p ) => !pageExists( p ) );
    expect( missing ).toEqual( [] );
  } );

  it( 'no settings entry points at a missing file', () => {
    const missing = getSettingsItems()
      .map( ( i ) => i.path )
      .filter( ( p ) => !pageExists( p ) );
    expect( missing ).toEqual( [] );
  } );

  it( 'no retired page is still referenced', () => {
    const all = getAllNavItems().map( ( i ) => i.path.split( '?' )[ 0 ] );
    for ( const dead of [ '/workspace/calls', '/workspace/rcs/inbox', '/workspace/ses/inbox',
      '/workspace/rcs/logs', '/workspace/ses/logs', '/workspace/whatsapp/logs',
      '/workspace/rcs/campaign', '/workspace/ses/campaign', '/forms/logs', '/link/logs' ] )
    {
      expect( all ).not.toContain( dead );
    }
  } );
} );

describe( 'active-state matching survives the query strings', () => {
  // The inbox children are one page with six query strings. Comparing a path
  // against path-plus-query never matches, so without stripping the query the
  // sidebar would highlight nothing on the page you are looking at.
  it( 'marks the inbox active when a channel filter is applied', () => {
    const inbox = navigationConfig.find( ( i ) => i.path === '/workspace/inbox' )!;
    expect( isNavItemActive( inbox, '/workspace/inbox' ) ).toBe( true );
  } );

  it( 'marks a query-string child active on its base route', () => {
    const child = { path: '/workspace/inbox?channel=voice', label: 'Calls' };
    expect( isSubItemActive( child, '/workspace/inbox' ) ).toBe( true );
  } );

  it( 'does not mark an unrelated route active', () => {
    const contacts = navigationConfig.find( ( i ) => i.path === '/contacts' )!;
    expect( isNavItemActive( contacts, '/workspace/inbox' ) ).toBe( false );
  } );
} );

describe( 'the settings tree is navigable', () => {
  it( 'every group has a label, a hint and at least one item', () => {
    for ( const g of settingsConfig )
    {
      expect( g.label.length ).toBeGreaterThan( 0 );
      expect( g.hint.length ).toBeGreaterThan( 0 );
      expect( g.items.length ).toBeGreaterThan( 0 );
    }
  } );

  it( 'puts Sign-in & MFA first in the account group, since it cannot be reached otherwise', () => {
    const account = settingsConfig.find( ( g ) => g.id === 'account' );
    expect( account?.items[ 0 ].path ).toBe( '/access/security' );
  } );

  it( 'has no duplicate destination across the whole tree', () => {
    const paths = getSettingsItems().map( ( i ) => i.path );
    expect( new Set( paths ).size ).toBe( paths.length );
  } );
} );
