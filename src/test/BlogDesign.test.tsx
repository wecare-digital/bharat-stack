import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
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

const secondPost: PublicBlogPost = {
  ...samplePost,
  id: 'post-2',
  title: 'A Guide to Better Decisions',
  slug: 'a-guide-to-better-decisions',
  category: 'Guides',
};

describe( 'Blog design alignment', () => {
  /**
   * REWRITTEN WITH THE PAGE, AND THE INTENT IS UNCHANGED.
   *
   * This asserted that /blog/ matched the home page's hero typography by pinning blog-LOCAL
   * copies of those rungs: .blog-hero h1 reading "Blog", .blog-shell{max-width:1300px, a
   * clamp(36px,4.3vw,60px) h1 rule and a .blog-hero>p body rule. That was the right intent
   * pursued by duplication - the numbers were re-typed into this page, so they could drift
   * from the home page they were copied from and this test would have kept passing.
   *
   * The page now renders the actual RotatingHero the home page uses, so the typography cannot
   * drift: there is one declaration, in one component. The assertions therefore move from
   * "these numbers appear in this page's CSS" to "this page renders that component".
   *
   * THE ONE THING KEPT VERBATIM is the no-repeated-brand-eyebrow rule, because that is a
   * design decision rather than an implementation detail. The home page removed its own copy
   * of the lime badge for exactly this reason - it restated the header's lockup 109px below
   * it - so badgeLabel is deliberately not passed here, and RotatingHero renders no
   * .brand-badge without it.
   */
  it( 'renders the homepage rotating hero on /blog/, and still does not repeat the brand eyebrow', () => {
    const { container } = render( <BlogIndex posts={ [ samplePost ] } /> );

    // The shared hero, not a local copy of its numbers.
    expect( container.querySelector( '.rh-hero' ) ).not.toBeNull();
    expect( container.querySelector( '.rh-head' ) ).not.toBeNull();

    // The old markup is gone, along with the line that restated the heading.
    expect( container.querySelector( '.blog-hero' ) ).toBeNull();
    expect( container.textContent ).not.toContain( 'Ideas, guides and updates published' );

    // The brand lockup must not appear twice on the page: header owns it.
    expect( container.querySelector( '.brand-badge' ) ).toBeNull();
    expect( container.querySelector( '.eyebrow' ) ).toBeNull();

    // Exactly one h1, and it is the hero's - the page has no competing headline.
    expect( container.querySelectorAll( 'h1' ) ).toHaveLength( 1 );

    // The breadcrumb and the blog-scoped search box are both present.
    expect( container.querySelector( 'nav[aria-label="Breadcrumb"]' ) ).not.toBeNull();
    expect( container.querySelector( 'form[role="search"]' ) ).not.toBeNull();
  } );

  it( 'filters the listing by text as well as by category', () => {
    render( <BlogIndex posts={ [ samplePost, secondPost ] } /> );
    const box = screen.getByLabelText( 'Search the blog' );

    // Matches the title of the second post only.
    fireEvent.change( box, { target: { value: 'Better Decisions' } } );
    expect( screen.queryByRole( 'heading', { name: samplePost.title } ) ).toBeNull();
    expect( screen.getByRole( 'heading', { name: secondPost.title } ) ).toBeInTheDocument();

    // A category name typed as text finds its posts even with the All pill active.
    fireEvent.change( box, { target: { value: 'conversations' } } );
    expect( screen.getByRole( 'heading', { name: samplePost.title } ) ).toBeInTheDocument();
    expect( screen.queryByRole( 'heading', { name: secondPost.title } ) ).toBeNull();

    // Clearing restores everything.
    fireEvent.change( box, { target: { value: '   ' } } );
    expect( screen.getByRole( 'heading', { name: samplePost.title } ) ).toBeInTheDocument();
    expect( screen.getByRole( 'heading', { name: secondPost.title } ) ).toBeInTheDocument();
  } );

  it( 'switches between all posts and each available category without a page load', () => {
    const { container } = render( <BlogIndex posts={ [ samplePost, secondPost ] } /> );

    const all = screen.getByRole( 'button', { name: 'All' } );
    const conversations = screen.getByRole( 'button', { name: 'Conversations' } );
    const guides = screen.getByRole( 'button', { name: 'Guides' } );

    expect( all ).toHaveAttribute( 'aria-pressed', 'true' );
    expect( screen.getByRole( 'heading', { name: samplePost.title } ) ).toBeInTheDocument();
    expect( screen.getByRole( 'heading', { name: secondPost.title } ) ).toBeInTheDocument();

    fireEvent.click( conversations );
    expect( conversations ).toHaveAttribute( 'aria-pressed', 'true' );
    expect( screen.getByRole( 'heading', { name: samplePost.title } ) ).toBeInTheDocument();
    expect( screen.queryByRole( 'heading', { name: secondPost.title } ) ).toBeNull();

    fireEvent.click( guides );
    expect( guides ).toHaveAttribute( 'aria-pressed', 'true' );
    expect( screen.queryByRole( 'heading', { name: samplePost.title } ) ).toBeNull();
    expect( screen.getByRole( 'heading', { name: secondPost.title } ) ).toBeInTheDocument();

    const css = cssOf( container );
    expect( css ).toContain( '.category-switch{display:flex;gap:8px;overflow-x:auto' );
    expect( css ).toContain( '.category-switch button[aria-pressed="true"]{background:#d1f470' );
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
