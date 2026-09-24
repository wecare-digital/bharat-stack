import type { GetStaticProps } from 'next';
import Head from 'next/head';
import Link from 'next/link';
import { listPublicBlogPosts, PublicBlogPost } from '../../lib/public-blog';

interface Props {
  posts: PublicBlogPost[];
}

/**
 * STRUCTURED DATA IS DECLARED HERE, not in _app.tsx.
 *
 * This route is in `isContentPublic`, and _app.tsx renders its shared <Head> behind
 * `!isContentPublic` - so the Organization, WebSite, WebPage and BreadcrumbList graph
 * every other public route gets is deliberately suppressed on /blog/ and /post/[slug]/,
 * to stop two components emitting competing canonicals. The consequence went unnoticed:
 * /blog/ is in the sitemap and indexable but shipped ZERO JSON-LD, while the structured
 * data checker only looked at six hardcoded routes and never asked about this one.
 *
 * THE GRAPH IS SELF-CONTAINED ON PURPOSE. It cannot reference the shared nodes by @id -
 * `#website` and `#organization` are defined in the <Head> that is suppressed here, so
 * pointing at them would emit references that resolve to nothing, which is worse than
 * omitting them. Publisher is therefore inlined.
 */
export default function BlogIndex ( { posts }: Props ) {
  const canonical = 'https://wecare.digital/blog/';
  const DESCRIPTION = 'Ideas, guides and updates from WECARE.DIGITAL.';

  const schema = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Blog',
        '@id': `${canonical}#blog`,
        url: canonical,
        name: 'WECARE.DIGITAL Blog',
        description: DESCRIPTION,
        inLanguage: 'en-IN',
        publisher: { '@type': 'Organization', name: 'WECARE.DIGITAL', url: 'https://wecare.digital' },
        breadcrumb: { '@id': `${canonical}#breadcrumb` },
      },
      {
        '@type': 'BreadcrumbList',
        '@id': `${canonical}#breadcrumb`,
        // The tail must be the canonical, slash included, or the breadcrumb describes a
        // URL that redirects. trailingSlash is on for this export.
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://wecare.digital/' },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: canonical },
        ],
      },
    ],
  };

  return (
    <>
      <Head>
        <title>Blog | WECARE.DIGITAL</title>
        <meta name="description" content={ DESCRIPTION } />
        <link rel="canonical" href={ canonical } />
        <meta property="og:type" content="website" />
        <meta property="og:title" content="Blog | WECARE.DIGITAL" />
        <meta property="og:description" content={ DESCRIPTION } />
        <meta property="og:url" content={ canonical } />
        <meta name="robots" content="index, follow, max-image-preview:large" />
        <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( schema ) } } />
      </Head>
      <main className="blog-shell">
        <section className="blog-hero">
          <p className="eyebrow">WECARE.DIGITAL</p>
          <h1>Blog</h1>
          <p>Ideas, guides and updates published by the WECARE.DIGITAL team.</p>
        </section>

        { posts.length > 0 ? (
          <section className="post-grid" aria-label="Published posts">
            { posts.map( post => (
              <article key={ post.id || post.slug } className="post-card">
                <div className="post-copy">
                  { post.category && <span className="category">{ post.category }</span> }
                  <h2><Link href={ `/post/${post.slug}/` }>{ post.title }</Link></h2>
                  { post.excerpt && <p>{ post.excerpt }</p> }
                  <div className="meta">
                    { post.authorName && <span>{ post.authorName }</span> }
                    { post.publishedDate && <time dateTime={ post.publishedDate }>{ new Date( post.publishedDate ).toLocaleDateString( 'en-IN' ) }</time> }
                  </div>
                </div>
              </article>
            ) ) }
          </section>
        ) : (
          <div className="empty">No posts have been published yet.</div>
        ) }
      </main>
      <style jsx>{`
        .blog-shell{max-width:1180px;margin:0 auto;padding:156px 24px 96px;color:#111827;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
        .blog-hero{max-width:720px;margin-bottom:56px}
        .eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;color:#1a3a2a;text-transform:uppercase;margin:0 0 12px}
        h1{font-size:clamp(44px,7vw,76px);line-height:1;letter-spacing:-.045em;margin:0 0 18px;color:#1a3a2a}
        .blog-hero>p:last-child{font-size:18px;line-height:1.7;color:#6b7280;margin:0}
        .post-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}
        .post-card{border:1px solid #e5e7eb;border-radius:18px;overflow:hidden;background:#fff}
        .post-copy{padding:22px}
        .category{display:inline-block;background:#d1f470;color:#1a3a2a;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:700;margin-bottom:12px}
        h2{font-size:21px;line-height:1.25;margin:0 0 10px}
        h2 :global(a){color:#111827;text-decoration:none}
        h2 :global(a:hover){color:#1a3a2a}
        .post-copy p{font-size:14px;line-height:1.65;color:#6b7280;margin:0 0 18px}
        .meta{display:flex;gap:10px;flex-wrap:wrap;font-size:11px;color:#9ca3af}
        .empty{border:1px dashed #d1d5db;border-radius:16px;padding:40px;text-align:center;color:#6b7280}
        @media(max-width:900px){.post-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
        @media(max-width:640px){.blog-shell{padding:128px 16px 64px}.post-grid{grid-template-columns:1fr}.blog-hero{margin-bottom:36px}}
      `}</style>
    </>
  );
}

export const getStaticProps: GetStaticProps<Props> = async () => {
  const posts = await listPublicBlogPosts();
  return { props: { posts } };
};
