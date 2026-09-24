import type { GetStaticPaths, GetStaticProps } from 'next';
import type { ReactNode } from 'react';
import { Fragment } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { getPublicBlogPost, listPublicBlogPosts, PublicBlogPost } from '../../lib/public-blog';

interface Props {
  post: PublicBlogPost;
}

interface RicosNode {
  type?: string;
  nodes?: RicosNode[];
  textData?: {
    text?: string;
    decorations?: Array<Record<string, any>>;
  };
  headingData?: { level?: number };
}

function textRun ( node: RicosNode, key: string ): ReactNode {
  let child: ReactNode = node.textData?.text || '';
  for ( const decoration of node.textData?.decorations || [] ) {
    const type = String( decoration.type || '' ).toUpperCase();
    if ( type === 'BOLD' ) child = <strong>{ child }</strong>;
    if ( type === 'ITALIC' ) child = <em>{ child }</em>;
    if ( type === 'UNDERLINE' ) child = <u>{ child }</u>;
    if ( type === 'STRIKETHROUGH' ) child = <s>{ child }</s>;
    if ( type === 'LINK' ) {
      const href = decoration.linkData?.link?.url;
      if ( href ) child = <a href={ href }>{ child }</a>;
    }
  }
  return <Fragment key={ key }>{ child }</Fragment>;
}

function inlineNodes ( nodes: RicosNode[] = [], prefix = 'inline' ): ReactNode[] {
  return nodes.map( ( node, index ) => {
    if ( node.type === 'TEXT' ) return textRun( node, `${prefix}-${index}` );
    return <Fragment key={ `${prefix}-${index}` }>{ inlineNodes( node.nodes || [], `${prefix}-${index}` ) }</Fragment>;
  } );
}

function listItemContent ( node: RicosNode, prefix: string ): ReactNode {
  return ( node.nodes || [] ).map( ( child, index ) => {
    if ( child.type === 'PARAGRAPH' || child.type === 'HEADING' ) {
      return <Fragment key={ `${prefix}-${index}` }>{ inlineNodes( child.nodes || [], `${prefix}-${index}` ) }</Fragment>;
    }
    return renderRicosNode( child, `${prefix}-${index}` );
  } );
}

function renderRicosNode ( node: RicosNode, key: string ): ReactNode {
  switch ( node.type ) {
    case 'PARAGRAPH':
      if ( !( node.nodes || [] ).length ) return <div key={ key } className="spacer" aria-hidden="true" />;
      return <p key={ key }>{ inlineNodes( node.nodes || [], key ) }</p>;
    case 'HEADING': {
      const level = Number( node.headingData?.level || 2 );
      if ( level >= 3 ) return <h3 key={ key }>{ inlineNodes( node.nodes || [], key ) }</h3>;
      return <h2 key={ key }>{ inlineNodes( node.nodes || [], key ) }</h2>;
    }
    case 'BLOCKQUOTE':
      return <blockquote key={ key }>{ ( node.nodes || [] ).map( ( child, index ) => renderRicosNode( child, `${key}-${index}` ) ) }</blockquote>;
    case 'BULLETED_LIST':
      return <ul key={ key }>{ ( node.nodes || [] ).map( ( child, index ) => renderRicosNode( child, `${key}-${index}` ) ) }</ul>;
    case 'ORDERED_LIST':
      return <ol key={ key }>{ ( node.nodes || [] ).map( ( child, index ) => renderRicosNode( child, `${key}-${index}` ) ) }</ol>;
    case 'LIST_ITEM':
      return <li key={ key }>{ listItemContent( node, key ) }</li>;
    case 'IMAGE':
    case 'GALLERY':
    case 'GIF':
    case 'VIDEO':
      return null;
    default:
      return <Fragment key={ key }>{ ( node.nodes || [] ).map( ( child, index ) => renderRicosNode( child, `${key}-${index}` ) ) }</Fragment>;
  }
}

function fallbackBlocks ( content: string ) {
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
  const richNodes = ( post.richContent?.nodes || [] ) as RicosNode[];
  const blocks = fallbackBlocks( post.content || '' );
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
            { richNodes.length > 0
              ? richNodes.map( ( node, index ) => renderRicosNode( node, `block-${index}` ) )
              : blocks.map( ( line, index ) => {
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
        .article-shell{max-width:900px;margin:0 auto;padding:148px 24px 96px;color:#111827;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
        article{max-width:760px;margin:0 auto}
        .back{display:inline-block;color:#1a3a2a;text-decoration:none;font-size:13px;font-weight:650;margin-bottom:26px}
        .back:before{content:'← ';margin-right:4px}
        .category{display:inline-block;background:#d1f470;color:#1a3a2a;border-radius:999px;padding:6px 10px;font-size:11px;font-weight:700;margin-bottom:18px}
        h1{font-size:clamp(36px,4.3vw,60px);line-height:1.04;letter-spacing:-2.2px;color:#1a3a2a;margin:0 0 18px;font-weight:600}
        .byline{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#6b7280;margin-bottom:38px}
        .content{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
        .content :global(p),
        .content :global(li),
        .content :global(blockquote){font-size:20px;line-height:1.4;letter-spacing:-.125px;font-weight:400;color:rgba(0,0,0,.898)}
        .content :global(p){margin:0}
        .content :global(p + p){margin-top:4px}
        .content :global(.spacer){height:28px}
        .content :global(h2){font-size:30px;line-height:1.18;letter-spacing:-.6px;color:#1a3a2a;margin:44px 0 18px;font-weight:700}
        .content :global(h3){font-size:23px;line-height:1.3;color:#1a3a2a;margin:36px 0 14px;font-weight:700}
        .content :global(ul),.content :global(ol){margin:0;padding-left:28px}
        .content :global(li + li){margin-top:8px}
        .content :global(blockquote){margin:0;padding-left:18px;border-left:3px solid #d1f470}
        .content :global(a){color:#1a3a2a;text-underline-offset:3px}
        .content :global(strong){font-weight:700}
        .tags{display:flex;gap:8px;flex-wrap:wrap;margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb}
        .tags span{font-size:11px;background:#f3f4f6;border-radius:999px;padding:6px 10px;color:rgba(0, 0, 0, 0.54)}
        @media(max-width:640px){
          .article-shell{padding:124px 16px 64px}
          .content :global(p),.content :global(li),.content :global(blockquote){font-size:18px;line-height:1.5}
          .content :global(.spacer){height:24px}
        }
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
