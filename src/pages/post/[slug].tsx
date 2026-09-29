import type { GetStaticPaths, GetStaticProps } from 'next';
import type { ReactNode } from 'react';
import { Fragment } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { getPublicBlogPost, listPublicBlogPosts, PublicBlogPost } from '../../lib/public-blog';
import { postContext, type PostLink } from '../../lib/post-neighbours';
import RotatingHero, { CycleWord } from '../../components/RotatingHero';
import Breadcrumbs from '../../components/Breadcrumbs';
import BlogSearch from '../../components/BlogSearch';

/**
 * EVERY FIELD BELOW `post` IS OPTIONAL, and that is not defensiveness - it is what keeps
 * BlogDesign.test.tsx compiling. Its two post-page tests render <BlogPostPage post={ samplePost } />
 * with no other props, so a required prop here would break them, and they are the only guard on
 * this page's type rungs.
 * They are also genuinely absent in real cases: `newer` on the newest post in a stream, `older`
 * on the oldest, and all of them if the corpus fetch returns nothing during a build.
 */
interface Props {
  post: PublicBlogPost;
  newer?: PostLink;
  older?: PostLink;
  related?: PostLink[];
  streamHref?: string;
  streamLabel?: string;
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

export default function BlogPostPage ( {
  post, newer, older, related = [], streamHref = '/blog/', streamLabel = 'Blog',
}: Props ) {
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

          {/* WALKING THE STREAM, ONE POST AT A TIME.
              Until now the only way out of a post was back up to the listing, so reading two in a
              row cost a round trip through /blog/ and a hunt for where you had got to.

              IT MIRRORS THE INDEX PAGER ON PURPOSE - the same rel=prev/next, the same
              "dead direction is rendered, not omitted" rule, the same 44px/12px-radius/#1a3a2a
              rung. Two different pagination idioms on one blog would read as two products.

              NEWER/OLDER RATHER THAN PREVIOUS/NEXT, because that is what /blog/ already calls
              these two directions, and "previous post" is ambiguous in a newest-first list - it
              means the one published before this, which is the one BELOW it. The rel attributes
              still say prev/next: those describe position in the document sequence, and the
              sequence is newest-first, so prev is the newer post. Same mapping the index uses.

              THE DEAD END IS RENDERED AND aria-hidden. Rendering it keeps the two boxes the same
              size so the row does not reflow between posts, and aria-hidden stops a screen reader
              announcing a control that does nothing. Copied from .pager-step.is-off. */}
          <nav className="post-nav" aria-label="Newer and older posts">
            { newer
              ? <Link className="post-nav-step is-prev" rel="prev" href={ `/post/${newer.slug}/` }>
                <span className="post-nav-dir"><i className="post-nav-mark" aria-hidden="true" />Newer</span>
                <span className="post-nav-name">{ newer.title }</span>
              </Link>
              : <span className="post-nav-step is-prev is-off" aria-hidden="true">
                <span className="post-nav-dir"><i className="post-nav-mark" />Newer</span>
                <span className="post-nav-name">This is the newest</span>
              </span> }
            { older
              ? <Link className="post-nav-step is-next" rel="next" href={ `/post/${older.slug}/` }>
                <span className="post-nav-dir">Older<i className="post-nav-mark" aria-hidden="true" /></span>
                <span className="post-nav-name">{ older.title }</span>
              </Link>
              : <span className="post-nav-step is-next is-off" aria-hidden="true">
                <span className="post-nav-dir">Older<i className="post-nav-mark" /></span>
                <span className="post-nav-name">This is the oldest</span>
              </span> }
          </nav>

          {/* RELATED BY SHARED TAGS, WEIGHTED - see src/lib/post-neighbours.ts for the scoring and
              the measurement behind it. Briefly: all 914 posts carry tags and nothing else on the
              record is a relatedness signal, so tags are it; each shared tag is worth 1/(posts
              carrying it), so a specific overlap beats a broad one and every post in a category
              does not end up with the same three neighbours.

              h2 AT THE EYEBROW RUNG. It is a real heading because it labels a section and a
              reader navigating by heading should find it, and it is 12px/700/.08em uppercase
              because it is furniture rather than a claim - the same thing .lgd-toc-title does on
              /grahak-os/ and the same declaration .home-close-eyebrow and Breadcrumbs use. The
              card titles below are h3, so the page's outline stays h1 > h2 > h3.

              THE CARDS ARE THE INDEX'S CARDS: 1px #e5e7eb, radius 14px, 23px/700 heading. The
              border is on the li and the link is the heading inside it, matching .post-card
              exactly - which is also what keeps the 1px-static / 2px-hoverable hairline rule
              intact, since the box is not the thing being hovered. */}
          { related.length > 0 && (
            <section className="post-related" aria-labelledby="post-related-title">
              <h2 className="post-related-title" id="post-related-title">More in { streamLabel }</h2>
              <ul className="post-related-list">
                { related.map( item => (
                  <li key={ item.slug } className="post-related-card">
                    <h3><Link href={ `/post/${item.slug}/` }>{ item.title }</Link></h3>
                  </li>
                ) ) }
              </ul>
              {/* Back to the listing this post is actually on - /blog/ for the default category,
                  /blog/topic/<slug>/ for the others. The same branch BlogIndexView uses for its
                  pills, so the link cannot point at a listing that does not contain this post. */}
              <Link className="post-related-all" href={ streamHref }>
                All { streamLabel } posts<i className="post-nav-mark" aria-hidden="true" />
              </Link>
            </section>
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

        /* THE NEWER/OLDER PAGER. Every value is lifted from .pager-step on the index rather than
           chosen again: 2px rgba(26,58,42,.22) border because a hoverable edge is 2px on this
           site and a static one is 1px, radius 12px, colour 1a3a2a, the lime .28 hover tint, and
           the solid-1a3a2a focus ring at offset 2px that the index pager uses.
           44px is the WCAG 2.5.8 floor for a touch target and it is a floor, not the height - the
           padding and the two lines take these well past it.
           Two equal columns, so the pair reads as one control and neither box changes size when
           the titles differ in length. text-align on the older half is logical (end, not right)
           so a mirrored page does not push it the wrong way. */
        /* THE STEPS GO THROUGH :global() BECAUSE THEY ARE next/link, and this is not a style
           preference - it is the difference between these rules applying and not applying.
           styled-jsx attaches its scoping class only to lowercase DOM tags it can see here, never
           to a capitalised component, so <Link className="post-nav-step"> renders
           class="post-nav-step" with no jsx- hash and a plain .post-nav-step rule matches nothing.
           The is-off placeholders are <span>, so those WOULD have been styled and the live links
           would not - a pager where only the dead halves look like buttons. The blog index pager
           had exactly this bug and shipped with it; see the long note in BlogIndexView.tsx.
           Scoped under .post-nav, which is a <nav> in this file and does carry the hash, so these
           compile to .jsx-xxx.post-nav .post-nav-step and cannot leak. Same idiom as
           .content :global(p) above. */
        .post-nav{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:52px;padding-top:24px;border-top:1px solid #e5e7eb}
        .post-nav :global(.post-nav-step){
          display:flex;flex-direction:column;gap:5px;min-height:44px;padding:14px 16px;
          border:2px solid rgba(26,58,42,.22);border-radius:12px;
          color:#1a3a2a;text-decoration:none;
        }
        .post-nav :global(.post-nav-step:hover){background:rgba(209,244,112,.28)}
        .post-nav :global(.post-nav-step:focus-visible){outline:3px solid #1a3a2a;outline-offset:2px}
        .post-nav :global(.post-nav-step.is-off){border-color:#e5e7eb;color:rgba(0,0,0,.32);cursor:default}
        .post-nav :global(.post-nav-step.is-next){align-items:flex-end;text-align:end}
        /* The site's 12px/700/.08em eyebrow rung, same as .post-related-title below. */
        .post-nav :global(.post-nav-dir){display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
        /* THE DIRECTION MARK IS DRAWN, NOT TYPED. These labels read "← Newer" and "Older →" with
           literal U+2190 / U+2192, and with the webfont unavailable both rendered as tofu next to
           legible text - confirmed by comparing their canvas advance width against a private-use
           codepoint with no glyph anywhere: identical, so nothing in the fallback chain covered
           them. A rotated border box cannot fall back to a missing glyph.
           Same technique as the breadcrumb chevron and the terminal's play/pause marks, which
           exist for this reason. currentColor so it dims with the is-off text for free. */
        .post-nav :global(.post-nav-mark){
          width:6px;height:6px;flex:0 0 auto;
          border-top:2px solid currentColor;border-right:2px solid currentColor;
        }
        .post-nav :global(.is-prev .post-nav-mark){transform:rotate(-135deg)}
        .post-nav :global(.is-next .post-nav-mark){transform:rotate(45deg)}
        /* 16px/600 is the index pager's own size for a control label. Two lines maximum, because
           a long title in a half-width box would otherwise set the height of the whole row. */
        .post-nav :global(.post-nav-name){
          font-size:16px;font-weight:600;line-height:1.3;
          display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
        }

        /* RELATED POSTS. .post-related-card is .post-card from the index - 1px #e5e7eb, radius
           14px - and the h3 is its 23px/700/-.3px card-heading rung with the same
           rgba(0,0,0,.95) resting colour going to 1a3a2a on hover. A related card should read as
           the same object a listing shows, not as a new kind of thing. */
        .post-related{margin-top:44px;padding-top:24px;border-top:1px solid #e5e7eb}
        .post-related-title{margin:0 0 16px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a}
        .post-related-list{margin:0;padding:0;list-style:none;display:grid;gap:12px}
        /* THE WHOLE CARD IS THE TARGET, NOT JUST THE WORDS. The padding used to sit on the li,
           which left the <a> as tall as one line of text - measured 28px at 1280 and 25px at 390,
           so the card looked like a 62px button and only the middle third of it responded. Moving
           the padding onto the anchor makes the target the box a reader is aiming at, and takes it
           past the 44px floor the rest of this page holds to. The 1px border stays on the li: it
           is the static frame, and the site's rule is 1px for a static edge and 2px for a
           hoverable one. */
        .post-related-card{border:1px solid #e5e7eb;border-radius:14px;transition:border-color .2s}
        .post-related-card:hover{border-color:#d1f470}
        .post-related-card h3{margin:0;font-size:23px;line-height:1.22;letter-spacing:-.3px;font-weight:700}
        .post-related-card h3 :global(a){display:block;padding:16px 18px;color:rgba(0,0,0,.95);text-decoration:none}
        .post-related-card h3 :global(a:hover){color:#1a3a2a;text-decoration:underline;text-underline-offset:3px}
        /* border-radius matches the card so the ring traces the shape it belongs to, and the
           offset is 2px rather than the usual 3px because the anchor now sits on the card's own
           edge - 3px would have the ring straddling the border. 12px of grid gap keeps it clear of
           the neighbouring card either way. */
        .post-related-card h3 :global(a:focus-visible){outline:3px solid rgba(26,58,42,.25);outline-offset:2px;border-radius:14px}
        /* 44px floor again - this is a link on its own line and a thumb has to be able to hit it.
           :global() because it is next/link, like the steps above. */
        .post-related :global(.post-related-all){
          display:inline-flex;align-items:center;gap:8px;min-height:44px;margin-top:14px;
          font-size:16px;font-weight:600;color:#1a3a2a;text-underline-offset:3px;
        }
        /* Its trailing mark, drawn for the same reason as the pager's - see the note there. */
        .post-related :global(.post-nav-mark){
          width:6px;height:6px;flex:0 0 auto;
          border-top:2px solid currentColor;border-right:2px solid currentColor;
          transform:rotate(45deg);
        }
        .post-related :global(.post-related-all:focus-visible){outline:3px solid rgba(26,58,42,.25);outline-offset:3px;border-radius:2px}
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
          /* ONE COLUMN BELOW 680px, and the older half stops being end-aligned with it. Two
             44px-plus boxes side by side at 360px leaves about 160px each, which clamps a title
             to two lines of five words - the link stops saying which post it goes to. Stacked,
             each gets the full measure. The index pager does the same thing at the same width
             (.pager-list goes full width and .pager-step flexes). */
          .post-nav{grid-template-columns:1fr;gap:10px}
          .post-nav :global(.post-nav-step.is-next){align-items:flex-start;text-align:start}
          .post-related-card h3{font-size:21px}
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
  /* FREE, because getStaticPaths above already pulled the corpus through the memoised fetch in
   * listPublicBlogPosts and postContext builds its tag index once for the whole build. What this
   * adds to the page is five slug/title pairs - about 0.4 kB - not a category of cards.
   * Spread rather than assigned key by key: newer and older are absent at the ends of a stream,
   * and Next refuses to serialise an explicit undefined in props. */
  const around = await postContext( slug );
  return { props: { post, ...around } };
};
