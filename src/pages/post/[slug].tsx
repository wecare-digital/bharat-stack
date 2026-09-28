import type { GetStaticPaths, GetStaticProps } from 'next';
import type { ReactNode } from 'react';
import { Fragment } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { getPublicBlogPost, listPublicBlogPosts, PublicBlogPost } from '../../lib/public-blog';
import RotatingHero, { CycleWord } from '../../components/RotatingHero';
import Breadcrumbs from '../../components/Breadcrumbs';
import BlogSearch from '../../components/BlogSearch';

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

/** Same four words and tints as /blog/ - this band is the blog's masthead, so it must not
 * say something different from the section it belongs to. */
const HERO_WORDS: CycleWord[] = [
  { word: 'clarity', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'practice', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'meaning', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'change', tint: '#ede9fe', dot: '#9849e8' },
];

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
      {/* THE BLOG'S MASTHEAD, ABOVE THE ARTICLE - option B, chosen by the owner from
          docs/post-layout-review.html.
          `subordinate` is not optional here: without it RotatingHero renders its own <main>
          and <h1>, and this page already has both. That would put two main landmarks and two
          h1s on all 824 posts, which fails MANY-MAIN at HIGH and H1-MANY in
          tools/audit/htmlcheck.js. Measured in the mock before the prop existed: 2 mains,
          2 h1s. With it the wrapper is a <section> and the headline an <h2>, styled by class
          so the 55px/600 rung is pixel-identical either way.
          NO badgeLabel, matching /blog/ and the home page: the header already states the
          brand, and repeating it directly beneath is what the home page removed.
          The trade is recorded rather than hidden: this band is the same on every post, so it
          is the blog's masthead and not the article's own content, and it moves the writing
          from 338px down to 812px. Both numbers are in the mock. */}
      <RotatingHero
        subordinate
        frame="Notes on"
        words={ HERO_WORDS }
        sub="Short pieces on the distinctions that change how a thing is seen."
        ariaLabel="WECARE.DIGITAL blog"
      />
      <main className="article-shell">
        <article>
          {/* A REAL TRAIL, replacing a single "← Blog" back link at 13px/650 - the only
              control on this page below the site's 12px/700 smallest UI rung. The page's own
              JSON-LD has always declared a BreadcrumbList; now the page shows one. */}
          <Breadcrumbs items={ [
            { label: 'Home', href: '/' },
            { label: 'Blog', href: '/blog/' },
            { label: post.title },
          ] } />
          {/* GET mode: the post list is not in this page, so the box navigates to /blog/?q=
              and the index filters. Same component, same markup, different mode. */}
          <BlogSearch />
          { post.category && <div className="category">{ post.category }</div> }
          <h1>{ post.title }</h1>
          <div className="byline">
            {/* data-wc-no-translate: AN AUTHOR NAME IS A PROPER NOUN. This is on the span
                rather than the .byline wrapper on purpose - the <time> sibling below renders
                a formatted date, and a date IS worth translating, so flagging the wrapper
                would cost that.
                It applies to the dynamic value as much as the fallback: post.authorName is a
                person's or a brand's name either way, and the fallback is two brand names
                joined by "by" - translating a single preposition is not worth rendering
                "Anew" and "WECARE.DIGITAL" as invented words around it. Measured at 1276
                occurrences across the exported blog, the largest single source of
                brand-name text on the site. */}
            <span data-wc-no-translate="true">{ post.authorName || 'Anew by WECARE.DIGITAL' }</span>
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
        /* padding-top is 40px, not 156px: the hero above now owns the header offset. */
        .article-shell{max-width:1300px;margin:0 auto;padding:40px 24px 96px;color:#1a1a1a;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
        article{max-width:700px;margin:0 auto}
        /* .back rules removed with the link - Breadcrumbs replaced it. */
        .category{display:inline-block;background:rgba(209,244,112,.28);color:#1a3a2a;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:700;margin-bottom:18px}
        h1{font-size:clamp(36px,4.3vw,60px);line-height:1.04;letter-spacing:-0.04em;color:rgba(0,0,0,.95);margin:0 0 20px;font-weight:600;text-wrap:balance;max-width:20ch}
        .byline{display:flex;gap:12px;flex-wrap:wrap;font-size:13px;line-height:1.4;color:#6b7280;margin-bottom:40px}
        .content{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
        .content :global(p),
        .content :global(li){font-size:20px;line-height:1.55;letter-spacing:-.125px;font-weight:400;color:rgba(0,0,0,.898)}
        .content :global(p){margin:0}
        .content :global(p + p){margin-top:28px}
        .content :global(.spacer){height:28px}
        .content :global(h2){font-size:30px;line-height:1.15;letter-spacing:-.6px;color:rgba(0,0,0,.95);margin:48px 0 20px;font-weight:700}
        .content :global(h3){font-size:23px;line-height:1.3;color:rgba(0,0,0,.95);margin:36px 0 16px;font-weight:700}
        .content :global(h2 + p),.content :global(h3 + p){margin-top:0}
        .content :global(ul),.content :global(ol){margin:28px 0;padding-inline-start:1.4em}
        .content :global(li + li){margin-top:10px}
        .content :global(blockquote){margin:36px 0;padding:2px 0 2px 22px;border-inline-start:3px solid #d1f470;font-size:21px;line-height:1.5;letter-spacing:-.125px;font-weight:400;color:rgba(0,0,0,.898)}
        .content :global(blockquote p){font:inherit;color:inherit;letter-spacing:inherit}
        .content :global(a){color:#1a3a2a;text-underline-offset:3px}
        .content :global(a:hover){text-decoration-thickness:2px}
        .content :global(a:focus-visible){outline:3px solid rgba(26,58,42,.25);outline-offset:3px;border-radius:2px}
        .content :global(strong){font-weight:700}
        .tags{display:flex;gap:8px;flex-wrap:wrap;margin-top:52px;padding-top:24px;border-top:1px solid #e5e7eb}
        .tags span{font-size:11px;background:#f3f4f6;border-radius:999px;padding:6px 10px;color:rgba(0,0,0,.54)}
        @media(max-width:680px){
          .article-shell{padding:128px 16px 64px}
          h1{max-width:none}
          .byline{margin-bottom:34px}
          .content :global(p),.content :global(li){font-size:18px;line-height:1.6}
          .content :global(p + p){margin-top:24px}
          .content :global(.spacer){height:24px}
          .content :global(h2){font-size:27px;margin-top:42px}
          .content :global(h3){font-size:22px}
          .content :global(blockquote){font-size:19px;line-height:1.55;margin:32px 0;padding-inline-start:18px}
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
