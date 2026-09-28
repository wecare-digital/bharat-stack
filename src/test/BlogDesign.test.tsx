import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import BlogIndex from '../pages/blog/index';
import BlogPostPage from '../pages/post/[slug]';
import type { PublicBlogPost } from '../lib/public-blog';

vi.mock( 'next/head', () => ( { default: ( { children }: { children: React.ReactNode } ) => <>{ children }</> } ) );

const cssOf = ( container: HTMLElement ) =>
  Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

const samplePost: PublicBlogPost = {
  id: 'post-1',
  title: 'A Clear Question Can Change the Work',
  slug: 'a-clear-question-can-change-the-work',
  excerpt: 'A short excerpt that makes the listing readable without turning the card into UI chrome.',
  url: '/post/a-clear-question-can-change-the-work',
  category: 'Conversations',
  tags: [ 'Practice', 'Inquiry' ],
  authorName: 'Anew by WECARE.DIGITAL',
  publishedDate: '2026-09-27T00:00:00Z',
  richContent: {
    nodes: [
      {
        type: 'PARAGRAPH',
        nodes: [ { type: 'TEXT', textData: { text: 'First paragraph.', decorations: [] } } ],
      },
      {
        type: 'PARAGRAPH',
        nodes: [ { type: 'TEXT', textData: { text: 'Second paragraph.', decorations: [] } } ],
      },
      {
        type: 'HEADING',
        headingData: { level: 2 },
        nodes: [ { type: 'TEXT', textData: { text: 'A section', decorations: [] } } ],
      },
    ],
  },
};

describe( 'Blog design alignment', () => {
  it( 'uses the homepage hero typography and does not repeat the brand eyebrow on /blog/', () => {
    const { container } = render( <BlogIndex posts={ [ samplePost ] } /> );
    const css = cssOf( container );

    expect( container.querySelector( '.eyebrow' ) ).toBeNull();
    expect( container.querySelector( '.blog-hero h1' )?.textContent ).toBe( 'Blog' );

    expect( css ).toContain( '.blog-shell{max-width:1300px' );
    expect( css ).toContain( 'h1{font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;letter-spacing:-0.04em' );
    expect( css ).toContain( '.blog-hero>p{font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:rgba(0,0,0,.898)' );
  } );

  it( 'keeps listing cards typographic, readable and responsive rather than dashboard-like', () => {
    const { container } = render( <BlogIndex posts={ [ samplePost ] } /> );
    const css = cssOf( container );

    expect( css ).toContain( '.post-card{border:1px solid #e5e7eb;border-radius:14px' );
    expect( css ).toContain( 'h2{font-size:23px;line-height:1.22' );
    expect( css ).toContain( '.post-copy p{font-size:16px;line-height:1.5' );
    expect( css ).toContain( '@media(max-width:1050px)' );
    expect( css ).toContain( '@media(max-width:680px)' );
    expect( css ).toContain( ':global(a:focus-visible)' );
  } );

  it( 'uses a reading measure and paragraph rhythm appropriate for long-form posts', () => {
    const { container } = render( <BlogPostPage post={ samplePost } /> );
    const css = cssOf( container );

    expect( css ).toContain( '.article-shell{max-width:1300px' );
    expect( css ).toContain( 'article{max-width:700px' );
    expect( css ).toContain( 'h1{font-size:clamp(36px,4.3vw,60px);line-height:1.04;letter-spacing:-0.04em;color:rgba(0,0,0,.95)' );
    expect( css ).toContain( 'text-wrap:balance;max-width:20ch' );
    expect( css ).toContain( 'font-size:20px;line-height:1.55;letter-spacing:-.125px' );
    expect( css ).toContain( '.content :global(p + p){margin-top:28px}' );
  } );

  it( 'finishes the rich-content styles for headings, lists, quotes and accessible links', () => {
    const { container } = render( <BlogPostPage post={ samplePost } /> );
    const css = cssOf( container );

    expect( css ).toContain( '.content :global(h2){font-size:30px;line-height:1.15' );
    expect( css ).toContain( '.content :global(ul),.content :global(ol){margin:28px 0;padding-inline-start:1.4em}' );
    expect( css ).toContain( '.content :global(li + li){margin-top:10px}' );
    expect( css ).toContain( '.content :global(blockquote){margin:36px 0;padding:2px 0 2px 22px;border-inline-start:3px solid #d1f470;font-size:21px;line-height:1.5;' );
    expect( css ).toContain( '.content :global(a:focus-visible){outline:3px solid rgba(26,58,42,.25);outline-offset:3px;border-radius:2px}' );
  } );
} );
