import React from 'react';
import Head from 'next/head';
import { blogPageHref } from './BlogIndexView';

/**
 * Head for one page of the blog index.
 *
 * STRUCTURED DATA IS DECLARED HERE, not in _app.tsx.
 *
 * /blog/ is in `isContentPublic`, and _app.tsx renders its shared <Head> behind
 * `!isContentPublic` - so the Organization, WebSite, WebPage and BreadcrumbList graph every
 * other public route gets is deliberately suppressed on /blog/ and /post/[slug]/, to stop two
 * components emitting competing canonicals. The consequence went unnoticed once: /blog/ is in
 * the sitemap and indexable but shipped ZERO JSON-LD, while the structured data checker only
 * looked at six hardcoded routes and never asked about this one.
 *
 * THE GRAPH IS SELF-CONTAINED ON PURPOSE. It cannot reference the shared nodes by @id -
 * `#website` and `#organization` are defined in the <Head> that is suppressed here, so
 * pointing at them would emit references that resolve to nothing, which is worse than
 * omitting them. Publisher is therefore inlined.
 *
 * WHAT PAGINATION ADDED TO THIS FILE
 * ----------------------------------
 * EVERY PAGE IS SELF-CANONICAL. /blog/page/7/ canonicalises to itself, NOT to /blog/. It is
 * tempting to point all 35 pages at /blog/, and it is wrong: a canonical says "index this
 * other URL instead of me", so 810 posts whose only listing is on pages 2-35 would have no
 * indexable page linking to them at all. Google's own guidance on paginated sequences is that
 * each page is its own canonical.
 *
 * rel=prev/next IS STILL EMITTED although Google retired it as an indexing signal in 2019. It
 * remains the correct semantic relationship between these documents, browsers and reading
 * tools use it to offer "next page", and nothing costs anything by its presence.
 *
 * PAGES 2 AND UP ARE index,follow, not noindex. noindex on a paginated tail is the other
 * common mistake: it removes the only crawlable route to most of the corpus. What they do get
 * is a DISTINCT <title> and description carrying the page number, because 35 pages sharing one
 * title is what actually reads as duplicate content in a search result list.
 *
 * ONLY THE Blog NODE CARRIES THE POST COUNT, and it sits on page 1. Repeating an
 * `itemListElement` of 24 posts on every page would describe 35 overlapping collections; the
 * pages instead describe themselves as parts of one Blog via `isPartOf`.
 */

const ORIGIN = 'https://wecare.digital';
const DESCRIPTION = 'Ideas, guides and updates from WECARE.DIGITAL.';

interface BlogIndexHeadProps {
  page: number;
  totalPages: number;
  /** Set on /blog/topic/<slug>/ - the category this stream lists. */
  topic?: string;
  topicHref?: string;
  /** Posts in this stream, for the description. */
  count?: number;
}

const BlogIndexHead: React.FC<BlogIndexHeadProps> = ( { page, totalPages, topic, topicHref, count } ) => {
  /*
   * A CATEGORY STREAM IS ITS OWN CANONICAL, like every paginated page. It has to be: the default
   * category is at /blog/ and the others are here, so these are the ONLY index pages listing
   * their posts. Canonicalising them at /blog/ would point at a page that does not contain them.
   */
  if ( topic ) {
    const url = `${ORIGIN}${topicHref}`;
    const title = `${topic} | WECARE.DIGITAL Blog`;
    const description = `${count ?? ''} ${count === 1 ? 'post' : 'posts'} on ${topic}, from WECARE.DIGITAL.`.trim();
    const schema = {
      '@context': 'https://schema.org',
      '@graph': [
        {
          '@type': 'CollectionPage',
          '@id': `${url}#page`,
          url,
          name: title,
          description,
          inLanguage: 'en-IN',
          isPartOf: { '@type': 'Blog', '@id': `${ORIGIN}/blog/#blog`, url: `${ORIGIN}/blog/`, name: 'WECARE.DIGITAL Blog' },
          breadcrumb: { '@id': `${url}#breadcrumb` },
        },
        {
          '@type': 'BreadcrumbList',
          '@id': `${url}#breadcrumb`,
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: `${ORIGIN}/` },
            { '@type': 'ListItem', position: 2, name: 'Blog', item: `${ORIGIN}/blog/` },
            { '@type': 'ListItem', position: 3, name: topic, item: url },
          ],
        },
      ],
    };
    return (
      <Head>
        <title>{ title }</title>
        <meta name="description" content={ description } />
        <link rel="canonical" href={ url } />
        <meta property="og:type" content="website" />
        <meta property="og:title" content={ title } />
        <meta property="og:description" content={ description } />
        <meta property="og:url" content={ url } />
        <meta name="robots" content="index, follow, max-image-preview:large" />
        <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( schema ) } } />
      </Head>
    );
  }

  const canonical = `${ORIGIN}${blogPageHref( page )}`;
  const blogRoot = `${ORIGIN}/blog/`;
  const first = page === 1;

  const title = first
    ? 'Blog | WECARE.DIGITAL'
    : `Blog — page ${page} of ${totalPages} | WECARE.DIGITAL`;
  const description = first
    ? DESCRIPTION
    : `${DESCRIPTION} Page ${page} of ${totalPages}.`;

  const schema = {
    '@context': 'https://schema.org',
    '@graph': [
      first
        ? {
          '@type': 'Blog',
          '@id': `${blogRoot}#blog`,
          url: blogRoot,
          name: 'WECARE.DIGITAL Blog',
          description: DESCRIPTION,
          inLanguage: 'en-IN',
          publisher: { '@type': 'Organization', name: 'WECARE.DIGITAL', url: ORIGIN },
          breadcrumb: { '@id': `${canonical}#breadcrumb` },
        }
        : {
          // A CollectionPage that declares itself part of the Blog, rather than a second
          // Blog node. Thirty-five Blog nodes at thirty-five URLs would each claim to be
          // the publication.
          '@type': 'CollectionPage',
          '@id': `${canonical}#page`,
          url: canonical,
          name: `WECARE.DIGITAL Blog — page ${page}`,
          description,
          inLanguage: 'en-IN',
          isPartOf: { '@type': 'Blog', '@id': `${blogRoot}#blog`, url: blogRoot, name: 'WECARE.DIGITAL Blog' },
          breadcrumb: { '@id': `${canonical}#breadcrumb` },
        },
      {
        '@type': 'BreadcrumbList',
        '@id': `${canonical}#breadcrumb`,
        // The tail must be the canonical, slash included, or the breadcrumb describes a
        // URL that redirects. trailingSlash is on for this export.
        itemListElement: first
          ? [
            { '@type': 'ListItem', position: 1, name: 'Home', item: `${ORIGIN}/` },
            { '@type': 'ListItem', position: 2, name: 'Blog', item: blogRoot },
          ]
          : [
            { '@type': 'ListItem', position: 1, name: 'Home', item: `${ORIGIN}/` },
            { '@type': 'ListItem', position: 2, name: 'Blog', item: blogRoot },
            { '@type': 'ListItem', position: 3, name: `Page ${page}`, item: canonical },
          ],
      },
    ],
  };

  return (
    <Head>
      <title>{ title }</title>
      <meta name="description" content={ description } />
      <link rel="canonical" href={ canonical } />
      { page > 1 && <link rel="prev" href={ `${ORIGIN}${blogPageHref( page - 1 )}` } /> }
      { page < totalPages && <link rel="next" href={ `${ORIGIN}${blogPageHref( page + 1 )}` } /> }
      <meta property="og:type" content="website" />
      <meta property="og:title" content={ title } />
      <meta property="og:description" content={ description } />
      <meta property="og:url" content={ canonical } />
      <meta name="robots" content="index, follow, max-image-preview:large" />
      <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( schema ) } } />
    </Head>
  );
};

export default BlogIndexHead;
