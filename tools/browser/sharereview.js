'use strict';

/**
 * Share row review: rest, primary hover, and the copy confirmation.
 *
 * The tip sits ABOVE the button (bottom: calc(100% + 8px)), so an element screenshot of
 * .share-row clips it off. Every grab therefore uses a page clip expanded upward from the row's
 * own box, which is the only way to see the thing being reviewed.
 */

const { target, OUT_DIR } = require( '/projects/sandbox/wecare-digital/tools/browser/lib/serve' );
const { launch, gotoStable } = require( '/projects/sandbox/wecare-digital/tools/browser/lib/browser' );
const fs = require( 'fs' );
const path = require( 'path' );

/**
 * Any exported post will do - the row is identical on all of them - so the first one is picked off
 * disk rather than hardcoded. A slug pinned here would rot the next time the corpus changes, which
 * is how a review script turns into a script nobody can run.
 */
function firstPostPath () {
  const dir = path.join( OUT_DIR, 'post' );
  const slug = fs.readdirSync( dir ).find( d => fs.statSync( path.join( dir, d ) ).isDirectory() );
  if ( !slug ) throw new Error( `No exported posts under ${dir} - run the build first.` );
  return `post/${slug}/`;
}

( async () => {
  const postPath = process.argv[ 2 ] || firstPostPath();
  const t = await target();
  const b = await launch();
  const p = await b.newPage( { viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 2 } );
  await gotoStable( p, t.base + '/' + postPath );

  await p.waitForSelector( '.share-row' );
  // The reveal only plays once the tail is on screen; scroll it into view and let it finish so the
  // shot shows the settled state rather than a mid-transition frame.
  await p.$eval( '.share-row', el => el.scrollIntoView( { block: 'center' } ) );
  await p.waitForTimeout( 1200 );

  const box = await p.$eval( '.share-row', el => {
    const r = el.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  } );
  const clip = {
    x: Math.max( 0, box.x - 12 ),
    y: Math.max( 0, box.y - 46 ),          // headroom for the tip
    width: Math.min( 560, box.width + 24 ),
    height: box.height + 58,
  };

  const shots = {};
  const grab = async key => { shots[ key ] = ( await p.screenshot( { clip } ) ).toString( 'base64' ); };

  await p.mouse.move( 0, 0 ); await p.waitForTimeout( 400 ); await grab( 'rest' );
  await p.hover( '.share-btn.is-primary' ); await p.waitForTimeout( 450 ); await grab( 'waHover' );
  await p.mouse.move( 0, 0 ); await p.waitForTimeout( 300 );
  await p.hover( '.share-copy' ); await p.waitForTimeout( 450 ); await grab( 'copyHover' );

  const measured = await p.$$eval( '.share-btn', els => els.map( el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle( el );
    return {
      label: el.getAttribute( 'aria-label' ),
      w: Math.round( r.width ), h: Math.round( r.height ),
      radius: cs.borderRadius, bg: cs.backgroundColor, border: cs.borderColor,
      visible: cs.display !== 'none',
    };
  } ) );
  console.log( JSON.stringify( measured, null, 2 ) );

  const panel = ( key, caption ) => `<figure style="margin:0">
      <img src="data:image/png;base64,${shots[ key ]}" style="display:block;width:${clip.width}px;border:1px solid #e5e7eb;border-radius:8px">
      <figcaption style="margin-top:8px;font:600 12px Inter,system-ui,sans-serif;color:#1a3a2a;letter-spacing:.06em;text-transform:uppercase">${caption}</figcaption>
    </figure>`;

  await p.setContent( `<body style="margin:0;background:#fff;padding:26px">
    <div style="display:flex;flex-direction:column;gap:22px;width:${clip.width + 4}px">
      ${panel( 'rest', 'At rest' )}
      ${panel( 'waHover', 'WhatsApp hovered' )}
      ${panel( 'copyHover', 'Copy link hovered' )}
    </div>
  </body>` );
  await p.waitForTimeout( 250 );
  const out = '/projects/sandbox/share-review.png';
  await p.screenshot( { path: out, fullPage: true } );
  console.log( 'wrote', out );

  await b.close();
  if ( t.close ) await t.close();
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
