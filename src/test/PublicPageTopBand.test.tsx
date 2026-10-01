import fs from 'node:fs';
import path from 'node:path';
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import PageTopBand from '../components/PageTopBand';
import Cart from '../pages/cart';
import SignIn from '../pages/account/sign-in';
import CheckoutStatus, { viewFor } from '../pages/checkout/status';
import CheckoutSuccess from '../pages/checkout/success';
import ShopProductPage from '../pages/shop/[slug]';
import { shopProductBySlug } from '../content/shop';
import type { ShopProduct } from '../content/shop';
import * as customerAuth from '../lib/customerAuth';
import * as cartLib from '../lib/cart';

/**
 * THE TOP SECTION EVERY PUBLIC PAGE MUST CARRY, and the four transactional pages that did not.
 *
 * The owner reported these pages as missing the shared structure, the animations and the home
 * page's design language. Two of the three were measurable defects rather than matters of taste:
 * /checkout/status/ and /checkout/success/ carried NO header clearance at all - they centred a card
 * inside min-height:100vh under a 108px fixed header - and declared no font family, so their
 * typeface was a side effect of an Amplify stylesheet setting one on body.
 *
 * What is asserted where. jsdom applies no CSS, so clearance, type rungs and tap targets are
 * measured in a real browser: tools/browser/devicecheck.js now carries /cart/, /account/sign-in/,
 * /checkout/status/ and /checkout/success/ across fifteen postures, and pageaudit.js probes the
 * header clearance with elementFromPoint. These tests cover what jsdom can decide: the structure
 * (one main, one h1, nothing conversion-shaped inside the band), the opt-in direction of the
 * entrance animation, and the copy invariants that protect a customer's money.
 */

const KIOSK = (): ShopProduct => shopProductBySlug( 'kiosk' ) as ShopProduct;

/** The four pages that moved onto the shared band, plus the catalogue page that joined them. */
const BAND_PAGE_FILES = [
  'src/pages/cart.tsx',
  'src/pages/account/sign-in.tsx',
  'src/pages/checkout/status.tsx',
  'src/pages/checkout/success.tsx',
  'src/pages/shop/[slug].tsx',
];

const read = ( rel: string ): string =>
  fs.readFileSync( path.join( process.cwd(), rel ), 'utf8' );

let navigatedTo: string;

beforeEach( () => {
  window.localStorage.clear();
  navigatedTo = '';
  Object.defineProperty( window, 'location', {
    configurable: true,
    value: {
      ...window.location,
      search: '',
      assign: ( url: string ) => { navigatedTo = String( url ); },
      replace: ( url: string ) => { navigatedTo = String( url ); },
    },
  } );
} );

afterEach( () => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
} );

describe( 'PageTopBand ships the settled state and arms the entrance afterwards', () => {
  it( 'renders a readable heading with no JavaScript having run', () => {
    /*
     * THE DIRECTION OF THIS IS THE WHOLE POINT, and getting it backwards shipped a blank hero on
     * twelve pages of this site. The CSS default must be the FINISHED band, with JavaScript adding
     * a class that puts the start state back - so a failed bundle, a crawler or a reader with
     * scripting off sees a complete heading rather than an invisible one.
     *
     * The first render is the no-JS proxy: the effect has not run, so .is-armed is absent and the
     * only declarations in play are the settled ones.
     */
    const { container } = render(
      <PageTopBand heading="Your cart" sub="A sub-line." ariaLabel="Your cart" />,
    );
    const layout = container.querySelector( '.ptb-layout' ) as HTMLElement;
    expect( layout.className ).not.toContain( 'is-armed' );
    expect( screen.getByRole( 'heading', { level: 1 } ).textContent ).toBe( 'Your cart' );
  } );

  it( 'arms and then reveals once motion is known to be allowed', async () => {
    const { container } = render(
      <PageTopBand heading="Your cart" ariaLabel="Your cart" />,
    );
    const layout = () => container.querySelector( '.ptb-layout' ) as HTMLElement;
    // .is-armed puts the start state back; .show plays it. Both land on the className, not through
    // classList - RotatingHero records why: React rewrites className on render and silently drops
    // an imperatively added class.
    await waitFor( () => expect( layout().className ).toContain( 'is-armed' ) );
    await waitFor( () => expect( layout().className ).toContain( 'show' ) );
  } );

  it( 'never arms at all when the reader asks for reduced motion', async () => {
    vi.spyOn( window, 'matchMedia' ).mockImplementation( ( query: string ) => ( {
      media: query, matches: true, onchange: null,
      addEventListener: () => undefined, removeEventListener: () => undefined,
      addListener: () => undefined, removeListener: () => undefined,
      dispatchEvent: () => false,
    } as unknown as MediaQueryList ) );

    const { container } = render( <PageTopBand heading="Your cart" ariaLabel="Your cart" /> );
    // Staying at the settled state is the correct response, because the settled state is what the
    // CSS already declares. There is nothing to undo.
    await new Promise( resolve => setTimeout( resolve, 120 ) );
    expect( ( container.querySelector( '.ptb-layout' ) as HTMLElement ).className )
      .not.toContain( 'is-armed' );
  } );

  it( 'puts the page inside the band rather than beside it', () => {
    const { container } = render(
      <PageTopBand heading="Your cart" ariaLabel="Your cart">
        <p className="child">below the band</p>
      </PageTopBand>,
    );
    // One main landmark, and the children share its measure. A page that rendered its own <main>
    // alongside this one would report two, which tools/audit/htmlcheck.js flags at HIGH.
    expect( container.querySelectorAll( 'main' ) ).toHaveLength( 1 );
    expect( container.querySelector( '.ptb-layout > .child' ) ).not.toBeNull();
  } );

  it( 'arms only the heading and the sub-line, never the children', () => {
    /*
     * opacity:0 does NOT remove an element from the tab order. Arming a band that contains a form
     * or a button would therefore leave invisible focusable controls for the length of the reveal,
     * which is the defect skill §6 names. So the armed selectors name .ptb-h1 and .ptb-sub and
     * nothing else.
     */
    const css = read( 'src/components/PageTopBand.tsx' );
    expect( css ).toContain( '.ptb-layout.is-armed .ptb-h1,.ptb-layout.is-armed .ptb-sub{opacity:0' );
    // No blanket rule over the layout or its descendants.
    expect( css ).not.toMatch( /\.ptb-layout\.is-armed\s*\{[^}]*opacity:0/ );
  } );

  it( 'carries both header heights and declares its own font stack', () => {
    const css = read( 'src/components/PageTopBand.tsx' );
    // The two-height clearance, which is the thing /checkout/* had none of. A style attribute
    // cannot express it, which is how an earlier page shipped a 48px pad under a 108px header.
    expect( css ).toContain( 'padding-top:108px' );
    expect( css ).toContain( 'padding-top:96px' );
    // Declared, not inherited: --font-sans has no Inter in it, so an inheriting band falls to a
    // serif the day the Amplify stylesheet import moves.
    expect( css ).toContain( "font-family:'Inter'" );
    // Tracking in em on the fluid size. A fixed px value against clamp() made optical tightness
    // swing 2.75x across the breakpoints.
    expect( css ).toContain( 'letter-spacing:-0.04em' );
    expect( css ).not.toMatch( /clamp\([^)]*\)[^}]*letter-spacing:-?[\d.]+px/ );
  } );
} );

describe( 'every page that moved onto the band kept exactly one h1 and one main', () => {
  it( 'renders one of each, with the page name as the heading', async () => {
    const cases: { name: string; element: React.ReactElement; heading: string }[] = [
      { name: 'cart', element: <Cart />, heading: 'Your cart' },
      { name: 'sign-in', element: <SignIn />, heading: 'Sign in to check out' },
      // No ?a= in the URL, so the honest answer is the holding screen rather than "confirming" -
      // there is no attempt to confirm. The structure is what this test is about either way.
      { name: 'status', element: <CheckoutStatus />, heading: 'Nothing to show here' },
      { name: 'success', element: <CheckoutSuccess />, heading: 'Payment successful' },
      { name: 'product', element: <ShopProductPage product={ KIOSK() } />, heading: 'Kiosk' },
    ];
    for ( const entry of cases )
    {
      vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
      const { container, unmount } = render( entry.element );
      expect( container.querySelectorAll( 'main' ), entry.name ).toHaveLength( 1 );
      const h1s = container.querySelectorAll( 'h1' );
      expect( h1s, entry.name ).toHaveLength( 1 );
      expect( h1s[ 0 ].textContent, entry.name ).toBe( entry.heading );
      unmount();
    }
  } );

  it( 'puts no button, no link and no price inside the band itself', async () => {
    /*
     * Skill §6: "No CTA, no price, no conversion furniture in that band - the action belongs further
     * down." The product page was the live violation - its price sat in the top band, directly under
     * the h1 - and the price now sits with the button that acts on it.
     */
    const { container } = render( <ShopProductPage product={ KIOSK() } /> );
    const band = container.querySelector( '.ptb-top' ) as HTMLElement;
    expect( band ).not.toBeNull();
    expect( band.querySelectorAll( 'button, a' ) ).toHaveLength( 0 );
    expect( band.textContent || '' ).not.toContain( '₹' );
    // And the price really is on the page, below the band, rather than having been deleted.
    expect( container.querySelector( '.shopd-about .shopd-price' )?.textContent )
      .toBe( '₹24,999.00' );
  } );

  it( 'stops hand-rolling the clearance each page used to own', () => {
    // The point of sharing the band: five pages previously each stated their own 108px/96px pair,
    // or in two cases stated neither. None of them may state it again - a second copy is a second
    // thing to get wrong at one of the two header heights.
    for ( const file of BAND_PAGE_FILES )
    {
      expect( read( file ), file ).toContain( 'PageTopBand' );
      // Comments stripped: two of these files explain in prose that they USED to centre a card
      // inside min-height:100vh, and a substring search cannot tell a citation from a declaration.
      const code = read( file ).replace( /\/\*[\s\S]*?\*\//g, '' ).replace( /^\s*\/\/.*$/gm, '' );
      expect( code, file ).not.toContain( 'padding-top:108px' );
      expect( code, file ).not.toContain( 'min-height:100vh' );
    }
  } );
} );

describe( 'no red anywhere on these pages, on owner instruction', () => {
  it( 'drops the pink/maroon error palette and the off-palette green', () => {
    /*
     * The owner's instruction was that error states use the lime scheme and that red is not used.
     * These five values were the whole of the off-palette colour on these pages:
     *   #fbe9e9 / #f0c0c0 / #8a1f1f   the pink error wash, its border and its maroon type
     *   #1f8f4e                       a green that appears nowhere in the home design, used as a
     *                                 button fill on both checkout screens
     * The replacement is the site's own state tint rgba(209,244,112,.22) behind a solid #d1f470
     * inline-start edge with #1a3a2a type - .shop-asof's treatment - and the lime pill CTA.
     *
     * Colour is NOT the only cue, which is what makes removing red safe rather than a regression:
     * role=alert / role=status carries the severity, the sentence states the problem, and the firm
     * variant steps the edge to 4px and the weight to 700 - a luminance and weight change, which
     * survives forced-colors and reduced colour discrimination in a way a hue swap does not.
     */
    const RETIRED = [ '#fbe9e9', '#f0c0c0', '#8a1f1f', '#1f8f4e' ];
    for ( const file of BAND_PAGE_FILES )
    {
      // Comments stripped first: these files cite the values they replaced, and a substring search
      // cannot tell a citation from a declaration. This repo has had to correct that three times.
      const code = read( file ).replace( /\/\*[\s\S]*?\*\//g, '' ).replace( /^\s*\/\/.*$/gm, '' );
      for ( const colour of RETIRED )
      {
        expect( code.toLowerCase(), `${file} still declares ${colour}` ).not.toContain( colour );
      }
    }
  } );

  it( 'keeps the severity in the role rather than in the colour', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockRejectedValue( new Error( 'Enter a valid mobile number' ) );
    vi.stubGlobal( 'fetch', vi.fn() );

    render( <SignIn /> );
    fireEvent.change( screen.getByLabelText( 'Mobile number' ), { target: { value: '1' } } );
    fireEvent.click( screen.getByRole( 'button', { name: 'Send code' } ) );

    // An alert, not a colour. A reader who cannot see the tint still gets the interruption.
    const alert = await screen.findByRole( 'alert' );
    expect( alert.textContent ).toBeTruthy();
  } );
} );

describe( 'the money copy survived being shortened', () => {
  it( 'never claims nothing was charged on the status screen', () => {
    /*
     * THE INVARIANT THAT MATTERS MOST IN THIS FILE. The two states a visitor is most likely to land
     * on are "in flight" and "unknown", and in both of them the money may in fact have been
     * captured - the browser cannot tell. "No charge was made" there is the one wrong answer that
     * cannot be taken back, so it appears nowhere on this page in any state.
     */
    for ( const [ status, orderNumber ] of [
      [ 'PAYMENT_PENDING', null ], [ 'PAYMENT_PAID', null ], [ '', null ],
      [ 'PAYMENT_INITIATION_DISABLED', null ], [ 'WHAT_IS_THIS', null ],
      [ 'PAYMENT_FAILED', null ],
    ] as [ string, string | null ][] )
    {
      const { container, unmount } = render( <CheckoutStatus /> );
      // Rendered for the default view; the copy table is what is being asserted, via viewFor.
      expect( viewFor( status, orderNumber ) ).toBeTruthy();
      expect( container.textContent || '' ).not.toMatch( /no charge|not been charged|nothing was taken/i );
      unmount();
    }
    const source = read( 'src/pages/checkout/status.tsx' )
      .replace( /\/\*[\s\S]*?\*\//g, '' ).replace( /^\s*\/\/.*$/gm, '' );
    expect( source.toLowerCase() ).not.toContain( 'no charge' );
  } );

  it( 'offers no retry for a paid, pending or unknown attempt', () => {
    // viewFor is the whole decision, so assert the mapping rather than six renders. Only 'failed'
    // may carry an action that starts a new checkout, and it is reached solely from a terminal
    // backend status.
    expect( viewFor( 'PAYMENT_PAID', null ) ).toBe( 'finalizing' );
    expect( viewFor( 'PAYMENT_PAID', 'WD-ORD-000123' ) ).toBe( 'confirming' );
    expect( viewFor( 'PAYMENT_PENDING', null ) ).toBe( 'confirming' );
    expect( viewFor( 'PAYMENT_REQUEST_SENT', null ) ).toBe( 'confirming' );
    expect( viewFor( 'PAYMENT_INITIATION_DISABLED', null ) ).toBe( 'unavailable' );
    expect( viewFor( undefined, null ) ).toBe( 'unavailable' );
    expect( viewFor( 'SOMETHING_NEW_FROM_THE_BACKEND', null ) ).toBe( 'unavailable' );
    for ( const terminal of [ 'PAYMENT_FAILED', 'PAYMENT_CANCELLED', 'PAYMENT_EXPIRED' ] )
    {
      expect( viewFor( terminal, null ) ).toBe( 'failed' );
    }
  } );

  it( 'keeps "Do not pay again" verbatim on the finalizing screen', () => {
    // The one sentence on that page that prevents a double charge. Shortening the copy around it is
    // fine; shortening it is not.
    expect( read( 'src/pages/checkout/status.tsx' ) ).toContain( 'Do not pay again.' );
  } );

  it( 'still says what the cart does and does not do', async () => {
    // The boundary note belongs to a cart with something in it; the empty state has nothing to make
    // a statement about.
    cartLib.addItem( KIOSK(), 1 );
    const { container } = render( <Cart /> );
    // Three guarantees, all of which survived the trim: the prices are catalogue prices, the store
    // decides the amount, and proceeding charges nothing.
    await waitFor( () => expect( container.textContent || '' ).toContain( 'store catalogue' ) );
    expect( container.textContent || '' ).toMatch( /confirms the amount/ );
    expect( container.textContent || '' ).toMatch( /charges you nothing/ );
  } );
} );

describe( 'the country code is an explicit field, on owner instruction', () => {
  const sendCode = (): void => {
    fireEvent.click( screen.getByRole( 'button', { name: 'Send code' } ) );
  };

  it( 'is a required, labelled control rather than something inferred from the digits', () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    render( <SignIn /> );
    const select = screen.getByLabelText( 'Country code' ) as HTMLSelectElement;
    expect( select.tagName ).toBe( 'SELECT' );
    expect( select.required ).toBe( true );
    // Prefilled with the market, not left blank: the field is always submitted and always applied.
    expect( select.value ).toBe( '91' );
  } );

  it( 'composes the selected code with the typed national number', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    const requestOtp = vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: 's', destination: '****1234', expiresInSeconds: 600, registered: true,
    } );
    vi.stubGlobal( 'fetch', vi.fn() );

    render( <SignIn /> );
    fireEvent.change( screen.getByLabelText( 'Country code' ), { target: { value: '971' } } );
    fireEvent.change( screen.getByLabelText( 'Mobile number' ), { target: { value: '501234567' } } );
    sendCode();

    // THE DEFECT THIS FIXES. customerAuth.normaliseMobile() turns any ten digits beginning 6-9 into
    // a +91 number, so a foreign number was silently signed in as an Indian one. That function is
    // NOT changed - it has to match the backend byte for byte - so the code is composed ahead of it,
    // which leaves it nothing to infer.
    await waitFor( () => expect( requestOtp ).toHaveBeenCalledWith( '+971501234567' ) );
  } );

  it( 'does not strip a dial code out of a bare national number', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    const requestOtp = vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: 's', destination: '****5432', expiresInSeconds: 600, registered: true,
    } );
    vi.stubGlobal( 'fetch', vi.fn() );

    render( <SignIn /> );
    // "9198765432" is a VALID ten-digit Indian number that happens to start with 91. Stripping a
    // prefix on the strength of the digits alone would sign in a different, non-existent customer -
    // so a prefix is only removed when the shopper typed it as one, with a + or 00.
    fireEvent.change( screen.getByLabelText( 'Mobile number' ), { target: { value: '9198765432' } } );
    sendCode();
    await waitFor( () => expect( requestOtp ).toHaveBeenCalledWith( '+919198765432' ) );
  } );

  it( 'does strip it when the shopper pasted a full international number', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    const requestOtp = vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: 's', destination: '****3210', expiresInSeconds: 600, registered: true,
    } );
    vi.stubGlobal( 'fetch', vi.fn() );

    render( <SignIn /> );
    fireEvent.change( screen.getByLabelText( 'Mobile number' ), { target: { value: '+91 98765 43210' } } );
    sendCode();
    // Not +919198765..., which is what a naive concatenation produces.
    await waitFor( () => expect( requestOtp ).toHaveBeenCalledWith( '+919876543210' ) );
  } );

  it( 'says the number could not be reached on WhatsApp when the send fails', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: '', destination: '', expiresInSeconds: 600, registered: false,
    } );
    // The registration front door's 502 {status:'send_failed'} is the only signal that distinguishes
    // "we could not deliver to this number over WhatsApp" from any other refusal.
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false, status: 502, json: async () => ( { status: 'send_failed' } ),
    } ) );

    render( <SignIn /> );
    fireEvent.change( screen.getByLabelText( 'Mobile number' ), { target: { value: '9876543210' } } );
    sendCode();

    const alert = await screen.findByRole( 'alert' );
    expect( alert.textContent ).toMatch( /could not reach that number on WhatsApp/ );
    expect( alert.textContent ).toMatch( /country code/ );
    // IT MUST NOT ASSERT THE NUMBER IS NOT ON WHATSAPP. The same 502 is returned when Meta's send
    // fails transiently, so a flat "this is not a WhatsApp number" would be a confident wrong answer
    // about our own outage.
    expect( alert.textContent ).not.toMatch( /is not a WhatsApp number/ );
  } );

  it( 'falls back to a generic failure for any other refusal', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: '', destination: '', expiresInSeconds: 600, registered: false,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false, status: 500, json: async () => ( { error: 'INTERNAL_ERROR' } ),
    } ) );

    render( <SignIn /> );
    fireEvent.change( screen.getByLabelText( 'Mobile number' ), { target: { value: '9876543210' } } );
    sendCode();

    const alert = await screen.findByRole( 'alert' );
    expect( alert.textContent ).toMatch( /could not send a code/ );
    expect( alert.textContent ).not.toMatch( /WhatsApp/ );
  } );
} );
