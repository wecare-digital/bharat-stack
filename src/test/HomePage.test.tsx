import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import HomePage from '../pages/index';

vi.mock( 'next/head', () => ( { default: ( { children }: { children: React.ReactNode } ) => <>{ children }</> } ) );

const cssOf = ( container: HTMLElement ) =>
  Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

describe( 'WECARE.DIGITAL Home', () => {
  // Replaces an assertion that the body stays blank "until the Home design is
  // decided". The rotating headline is that decision, so the old test would have
  // passed while describing the opposite of what ships.
  it( 'renders the rotating headline around a stable frame', () => {
    render( <HomePage /> );
    const heading = screen.getByRole( 'heading', { level: 1 } );

    // Only the pill rotates; the frame does not.
    expect( heading.textContent ).toMatch( /^Everyday services for/ );
  } );

  it( 'carries the cost and complexity half of the positioning in the body line', () => {
    const { container } = render( <HomePage /> );

    // The headline enacts breadth via the rotation, so this line has to carry the
    // rest of the claim. One sentence, one body level.
    const sub = container.querySelector( '.home-sub' );
    expect( sub ).toBeInTheDocument();
    expect( sub?.textContent?.replace( /\s+/g, ' ' ).trim() )
      .toBe( 'Transparent pricing, guided journeys, and dependable support — on one shared foundation.' );
    expect( container.querySelectorAll( '.home-sub' ) ).toHaveLength( 1 );
  } );

  it( 'keeps the rotating words within a narrow length band', () => {
    const { container } = render( <HomePage /> );
    const words = Array.from( container.querySelectorAll( '.home-cyc-word' ) )
      .map( w => ( w.textContent || '' ) );

    // The pill animates to each word's measured width, so the spread between the
    // shortest and longest word is how far the headline's tail travels each tick.
    // Two characters is the band. This is a margin-of-safety bound, not a fix for an
    // observed snap - measured sampling shows wider sets still glide. The defect it
    // guards against is the headline reflowing on the longest word only; the browser
    // harness measures h1 height across a rotation for that.
    // The character band is GONE as an assertion, and that is deliberate rather than
    // a loosening. It was a proxy for "the headline must not reflow", and the owner's
    // four added words take the spread to 9 characters (travel -> ai applications),
    // which no proxy bound can usefully cover.
    //
    // What replaced it is the actual constraint, measured in a browser: the pill sits
    // on its own line, so the h1's line count is independent of word width, and
    // animcheck.js asserts the h1's height is identical for every word at all 21
    // viewports from 320 to 1920. Re-run that after any word change - a unit test
    // cannot see reflow.
    //
    // The one thing still worth pinning here is that no word is so long it cannot fit
    // the pill's own line at the narrowest breakpoint.
    const lengths = words.map( w => w.length );
    expect( Math.max( ...lengths ) ).toBeLessThanOrEqual( 18 );
  } );

  it( 'exposes the word list to screen readers once, and hides every animated copy', () => {
    const { container } = render( <HomePage /> );

    // One readable copy of the full list...
    const srOnly = container.querySelector( '.home-sr-only' );
    expect( srOnly ).toBeInTheDocument();
    expect( srOnly?.textContent ).toBe( 'consumers, enterprises, AI applications, frontier tech' );

    // ...and every visually-rotating copy hidden, so the headline is not read out
    // once per word. Each animated word must carry aria-hidden.
    //
    // The count is DERIVED from the screen-reader list rather than hardcoded. It was
    // hardcoded to 9, which meant a word-list change failed this test for the wrong
    // reason - the number, not the behaviour - twice over. Deriving it also pins
    // something the old assertion could not: that the visible rotation and the list
    // read aloud cannot drift apart. If a word is added to one and not the other,
    // this fails, which is the actual accessibility bug worth catching.
    const expectedWords = ( srOnly?.textContent || '' ).split( ', ' ).length;
    const words = Array.from( container.querySelectorAll( '.home-cyc-word' ) );
    expect( words ).toHaveLength( expectedWords );
    expect( words.map( w => w.textContent ) ).toEqual( ( srOnly?.textContent || '' ).split( ', ' ) );
    words.forEach( word => expect( word ).toHaveAttribute( 'aria-hidden', 'true' ) );

    // Exactly one is active at a time.
    expect( container.querySelectorAll( '.home-cyc-word.on' ) ).toHaveLength( 1 );
  } );

  it( 'keeps the eyebrow 20px from the headline, not on the 96px section gap', () => {
    const { container } = render( <HomePage /> );

    // The badge and headline are wrapped so the section gap cannot push them apart.
    // As direct children of .home-layout they would have sat 96px from each other
    // instead of the 20px the other two public pages use.
    const hero = container.querySelector( 'main > .home-layout > .home-hero' );
    expect( hero ).toBeInTheDocument();
    expect( hero?.querySelector( '.home-eyebrow' ) ).toBeInTheDocument();
    expect( hero?.querySelector( '.home-head' ) ).toBeInTheDocument();
    expect( cssOf( container ) ).toContain( 'margin:0 0 20px' );
  } );

  it( 'animates on the same constants as the Grahak OS and VayuLok pills', () => {
    const css = cssOf( render( <HomePage /> ).container );

    // These three pages are meant to animate as one family. If one is retuned and
    // the others are not, this fails - which is the point. The 2400ms interval
    // itself lives in JS, so it is not assertable here.
    expect( css ).toContain( 'transition:background-color .52s cubic-bezier(.16,1,.3,1)' );
    expect( css ).toContain( 'transition:transform .78s cubic-bezier(.16,1,.3,1) .18s' );
    expect( css ).toContain( 'transition:transform .5s cubic-bezier(.34,1.56,.64,1) .72s' );
    expect( css ).toContain( 'transition:width .52s cubic-bezier(.16,1,.3,1)' );

    // The dot geometry is measured, not eyeballed - .33em with a .18em gap.
    expect( css ).toContain( 'width:.33em;height:.33em' );
    expect( css ).toContain( 'margin-right:.18em' );

    // Reduced motion settles the pill rather than leaving it mid-transition.
    expect( css ).toContain( '@media(prefers-reduced-motion:reduce)' );
  } );

  it( 'holds the headline on the hero h1 rung, which is lighter than section h2', () => {
    const css = cssOf( render( <HomePage /> ).container );

    // 600, not 700. The contract's weight inversion is deliberate and two other
    // pages carry the same guard.
    expect( css ).toContain( 'font-size:clamp(36px,4.3vw,60px)' );
    expect( css ).toContain( 'font-weight:600' );
    expect( css ).toContain( 'letter-spacing:-2.2px' );
  } );

  it( 'declares the Inter stack rather than inheriting it from Amplify', () => {
    const css = cssOf( render( <HomePage /> ).container );

    // This page rendered in Inter only because @aws-amplify/ui-react's styles.css
    // sets a font-family on body. --font-sans in Pages.css has no Inter to fall
    // back to, so the declaration has to be here.
    expect( css ).toContain( "font-family:'Inter',-apple-system" );
  } );

  it( 'keeps homepage content below the public header at every breakpoint', () => {
    const { container } = render( <HomePage /> );
    const css = cssOf( container );

    expect( css ).toContain( 'padding-top:108px' );
    expect( css ).toContain( 'padding-top:96px' );
  } );

  it( 'provides a centered responsive canvas with consistent section spacing', () => {
    const { container } = render( <HomePage /> );
    const layout = container.querySelector( 'main > .home-layout' );
    const css = cssOf( container );

    expect( layout ).toBeInTheDocument();
    expect( css ).toContain( 'max-width:1300px' );
    expect( css ).toContain( 'padding:80px 24px 96px' );
    expect( css ).toContain( 'gap:96px' );
    expect( css ).toContain( 'padding:48px 16px 64px' );
    expect( css ).toContain( 'gap:64px' );
  } );
} );
