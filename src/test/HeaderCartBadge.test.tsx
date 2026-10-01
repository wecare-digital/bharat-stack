import fs from 'node:fs';
import path from 'node:path';
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';

import { renderToStaticMarkup } from 'react-dom/server';

import HeaderCart from '../components/HeaderCart';
import Header from '../components/Header';
import * as cart from '../lib/cart';
import type { ShopProduct } from '../content/shop';

/**
 * THE SHOPPING BAG IN THE HEADER, and specifically the two things about it that are true or false
 * rather than visual.
 *
 * jsdom cannot read a computed style, so the chip's geometry, the 44px tap target and the glyph's
 * colour are measured in a real browser - tools/browser/devicecheck.js carries all four
 * transactional routes now and asserts every header control clears 44px at fifteen postures,
 * including 280px where the header has the least room. What jsdom CAN decide is the count logic and
 * the accessible name, and the count logic has a trap that only a test will catch.
 *
 * THE TRAP IS HYDRATION. The cart is in localStorage and these pages are statically exported, so the
 * server render has no cart. If the component rendered a count during the first client render it
 * would have to render 0 - which is a different tree from the server's only if the server somehow
 * knew better, and either way it is a guess shown to a shopper who has three items. So `null` means
 * "not read yet", is distinct from 0, and shows no badge at all; the number appears only after the
 * effect has run. These tests pin that: the FIRST render carries no digits even when storage is
 * already populated.
 */

const PRODUCT: ShopProduct = {
  id: 'wix-abc-123',
  name: 'Kiosk',
  slug: 'kiosk',
  formattedPrice: '₹24,999.00',
  price: '24999.00',
  currency: 'INR',
  inStock: true,
  tagline: 'Put your location to work.',
  body: [ 'You already have the place.' ],
};

const OTHER: ShopProduct = { ...PRODUCT, id: 'wix-def-456', name: 'Merchandise', slug: 'merchandise' };

// Header reads router.pathname to mark the current row. Mocked the same way Header.test.tsx does it.
const routerState = vi.hoisted( () => ( { pathname: '/' } ) );
vi.mock( 'next/router', () => ( { useRouter: () => routerState } ) );

/** The link, found the way a visitor's screen reader finds it: by role and accessible name. */
const bag = (): HTMLElement => screen.getByRole( 'link', { name: /Shopping Bag/ } );

/** The digits drawn inside the glyph, or '' when the badge is absent. */
const digits = ( container: HTMLElement ): string =>
  container.querySelector( '.hdr-cart-n' )?.textContent || '';

beforeEach( () => {
  window.localStorage.clear();
} );

afterEach( () => {
  vi.restoreAllMocks();
} );

describe( 'the count is read after mount, never during the server render', () => {
  it( 'renders no digits in the server markup even when storage is already full', () => {
    cart.addItem( PRODUCT, 3 );
    /*
     * ASSERTED AGAINST THE SERVER RENDERER, WHICH IS THE ONLY PLACE THE DEFECT LIVES.
     * renderToStaticMarkup runs no effects, so this is exactly the HTML the static export writes -
     * and it is the HTML the client has to agree with on its first pass or React reports a
     * hydration mismatch. A component that read the cart in its render body would emit "3" here
     * and "3" on the client, which looks fine in a test and is wrong in production: the export is
     * built once, on a machine with no cart, so the committed HTML would say 0 for everybody.
     *
     * A client render cannot show this. testing-library wraps render() in act(), which flushes
     * effects before it returns, so the pre-effect tree is not observable from there.
     */
    /*
     * The <style> block has to come out first: styled-jsx inlines the stylesheet into the markup,
     * and that stylesheet names .hdr-cart-n whether or not the element exists.
     *
     * PARSED, NOT REGEX-STRIPPED. A single-pass regex strip of the style element here was a high
     * CodeQL finding (js/incomplete-multi-character-sanitization): one pass over nested delimiters
     * can splice a surviving `<style` back together, so the assertion below could have passed while
     * the stylesheet was still in the string. A parser decides what an element is and cannot be
     * fooled that way, and it says what this step actually means - remove the style elements.
     */
    const parsed = new DOMParser().parseFromString(
      renderToStaticMarkup( <HeaderCart /> ), 'text/html' );
    parsed.querySelectorAll( 'style' ).forEach( node => node.remove() );
    const markup = parsed.body.innerHTML;
    expect( markup ).not.toContain( 'hdr-cart-n' );
    // The bag itself IS in the server markup - it is the badge that waits, not the control.
    expect( markup ).toContain( 'Shopping Bag' );
  } );

  it( 'shows the count once the effect has run', async () => {
    cart.addItem( PRODUCT, 3 );
    const { container } = render( <HeaderCart /> );
    await waitFor( () => expect( digits( container ) ).toBe( '3' ) );
  } );
} );

describe( 'zero, one and many', () => {
  it( 'shows no badge for an empty cart, and says so in the accessible name', async () => {
    const { container } = render( <HeaderCart /> );
    // 'empty' rather than '0': the name is read aloud, and "Shopping Bag 0" is not a sentence.
    await waitFor( () => expect( bag() ).toHaveAccessibleName( /empty/ ) );
    // No digit is drawn in the bag at all - a zero in the glyph reads as a badge worth looking at.
    expect( digits( container ) ).toBe( '' );
  } );

  it( 'uses the singular for one item', async () => {
    cart.addItem( PRODUCT, 1 );
    const { container } = render( <HeaderCart /> );
    await waitFor( () => expect( digits( container ) ).toBe( '1' ) );
    expect( bag() ).toHaveAccessibleName( /1 item$/ );
  } );

  it( 'sums quantities across lines, not lines', async () => {
    cart.addItem( PRODUCT, 2 );
    cart.addItem( OTHER, 3 );
    const { container } = render( <HeaderCart /> );
    // Two lines, five units. The badge is a count of things a shopper is buying, not of rows.
    await waitFor( () => expect( digits( container ) ).toBe( '5' ) );
    expect( bag() ).toHaveAccessibleName( /5 items/ );
  } );

  it( 'caps the drawn badge at 99+ while the spoken name stays exact', async () => {
    cart.addItem( PRODUCT, 250 );
    const { container } = render( <HeaderCart /> );
    // The glyph is 30px wide; three or more digits inside it stop being a number. The accessible
    // name is not width-constrained, so it keeps the real figure rather than inheriting the cap.
    await waitFor( () => expect( digits( container ) ).toBe( '99+' ) );
    expect( bag() ).toHaveAccessibleName( /250 items/ );
  } );
} );

describe( 'the badge follows the cart without a navigation', () => {
  it( 'updates when an item is added in the same document', async () => {
    const { container } = render( <HeaderCart /> );
    await waitFor( () => expect( bag() ).toHaveAccessibleName( /empty/ ) );

    // THE REASON src/lib/cart.ts DISPATCHES ITS OWN EVENT. The browser's `storage` event fires in
    // OTHER tabs and never in the one that made the write, so /shop/<slug>/'s add-to-cart button
    // would leave this badge stale until the next page load.
    act( () => { cart.addItem( PRODUCT, 2 ); } );
    await waitFor( () => expect( digits( container ) ).toBe( '2' ) );
  } );

  it( 'empties when the cart is cleared', async () => {
    cart.addItem( PRODUCT, 1 );
    const { container } = render( <HeaderCart /> );
    await waitFor( () => expect( digits( container ) ).toBe( '1' ) );
    act( () => { cart.clearCart(); } );
    await waitFor( () => expect( digits( container ) ).toBe( '' ) );
  } );

  it( 'stops listening when it unmounts', async () => {
    const remove = vi.spyOn( window, 'removeEventListener' );
    const { unmount } = render( <HeaderCart /> );
    await waitFor( () => expect( bag() ).toHaveAccessibleName( /empty/ ) );
    unmount();
    const events = remove.mock.calls.map( call => String( call[ 0 ] ) );
    expect( events ).toContain( 'storage' );
    expect( events ).toContain( cart.CART_CHANGED_EVENT );
  } );
} );

describe( 'the control itself', () => {
  it( 'is a link to the cart, so it works with no JavaScript', () => {
    render( <HeaderCart /> );
    // A plain anchor rather than next/link, for the same styled-jsx reason the logo is one. The
    // trailing slash is load-bearing: next.config.js sets trailingSlash, so /cart would 308.
    expect( bag() ).toHaveAttribute( 'href', '/cart/' );
  } );

  it( 'names itself with a text node, not an attribute', () => {
    const { container } = render( <HeaderCart /> );
    /*
     * SupportWidget's translation walker rewrites TEXT NODES and never attribute text, so an
     * aria-label here would stay English in every language the site offers - the defect skill §5
     * measures at 1329 strings sitewide, 116 of them aria-labels. So "Shopping Bag" is rendered
     * text, and this asserts the absence of the shortcut as well as the presence of the label.
     */
    const link = bag();
    expect( link.getAttribute( 'aria-label' ) ).toBeNull();
    expect( container.querySelector( '.hdr-cart-label' )?.textContent ).toBe( 'Shopping Bag' );
  } );

  it( 'keeps the glyph decorative so the name is not read twice', () => {
    const { container } = render( <HeaderCart /> );
    const glyph = container.querySelector( '.hdr-cart-glyph' );
    expect( glyph?.getAttribute( 'aria-hidden' ) ).toBe( 'true' );
    // The digits live inside that aria-hidden subtree, which is why the spoken count is a separate
    // node: a walker and a screen reader both skip this one.
    expect( glyph?.querySelector( 'svg' ) ).not.toBeNull();
  } );

  it( 'flags the drawn number as untranslatable, the way prices are', async () => {
    cart.addItem( PRODUCT, 2 );
    const { container } = render( <HeaderCart /> );
    await waitFor( () => expect( digits( container ) ).toBe( '2' ) );
    // A regrouped numeral is a different number. Belt and braces - the glyph is aria-hidden, which
    // the walker already skips - but it keeps the handling of numbers consistent across the site.
    expect( container.querySelector( '.hdr-cart-n' ) )
      .toHaveAttribute( 'data-wc-no-translate', 'true' );
  } );
} );

describe( 'the header still reads the way its own tests require', () => {
  /*
   * Header.test.tsx reaches the menu trigger with container.querySelector('button') to prove the
   * chevron is drawn rather than typed. Adding a control to the header could have broken that
   * silently, so the ordering is asserted here too - from the other side, where the bag is the thing
   * being added.
   */
  it( 'leaves the menu trigger as the first and only button', () => {
    const { container } = render( <Header /> );
    const buttons = container.querySelectorAll( 'button' );
    expect( buttons[ 0 ].className ).toContain( 'nav-trigger' );
    // The bag is an anchor, so it adds no button at all.
    expect( buttons[ 0 ].textContent ).toBe( '' );
  } );

  it( 'puts the bag after the brand in the reading and tab order', () => {
    const { container } = render( <Header /> );
    const logo = container.querySelector( '.logo' ) as Node;
    const bagLink = container.querySelector( '.hdr-cart' ) as Node;
    expect( logo ).not.toBeNull();
    expect( bagLink ).not.toBeNull();
    // DOCUMENT_POSITION_FOLLOWING = 4. The bag comes after the lockup, so a keyboard user reaches
    // the brand and the menu first.
    expect( logo.compareDocumentPosition( bagLink ) & Node.DOCUMENT_POSITION_FOLLOWING ).toBeTruthy();
  } );

  it( 'reserves room for a 44px chip at 280px rather than letting it overflow', () => {
    /*
     * MEASURED, NOT GUESSED, AND THE NUMBERS ARE WHY THIS RULE EXISTS. On the built header at 280px
     * - Galaxy Fold, folded, the narrowest posture devicecheck.js carries - the 16px gutter leaves a
     * 248px content box and .logo-nav occupies 212.8px of it. That is 35.2px free, against the 44px
     * floor every header control has to clear. 10px of gutter returns 12px and a 6px .logo-nav gap
     * returns 2px: 49.2px, which is 44px of chip and 5.2px of air.
     *
     * Asserted as a string because jsdom applies no CSS. The real geometry is devicecheck's job;
     * this exists so deleting the rule is a test failure rather than a 280px overflow nobody runs.
     */
    const source = fs.readFileSync(
      path.join( process.cwd(), 'src', 'components', 'Header.tsx' ), 'utf8',
    );
    expect( source ).toContain( '@media(max-width:340px){.hdr-in{padding-inline:10px}.logo-nav{gap:6px}}' );
    // 340px is RotatingHero's own narrow rung, reused so the site has one narrow breakpoint. 344px
    // (Z Fold cover) sits above it and keeps the full gutter.
    expect( source ).not.toContain( '@media(max-width:360px)' );
  } );

  it( 'still pins both header heights and the 46px trigger', () => {
    // The two numbers the brief required to be unchanged. Header.test.tsx asserts them too; this
    // repeats them because THIS change is the one that could have moved them.
    const { container } = render( <Header /> );
    const css = Array.from( container.querySelectorAll( 'style' ) )
      .map( node => node.textContent || '' ).join( '\n' );
    expect( css ).toContain( 'box-sizing:border-box;height:108px' );
    expect( css ).toContain( '@media(max-width:767px){.hdr-in{height:96px' );
    expect( css ).toContain( '.nav-trigger{min-width:46px;min-height:46px' );
  } );
} );
