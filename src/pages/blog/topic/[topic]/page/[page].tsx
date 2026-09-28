import type { GetStaticPaths, GetStaticProps } from 'next';
import BlogIndexView from '../../../../../components/BlogIndexView';
import BlogIndexHead from '../../../../../components/BlogIndexHead';
import { blogIndexProps, blogCategories, topicSlug, type BlogIndexPageProps } from '../../../../../lib/blog-index-props';
import { listPublicBlogPosts, listBlogCards, blogPageCount } from '../../../../../lib/public-blog';

/**
 * /blog/topic/<slug>/page/2/ … — the tail of each category stream.
 *
 * WHY THIS ROUTE EXISTS NOW AND DID NOT BEFORE. /blog/topic/<slug>/ listed a whole category on a
 * single page, and its own comment recorded both why that was safe and exactly when it would stop
 * being: "If a category passes roughly 100 posts this needs the same page/[page] treatment /blog/
 * has." Gastronomy has gone from 40 posts to 90 and its one page measured 30.2 kB of props
 * against the 128 kB threshold blogcheck enforces. So the streams paginate like /blog/ does, and
 * the blog has ONE pagination rule instead of a rule plus an exception.
 *
 * A DYNAMIC SEGMENT IN A STATIC EXPORT IS ONLY SAFE WITH getStaticPaths - and here there are two
 * of them, so the paths are a product of categories and their page counts. The failure this
 * avoids is on record: /workspace/seo/page/[id] shipped a directory named literally `[id]`
 * serving HTTP 200 while every real id 404'd. `find out -name '*[*'` must stay empty.
 *
 * PATHS START AT 2, for the same reason /blog/page/ does: page 1 is the stream's own URL, which
 * is what the pills link to, what the sitemap carries and what the canonical names. Emitting
 * page/1/ as well would be the same cards at a second self-canonical URL, and blogcheck asserts
 * that /blog/page/1/ does not exist - the same duplication is no better one level down.
 *
 * THE DEFAULT CATEGORY IS EXCLUDED. It lives at /blog/ and /blog/page/N/; emitting it here too
 * would be a third URL for cards that already have two.
 *
 * ROUTING: '/blog/topic/[topic]/page/[page]' must be in the isContentPublic check in _app.tsx or
 * every page of every stream but the first renders an empty body at HTTP 200. The sitemap needs
 * nothing new - generate-sitemap.js walks the export and matches the '/blog/topic/' prefix, which
 * these paths are under.
 */
export default function BlogTopicPagedPage ( props: BlogIndexPageProps ) {
  return (
    <>
      <BlogIndexHead
        page={ props.page }
        totalPages={ props.totalPages }
        topic={ props.activeCategory }
        topicHref={ `/blog/topic/${topicSlug( props.activeCategory )}/` }
        count={ props.totalPosts }
      />
      <BlogIndexView { ...props } />
    </>
  );
}

export const getStaticPaths: GetStaticPaths = async () => {
  const categories = await blogCategories();
  const cards = listBlogCards( await listPublicBlogPosts() );
  const paths: Array<{ params: { topic: string; page: string } }> = [];
  // slice(1): the first category is the default and is paginated at /blog/page/N/.
  for ( const category of categories.slice( 1 ) ) {
    /* Counted from the same sorted list getStaticProps slices, through the same memoised fetch.
     * If paths and props disagreed by one the last page would either 404 or render empty - the
     * warning /blog/page/[page] already carries, and it is the same hazard here. */
    const total = blogPageCount( cards.filter( c => c.category === category ).length );
    for ( let page = 2; page <= total; page++ ) {
      paths.push( { params: { topic: topicSlug( category ), page: String( page ) } } );
    }
  }
  return { paths, fallback: false };
};

export const getStaticProps: GetStaticProps<BlogIndexPageProps> = async ( context ) => {
  const slug = String( context.params?.topic || '' );
  const page = Number( context.params?.page );
  /* Guarded even though getStaticPaths only hands over valid pairs: fallback is false, so nothing
   * else can arrive at build time, but a hand-edited params object or a later move to
   * fallback:'blocking' would, and notFound is honest where an empty grid under a paginator
   * pointing nowhere is not. */
  if ( !Number.isInteger( page ) || page < 2 ) return { notFound: true };
  const categories = await blogCategories();
  /* Resolved by slug rather than by index, so a category rename cannot silently serve the wrong
   * stream at an old URL - it 404s, which is the honest answer. Same rule as the page-1 route. */
  const category = categories.find( c => topicSlug( c ) === slug );
  if ( !category || category === categories[ 0 ] ) return { notFound: true };
  const props = await blogIndexProps( page, category );
  if ( page > props.totalPages ) return { notFound: true };
  return { props };
};
