import {
  listPublicBlogPosts,
  orderPostsNewestFirst,
  type PublicBlogPost,
} from './public-blog';
import { topicSlug } from './blog-index-props';

/**
 * What surrounds one post: the two neighbours in its stream, and a few posts genuinely like it.
 *
 * WHY THIS IS A LIB MODULE AND NOT PART OF THE PAGE. Same reason blog-index-props.ts is: a
 * sibling module inside src/pages/post/ would be emitted as a public URL by the static export.
 *
 * THE PAYLOAD DISCIPLINE IS THE WHOLE DESIGN CONSTRAINT. There are 914 post pages, and whatever
 * this module returns is serialised into every one of them. The BlogCard note in public-blog.ts
 * records how /blog/ reached 842 kB of props by shipping eighteen fields of 834 posts to render
 * seven; the same mistake here would be shipping a category's worth of cards to render five
 * links. So the return type is PostLink - slug and title, nothing else - and it is a SEPARATE
 * narrowing from toBlogCard rather than a widening of it, because BlogDesign.test.tsx asserts
 * toBlogCard's key set exactly and that assertion is worth keeping intact.
 * Measured: five PostLinks is about 0.4 kB per page against a 128 kB threshold.
 */
export interface PostLink {
  slug: string;
  title: string;
}

export interface PostContext {
  /** The next post up the stream, i.e. published after this one. Absent on the newest post. */
  newer?: PostLink;
  /** The next post down the stream. Absent on the oldest post. */
  older?: PostLink;
  /** Up to RELATED_COUNT posts sharing tags with this one, best match first. */
  related: PostLink[];
  /** The listing this post appears on, for the "back to the stream" link. */
  streamHref: string;
  /** That listing's human name - the category, which is what the reader chose. */
  streamLabel: string;
}

/** Three fits the 700px article measure as one column without becoming a second index page. */
const RELATED_COUNT = 3;

const toPostLink = ( post: PublicBlogPost ): PostLink => ( { slug: post.slug, title: post.title } );

/**
 * WHY TAG OVERLAP, AND WHY WEIGHTED.
 *
 * Measured against the live endpoint: all 914 posts carry tags, 449 distinct, and the most
 * common are broad - Relationships 99, Awareness 91, Communication 86. `hashtags` and
 * `focusKeyword` are empty on every post, so tags are the only relatedness signal the data
 * actually has. Recency alone was the alternative and it is not relatedness at all: it would put
 * the same three posts under every article in a category.
 *
 * Each shared tag is worth 1/(number of posts carrying it), so a shared `Carrot` (a handful of
 * posts) outweighs a shared `Relationships` (99). Without the weighting the broad tags dominate
 * and every Conversations post gets the same neighbours again, which is the recency failure with
 * extra steps. Frequency is counted across the WHOLE corpus, because how specific a tag is, is a
 * property of the tag rather than of the stream being listed.
 */
interface TagIndex {
  /** Tag -> how many posts carry it, across the corpus. */
  weight: Map<string, number>;
  /** Tag -> the posts carrying it, so scoring only visits plausible candidates. */
  byTag: Map<string, PublicBlogPost[]>;
  /** The corpus in index order. */
  ordered: PublicBlogPost[];
  /** Category -> that category's posts, in index order. */
  streams: Map<string, PublicBlogPost[]>;
  /** The category /blog/ itself paginates; every other one lives at /blog/topic/<slug>/. */
  defaultCategory: string;
}

/**
 * BUILT ONCE PER BUILD, for the same reason listPublicBlogPosts memoises its fetch.
 *
 * getStaticProps runs 914 times. Scoring a post against the whole corpus each time would be
 * 914 x 914 comparisons; building the inverted index once makes each page visit only the posts
 * that share at least one tag with it. The promise is cached rather than the value so the
 * parallel renders Next does share one build instead of racing to repeat it.
 */
let indexPromise: Promise<TagIndex> | null = null;

async function tagIndex (): Promise<TagIndex> {
  if ( indexPromise ) return indexPromise;
  indexPromise = build();
  const built = await indexPromise;
  // An empty corpus means the fetch failed; do not cache that, exactly as listPublicBlogPosts
  // refuses to cache an empty result - one network blip would otherwise strip related posts from
  // every page in the build.
  if ( built.ordered.length === 0 ) indexPromise = null;
  return built;
}

async function build (): Promise<TagIndex> {
  const ordered = orderPostsNewestFirst( await listPublicBlogPosts() );
  const weight = new Map<string, number>();
  const byTag = new Map<string, PublicBlogPost[]>();
  const streams = new Map<string, PublicBlogPost[]>();

  for ( const post of ordered ) {
    for ( const tag of post.tags || [] ) {
      weight.set( tag, ( weight.get( tag ) || 0 ) + 1 );
      const bucket = byTag.get( tag );
      if ( bucket ) bucket.push( post );
      else byTag.set( tag, [ post ] );
    }
    const category = post.category || '';
    const stream = streams.get( category );
    if ( stream ) stream.push( post );
    else streams.set( category, [ post ] );
  }

  /* The same rule blogCategories() uses - sorted, first one is the default - restated from the
   * same data rather than imported, because importing blogIndexProps here would pull the index's
   * whole props builder into every post page's build graph for one string. topicSlug is imported
   * because a second copy of the slug rule is how two URLs for one category happen. */
  const defaultCategory = Array.from( streams.keys() ).filter( Boolean ).sort( ( a, b ) => a.localeCompare( b ) )[ 0 ] || '';

  return { weight, byTag, ordered, streams, defaultCategory };
}

/**
 * THE STREAM IS THE CATEGORY, NOT THE CORPUS.
 *
 * Neighbours are computed inside the post's own category because that is the only listing the
 * post appears on - blog-index-props.ts slices the pages by category precisely so every post is
 * listed exactly once. Walking the whole corpus instead would hand a reader of a Gastronomy
 * recipe a "next" link into a Conversations essay, and the listing they came from would not
 * contain it. Same reasoning as the index's own model, so the two agree.
 */
export async function postContext ( slug: string ): Promise<PostContext> {
  const { weight, byTag, streams, defaultCategory } = await tagIndex();

  const self = streams.get( '' )?.find( p => p.slug === slug )
    || Array.from( streams.values() ).flat().find( p => p.slug === slug );
  const category = self?.category || '';
  const stream = streams.get( category ) || [];
  const at = stream.findIndex( p => p.slug === slug );

  const streamHref = !category || category === defaultCategory
    ? '/blog/'
    : `/blog/topic/${topicSlug( category )}/`;

  const context: PostContext = {
    related: [],
    streamHref,
    streamLabel: category || 'Blog',
  };
  if ( at < 0 ) return context;

  // Newest first, so the entry BEFORE this one in the array is the newer post.
  const newer = stream[ at - 1 ];
  const older = stream[ at + 1 ];
  if ( newer ) context.newer = toPostLink( newer );
  if ( older ) context.older = toPostLink( older );

  // Already offered by the pager directly above; repeating them as "related" wastes two of three
  // slots on links the reader can see.
  const taken = new Set( [ slug, newer?.slug, older?.slug ].filter( Boolean ) as string[] );

  const scores = new Map<string, number>();
  for ( const tag of self?.tags || [] ) {
    const carriers = byTag.get( tag ) || [];
    const tagWeight = 1 / ( weight.get( tag ) || 1 );
    for ( const candidate of carriers ) {
      if ( taken.has( candidate.slug ) ) continue;
      // Same stream only, so a related link never leaves the listing the reader is browsing.
      if ( ( candidate.category || '' ) !== category ) continue;
      scores.set( candidate.slug, ( scores.get( candidate.slug ) || 0 ) + tagWeight );
    }
  }

  const bySlug = new Map( stream.map( p => [ p.slug, p ] ) );
  const scored = Array.from( scores.entries() )
    .sort( ( a, b ) => {
      if ( b[ 1 ] !== a[ 1 ] ) return b[ 1 ] - a[ 1 ];
      // Ties broken by stream position, which is recency - deterministic, so two builds of the
      // same corpus emit identical HTML.
      return stream.indexOf( bySlug.get( a[ 0 ] )! ) - stream.indexOf( bySlug.get( b[ 0 ] )! );
    } )
    .slice( 0, RELATED_COUNT )
    .map( ( [ candidateSlug ] ) => bySlug.get( candidateSlug )! );

  /* TOPPED UP BY PROXIMITY WHEN THE TAGS RUN OUT, rather than rendering a short row or none.
   * A post whose tags are unique to it scores nothing against anything, and an empty block is a
   * worse answer than a nearby one - the reader asked for somewhere to go next. Nearest in the
   * stream is the honest filler: it is the same relationship the pager offers, one step further
   * out. */
  const chosen = [ ...scored ];
  for ( let step = 1; chosen.length < RELATED_COUNT && step < stream.length; step++ ) {
    for ( const candidate of [ stream[ at - step ], stream[ at + step ] ] ) {
      if ( !candidate || chosen.length >= RELATED_COUNT ) continue;
      if ( taken.has( candidate.slug ) || chosen.some( c => c.slug === candidate.slug ) ) continue;
      chosen.push( candidate );
    }
  }

  context.related = chosen.map( toPostLink );
  return context;
}
