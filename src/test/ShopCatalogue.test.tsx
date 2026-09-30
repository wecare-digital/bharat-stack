import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import ShopIndex from '../pages/shop/index';
import ShopProductPage from '../pages/shop/[slug]';
import {
  SHOP_PRODUCTS, shopProductBySlug, shopMetaDescription, shopPageTitle, shopProductPath,
  toParagraphs, catalogReadOn, CATALOG_FETCHED_AT,
} from '../content/shop';
import type { ShopProduct } from '../content/shop';

/**
 * The /shop/ catalogue: the snapshot reader, and the two pages built on it.
 *
 * WHAT IS WORTH ASSERTING HERE AND WHAT IS NOT. The layout is measured in the browser -
 * tools/browser/seocheck.js, sectioncheck.js, devicecheck.js, lhcheck.js and pageaudit.js all
 * carry /shop/ and /shop/kiosk/, and a jsdom test cannot read a computed style, which is the trap
 * the mega-menu documents: 112 browser assertions passed while every row was unstyled.
 *
 * So this file asserts the things that are TRUE OR FALSE rather than visual: that the snapshot is
 * read correctly, that the derived strings stay inside the bounds seocheck enforces, that
 * merchant-authored HTML never reaches the DOM as HTML, and that the out-of-stock branch renders -
 * which nothing else can check, because all seven items in the committed snapshot are in stock.
 */

/** A product that is not in the snapshot, so the assertions below cannot be satisfied by luck. */
const SYNTHETIC: ShopProduct = {
  id: 'synthetic',
  name: 'Sold Out Thing',
  slug: 'sold-out-thing',
  formattedPrice: '₹1,234.00',
  price: '1234.00',
  currency: 'INR',
  inStock: false,
  tagline: 'A thing nobody can buy today.',
  body: [ 'One paragraph of body copy.' ],
};

describe( 'the Wix snapshot is read correctly', () => {
  it( 'reads the seven visible products the snapshot holds', () => {
    // Pinned at seven, not derived from the file. Derived, it would agree with whatever the
    // snapshot said, including an empty array - which is how a catalogue page ships blank.
    expect( SHOP_PRODUCTS ).toHaveLength( 7 );
    expect( SHOP_PRODUCTS.map( p => p.slug ) ).toEqual( [
      'file-assist', 'guided-resolution', 'kiosk', 'merchandise', 'paperwork',
      'referral-partner', 'viveka',
    ] );
  } );

  it( 'sorts by name, because the snapshot offers no other order', () => {
    const names = SHOP_PRODUCTS.map( p => p.name );
    expect( names ).toEqual( [ ...names ].sort( ( a, b ) => a.localeCompare( b ) ) );
  } );

  it( 'passes Wix\'s own formatted price through rather than rebuilding it', () => {
    // The rule the whole commerce architecture rests on: a price rendered here must be the string
    // Wix would quote, not a locally formatted version of the number beside it. A reimplemented
    // formatter is a second opinion about the amount.
    const kiosk = shopProductBySlug( 'kiosk' );
    expect( kiosk?.formattedPrice ).toBe( '₹24,999.00' );
    expect( kiosk?.price ).toBe( '24999.00' );
    expect( kiosk?.currency ).toBe( 'INR' );
  } );

  it( 'splits the description into a tagline and body paragraphs', () => {
    const kiosk = shopProductBySlug( 'kiosk' );
    expect( kiosk?.tagline ).toBe( 'Put your location to work.' );
    expect( kiosk?.body[ 0 ] ).toBe( 'You already have the place.' );
    // Every one of the seven has a tagline and at least one body paragraph, so neither the card
    // nor the detail page can render an empty lead.
    for ( const product of SHOP_PRODUCTS ) {
      expect( product.tagline.length, `${product.slug} has no tagline` ).toBeGreaterThan( 0 );
      expect( product.body.length, `${product.slug} has no body copy` ).toBeGreaterThan( 0 );
    }
  } );

  it( 'returns null for a slug that is not in the catalogue', () => {
    expect( shopProductBySlug( 'not-a-product' ) ).toBeNull();
    expect( shopProductBySlug( '' ) ).toBeNull();
  } );

  it( 'renders the fetch date in UTC, so the build cannot produce two answers', () => {
    // The snapshot timestamp is UTC. Resolving it in the visitor's zone would print a different
    // date either side of midnight for one build, which is a hydration mismatch as well as a wrong
    // answer.
    expect( CATALOG_FETCHED_AT ).toBe( '2026-09-26T02:02:44.271Z' );
    expect( catalogReadOn() ).toBe( '26 September 2026' );
  } );
} );

describe( 'toParagraphs turns merchant rich text into plain paragraphs', () => {
  it( 'breaks on </p> and <br> and drops every other tag', () => {
    expect( toParagraphs( '<p>One</p><p>Two</p>' ) ).toEqual( [ 'One', 'Two' ] );
    expect( toParagraphs( 'One<br>Two<br/>Three' ) ).toEqual( [ 'One', 'Two', 'Three' ] );
    expect( toParagraphs( '<p><span style="font-weight: 700">Bold</span></p>' ) ).toEqual( [ 'Bold' ] );
  } );

  it( 'collapses whitespace per line rather than across the whole string', () => {
    // The ordering is load-bearing. Collapsing before the split would eat the newlines the
    // replacements just created; a near-identical helper in this repo trimmed at every recursion
    // instead and produced "2 tbsptoastedsesame oil" - words fused at a tag boundary.
    expect( toParagraphs( '<p>  a   b  </p>\n<p>\tc\n\nd</p>' ) ).toEqual( [ 'a b', 'c d' ] );
  } );

  it( 'decodes &amp; last, so a double-encoded entity is not decoded twice', () => {
    // "&amp;lt;" is a literal "&lt;" in the source. Decoding &amp; first would turn it into "<".
    expect( toParagraphs( '<p>&amp;lt;</p>' ) ).toEqual( [ '&lt;' ] );
    expect( toParagraphs( '<p>Tom &amp; Jerry</p>' ) ).toEqual( [ 'Tom & Jerry' ] );
    expect( toParagraphs( '<p>&nbsp;a&#39;b&quot;c&nbsp;</p>' ) ).toEqual( [ 'a\'b"c' ] );
  } );

  it( 'drops empty paragraphs instead of rendering blank lines', () => {
    expect( toParagraphs( '<p></p><p>a</p><p>   </p>' ) ).toEqual( [ 'a' ] );
    expect( toParagraphs( '' ) ).toEqual( [] );
  } );
} );

describe( 'the derived head strings stay inside the bounds seocheck enforces', () => {
  /*
   * tools/browser/seocheck.js fails a title outside 15-75 characters or a description outside
   * 50-170. Those are browser assertions against the built export, so they only run after a build;
   * these run on every push and name the product that broke the bound.
   */
  it( 'keeps every product title within 15-75 characters', () => {
    for ( const product of SHOP_PRODUCTS ) {
      const title = shopPageTitle( product );
      expect( title.length, `${product.slug}: "${title}"` ).toBeGreaterThanOrEqual( 15 );
      expect( title.length, `${product.slug}: "${title}"` ).toBeLessThanOrEqual( 75 );
      expect( title.endsWith( '| WECARE.DIGITAL' ), `${product.slug} drops the brand suffix` ).toBe( true );
    }
  } );

  it( 'keeps every product description within 50-170 characters', () => {
    for ( const product of SHOP_PRODUCTS ) {
      const description = shopMetaDescription( product );
      expect( description.length, `${product.slug}: "${description}"` ).toBeGreaterThanOrEqual( 50 );
      expect( description.length, `${product.slug}: "${description}"` ).toBeLessThanOrEqual( 170 );
    }
  } );

  it( 'never cuts a sentence in half to fit the budget', () => {
    // The whole point of joining whole paragraphs rather than truncating: the description is the
    // owner's sentences, entire, or it is not used. Measured lengths across the seven: 54 to 159.
    for ( const product of SHOP_PRODUCTS ) {
      const description = shopMetaDescription( product );
      expect( description ).not.toContain( '…' );
      expect( description.startsWith( product.tagline ), `${product.slug} does not open with its tagline` ).toBe( true );
      // Every character of it comes from a whole paragraph, in order.
      const whole = [ product.tagline, ...product.body ].join( ' ' );
      expect( whole.startsWith( description ) ).toBe( true );
    }
  } );

  it( 'gives every product a distinct title and description', () => {
    // seocheck asserts uniqueness across all 24 public routes; this is the half of it that is
    // this file's responsibility.
    const titles = SHOP_PRODUCTS.map( shopPageTitle );
    const descriptions = SHOP_PRODUCTS.map( shopMetaDescription );
    expect( new Set( titles ).size ).toBe( titles.length );
    expect( new Set( descriptions ).size ).toBe( descriptions.length );
  } );

  it( 'builds a product path with the trailing slash the canonical form needs', () => {
    // trailingSlash is set in next.config.js, so the slashless spelling 308s. A canonical or a
    // breadcrumb item pointing at it names a URL that redirects.
    expect( shopProductPath( SYNTHETIC ) ).toBe( '/shop/sold-out-thing/' );
    for ( const product of SHOP_PRODUCTS ) {
      expect( shopProductPath( product ) ).toMatch( /^\/shop\/[a-z0-9-]+\/$/ );
    }
  } );
} );

/**
 * THE TRAILING SLASH IS ABSENT IN jsdom, AND THAT IS THE ROUTER RATHER THAN THE PAGE.
 *
 * next/link puts href through resolveHref, which calls normalizePathTrailingSlash - and that
 * REMOVES a trailing slash unless `trailingSlash` is true. The flag lives in next.config.js, which
 * a vitest run does not load, so a Link given '/contact/' renders href="/contact" here and
 * href="/contact/" in the export.
 *
 * Measured on the built export rather than assumed:
 *   out/shop/index.html        href="/shop/file-assist/" ... href="/shop/viveka/"   (7 links)
 *   out/shop/kiosk/index.html  href="/contact/"  href="/shop/"
 *
 * So these tests assert the path the PAGE hands to Link, normalised the way this environment
 * normalises it. The canonical form of the built URL is seocheck.js's assertion, against the
 * export, where the real config applies. Hard-coding the slashless string instead would hide which
 * of the two is being checked.
 */
const asRendered = ( path: string ): string => path.replace( /\/$/, '' ) || '/';

describe( 'the listing page', () => {
  it( 'links every product at its own URL', () => {
    render( <ShopIndex products={ SHOP_PRODUCTS } /> );
    for ( const product of SHOP_PRODUCTS ) {
      const link = screen.getByRole( 'link', { name: product.name } );
      expect( link.getAttribute( 'href' ) ).toBe( asRendered( shopProductPath( product ) ) );
    }
  } );

  it( 'prints the price Wix formatted, not a rebuilt one', () => {
    render( <ShopIndex products={ SHOP_PRODUCTS } /> );
    expect( screen.getByText( '₹24,999.00' ) ).toBeTruthy();
    expect( screen.getByText( '₹599.00' ) ).toBeTruthy();
  } );

  it( 'says when the prices were read, rather than implying they are live', () => {
    render( <ShopIndex products={ SHOP_PRODUCTS } /> );
    expect( screen.getByText( /read from the store catalogue on 26 September 2026/ ) ).toBeTruthy();
  } );

  it( 'says nothing about stock while everything is in stock', () => {
    // Seven identical "In stock" chips would be seven badges carrying no information, which is why
    // the notice is rendered only when it is false. This is the negative half.
    render( <ShopIndex products={ SHOP_PRODUCTS } /> );
    expect( screen.queryByText( /Not available right now/ ) ).toBeNull();
  } );

  it( 'marks an item that is out of stock', () => {
    // The positive half, and the reason this page takes its catalogue as a prop: every item in the
    // committed snapshot is in stock, so this branch is unreachable from the real data.
    render( <ShopIndex products={ [ SYNTHETIC ] } /> );
    expect( screen.getByText( 'Not available right now.' ) ).toBeTruthy();
  } );
} );

describe( 'the product page', () => {
  it( 'renders the name as the only h1 and the description as text', () => {
    const kiosk = shopProductBySlug( 'kiosk' ) as ShopProduct;
    const { container } = render( <ShopProductPage product={ kiosk } /> );
    const h1s = container.querySelectorAll( 'h1' );
    expect( h1s ).toHaveLength( 1 );
    expect( h1s[ 0 ].textContent ).toBe( 'Kiosk' );
    expect( screen.getByText( kiosk.tagline ) ).toBeTruthy();
    expect( container.querySelectorAll( 'p.shopd-p' ) ).toHaveLength( kiosk.body.length );
  } );

  it( 'never puts merchant HTML into the DOM as HTML', () => {
    /*
     * THE ASSERTION THAT MATTERS MOST IN THIS FILE. descriptionHtml is rich text from a
     * third-party CMS; rendering it through dangerouslySetInnerHTML would make the storefront an
     * XSS surface that depends on Wix's sanitiser rather than ours. Every one of the seven
     * descriptions contains <span style="font-weight: 700">, so if the tags were passing through,
     * this would find them.
     */
    for ( const product of SHOP_PRODUCTS ) {
      const { container, unmount } = render( <ShopProductPage product={ product } /> );
      const about = container.querySelector( 'section.shopd-about' ) as HTMLElement;
      expect( about, `${product.slug} has no about section` ).toBeTruthy();
      expect( about.innerHTML, `${product.slug} leaked a Wix span` ).not.toContain( '<span' );
      expect( about.innerHTML, `${product.slug} leaked a style attribute` ).not.toContain( 'style=' );
      unmount();
    }
  } );

  it( 'sends the call to action to /contact/, because there is no checkout', () => {
    const kiosk = shopProductBySlug( 'kiosk' ) as ShopProduct;
    render( <ShopProductPage product={ kiosk } /> );
    const cta = screen.getByRole( 'link', { name: 'Ask about Kiosk' } );
    expect( cta.getAttribute( 'href' ) ).toBe( asRendered( '/contact/' ) );
  } );

  it( 'states that nothing is charged on the page', () => {
    // The boundary statement is the honest part of shipping a priced catalogue with no checkout,
    // and it is load-bearing rather than decorative: an order in this system exists only after a
    // payment has been verified against the provider.
    const kiosk = shopProductBySlug( 'kiosk' ) as ShopProduct;
    render( <ShopProductPage product={ kiosk } /> );
    expect( screen.getByText( /not a checkout: nothing is charged here/ ) ).toBeTruthy();
    expect( screen.getByText( /order only exists once a payment has been verified/ ) ).toBeTruthy();
  } );

  it( 'marks a product that is out of stock', () => {
    render( <ShopProductPage product={ SYNTHETIC } /> );
    expect( screen.getByText( 'Not available right now.' ) ).toBeTruthy();
  } );

  it( 'offers a way back to the listing', () => {
    const kiosk = shopProductBySlug( 'kiosk' ) as ShopProduct;
    render( <ShopProductPage product={ kiosk } /> );
    expect( screen.getByRole( 'link', { name: 'All items in the shop' } ).getAttribute( 'href' ) )
      .toBe( asRendered( '/shop/' ) );
  } );
} );
