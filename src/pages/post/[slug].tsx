import type { GetStaticPaths, GetStaticProps } from 'next';
import Head from 'next/head';
import Link from 'next/link';
import { getPublicBlogPost, listPublicBlogPosts, PublicBlogPost } from '../../lib/public-blog';

interface Props {
  post: PublicBlogPost;
}

function contentBlocks ( content: string ) {
  return content.split( /\r?\n/ ).map( line => line.trim() ).filter( Boolean );
}

function inlineFormat ( text: string ) {
  return text.split( /(\*\*[^*]+\*\*|\*[^*]+\*)/g ).filter( Boolean ).map( ( part, index ) => {
    if ( part.startsWith( '**' ) && part.endsWith( '**' ) ) {
      return <strong key={ index }>{ part.slice( 2, -2 ) }</strong>;
    }
    if ( part.startsWith( '*' ) && part.endsWith( '*' ) ) {
      return <em key={ index }>{ part.slice( 1, -1 ) }</em>;
    }
    return part;
  } );
}

export default function BlogPostPage ( { post }: Props ) {
  const canonical = `https://wecare.digital/post/${post.slug}/`;
  const title = post.seoTitle || post.title;
  const description = post.metaDescription || post.excerpt || '';
  const blocks = contentBlocks( post.content || '' );
  const storedSchema = post.jsonLd?.blogPosting;
  const articleSchema = storedSchema || {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: post.title,
    description,
    url: canonical,
    datePublished: post.publishedDate || undefined,
    dateModified: post.modifiedDate || post.publishedDate || undefined,
    author: { '@type': 'Organization', name: post.authorName || 'Anew by WECARE.DIGITAL' },
    publisher: { '@type': 'Organization', name: 'WECARE.DIGITAL', url: 'https://wecare.digital/' },
    inLanguage: 'en-IN',
  };
  const breadcrumbSchema = post.jsonLd?.breadcrumbList || {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://wecare.digital/' },
      { '@type': 'ListItem', position: 2, name: 'Blog', item: 'https://wecare.digital/blog/' },
      { '@type': 'ListItem', position: 3, name: post.title, item: canonical },
    ],
  };

  return (
    <>
      <Head>
        <title>{ title }</title>
        <meta name="description" content={ description } />
        <link rel="canonical" href={ canonical } />
        <meta name="robots" content={ post.robots || 'index, follow, max-image-preview:large' } />
        <meta property="og:type" content="article" />
        <meta property="og:title" content={ title } />
        <meta property="og:description" content={ description } />
        <meta property="og:url" content={ canonical } />
        <meta property="og:site_name" content="WECARE.DIGITAL" />
        <meta property="og:locale" content="en_IN" />
        <meta name="twitter:card" content="summary" />
        <meta name="twitter:title" content={ title } />
        <meta name="twitter:description" content={ description } />
        <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( articleSchema ) } } />
        <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( breadcrumbSchema ) } } />
        { ( post.jsonLd?.faqSchema?.mainEntity?.length || 0 ) > 0 && (
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( post.jsonLd?.faqSchema ) } } />
        ) }
      </Head>
      <main className="article-shell">
        <article>
          <Link className="back" href="/blog/">Blog</Link>
          { post.category && <div className="category">{ post.category }</div> }
          <h1>{ post.title }</h1>
          <div className="byline">
            <span>{ post.authorName || 'Anew by WECARE.DIGITAL' }</span>
            { post.publishedDate && <time dateTime={ post.publishedDate }>{ new Date( post.publishedDate ).toLocaleDateString( 'en-IN', { day: 'numeric', month: 'long', year: 'numeric' } ) }</time> }
          </div>
          <div className="content">
            { blocks.map( ( line, index ) => {
              if ( line.startsWith( '### ' ) ) return <h3 key={ index }>{ inlineFormat( line.slice( 4 ) ) }</h3>;
              if ( line.startsWith( '## ' ) ) return <h2 key={ index }>{ inlineFormat( line.slice( 3 ) ) }</h2>;
              if ( line.startsWith( '# ' ) ) return <h2 key={ index }>{ inlineFormat( line.slice( 2 ) ) }</h2>;
              return <p key={ index }>{ inlineFormat( line ) }</p>;
            } ) }
          </div>
          { post.tags && post.tags.length > 0 && (
            <div className="tags">{ post.tags.map( tag => <span key={ tag }>{ tag }</span> ) }</div>
          ) }
        </article>
      </main>
      <style jsx>{`
        .article-shell{max-width:900px;margin:0 auto;padding:148px 24px 96px;color:#111827}
        article{max-width:760px;margin:0 auto}
        .back{display:inline-block;color:#1a3a2a;text-decoration:none;font-size:13px;font-weight:650;margin-bottom:26px}
        .back:before{content:'← ';margin-right:4px}
        .category{display:inline-block;background:#d1f470;color:#1a3a2a;border-radius:999px;padding:6px 10px;font-size:11px;font-weight:700;margin-bottom:18px}
        h1{font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;letter-spacing:-2.2px;color:#1a3a2a;margin:0 0 18px}
        .byline{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#6b7280;margin-bottom:38px}
        .content{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
        .content p{font-size:20px;line-height:1.6;letter-spacing:-.125px;font-weight:400;margin:0 0 24px;color:#27272a}
        .content strong{font-weight:700}
        .content em{font-style:italic}
        .content h2{font-family:inherit;font-size:30px;line-height:1.2;color:#1a3a2a;margin:46px 0 18px}
        .content h3{font-family:inherit;font-size:23px;line-height:1.3;color:#1a3a2a;margin:36px 0 14px}
        .tags{display:flex;gap:8px;flex-wrap:wrap;margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb}
        .tags span{font-size:11px;background:#f3f4f6;border-radius:999px;padding:6px 10px;color:#4b5563}
        @media(max-width:640px){.article-shell{padding:124px 16px 64px}.content p{font-size:18px;line-height:1.62}}
      `}</style>
    </>
  );
}

export const getStaticPaths: GetStaticPaths = async () => {
  const posts = await listPublicBlogPosts();
  return {
    paths: posts.map( post => ( { params: { slug: post.slug } } ) ),
    fallback: false,
  };
};

export const getStaticProps: GetStaticProps<Props> = async ( context ) => {
  const slug = String( context.params?.slug || '' );
  const post = await getPublicBlogPost( slug );
  if ( !post ) return { notFound: true };
  return { props: { post } };
};
