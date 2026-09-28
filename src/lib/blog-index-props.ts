import {
  listPublicBlogPosts,
  listBlogCards,
  blogPageCount,
  POSTS_PER_PAGE,
  type BlogCard,
} from './public-blog';

/**
 * The props for one page of the blog index, built the same way for /blog/ and /blog/page/N/.
 *
 * WHY A SHARED MODULE RATHER THAN A COPY IN EACH PAGE. The two routes must slice the same
 * sorted list with the same page size and report the same total, or page 1 and page 2 will
 * disagree about how many pages exist and a post can fall between them. One function makes
 * that impossible instead of merely unlikely.
 *
 * NOT UNDER src/pages/. Next treats files there as routes, and a sibling module in a route
 * directory is a standing invitation to emit /blog/page/blogIndexProps - which is exactly the
 * class of accidental public URL that /workspace/seo/page/[id] turned out to be.
 */
export interface BlogIndexPageProps {
  posts: BlogCard[];
  page: number;
  totalPages: number;
  totalPosts: number;
  categories: string[];
  categoryCounts: Record<string, number>;
  /** The category this page lists. Server-decided, so the HTML matches what is shown. */
  activeCategory: string;
  /** The one that lives at /blog/. Every other category lives at /blog/topic/<slug>/. */
  defaultCategory: string;
}

/** URL-safe form of a category name. "Gastronomy" -> "gastronomy". */
export const topicSlug = ( category: string ): string =>
  category.toLowerCase().replace( /[^a-z0-9]+/g, '-' ).replace( /^-|-$/g, '' );

/**
 * Every category, sorted, with the FIRST one being the default that /blog/ paginates.
 * Exported because three routes need to agree on which category is the default.
 */
export async function blogCategories (): Promise<string[]> {
  const cards = listBlogCards( await listPublicBlogPosts() );
  return Array.from( new Set( cards.map( c => c.category ).filter( Boolean ) as string[] ) )
    .sort( ( a, b ) => a.localeCompare( b ) );
}

/**
 * ONE CATEGORY IS PAGINATED, THE REST GET THEIR OWN LISTING, and the reason is a measurement.
 *
 * Removing the "All" pill and defaulting to the first category is an owner instruction, and
 * filtering the full-corpus pages client-side to honour it produced this, caught by blogcheck:
 *
 *   FAIL every post is listed on an index page   40 unreachable
 *   note cards per index page                    0-24 across 36 pages, 824 total
 *
 * The 40 Gastronomy posts are the NEWEST in the corpus, so in date order they filled the whole
 * of page 1 and 16 of page 2. A default-category filter therefore rendered /blog/ with ZERO
 * cards, and put 40 posts on no index page at all. Applying the filter after hydration instead
 * would have swapped that for a page that paints 24 cards and then empties.
 *
 * So the pages are sliced BY CATEGORY at build time: /blog/ and /blog/page/N/ carry the default
 * category only, and each other category gets /blog/topic/<slug>/. Every post is listed exactly
 * once, the static HTML matches what the reader sees, the pills become real links that work
 * without JavaScript, and no index fetch is needed to change category.
 */
/*
 * `wholeCategory` IS GONE, AND THE CONDITION IT WAS WAITING FOR ARRIVED.
 *
 * It put a whole category on one page for the /blog/topic/ streams, because a stream is the only
 * listing its posts appear on and paginating it without emitting the extra pages orphaned the
 * tail - blogcheck went from "40 unreachable" to "16 unreachable", which looks like progress and
 * is still a broken export. The option was documented as safe only while the streams were small,
 * with the explicit trigger: "If a category passes roughly 100 posts this needs the same
 * page/[page] treatment /blog/ has, and blogcheck's payload assertion is what will say so."
 *
 * Gastronomy is now 90 posts, up from 40, and its single page measured 30.2 kB of props against
 * the 128 kB threshold. So the streams paginate like /blog/ does, at /blog/topic/<slug>/page/N/,
 * and every page of every stream is emitted - which is what keeps the tail listed rather than
 * orphaned. There is one pagination rule on the blog again instead of two.
 */
export async function blogIndexProps (
  page: number,
  category?: string
): Promise<BlogIndexPageProps> {
  const all = await listPublicBlogPosts();
  const everyCard = listBlogCards( all );
  const categories = Array.from( new Set( everyCard.map( c => c.category ).filter( Boolean ) as string[] ) )
    .sort( ( a, b ) => a.localeCompare( b ) );
  const active = category || categories[ 0 ] || '';

  const cards = active ? everyCard.filter( c => c.category === active ) : everyCard;
  const perPage = POSTS_PER_PAGE;
  const totalPages = blogPageCount( cards.length );
  const start = ( page - 1 ) * perPage;

  /**
   * Counts come from the WHOLE corpus, not this slice, so every pill can show its own size and
   * the search box has an honest denominator. Measured live: Conversations 824, Gastronomy 40.
   */
  const categoryCounts: Record<string, number> = {};
  for ( const card of everyCard ) {
    if ( card.category ) categoryCounts[ card.category ] = ( categoryCounts[ card.category ] || 0 ) + 1;
  }

  return {
    posts: cards.slice( start, start + perPage ),
    page,
    totalPages,
    totalPosts: cards.length,
    categories,
    categoryCounts,
    activeCategory: active,
    defaultCategory: categories[ 0 ] || '',
  };
}
