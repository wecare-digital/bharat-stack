import fs from 'fs';
import path from 'path';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import BlogIndex from '../pages/blog/index';
import BlogPostPage from '../pages/post/[slug]';
import ShareLinks from '../components/ShareLinks';
import {
  MEDIA_BASE, SOCIAL_CARD_URL, SOCIAL_CARD_W, SOCIAL_CARD_H, SHARE_CARD_TYPE, whatsappShareHref,
} from '../config/share';
import { toBlogCard, type PublicBlogPost } from '../lib/public-blog';

/**
 * LINK PREVIEWS, AND THE SHARE CONTROLS.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * /blog/ and /post/<slug>/ shipped no og:image at all, and the post page asked for the small
 * twitter card. Measured on the live site before the change:
 *
 *   /                 og:image present   twitter:card summary_large_image
 *   /blog/            og:image MISSING   twitter:card MISSING
 *   /post/<slug>/     og:image MISSING   twitter:card summary   twitter:image MISSING
 *
 * The cause is the `!isContentPublic` gate in pages/_app.tsx, which suppresses the sitewide Head
 * for the five content routes because they declare their own - and theirs declared no image. It
 * is the same gate that once swallowed the favicon, which is why this is asserted rather than
 * left to a comment: the next route added to that gate will have the same hole.
 *
 * The head is rendered through a mocked next/head so the tags land in the container, the way
 * BlogDesign.test.tsx already does it.
 */

vi.mock( 'next/head', () => ( { default: ( { children }: { children: React.ReactNode } ) => <>{ children }</> } ) );

const samplePost: PublicBlogPost = {
  id: 'post-1',
  title: 'A Clear Question Can Change the Work',
  slug: 'a-clear-question-can-change-the-work',
  excerpt: 'A short excerpt.',
  url: '/post/a-clear-question-can-change-the-work',
  category: 'Conversations',
  tags: [ 'Practice' ],
  authorName: 'Anew by WECARE.DIGITAL',
  publishedDate: '2026-09-27T00:00:00Z',
  seoTitle: 'A Clear Question Can Change the Work | WECARE.DIGITAL',
  metaDescription: 'A meta description.',
  robots: 'index, follow',
};

const card = toBlogCard( samplePost );

/**
 * READ FROM THE DOCUMENT, NOT THE RENDER CONTAINER - and that is React 19, not a mistake.
 *
 * React 19 hoists document metadata: a meta, title or link rendered anywhere in a tree is moved
 * into document.head. So with next/head mocked out to render its children inline, these tags do
 * not stay in the container the way the JSON-LD script tags do - scripts without async are not
 * hoisted, which is why asserting on those from the container works and this does not.
 *
 * Querying the document is therefore correct rather than lax. The risk it carries is a tag
 * lingering between cases, and the og:type assertions are what cover it: the blog index must say
 * "website" and the post must say "article", so a leaked tag from either test fails the other.
 */
const metaOf = ( _container: HTMLElement, key: string ) =>
  document.querySelector( `meta[property="${key}"]` )?.getAttribute( 'content' )
  ?? document.querySelector( `meta[name="${key}"]` )?.getAttribute( 'content' )
  ?? null;

/** The tag set every shareable public surface has to carry. */
const expectShareCard = ( container: HTMLElement ) => {
  expect( metaOf( container, 'og:image' ) ).toBe( SOCIAL_CARD_URL );
  expect( metaOf( container, 'og:image:secure_url' ) ).toBe( SOCIAL_CARD_URL );
  expect( metaOf( container, 'og:image:width' ) ).toBe( SOCIAL_CARD_W );
  expect( metaOf( container, 'og:image:height' ) ).toBe( SOCIAL_CARD_H );
  expect( metaOf( container, 'og:image:type' ) ).toBe( 'image/png' );
  expect( metaOf( container, 'og:image:alt' ) ).toBeTruthy();
  expect( metaOf( container, 'og:site_name' ) ).toBe( 'WECARE.DIGITAL' );
  // The card type comes from the same module as the image, because the two have to agree about
  // shape: "summary" frames a 1:1 image, summary_large_image centre-crops it.
  expect( metaOf( container, 'twitter:card' ) ).toBe( SHARE_CARD_TYPE );
  expect( metaOf( container, 'twitter:image' ) ).toBe( SOCIAL_CARD_URL );
};

describe( 'Share previews', () => {
  it( 'gives the blog index a full link-preview card, which it had none of', () => {
    const { container } = render(
      <BlogIndex posts={ [ card ] } page={ 1 } totalPages={ 1 } totalPosts={ 1 }
        categories={ [ 'Conversations' ] } categoryCounts={ { Conversations: 1 } }
        activeCategory="Conversations" defaultCategory="Conversations" />
    );
    expectShareCard( container );
    expect( metaOf( container, 'og:type' ) ).toBe( 'website' );
  } );

  it( 'gives a post the same card, and declares itself an article', () => {
    const { container } = render( <BlogPostPage post={ samplePost } /> );
    expectShareCard( container );
    expect( metaOf( container, 'og:type' ) ).toBe( 'article' );
    // og:url has to be the canonical, not a path: a share target handed a relative URL shares
    // nothing, and a crawler resolves it against whatever page it found the link on.
    expect( metaOf( container, 'og:url' ) ).toBe( `https://wecare.digital/post/${samplePost.slug}/` );
  } );

  /**
   * THE DRIFT GUARD config/share.ts PROMISES.
   *
   * pages/_app.tsx keeps its own copies of these literals because BrandAssets.test.ts pins them
   * to that file by source string, and moving them would mean rewriting six assertions for no
   * behavioural gain. The cost of that decision is two declarations of one value, so this holds
   * them equal - if someone repoints the card in one place the other fails here rather than
   * silently serving two different images to two halves of the site.
   */
  it( 'keeps the card in config/share.ts identical to the copy in _app.tsx', () => {
    const app = fs.readFileSync(
      path.join( __dirname, '..', 'pages', '_app.tsx' ), 'utf8'
    );
    expect( app ).toContain( `const MEDIA_BASE = '${MEDIA_BASE}'` );
    // _app.tsx aliases its share image to LOGO_URL rather than restating the filename, so there is
    // one place in that file where the asset is named.
    expect( app ).toContain( 'const SOCIAL_CARD_URL = LOGO_URL;' );
    expect( app ).toContain( 'const LOGO_URL = `${MEDIA_BASE}/wecare-digital.png`' );
    expect( app ).toContain( `const SOCIAL_CARD_W = '${SOCIAL_CARD_W}'` );
    expect( app ).toContain( `const SOCIAL_CARD_H = '${SOCIAL_CARD_H}'` );
    // And the shared module resolves to the same absolute URL the marketing branch emits.
    expect( SOCIAL_CARD_URL ).toBe( 'https://wecare.digital/get/o/stream/media/m/wecare-digital.png' );
  } );

  /**
   * THE PAIRING INVARIANT, which is the thing that actually prevents a broken preview.
   *
   * The share image and the Twitter card type have to agree about shape. A 1:1 image in a
   * summary_large_image slot is centre-cropped top and bottom - that is what once cut the ends off
   * this mark - and a 1.91:1 image in a "summary" slot is squeezed into a small square instead of
   * getting the wide frame it was designed for. Either mistake is one careless edit away, because
   * the two values look unrelated.
   *
   * So this asserts the RELATIONSHIP rather than the values: if the declared image is square the
   * card must be "summary", and if it is not square the card must be the large one. Swapping the
   * asset later is then a change this test either accepts or explains.
   */
  it( 'keeps the card type agreeing with the share image shape', () => {
    const square = SOCIAL_CARD_W === SOCIAL_CARD_H;
    expect( SHARE_CARD_TYPE ).toBe( square ? 'summary' : 'summary_large_image' );

    // And whatever the shape, it stays inside WhatsApp's stated limits: at least 300px wide, and
    // an aspect ratio no wider than 4:1.
    const w = Number( SOCIAL_CARD_W );
    const h = Number( SOCIAL_CARD_H );
    expect( w ).toBeGreaterThanOrEqual( 300 );
    expect( w / h ).toBeLessThanOrEqual( 4 );
  } );

  /**
   * THE STAGED WIDE CARD STAYS FIT FOR PURPOSE, even though nothing currently points at it.
   *
   * docs/brand/wd-brand-16x9.png is the 1200x675 / 273 KB re-export of the designed card - mark,
   * wordmark and tagline - kept as the documented way back to a wide preview if the S3 upload is
   * ever done. It is a fallback, not the live asset: the share image is the square icon, which
   * needs no upload.
   *
   * This used to assert the file's pixels equalled SOCIAL_CARD_W/H. That coupling is now wrong and
   * was removed - tying the live declaration to an asset the site does not use would fail the
   * moment the icon was adopted, which is exactly what happened. What is still worth holding is
   * that the staged file remains VALID, so whoever picks it up later is not inheriting a broken
   * one: a real PNG, inside both weight ceilings, past the minimum width, under the aspect limit,
   * and opaque.
   *
   * Parsed by hand rather than with an image library: a PNG's IHDR is the first chunk after the
   * 8-byte signature and width and height are big-endian uint32s at offsets 16 and 20. No
   * dependency for four bytes.
   */
  it( 'keeps the staged wide-card fallback valid, opaque and inside WhatsApp limits', () => {
    const file = path.join( __dirname, '..', '..', 'docs', 'brand', 'wd-brand-16x9.png' );
    const bytes = fs.readFileSync( file );

    expect( bytes.subarray( 0, 8 ).toString( 'hex' ) ).toBe( '89504e470d0a1a0a' ); // PNG signature
    expect( bytes.subarray( 12, 16 ).toString( 'ascii' ) ).toBe( 'IHDR' );
    const width = bytes.readUInt32BE( 16 );
    const height = bytes.readUInt32BE( 20 );

    // Meta's documented ceiling, and the working one that accounts for a silent drop.
    expect( bytes.length ).toBeLessThan( 600 * 1024 );
    expect( bytes.length ).toBeLessThan( 300 * 1024 );
    // Their stated minimum width, and the 4:1 aspect ceiling.
    expect( width ).toBeGreaterThanOrEqual( 300 );
    expect( width / height ).toBeLessThanOrEqual( 4 );
    // It is the WIDE one - if this ever became square it would no longer be the thing the README
    // describes, and adopting it would need the card type changed as well.
    expect( width ).toBeGreaterThan( height );

    // OPAQUE. The binding rule for anything handed to a renderer we do not control is that it must
    // not rely on alpha - Apple and the preview services flatten it to black and the mark is
    // light. A palette PNG carries transparency in a tRNS chunk, so its absence is the check.
    expect( bytes.includes( Buffer.from( 'tRNS', 'ascii' ) ) ).toBe( false );
  } );
} );

describe( 'Share controls', () => {
  /**
   * api.whatsapp.com, NOT wa.me. wa.me is built around wa.me/<number> and serves an error page
   * when called without one - and a share button cannot know the recipient, which is the whole
   * reason the reader is being shown a contact picker. Asserted because the two hosts look
   * interchangeable and only one of them works for this job.
   */
  it( 'builds a WhatsApp link that opens a contact picker rather than an error page', () => {
    const href = whatsappShareHref( 'A & B', 'https://wecare.digital/post/x/' );
    expect( href.startsWith( 'https://api.whatsapp.com/send?text=' ) ).toBe( true );
    expect( href ).not.toContain( 'wa.me' );
    // One encoded text field, because WhatsApp has one message body - there is no url parameter.
    expect( href ).toContain( encodeURIComponent( 'A & B' ) );
    expect( href ).toContain( encodeURIComponent( 'https://wecare.digital/post/x/' ) );
    // The ampersand must not survive raw, or it ends the parameter and truncates the message.
    expect( href.split( '?text=' )[ 1 ] ).not.toContain( '&' );
  } );

  it( 'ships a working WhatsApp link with no JavaScript, and hides the script-only controls', () => {
    const { container } = render(
      <ShareLinks url="https://wecare.digital/post/x/" title="A Post" />
    );

    // The baseline: a real anchor with a real href, present in the static export.
    const wa = screen.getByRole( 'link', { name: /WhatsApp/i } );
    expect( wa.getAttribute( 'href' ) ).toBe( whatsappShareHref( 'A Post', 'https://wecare.digital/post/x/' ) );
    // Opening a share target must not hand it a window.opener back into this page.
    expect( wa.getAttribute( 'rel' ) ).toContain( 'noopener' );

    // jsdom has neither navigator.share nor a clipboard, so neither capability class is added and
    // both controls stay display:none. This is the assertion that the row degrades instead of
    // offering buttons that cannot work - and it is feature detection doing it, not a device list.
    const row = container.querySelector( '.share-row' );
    expect( row ).not.toBeNull();
    expect( row?.classList.contains( 'is-native' ) ).toBe( false );
    expect( row?.classList.contains( 'is-clip' ) ).toBe( false );
  } );

  /**
   * THE ICON-ONLY CONTRACT. These controls carry no visible text, which is the one change that can
   * silently make a control group unusable: an icon button with no aria-label announces as an empty
   * string, or at best as its filename, so a screen reader reader gets three anonymous buttons.
   *
   * Asserted through getByLabelText rather than by reading the attribute, because that resolves the
   * accessible NAME the way an assistive technology would - it would fail just as loudly if the
   * label were on the wrong element or cancelled by an aria-hidden ancestor.
   *
   * The tooltip is also checked for aria-hidden. Without it the visible word and the label are both
   * in the accessible name and the control announces its own name twice.
   */
  it( 'labels every icon-only control, and keeps the visual tip out of the accessible name', () => {
    vi.stubGlobal( 'navigator', Object.create( navigator, {
      share: { value: () => Promise.resolve(), configurable: true },
      canShare: { value: () => true, configurable: true },
      clipboard: { value: { writeText: () => Promise.resolve() }, configurable: true },
    } ) );

    const { container } = render(
      <ShareLinks url="https://wecare.digital/post/x/" title="A Post" />
    );

    // All three announce something meaningful.
    expect( screen.getByLabelText( 'Share this page on WhatsApp' ) ).toBeInTheDocument();
    expect( screen.getByLabelText( 'Share this page using your device' ) ).toBeInTheDocument();
    expect( screen.getByLabelText( 'Copy link to this page' ) ).toBeInTheDocument();

    // No control is left without a name, and none of them leans on visible text for it.
    const controls = Array.from( container.querySelectorAll( '.share-btn' ) );
    expect( controls ).toHaveLength( 3 );
    for ( const c of controls ) {
      expect( c.getAttribute( 'aria-label' ) ).toBeTruthy();
      // The only text inside is the tip, and the tip is hidden from the accessibility tree.
      const tip = c.querySelector( '.share-tip' );
      expect( tip ).not.toBeNull();
      expect( tip?.getAttribute( 'aria-hidden' ) ).toBe( 'true' );
    }

    // 44px square, drawn at the WCAG 2.5.8 floor rather than above it - a circle has to be square
    // to be round, so this is the one place the floor is also the size.
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( n => n.textContent || '' ).join( '' );
    expect( css ).toContain( 'width:44px;height:44px' );
    expect( css ).toContain( 'border-radius:50%' );
    // The home CTA's hover, which is what makes the group draw the eye.
    expect( css ).toContain( 'transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)' );

    vi.unstubAllGlobals();
  } );

  it( 'reveals the OS share sheet only when the browser really has the API', () => {
    const share = vi.fn( () => Promise.resolve() );
    vi.stubGlobal( 'navigator', Object.create( navigator, {
      share: { value: share, configurable: true },
      canShare: { value: () => true, configurable: true },
    } ) );

    const { container } = render(
      <ShareLinks url="https://wecare.digital/post/x/" title="A Post" />
    );
    expect( container.querySelector( '.share-row' )?.classList.contains( 'is-native' ) ).toBe( true );

    vi.unstubAllGlobals();
  } );
} );
