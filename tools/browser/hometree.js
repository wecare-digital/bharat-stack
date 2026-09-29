'use strict';

/**
 * hometree - the home page's rendered structure as a text tree, with measurements.
 *
 * WHY A SEPARATE SCRIPT FROM sectioncheck.js. sectioncheck answers "how many bands" across
 * 18 routes and deliberately stops at band level, because going deeper on 18 pages produces
 * output nobody reads. This goes all the way down on ONE page, which is a different job: it
 * is the map you read before deciding what a band mock has to cover.
 *
 * MEASURED, NOT PARSED FROM SOURCE. index.tsx is ~1000 lines of which most is comment, and
 * its markup is nested inside conditional class strings and a styled-jsx block. The rendered
 * tree is the thing the visitor gets, so the tree is read after layout in Chromium.
 *
 * WHAT IS PRUNED, and why the tree is still complete:
 *   - zero-height and display:none nodes, which are not part of the visual structure
 *   - jsx-xxxx scoping classes, which are build output and change every edit
 *   - text nodes past 64 characters, truncated - the point is the shape, not the copy
 * Nothing structural is dropped: every element with a box is in the tree.
 *
 * DEPTH IS UNCAPPED ON PURPOSE. An earlier version capped at 4 and hid the rotating pill's
 * internals - the four absolutely-positioned word spans and the sr-only list - which is
 * exactly the part of this page that has caused the most defects.
 *
 * Run: node tools/browser/hometree.js            (needs out/ - see README.md)
 *      node tools/browser/hometree.js --width 390
 */

const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

const wi = process.argv.indexOf( '--width' );
const WIDTH = wi > -1 ? Number( process.argv[ wi + 1 ] ) : 1280;

( async () => {
  const t = await target();
  const browser = await launch();
  const page = await browser.newPage( { viewport: { width: WIDTH, height: 900 } } );
  await gotoStable( page, t.base + '/' );

  const tree = await page.evaluate( () => {
    const skip = new Set( [ 'SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE' ] );

    const describe = el => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle( el );
      const cls = ( el.getAttribute( 'class' ) || '' )
        .split( /\s+/ ).filter( c => c && !c.startsWith( 'jsx-' ) ).join( '.' );

      // Own text only - a wrapper should not be labelled with its children's copy.
      const own = [ ...el.childNodes ]
        .filter( n => n.nodeType === 3 )
        .map( n => n.textContent )
        .join( ' ' ).replace( /\s+/g, ' ' ).trim();

      return {
        tag: el.tagName.toLowerCase(),
        cls,
        text: own.slice( 0, 64 ) + ( own.length > 64 ? '…' : '' ),
        w: Math.round( r.width ),
        h: Math.round( r.height ),
        top: Math.round( r.top + window.scrollY ),
        fs: Math.round( parseFloat( cs.fontSize ) * 10 ) / 10,
        fw: cs.fontWeight,
        pos: cs.position,
        aria: el.getAttribute( 'aria-hidden' ) === 'true' ? 'aria-hidden' : '',
        kids: [],
      };
    };

    const walk = el => {
      const node = describe( el );
      for ( const c of el.children ) {
        if ( skip.has( c.tagName ) ) continue;
        const r = c.getBoundingClientRect();
        const cs = getComputedStyle( c );
        // Keep absolutely-positioned zero-opacity nodes: the rotating words are exactly
        // that, and they are structure even when only one is visible.
        //
        // THIS IS THE ONE SUITE THAT DELIBERATELY DOES NOT USE window.__visible, and the
        // clause above is why. The other five were converted to lib/visible.js because each
        // was answering "can a visitor see this", badly and differently. This one is not
        // asking that. It prints the document's SHAPE, so a node that exists in the tree
        // belongs in the output whether or not it is currently painted - the four rotating
        // words are one slot in the structure, and __visible would report three of them
        // gone and the tree would change every 2400ms.
        // Converting this would not be a consolidation; it would be a different measurement.
        const real = ( r.height > 0 && r.width > 0 ) || cs.position === 'absolute';
        if ( !real || cs.display === 'none' ) continue;
        node.kids.push( walk( c ) );
      }
      return node;
    };

    const main = document.querySelector( 'main' );
    return {
      header: ( () => {
        const h = document.querySelector( 'header' );
        return h ? Math.round( h.getBoundingClientRect().height ) : 0;
      } )(),
      footer: ( () => {
        const f = document.querySelector( 'footer' );
        return f ? Math.round( f.getBoundingClientRect().height ) : 0;
      } )(),
      doc: Math.round( document.documentElement.scrollHeight ),
      main: walk( main ),
      links: [ ...main.querySelectorAll( 'a' ) ].map( a => ( {
        href: a.getAttribute( 'href' ),
        text: a.textContent.replace( /\s+/g, ' ' ).trim().slice( 0, 40 ),
        top: Math.round( a.getBoundingClientRect().top + window.scrollY ),
      } ) ),
      focusable: [ ...main.querySelectorAll( 'a[href],button,input,select,textarea,[tabindex]' ) ].length,
    };
  } );

  await browser.close();
  await t.close();

  const FOLD = 900;

  console.log( `\nHOME PAGE STRUCTURE — measured at ${WIDTH}x${FOLD}` );
  console.log( `document ${tree.doc}px  ·  header ${tree.header}px  ·  footer ${tree.footer}px` );
  console.log( `fold at ${FOLD}px  ·  focusable elements inside <main>: ${tree.focusable}\n` );

  const print = ( n, prefix, last, depth ) => {
    const stem = depth === 0 ? '' : prefix + ( last ? '└─ ' : '├─ ' );
    const name = `${n.tag}${n.cls ? '.' + n.cls : ''}`;
    const geo = `${n.w}x${n.h}`;
    const meta = [
      `@${n.top}`,
      n.fs >= 1 ? `${n.fs}px/${n.fw}` : '',
      n.pos !== 'static' ? n.pos : '',
      n.aria,
    ].filter( Boolean ).join( ' ' );

    let line = `${stem}${name}`;
    line = line.padEnd( 46 ).slice( 0, Math.max( 46, line.length ) );
    line += `  ${geo.padStart( 9 )}  ${meta}`;
    if ( n.text ) line += `\n${prefix}${last ? '   ' : '│  '}${depth === 0 ? '' : '   '}"${n.text}"`;
    console.log( line );

    const nextPrefix = depth === 0 ? '' : prefix + ( last ? '   ' : '│  ' );
    n.kids.forEach( ( k, i ) => print( k, nextPrefix, i === n.kids.length - 1, depth + 1 ) );
  };

  print( tree.main, '', true, 0 );

  console.log( `\nLINKS INSIDE <main> (${tree.links.length})` );
  if ( !tree.links.length ) console.log( '  none' );
  for ( const l of tree.links ) {
    console.log( `  @${String( l.top ).padStart( 5 )}  ${l.href}   "${l.text}"` +
      ( l.top > FOLD ? '   [below the fold]' : '' ) );
  }
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
