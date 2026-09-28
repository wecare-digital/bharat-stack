import type { GetStaticPaths, GetStaticProps } from 'next';
import BlogIndexView from '../../../components/BlogIndexView';
import BlogIndexHead from '../../../components/BlogIndexHead';
import { blogIndexProps, blogCategories, topicSlug, type BlogIndexPageProps } from '../../../lib/blog-index-props';

/**
 * /blog/topic/<slug>/ — every category except the default one.
 *
 * WHY THIS ROUTE EXISTS. Removing the "All" pill and defaulting to the first category is an
 * owner instruction. Honouring it by filtering the full-corpus pages in the browser produced a
 * real defect, caught by blogcheck rather than by looking at the page:
 *
 *   FAIL every post is listed on an index page   40 unreachable
 *   note cards per index page                    0-24 across 36 pages, 824 total
 *
 * The 40 Gastronomy posts are the NEWEST in the corpus, so in date order they occupied the whole
 * of page 1 and 16 of page 2. A default-category filter therefore rendered /blog/ with ZERO
 * cards and left 40 posts listed on no index page anywhere. Deferring the filter to after
 * hydration would only have traded that for a page that paints 24 cards and then empties.
 *
 * So each category is its own prerendered stream. The default lives at /blog/ and /blog/page/N/;
 * everything else lives here. Every post is listed exactly once, the HTML is what the reader
 * sees, and the category pills are links that work with JavaScript off.
 *
 * PAGINATED NOW, and this route is page 1 of its stream. It used to list a whole category on one
 * page, documented as safe only while the streams were small and with the trigger written down:
 * "If a category passes roughly 100 posts this needs the same page/[page] treatment /blog/ has,
 * and blogcheck's payload assertion is what will say so rather than a person noticing."
 * That arrived. Gastronomy is 90 posts, up from 40, and its single page measured 30.2 kB of props
 * against the 128 kB threshold. Pages 2 and up live at /blog/topic/<slug>/page/N/, which is the
 * same shape /blog/ and /blog/page/N/ already use, so the blog has one pagination rule rather
 * than one rule and one exception.
 *
 * ROUTING: '/blog/topic/[topic]' must be in the isContentPublic check in _app.tsx or this
 * renders an empty body at HTTP 200, and '/blog/topic/' must be in PUBLIC_PREFIXES in
 * scripts/generate-sitemap.js or the stream is unadvertised.
 *
 * getStaticPaths lists every non-default category with fallback:false, so the export writes real
 * directories and no literal [topic] is emitted - the failure /workspace/seo/page/[id] shipped.
 */
export default function BlogTopicPage ( props: BlogIndexPageProps ) {
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
  // slice(1): the first category is the default and is served at /blog/. Emitting it here too
  // would be the same cards at a second self-canonical URL.
  return {
    paths: categories.slice( 1 ).map( category => ( { params: { topic: topicSlug( category ) } } ) ),
    fallback: false,
  };
};

export const getStaticProps: GetStaticProps<BlogIndexPageProps> = async ( context ) => {
  const slug = String( context.params?.topic || '' );
  const categories = await blogCategories();
  /* Resolved by slug rather than by index, so a category rename cannot silently serve the wrong
   * stream at an old URL - it 404s, which is the honest answer. */
  const category = categories.find( c => topicSlug( c ) === slug );
  if ( !category || category === categories[ 0 ] ) return { notFound: true };
  // Page 1 of the stream. The tail is emitted by the sibling page/[page] route, and every post
  // stays listed exactly once because the two together cover the whole category - which is the
  // property blogcheck asserts, and the reason the previous whole-category shortcut existed.
  return { props: await blogIndexProps( 1, category ) };
};
