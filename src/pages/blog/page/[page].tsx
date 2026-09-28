import type { GetStaticPaths, GetStaticProps } from 'next';
import BlogIndexView from '../../../components/BlogIndexView';
import BlogIndexHead from '../../../components/BlogIndexHead';
import { blogIndexProps, type BlogIndexPageProps } from '../../../lib/blog-index-props';
import { listPublicBlogPosts, listBlogCards, blogPageCount } from '../../../lib/public-blog';

/**
 * /blog/page/2/ … /blog/page/N/ — the rest of the blog index.
 *
 * A DYNAMIC SEGMENT IN A STATIC EXPORT IS ONLY SAFE WITH getStaticPaths, and this file is the
 * reason to say so out loud. /workspace/seo/page/[id] had no getStaticPaths - its ids come
 * from a live API - so the export emitted exactly one file: a directory named, literally,
 * `[id]`, which served HTTP 200 at /%5Bid%5D/ while every real id 404'd on reload. Here the
 * page numbers ARE known at build time, so getStaticPaths lists all of them with
 * fallback:false and the export writes 34 real directories. `find out -name '*[*'` must stay
 * empty; that is the check.
 *
 * PATHS START AT 2. Page 1 is /blog/, which is the URL in the sitemap, the mega-menu and
 * every inbound link. Emitting /blog/page/1/ as well would be the same 24 cards at a second
 * URL, and self-canonical pages (see BlogIndexHead) mean both would be indexed.
 *
 * THE COUNT COMES FROM THE SAME SORTED LIST getStaticProps slices, through the same memoised
 * fetch - see listPublicBlogPosts. If paths and props disagreed by one, the last page would
 * either 404 or render empty.
 *
 * ROUTING: '/blog/page/[page]' must be in the isContentPublic check in _app.tsx or this
 * renders an empty body at HTTP 200 - a 404 that does not look like one. It also needs
 * '/blog/page/' in PUBLIC_PREFIXES in scripts/generate-sitemap.js, or 34 real pages stay out
 * of the sitemap and most of the corpus has no advertised route.
 */
export default function BlogIndexPage ( props: BlogIndexPageProps ) {
  return (
    <>
      <BlogIndexHead page={ props.page } totalPages={ props.totalPages } />
      <BlogIndexView { ...props } />
    </>
  );
}

export const getStaticPaths: GetStaticPaths = async () => {
  const cards = listBlogCards( await listPublicBlogPosts() );
  const totalPages = blogPageCount( cards.length );
  const paths = [];
  for ( let page = 2; page <= totalPages; page++ ) {
    paths.push( { params: { page: String( page ) } } );
  }
  return { paths, fallback: false };
};

export const getStaticProps: GetStaticProps<BlogIndexPageProps> = async ( context ) => {
  const page = Number( context.params?.page );
  /**
   * Guard even though getStaticPaths only ever hands over integers from 2 to N. fallback is
   * false, so an out-of-range page cannot arrive at build time - but a hand-edited params
   * object or a future move to fallback:'blocking' would, and notFound is the honest answer
   * rather than a page rendering an empty grid with a paginator pointing nowhere.
   */
  if ( !Number.isInteger( page ) || page < 2 ) return { notFound: true };
  const props = await blogIndexProps( page );
  if ( page > props.totalPages ) return { notFound: true };
  return { props };
};
