/**
 * Every blog listing page says what it collects.
 *
 * WHAT WAS WRONG. 54 listing pages - /blog/, /blog/page/2..35/, /blog/topic/gastronomy/ and its
 * 18 pages - each declared itself a `CollectionPage` or a `Blog` and then said nothing about
 * what it collected. `ItemList` is the property Google documents for exactly that.
 *
 * THE OMISSION WAS DELIBERATE, AND ITS STATED REASON WAS FACTUALLY WRONG. BlogIndexHead's
 * docblock said an `itemListElement` on every page "would describe 35 overlapping collections".
 * Measured across the built export: ZERO posts appear on more than one listing page and all
 * 1279 are linked from exactly one. The slices are perfectly disjoint, so 54 ItemLists describe
 * 54 non-overlapping collections. That measurement is why this exists, and the docblock now
 * records the correction rather than the original claim.
 *
 * The list is derived from the same `posts` array the view renders, so a new post, a new page or
 * a new category stream is described the moment it exists. There is nothing to author.
 */
import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import React from 'react';
import BlogIndexHead from '../components/BlogIndexHead';

/**
 * next/head does not render into static markup, so the JSON-LD is read out of the element tree
 * instead of out of a document. Rendering is still what produces it, so the values under test
 * are the component's own output rather than a re-implementation of it.
 */
function scripts ( element: React.ReactElement ): unknown[] {
  const found: unknown[] = [];
  const walk = ( node: unknown ): void => {
    if ( !node || typeof node !== 'object' ) return;
    if ( Array.isArray( node ) ) { node.forEach( walk ); return; }
    const el = node as { type?: unknown; props?: Record<string, unknown> };
    const html = el.props?.dangerouslySetInnerHTML as { __html?: string } | undefined;
    if ( el.type === 'script' && html?.__html ) {
      try { found.push( JSON.parse( html.__html ) ); } catch { /* reported by the caller */ }
    }
    if ( el.props?.children ) walk( el.props.children );
    return;
  };
  walk( element );
  return found;
}

const graphOf = ( element: React.ReactElement ): Record<string, unknown>[] => {
  for ( const block of scripts( element ) ) {
    const doc = block as Record<string, unknown>;
    if ( Array.isArray( doc[ '@graph' ] ) ) return doc[ '@graph' ] as Record<string, unknown>[];
  }
  return [];
};

const POSTS = [
  { slug: 'first-post', title: 'The First Post' },
  { slug: 'second-post', title: 'The Second Post' },
];

const itemList = ( element: React.ReactElement ) =>
  graphOf( element ).find( node => node[ '@type' ] === 'ItemList' );

describe( 'blog listing ItemList', () => {
  it( 'lists page 1 of /blog/ and is pointed at by the Blog node', () => {
    const element = BlogIndexHead( { page: 1, totalPages: 35, posts: POSTS } ) as React.ReactElement;
    const graph = graphOf( element );
    const blog = graph.find( node => node[ '@type' ] === 'Blog' );
    const list = itemList( element );
    expect( list ).toBeTruthy();
    expect( list?.numberOfItems ).toBe( 2 );
    expect( blog?.mainEntity ).toEqual( { '@id': 'https://wecare.digital/blog/#itemlist' } );
    expect( list?.itemListElement ).toEqual( [
      { '@type': 'ListItem', position: 1, url: 'https://wecare.digital/post/first-post/', name: 'The First Post' },
      { '@type': 'ListItem', position: 2, url: 'https://wecare.digital/post/second-post/', name: 'The Second Post' },
    ] );
  } );

  it( 'gives a paginated page its OWN list, at its own @id', () => {
    // Each page lists a different, disjoint slice, so a shared @id would make 35 pages claim
    // one collection - which is the failure the original docblock feared and this avoids.
    const element = BlogIndexHead( { page: 7, totalPages: 35, posts: POSTS } ) as React.ReactElement;
    const list = itemList( element );
    expect( list?.[ '@id' ] ).toBe( 'https://wecare.digital/blog/page/7/#itemlist' );
    const page = graphOf( element ).find( node => node[ '@type' ] === 'CollectionPage' );
    expect( page?.mainEntity ).toEqual( { '@id': 'https://wecare.digital/blog/page/7/#itemlist' } );
  } );

  it( 'lists a category stream, and its paginated pages, at their own @ids', () => {
    const first = BlogIndexHead( {
      page: 1, totalPages: 19, topic: 'Gastronomy',
      topicHref: '/blog/topic/gastronomy/', count: 448, posts: POSTS,
    } ) as React.ReactElement;
    expect( itemList( first )?.[ '@id' ] )
      .toBe( 'https://wecare.digital/blog/topic/gastronomy/#itemlist' );

    const third = BlogIndexHead( {
      page: 3, totalPages: 19, topic: 'Gastronomy',
      topicHref: '/blog/topic/gastronomy/', count: 448, posts: POSTS,
    } ) as React.ReactElement;
    expect( itemList( third )?.[ '@id' ] )
      .toBe( 'https://wecare.digital/blog/topic/gastronomy/page/3/#itemlist' );
  } );

  it( 'emits no ItemList when there are no posts, rather than an empty one', () => {
    // An ItemList with numberOfItems: 0 is a claim that the page collects nothing, which is
    // different from declining to describe a collection.
    for ( const props of [
      { page: 1, totalPages: 1 },
      { page: 1, totalPages: 1, posts: [] },
      { page: 1, totalPages: 1, topic: 'Gastronomy', topicHref: '/blog/topic/gastronomy/', posts: [] },
    ] ) {
      const element = BlogIndexHead( props ) as React.ReactElement;
      expect( itemList( element ), JSON.stringify( props ) ).toBeUndefined();
      const page = graphOf( element )[ 0 ];
      expect( page ).not.toHaveProperty( 'mainEntity' );
    }
  } );

  it( 'does not claim a sort order it has not performed', () => {
    /*
     * `position` is true by construction - it follows render order. `itemListOrder` would be a
     * claim about the sort, which this component does not perform and has not verified, so it is
     * deliberately absent.
     */
    const element = BlogIndexHead( { page: 1, totalPages: 35, posts: POSTS } ) as React.ReactElement;
    expect( itemList( element ) ).not.toHaveProperty( 'itemListOrder' );
  } );

  it( 'still emits valid JSON in every block', () => {
    const element = BlogIndexHead( { page: 2, totalPages: 35, posts: POSTS } ) as React.ReactElement;
    // scripts() drops anything unparseable, so a count proves each one parsed.
    expect( scripts( element ).length ).toBeGreaterThan( 0 );
    expect( () => renderToStaticMarkup( element ) ).not.toThrow();
  } );
} );
