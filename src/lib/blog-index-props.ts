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
}

export async function blogIndexProps ( page: number ): Promise<BlogIndexPageProps> {
  const all = await listPublicBlogPosts();
  const cards = listBlogCards( all );
  const totalPages = blogPageCount( cards.length );
  const start = ( page - 1 ) * POSTS_PER_PAGE;

  /**
   * CATEGORIES ARE COMPUTED FROM THE WHOLE CORPUS, not from this page's slice, and the cost
   * of that is one short string array per page - 12 kB of category values across all 834
   * posts dedupes to a handful. Deriving them per page would give page 3 four pills and page
   * 9 a different four, which reads as a broken filter rather than as sliced data.
   */
  const categories = Array.from(
    new Set( cards.map( card => card.category ).filter( Boolean ) as string[] )
  ).sort( ( a, b ) => a.localeCompare( b ) );

  return {
    posts: cards.slice( start, start + POSTS_PER_PAGE ),
    page,
    totalPages,
    totalPosts: cards.length,
    categories,
  };
}
