import fs from 'fs';
import path from 'path';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import BlogIndex from '../pages/blog/index';
import BlogPostPage from '../pages/post/[slug]';
import ShareLinks from '../components/ShareLinks';
import {
  MEDIA_BASE, SOCIAL_CARD_URL, SOCIAL_CARD_W, SOCIAL_CARD_H, whatsappShareHref,
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
  // summary_large_image, not summary: the asset is 16:9 and the small card centre-crops a wide
  // image to a square, which takes the ends off a wordmark.
  expect( metaOf( container, 'twitter:card' ) ).toBe( 'summary_large_image' );
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
    expect( app ).toContain( 'const SOCIAL_CARD_URL = `${MEDIA_BASE}/wd-brand-16x9.png`' );
    expect( app ).toContain( `const SOCIAL_CARD_W = '${SOCIAL_CARD_W}'` );
    expect( app ).toContain( `const SOCIAL_CARD_H = '${SOCIAL_CARD_H}'` );
    // And the shared module resolves to the same absolute URL the marketing branch emits.
    expect( SOCIAL_CARD_URL ).toBe( 'https://wecare.digital/get/o/stream/media/m/wd-brand-16x9.png' );
  } );

  /**
   * THE DECLARED SIZE IS CHECKED AGAINST THE ACTUAL FILE, not just against the other declaration.
   *
   * og:image:width and og:image:height once read 512x512 against a 1080x1080 object, and nothing
   * caught it because every check compared one written-down number to another written-down number.
   * This reads the PNG header of the committed replacement in docs/brand/ and fails if the pixels
   * and the declaration disagree, which is the only version of this assertion that could have
   * caught the original bug.
   *
   * It also holds the WEIGHT, which is why the asset was re-exported at all. The live card was
   * 801,077 bytes against the 600 KB ceiling Meta documents for a WhatsApp link preview, so the
   * preview was being dropped on the platform this company is built around. 300 KB is the working
   * limit rather than 600 KB because WhatsApp discards an oversized image silently and the
   * reported ceiling has no margin in it.
   *
   * The file is parsed by hand rather than with an image library: a PNG's IHDR is the first chunk
   * after the 8-byte signature, width and height are big-endian uint32s at offsets 16 and 20, and
   * that is the whole of what this needs. No dependency for four bytes.
   */
  it( 'keeps the committed card within WhatsApp limits and true to its declared size', () => {
    const file = path.join( __dirname, '..', '..', 'docs', 'brand', 'wd-brand-16x9.png' );
    const bytes = fs.readFileSync( file );

    expect( bytes.subarray( 0, 8 ).toString( 'hex' ) ).toBe( '89504e470d0a1a0a' ); // PNG signature
    expect( bytes.subarray( 12, 16 ).toString( 'ascii' ) ).toBe( 'IHDR' );
    const width = bytes.readUInt32BE( 16 );
    const height = bytes.readUInt32BE( 20 );

    // The pixels ARE what the meta tags claim.
    expect( String( width ) ).toBe( SOCIAL_CARD_W );
    expect( String( height ) ).toBe( SOCIAL_CARD_H );

    // Meta's documented ceiling, and the working one that accounts for a silent drop.
    expect( bytes.length ).toBeLessThan( 600 * 1024 );
    expect( bytes.length ).toBeLessThan( 300 * 1024 );
    // Their stated minimum width, and the 4:1 aspect ceiling.
    expect( width ).toBeGreaterThanOrEqual( 300 );
    expect( width / height ).toBeLessThanOrEqual( 4 );

    // STILL OPAQUE. The binding rule for anything handed to a renderer we do not control is that
    // it must not rely on alpha - Apple and the preview services flatten it to black and this
    // mark is light. A palette PNG carries transparency in a tRNS chunk, so its absence is the
    // check. BrandAssets.test.ts argues the rule; this enforces it on the bytes.
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
