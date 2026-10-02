import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import NotFound from '../pages/404';

const router = vi.hoisted( () => ( { replace: vi.fn() } ) );
vi.mock( 'next/router', () => ( { useRouter: () => router } ) );
vi.mock( 'next/head', () => ( { default: () => null } ) );

// Owner's retirement list, independent of the component's matching implementation.
const retired = [
  '/access', '/dm', '/engage', '/dashboard', '/contacts', '/commerce', '/pay',
  '/forms', '/service', '/docs', '/seo', '/admin', '/link', '/task', '/settings',
  '/swdhya', '/no-fault', '/legal-stuff', '/legal-stuffs', '/faq', '/my-order',
  '/expoweek', '/ritual-store', '/swdhya-store', '/request-tracking', '/rx-slot',
  '/bring-friends', '/home', '/open-possibility', '/product-page/partner',
  '/selfservice', '/track',
];
beforeEach( () => router.replace.mockClear() );
afterEach( () => { cleanup(); window.history.replaceState( {}, '', '/' ); } );

describe( 'retired URLs use the single missing-page home fallback', () => {
  it.each( retired )( '%s uses home fallback, including slash and descendant forms', prefix => {
    for ( const suffix of [ '', '/', '/nested/?next=https://example.com' ] ) {
      window.history.replaceState( {}, '', prefix + suffix );
      const view = render( <NotFound /> );
      expect( router.replace ).toHaveBeenLastCalledWith( '/' );
      expect( screen.getByText( 'This page is unavailable.' ) ).toBeVisible();
      expect( screen.getByRole( 'link', { name: 'Go to WECARE.DIGITAL' } ) ).toHaveAttribute( 'href', '/' );
      view.unmount();
    }
  } );
  it.each( [ '/ACCESS/', '/%61ccess/', '/track%2Fnested/' ] )( 'also retires %s', path => {
    window.history.replaceState( {}, '', path );
    render( <NotFound /> );
    expect( router.replace ).toHaveBeenLastCalledWith( '/' );
  } );
  it.each( [ '/definitely-not-a-page/', '/tracking-unknown/', '/contact-unknown/' ] )(
    'uses the same home fallback for %s', path => {
      window.history.replaceState( {}, '', path );
      render( <NotFound /> );
      expect( router.replace ).toHaveBeenLastCalledWith( '/' );
    }
  );
} );
