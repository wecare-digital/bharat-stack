import React from 'react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import HomePage from '../pages/index';

vi.mock( 'next/head', () => ( { default: ( { children }: { children: React.ReactNode } ) => <>{ children }</> } ) );
vi.mock( 'next/script', () => ( { default: () => null } ) );

beforeAll( () => {
  class MockIntersectionObserver {
    observe () {}
    unobserve () {}
    disconnect () {}
  }
  vi.stubGlobal( 'IntersectionObserver', MockIntersectionObserver );
} );

describe( 'HomePage typography', () => {
  it( 'uses the scoped responsive typography contract', () => {
    const { container } = render( <HomePage /> );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );
    expect( css ).toContain( '.hero-left h1{font-size:clamp(' );
    expect( css ).toContain( '.hero-left p{font-size:clamp(' );
    expect( css ).toContain( '.capability-card p{font-size:var(--text-base)' );
  } );
} );
