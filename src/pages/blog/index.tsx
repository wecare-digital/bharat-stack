import type { GetStaticProps } from 'next';
import Head from 'next/head';
import Link from 'next/link';
import { listPublicBlogPosts, PublicBlogPost } from '../../lib/public-blog';

interface Props {
  posts: PublicBlogPost[];
}

export default function BlogIndex ( { posts }: Props ) {
  const canonical = 'https://wecare.digital/blog/';

  return (
    <>
      <Head>
        <title>Blog | WECARE.DIGITAL</title>
        <meta name="description" content="Ideas, guides and updates from WECARE.DIGITAL." />
        <link rel="canonical" href={ canonical } />
        <meta property="og:type" content="website" />
        <meta property="og:title" content="Blog | WECARE.DIGITAL" />
        <meta property="og:description" content="Ideas, guides and updates from WECARE.DIGITAL." />
        <meta property="og:url" content={ canonical } />
        <meta name="robots" content="index, follow, max-image-preview:large" />
      </Head>
      <main className="blog-shell">
        <section className="blog-hero">
          <p className="eyebrow">WECARE.DIGITAL</p>
          <h1>Blog</h1>
          <p>Ideas, guides and updates published from Bharat Stack.</p>
        </section>

        { posts.length > 0 ? (
          <section className="post-grid" aria-label="Published posts">
            { posts.map( post => (
              <article key={ post.id || post.slug } className="post-card">
                { post.coverImage && <img src={ post.coverImage } alt="" loading="lazy" /> }
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
        .blog-shell{max-width:1180px;margin:0 auto;padding:156px 24px 96px;color:#111827}
        .blog-hero{max-width:720px;margin-bottom:56px}
        .eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;color:#1a3a2a;text-transform:uppercase;margin:0 0 12px}
        h1{font-size:clamp(44px,7vw,76px);line-height:1;letter-spacing:-.045em;margin:0 0 18px;color:#1a3a2a}
        .blog-hero>p:last-child{font-size:18px;line-height:1.7;color:#6b7280;margin:0}
        .post-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}
        .post-card{border:1px solid #e5e7eb;border-radius:18px;overflow:hidden;background:#fff}
        .post-card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}
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
