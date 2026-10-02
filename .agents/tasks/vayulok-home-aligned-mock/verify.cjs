const { chromium } = require( 'playwright' );

const FILE = 'file:///projects/sandbox/wecare-digital/docs/mocks/vayulok-live-mock.html';
const OUT = '/projects/sandbox/wecare-digital/docs/mocks';

( async () => {
  const browser = await chromium.launch();
  console.log( 'BROWSER:', browser.version() );

  for ( const [ width, name ] of [ [ 1280, '1280' ], [ 390, '390' ] ] ) {
    const page = await browser.newPage( { viewport: { width, height: 900 } } );
    const requests = [];
    const consoleErrors = [];
    const pageErrors = [];
    page.on( 'request', r => requests.push( r.method() + ' ' + r.url() ) );
    page.on( 'console', m => { if ( m.type() === 'error' ) consoleErrors.push( m.text() ); } );
    page.on( 'pageerror', e => pageErrors.push( String( e ) ) );

    await page.goto( FILE, { waitUntil: 'networkidle' } );
    await page.waitForTimeout( 600 );
    await page.screenshot( { path: `${OUT}/vayulok-live-mock-${name}.png`, fullPage: true } );

    const outbound = requests.filter( u => !u.includes( 'file://' ) );
    console.log( `\n--- ${width}px ---` );
    console.log( 'total requests logged:', requests.length, JSON.stringify( requests ) );
    console.log( 'OUTBOUND (non-file) requests:', outbound.length, JSON.stringify( outbound ) );
    console.log( 'console errors:', consoleErrors.length, JSON.stringify( consoleErrors ) );
    console.log( 'page errors:', pageErrors.length, JSON.stringify( pageErrors ) );

    if ( width === 1280 ) {
      const order = await page.$$eval( '[data-vl-section]', els => els.map( e => ( {
        n: e.getAttribute( 'data-vl-section' ),
        tag: e.tagName.toLowerCase(),
      } ) ) );
      console.log( 'DOM section order:', JSON.stringify( order ) );

      const headings = await page.$$eval(
        'h1, h2:not(.vl-sr), h3',
        els => els.filter( e => e.offsetParent !== null || e.className.includes( 'vl-sr' ) )
          .map( e => e.tagName.toLowerCase() + ': ' + e.textContent.trim().slice( 0, 60 ) )
      );
      console.log( 'HEADINGS:', JSON.stringify( headings, null, 0 ) );

      const bc = await page.$eval( '#vl-bc-title', e => ( {
        text: e.textContent,
        transform: getComputedStyle( e ).textTransform,
      } ) );
      console.log( 'SECTION 10 LABEL:', JSON.stringify( bc ) );

      const geo = await page.evaluate( () => {
        const g = s => { const e = document.querySelector( s ); const r = e.getBoundingClientRect(); return { x: Math.round( r.x ), w: Math.round( r.width ), h: Math.round( r.height ) }; };
        return {
          vw: window.innerWidth,
          doc: Math.round( document.documentElement.scrollHeight ),
          map: g( '.vl-mapband' ),
          stage: g( '.vl-map-stage' ),
          wrap: g( '.vl-wrap' ),
          bodyOverflow: getComputedStyle( document.body ).overflow,
          gate: !document.getElementById( 'vl-keygate' ).hidden,
          font: getComputedStyle( document.body ).fontFamily,
        };
      } );
      console.log( 'GEOMETRY:', JSON.stringify( geo ) );

      const last = await page.evaluate( () => {
        const kids = Array.from( document.body.children );
        return kids[ kids.length - 1 ].tagName.toLowerCase() + '.' + kids[ kids.length - 1 ].className;
      } );
      console.log( 'LAST BODY CHILD (script excluded?):', last );

      const order2 = await page.evaluate( () => {
        const f = document.querySelector( 'footer' );
        const after = [];
        let n = f.nextElementSibling;
        while ( n ) { after.push( n.tagName.toLowerCase() ); n = n.nextElementSibling; }
        return after;
      } );
      console.log( 'ELEMENTS AFTER FOOTER:', JSON.stringify( order2 ) );

      // Google attribution-hiding rules must be absent.
      const sheet = await page.evaluate( () => document.querySelector( 'style' ).textContent );
      console.log( 'gm-style-cc rules:', ( sheet.match( /gm-style/g ) || [] ).length );
      console.log( 'img[alt=Google] rules:', ( sheet.match( /alt="Google"/g ) || [] ).length );
    } else {
      const geo = await page.evaluate( () => {
        const r = document.querySelector( '.vl-map-stage' ).getBoundingClientRect();
        return { vw: window.innerWidth, stageH: Math.round( r.height ), stageW: Math.round( r.width ), doc: Math.round( document.documentElement.scrollHeight ) };
      } );
      console.log( 'MOBILE GEOMETRY:', JSON.stringify( geo ) );
    }
    await page.close();
  }

  await browser.close();
  console.log( '\nDONE' );
} )().catch( e => { console.error( 'FAILED:', e ); process.exit( 1 ); } );
