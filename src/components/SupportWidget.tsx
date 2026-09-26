import React, { useCallback, useEffect, useRef, useState } from 'react';

/**
 * The single floating widget on every page: WhatsApp contact, and page translation.
 *
 * ONE ENDPOINT, ONE RESPONSE SHAPE. There is deliberately no provider probing and no
 * second URL here. This used to call a Cloud Run relay directly, which held the Google
 * API key server-side - the right instinct, since a browser widget can never hold a key -
 * but it billed a Google project with no request cap and was reachable by anything that
 * could set an Origin header. Provider selection now happens inside wecare-site-language,
 * behind the API Gateway throttle and the DynamoDB cache, where the key lives in Secrets
 * Manager. See amplify/functions/core/site-language/handler.py.
 *
 * Practical consequence: do NOT reintroduce a provider flag on the client. If Google
 * fails, the Lambda degrades to Amazon Translate and reports which one it used in
 * `provider` on the response. The widget does not need to care.
 *
 * TEXT TRANSLATION ONLY - READ-ALOUD HAS BEEN REMOVED, and it is not an oversight:
 *  - Amazon Polly has NO voice for Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada,
 *    Malayalam or Punjabi. Its entire Indic coverage is Hindi and Indian English, so the
 *    Listen button was hidden for almost every language this product serves.
 *  - Speaking English over Tamil text is worse than silence: it breaks the pairing
 *    between what is read and what is heard.
 *  - /tts responses were never cached, so every press billed ~2,800 characters. It was
 *    the single largest cost line in this feature - larger than all translation combined.
 *  - Pre-generating audio was considered and rejected: the blog, /my-order and /get are
 *    dynamic, so the audio would either be stale or missing.
 *  - Accessibility is unaffected and arguably better served: VoiceOver, TalkBack and NVDA
 *    already read pages aloud in the user's own language, natively and already installed,
 *    including the Indic languages Polly does not support.
 * Removing it also deleted the /voices fetch (one less request on every page) and the
 * `canSpeak` branch it existed to feed.
 */
const API_BASE = ( process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital' ) + '/site-language';
const LS_LANG = 'wc:stack:lang';
const MAX_BATCH_ITEMS = 30;
const MAX_BATCH_BYTES = 20000;

interface Lang { code: string; name: string; native?: string }

const NATIVE: Record<string, string> = {
  en: 'English', hi: 'हिन्दी', bn: 'বাংলা', ta: 'தமிழ்', te: 'తెలుగు', mr: 'मराठी',
  gu: 'ગુજરાતી', kn: 'ಕನ್ನಡ', ml: 'മലയാളം', pa: 'ਪੰਜਾਬੀ', ur: 'اردو',
};

/**
 * THE CATALOGUE IS TRIMMED ON ARRIVAL, and every entry here has a reason.
 *
 * /languages returns the provider's full list - 76 entries - and it used to go straight
 * into the picker untouched. Two problems with that, one of them a real bug.
 *
 * 'auto' IS NOT A LANGUAGE. The provider includes {"code":"auto","name":"Auto"} as a
 * SOURCE-language sentinel meaning "detect it". As a destination it is meaningless:
 * selecting it sent `targetLanguage: "auto"` to /translate. It was offered to every
 * visitor, in the list, indistinguishable from a real choice.
 *
 * THE FOUR REGION VARIANTS ARE DROPPED because the requirement is one word per row and
 * "Canadian French", "Mexican Spanish", "Portugal Portuguese" and "Chinese Traditional"
 * are not. They are also the only entries in the list that duplicate a language already
 * in it - French, Spanish, Portuguese and Chinese all remain - so for translating a web
 * page nothing is lost; the base language serves the reader either way.
 *
 * That leaves 71 languages, every one a single word. The only remaining multi-word name
 * was "Haitian Creole", renamed rather than dropped - it has no base-language twin, and
 * "Creole" is how it is ordinarily labelled.
 *
 * Verified against the live endpoint, not assumed: mock/lang-search/live-catalogue.json on
 * the mock-device-audit branch is the response these rules were derived from.
 */
const DROP_CODES = new Set( [ 'auto', 'fr-CA', 'zh-TW', 'es-MX', 'pt-PT' ] );
const RENAME: Record<string, string> = { ht: 'Creole' };

/** Rows shown at once. Five is not arbitrary - see the note on searching below. */
const MAX_ROWS = 5;

/**
 * SEARCHING THE CATALOGUE. Three rules, each one measured against the real 71 entries
 * rather than guessed at.
 *
 * 1. MATCH THE CODE AS WELL AS THE NAME. For half the Indian languages the ISO code is not
 *    the first two letters of the English name - bn/Bengali, mr/Marathi, kn/Kannada,
 *    ml/Malayalam, pa/Punjabi. Matching only the name would mean a reader who knows the
 *    code types it and gets nothing; matching only the code would mean the opposite. Both
 *    are matched, so 'bn' and 'be' both find Bengali and it does not matter which one they
 *    reach for.
 *
 * 2. AN EXACT CODE MATCH RANKS FIRST, and this was a real defect caught in the mockup. The
 *    rows are sorted alphabetically, so typing 'ta' listed TAGALOG ABOVE TAMIL - Tagalog
 *    wins on spelling - while 'ta' is Tamil's own ISO code. For an audience in Bharat the
 *    most likely language was sitting second behind one almost nobody here will want. Same
 *    shape for 'ml', where Malayalam was behind Malay and Maltese.
 *
 * 3. THE NATIVE NAME IS MATCHED TOO, so a reader typing in their own script finds their own
 *    language. Costs nothing and is the only route in for someone using an Indic keyboard.
 *
 * WHY FIVE ROWS IS ENOUGH, measured across the whole catalogue: two letters resolve to
 * exactly one language 46 times out of 71, two languages 18 times, three twice, and five
 * times it returns five - the 'ma' cluster of Macedonian, Malay, Malayalam, Maltese,
 * Marathi. It never returns more than five. So five rows is not a truncation that usually
 * works, it is the true worst case, and the panel therefore has a fixed height and never
 * scrolls. The overflow hint below exists for the one- and zero-letter states only.
 */
function searchLanguages ( all: Lang[], query: string ): Lang[] {
  const q = query.trim().toLowerCase();
  if ( !q ) return all;
  const scored: Array<{ lang: Lang; rank: number }> = [];
  for ( const lang of all ) {
    const code = lang.code.toLowerCase();
    const name = lang.name.toLowerCase();
    const native = ( lang.native || '' ).toLowerCase();
    let rank = -1;
    if ( code === q ) rank = 0;
    else if ( name.startsWith( q ) ) rank = 1;
    else if ( native && native.startsWith( q ) ) rank = 2;
    else if ( code.startsWith( q ) ) rank = 3;
    // Substring last, and only for three or more characters: on one or two letters it turns
    // a five-row answer into a twenty-row one and defeats the fixed height.
    else if ( q.length >= 3 && name.includes( q ) ) rank = 4;
    if ( rank >= 0 ) scored.push( { lang, rank } );
  }
  // Stable within a rank, so the alphabetical order of the catalogue survives.
  return scored.sort( ( a, b ) => a.rank - b.rank ).map( row => row.lang );
}

const SKIP_TAGS = new Set( [
  'SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SVG', 'CANVAS', 'VIDEO', 'AUDIO',
  'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'CODE', 'PRE', 'HEAD', 'META', 'LINK',
] );

function collectTextNodes ( root: HTMLElement ): Text[] {
  const nodes: Text[] = [];
  const walker = document.createTreeWalker( root, NodeFilter.SHOW_TEXT, {
    acceptNode ( node: Node ) {
      const value = node.nodeValue?.trim() || '';
      if ( value.length < 2 || !/[A-Za-z\u0900-\u0DFF\u0600-\u06FF]/.test( value ) ) return NodeFilter.FILTER_REJECT;
      let el = node.parentElement;
      while ( el ) {
        // data-wc-no-translate is what keeps the dashboard safe. Layout.tsx puts it on
        // .main-content, and this walk rejects a node if ANY ancestor up to the root
        // carries it - so customer names, numbers and message bodies are exempt while the
        // sidebar around them still translates.
        if ( SKIP_TAGS.has( el.tagName ) || el.dataset.wcNoTranslate === 'true' || el.getAttribute( 'aria-hidden' ) === 'true' ) return NodeFilter.FILTER_REJECT;
        if ( el === root ) break;
        el = el.parentElement;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  } );
  let node = walker.nextNode();
  while ( node ) { nodes.push( node as Text ); node = walker.nextNode(); }
  return nodes;
}

function buildBatches ( nodes: Text[] ): Array<Array<{ node: Text; text: string }>> {
  const batches: Array<Array<{ node: Text; text: string }>> = [];
  let current: Array<{ node: Text; text: string }> = [];
  let bytes = 0;
  for ( const node of nodes ) {
    const text = node.nodeValue?.trim() || '';
    const size = new Blob( [ text ] ).size;
    if ( !text || size > MAX_BATCH_BYTES ) continue;
    if ( current.length >= MAX_BATCH_ITEMS || bytes + size > MAX_BATCH_BYTES ) {
      if ( current.length ) batches.push( current );
      current = [];
      bytes = 0;
    }
    current.push( { node, text } );
    bytes += size;
  }
  if ( current.length ) batches.push( current );
  return batches;
}

/** Below this width the pill goes slim and parks above the footer. Matches the CSS. */
const MOBILE_MAX = 767;
/** Clear air left between the parked pill and the footer's top edge. */
const PARK_GAP = 16;
/** The pill may never park closer than this to the fixed header's bottom edge. */
const HEADER_GAP = 12;
/** Space between the pill and the panel above it. Matches the flex gap on .wc-langbar. */
const PANEL_GAP = 10;

const SupportWidget: React.FC = () => {
  const [ langs, setLangs ] = useState<Lang[]>( [] );
  const [ current, setCurrent ] = useState( 'en' );
  const [ busy, setBusy ] = useState( false );
  const [ status, setStatus ] = useState( '' );
  const [ appShell, setAppShell ] = useState( false );
  const [ parkedBottom, setParkedBottom ] = useState<number | null>( null );
  const [ open, setOpen ] = useState( false );
  const [ query, setQuery ] = useState( '' );
  const [ active, setActive ] = useState( 0 );
  const [ panelMax, setPanelMax ] = useState<number | null>( null );
  const barRef = useRef<HTMLDivElement | null>( null );
  const chipRef = useRef<HTMLButtonElement | null>( null );
  const inputRef = useRef<HTMLInputElement | null>( null );
  const listRef = useRef<HTMLDivElement | null>( null );
  const originals = useRef<Map<Text, string> | null>( null );
  const applyLanguageRef = useRef<( ( code: string, label?: string ) => Promise<void> ) | null>( null );

  /**
   * WHAT GETS TRANSLATED, AND THE ONE RULE THAT MAKES IT SAFE ON THE DASHBOARD.
   *
   * `.layout` is checked FIRST, and it only exists on the authenticated dashboard. Picking
   * it means the walk starts above the sidebar, so navigation labels translate - which is
   * the point for an operator who reads Hindi or Tamil.
   *
   * It is safe only because Layout.tsx marks `.main-content` with data-wc-no-translate.
   * Machine-translating live operational data would corrupt what an operator is reading
   * and could not be distinguished from real data afterwards.
   *
   * Public pages have no `.layout`, so they fall through to `.page` / `main` and translate
   * in full.
   */
  const contentRoot = useCallback( (): HTMLElement => (
    document.querySelector( '.layout' ) as HTMLElement
      || document.querySelector( '.page' ) as HTMLElement
      || document.querySelector( 'main' ) as HTMLElement
      || document.getElementById( '__next' ) as HTMLElement
      || document.body
  ), [] );

  const restore = useCallback( () => {
    if ( !originals.current ) return;
    for ( const [ node, value ] of originals.current ) {
      if ( node.parentNode ) node.nodeValue = value;
    }
  }, [] );

  useEffect( () => {
    let cancelled = false;
    ( async () => {
      try {
        const response = await fetch( `${API_BASE}/languages` );
        if ( !response.ok ) return;
        const rows: Array<{ code: string; name: string }> = ( await response.json() ).languages || [];
        const normalized = rows.filter( row => !DROP_CODES.has( row.code ) ).map( row => {
          const base = row.code.toLowerCase().split( '-' )[ 0 ];
          return { code: row.code, name: RENAME[ row.code ] || row.name, native: NATIVE[ base ] };
        } ).sort( ( a, b ) => {
          if ( a.code === 'en' ) return -1;
          if ( b.code === 'en' ) return 1;
          return a.name.localeCompare( b.name );
        } );
        if ( cancelled ) return;
        setLangs( normalized );

        // The saved-language restore lives here, in the flow that just produced the
        // catalogue, rather than in a second effect watching `langs`. That second effect
        // was a react-hooks/set-state-in-effect error: it called applyLanguage in an
        // effect body, which cascades a render, and it could not declare applyLanguage as
        // a dependency because that identity changes the moment `busy` flips - so listing
        // it honestly would have re-fired the restore mid-translation.
        let saved = '';
        try { saved = localStorage.getItem( LS_LANG ) || ''; } catch { /* ignore */ }
        if ( !saved || saved === 'en' ) return;
        const savedLang = normalized.find( lang => lang.code === saved );
        if ( !savedLang ) return;
        // The label is passed in because this ref was captured on mount, when `langs` was
        // still empty - applyLanguage's own lookup would miss and the status line would
        // read the raw code instead of the language name.
        await applyLanguageRef.current?.( saved, savedLang.name );
      } catch { /* stay quiet if language services are unavailable */ }
    } )();
    return () => { cancelled = true; };
  }, [] );

  const applyLanguage = useCallback( async ( code: string, labelOverride?: string ) => {
    if ( busy ) return;
    setCurrent( code );
    try { localStorage.setItem( LS_LANG, code ); } catch { /* ignore */ }

    if ( code === 'en' ) {
      restore();
      document.documentElement.lang = 'en';
      setStatus( 'Showing the original English text.' );
      return;
    }

    const root = contentRoot();
    const nodes = collectTextNodes( root );
    if ( !originals.current ) originals.current = new Map( nodes.map( node => [ node, node.nodeValue || '' ] ) );
    restore();
    setBusy( true );
    const label = labelOverride || langs.find( lang => lang.code === code )?.name || code;
    setStatus( `Translating to ${label}.` );

    try {
      for ( const batch of buildBatches( nodes ) ) {
        const response = await fetch( `${API_BASE}/translate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify( { texts: batch.map( item => item.text ), targetLanguage: code, sourceLanguage: 'en' } ),
        } );
        if ( !response.ok ) throw new Error( 'translate failed' );
        const payload = await response.json();
        const translated: Array<{ translatedText?: string }> = payload?.translations || [];
        if ( translated.length !== batch.length ) throw new Error( 'translation shape mismatch' );
        translated.forEach( ( row, index ) => { if ( row.translatedText && batch[ index ].node.parentNode ) batch[ index ].node.nodeValue = row.translatedText; } );
      }
      document.documentElement.lang = code;
      setStatus( `Page translated to ${label}.` );
    } catch {
      restore();
      setCurrent( 'en' );
      setStatus( 'Translation is unavailable right now.' );
    } finally { setBusy( false ); }
  }, [ busy, contentRoot, langs, restore ] );

  // Keeps the restore above pointed at the current applyLanguage. Assigned in an effect
  // rather than during render: a ref written mid-render is its own hooks violation, and
  // this only has to be current by the time the catalogue fetch resolves.
  useEffect( () => { applyLanguageRef.current = applyLanguage; }, [ applyLanguage ] );

  /**
   * OPENING AND CLOSING THE SEARCH PANEL.
   *
   * THIS IS THE COST OF LEAVING THE NATIVE CONTROL, and it is worth naming rather than
   * burying. A <select> gave us keyboard navigation, screen-reader announcement, an
   * outside-click that could not go wrong and the OS picker on a phone - all of it free and
   * all of it correct. A custom box means owning every part of that: arrow keys, Enter,
   * Escape, aria-expanded, aria-activedescendant, focus into the input on open, focus back
   * to the chip on close, and a document listener that does not fight the pill's own clicks.
   * Everything below is that bill being paid. If a future change is tempted to simplify it,
   * the thing that breaks first is the keyboard, and nobody notices a broken keyboard by
   * looking at a screenshot.
   */
  const closePanel = useCallback( ( returnFocus: boolean ) => {
    setOpen( false );
    setQuery( '' );
    setActive( 0 );
    // Focus goes back to the chip, not to the body. Dropping focus to the body would send a
    // keyboard user back to the top of the document, which is a page-length punishment for
    // pressing Escape.
    if ( returnFocus ) chipRef.current?.focus();
  }, [] );

  useEffect( () => {
    if ( !open ) return;
    // The input is focused in an effect rather than with autoFocus: autoFocus on a
    // conditionally rendered element is inconsistent across browsers, and on iOS it can
    // raise the keyboard before the panel has finished positioning.
    inputRef.current?.focus();

    const onPointerDown = ( event: MouseEvent | TouchEvent ) => {
      const bar = barRef.current;
      if ( bar && event.target instanceof Node && !bar.contains( event.target ) ) closePanel( false );
    };
    // Capture phase, so a click on a page element that stops propagation still closes the
    // panel. Without it the panel can be left open behind an overlay that swallowed the event.
    document.addEventListener( 'mousedown', onPointerDown, true );
    document.addEventListener( 'touchstart', onPointerDown, true );
    return () => {
      document.removeEventListener( 'mousedown', onPointerDown, true );
      document.removeEventListener( 'touchstart', onPointerDown, true );
    };
  }, [ open, closePanel ] );

  /**
   * THE PILL PARKS ABOVE THE FOOTER INSTEAD OF SLIDING OVER IT.
   *
   * The problem, measured at the end of the home page on every phone size: the pill landed
   * INSIDE the footer at all seven of them, covering the brand lockup or the tagline. A
   * fixed element and a footer both want the bottom of the screen, and the footer is the
   * one that has content in it.
   *
   * WHY NOT JUST HIDE IT THERE. That was the obvious alternative and it is the wrong one:
   * somebody who has read to the end of the page is the most likely person in the session
   * to want to talk to us, and hiding the contact button at that exact moment is the
   * opposite of what it is for. So it moves instead of disappearing - it stops descending
   * when the footer's top edge arrives and rides up with it.
   *
   * WHY THE FOOTER IS MEASURED RATHER THAN ASSUMED. A hardcoded offset would have been
   * right on six phones and wrong on the narrowest: at 280px the footer is 216px tall, not
   * 192, because the tagline wraps onto an extra line. Reading the live rectangle also means
   * a future change to the footer's own height needs no edit here.
   *
   * THE CEILING IS NOT DECORATION. A short viewport with a tall footer - a landscape phone,
   * or a footer that grows - would push a naively parked pill up behind the fixed header,
   * turning one collision into another. No current device triggers it (on a 320x568 screen
   * the parked pill sits at y316 and the header ends at y96), which is exactly why it has to
   * be written down rather than discovered later.
   *
   * MOBILE ONLY. Above 767px the footer is 179px tall and the pill clears it at its resting
   * 20px now that the lime dash has moved out of that corner, so there is nothing to solve
   * and no listener worth paying for.
   */
  useEffect( () => {
    // The dashboard is the one surface with a real BottomNav to clear, and the one with no
    // footer to park above. Detected once - a page does not change shell without remounting.
    setAppShell( !!document.querySelector( '.layout' ) );

    let frame = 0;
    const compute = () => {
      frame = 0;
      const bar = barRef.current;
      if ( !bar ) return;
      if ( window.innerWidth > MOBILE_MAX ) { setParkedBottom( null ); return; }

      const footer = document.querySelector( 'footer.ft-footer' );
      if ( !footer ) { setParkedBottom( null ); return; }

      const viewportHeight = window.innerHeight;
      // How far the footer reaches up into the viewport. Negative while it is still below.
      const intrusion = viewportHeight - footer.getBoundingClientRect().top;
      const wanted = intrusion + PARK_GAP;
      if ( wanted <= 0 ) { setParkedBottom( null ); return; }

      const header = document.querySelector( 'header.hdr' );
      const headerBottom = header ? header.getBoundingClientRect().bottom : 0;
      const pillHeight = bar.getBoundingClientRect().height || 44;
      const ceiling = viewportHeight - ( headerBottom + HEADER_GAP ) - pillHeight;
      setParkedBottom( Math.min( wanted, Math.max( ceiling, 0 ) ) );
    };

    /**
     * HOW TALL THE PANEL IS ALLOWED TO BE.
     *
     * The panel opens UPWARD, because the pill is at the bottom of the screen. That is fine
     * until the two constraints meet: on a 320x568 phone, with the pill parked 208px up to
     * clear the footer, the space left above it is about 194px - and five rows plus the
     * search field is about 230px. The panel would have opened straight through the fixed
     * header.
     *
     * No current desktop or tablet width comes close, which is exactly why this is computed
     * rather than assumed. Measuring the PILL rather than the bar is deliberate: the bar
     * contains the panel, so measuring the bar while the panel is open would be circular.
     *
     * When the cap bites, .wc-rows scrolls and the panel shows four rows instead of five.
     * That is the graceful end of it. The alternative considered and rejected was to unpark
     * the pill while the panel is open, which would have dropped it ~190px the instant a
     * phone user tapped the chip - a jump, to solve a problem only the smallest screens have.
     */
    const measurePanel = () => {
      const bar = barRef.current;
      const pill = bar?.querySelector( '.wc-pill' );
      if ( !pill ) return;
      const header = document.querySelector( 'header.hdr' );
      const headerBottom = header ? header.getBoundingClientRect().bottom : 0;
      const room = pill.getBoundingClientRect().top - headerBottom - HEADER_GAP - PANEL_GAP;
      setPanelMax( Math.max( Math.round( room ), 132 ) );
    };

    // Coalesced to one computation per frame. A scroll listener that writes state on every
    // event would set state dozens of times per frame on a trackpad or a momentum flick.
    const onScroll = () => { if ( !frame ) frame = requestAnimationFrame( () => { compute(); measurePanel(); } ); };

    compute();
    measurePanel();
    window.addEventListener( 'scroll', onScroll, { passive: true } );
    window.addEventListener( 'resize', onScroll );
    return () => {
      if ( frame ) cancelAnimationFrame( frame );
      window.removeEventListener( 'scroll', onScroll );
      window.removeEventListener( 'resize', onScroll );
    };
  }, [] );

  /**
   * The widget ALWAYS renders. Two early returns used to sit here and both were bugs:
   *  - `pathname === '/'` hid translation from the home page, the most visited route
   *  - `langs.length < 2` returned null when the catalogue failed to load, which would now
   *    take the WhatsApp button down with the translation API
   * The catalogue failing hides the language chip alone.
   */
  const canTranslate = langs.length >= 2;
  const hits = searchLanguages( langs, query );
  // Uppercased base code - "EN", "HI", "TA". Short enough to sit in the pill without the
  // chip changing width between languages, which a full name would do on every switch.
  const chipLabel = ( current.split( '-' )[ 0 ] || 'en' ).toUpperCase();

  return (
    <div
      ref={ barRef }
      data-wc-no-translate="true"
      className={ `wc-langbar ${appShell ? 'is-appshell' : ''}`.trim() }
      /* The parked offset has to be inline: it is a measured pixel value that changes on
         every scroll frame, so there is no stylesheet form of it. null leaves the CSS
         resting value in charge, which is what keeps desktop and the un-scrolled state
         entirely declarative. */
      style={ parkedBottom === null ? undefined : { bottom: `${parkedBottom}px` } }
    >
      <style jsx>{`
        /* WE OWN THE STACKING CONTEXT. The WhatsApp button used to be injected by an
           external script at z-index 2147483647 - the maximum 32-bit integer - which
           nothing could be stacked above, so this component had to derive its geometry
           from that button's and shove its panel sideways to avoid being punched through.
           That script is retired and the button is the left half of the pill below, so
           z-index only has to clear the mobile BottomNav (1200) and the header menu
           (1002). 1300 does both. */
        .wc-langbar{position:fixed;right:20px;left:auto;bottom:20px;top:auto;z-index:1300;display:flex;flex-direction:column;align-items:flex-end;gap:10px;font-family:inherit}

        /* THE PILL. One container, two actions, reading as a single object rather than the
           two unrelated circles this replaced. 4px of padding around 40px controls makes
           it 48px tall.
           position:relative so the progress sweep below can pin to its bottom edge, and
           overflow:hidden so that sweep is clipped to the pill's rounded shape. */
        .wc-pill{position:relative;overflow:hidden;display:inline-flex;align-items:center;gap:2px;padding:4px;background:#fff;border:1.5px solid #d1f470;border-radius:9999px;box-shadow:0 6px 22px rgba(16,32,24,.14)}
        /* Full-strength lime with #1a3a2a type: the palette's own-surface pairing, correct
           here because contacting us is the primary action. Deliberately NOT WhatsApp
           green - that is their brand, not ours, and it was the one off-palette colour on
           every public page. */
        /* min-width/min-height ARE LOAD-BEARING, not belt-and-braces. Two global rules
           fight over every <a> on this site and the widget loses the fight silently:
           tokens.css raises min-width AND min-height to 44px below 768px (a fair
           touch-target floor), then Layout.css:94 resets min-height to 32px for the same
           selector list with no media query - later in the cascade, same specificity, so
           it wins - and never touches min-width. The floor thus applied to width only,
           and this 40px circle rendered as a 44x40 OVAL on every phone, because
           border-radius:50% follows the box. Pinning both axes here (two classes, so it
           outranks the bare element selector) is what keeps it round. uicheck.js asserts
           width === height at 4 widths so it cannot come back.
           NOTE for future edits in this block: no backticks in these comments. This file
           is a template literal, so a backtick ends the CSS early and the build fails with
           "Expected '</', got 'ident'" pointing at the comment rather than the cause. */
        .wc-wa{width:40px;height:40px;min-width:40px;min-height:40px;border-radius:50%;background:#d1f470;color:#1a3a2a;display:grid;place-items:center;text-decoration:none;transition:background-color .2s}
        .wc-wa:hover{background:#c5e866}
        .wc-wa:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:2px}
        .wc-wa svg{width:21px;height:21px;display:block}
        .wc-sep{width:1px;height:22px;background:#eef0e6;flex:0 0 auto}

        /* THE CHIP IS A BUTTON THAT OPENS THE SEARCH PANEL.
           It was a transparent <select> stretched over the chip, which bought keyboard
           navigation, screen-reader announcement and the phone's OS picker for nothing. That
           is a real loss and it was traded deliberately: the picker showed the provider's
           raw 76-entry list, two-thirds of it irrelevant, with no way to search on desktop.
           What replaces it is in .wc-panel below, and the keyboard and ARIA work the select
           used to do for free is in the component.

           NO HOVER TINT. The chip used to fill with rgba(209,244,112,.38) on hover. It is
           removed on instruction, and it is the right call for a reason worth recording: the
           same tint marks the ACTIVE ROW inside the panel, so using it on the trigger as well
           meant one colour saying two different things a few pixels apart. The chip now
           signals only real state - focus, and busy. */
        .wc-chip{position:relative;display:inline-flex;align-items:center;height:40px;min-width:52px;justify-content:center;padding:0 9px 0 11px;border:0;border-radius:9999px;background:transparent;color:#1a3a2a;font-family:inherit;font-size:14px;font-weight:700;letter-spacing:.02em;cursor:pointer;transition:background-color .2s}
        .wc-chip[aria-disabled='true']{cursor:progress}
        /* FOCUS IS A RING, NEVER A FILL, and that is a cross-browser correctness fix rather
           than a preference.
           This rule used to add background:rgba(209,244,112,.38) as well. On Windows Chrome
           the chip kept that pale lime fill indefinitely after a language was chosen with
           the mouse - reported from a photograph of a real screen, with the pointer nowhere
           near the widget - so the control looked permanently switched on. Headless Chromium
           did not reproduce it: there, :focus-visible correctly did not match.
           The cause is a documented difference in how browsers resolve :focus-visible for
           PROGRAMMATIC focus. Choosing a language calls chip.focus() so a keyboard user is
           not stranded, and at that moment the previously focused element is the search
           input - and a text input always matches :focus-visible. Chrome carries that
           modality across the programmatic focus, so the chip matched too.
           Two changes make it robust rather than dependent on that resolution: the fill is
           gone, so the worst case is a legible focus ring instead of a state that reads as
           "selected", and focus is only returned when the panel was closed by keyboard. */
        .wc-chip:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:2px}
        .wc-arw{width:6px;height:6px;box-sizing:border-box;border-right:2px solid #1a3a2a;border-bottom:2px solid #1a3a2a;transform:translateY(-2px) rotate(45deg);margin-left:7px;opacity:.7;transition:transform .2s}
        .wc-chip[aria-expanded='true'] .wc-arw{transform:translateY(1px) rotate(225deg)}

        /* ===== THE SEARCH PANEL =====
           210px, and the width is the point: it is narrow enough to sit inside a 280px folded
           phone with the pill's own 16px inset and still leave room, and it never has to grow
           because every row is a single word.
           The 3px lime top edge is the same device the header dropdown and the sign-in card
           use, so a floating surface reads as ours without a lime outline on all four sides -
           which the contract reserves for interactive state and which made inputs look
           permanently focused when it was tried. */
        /* order:-1 puts the panel ABOVE the pill visually while leaving it after the pill in
           the DOM. Both halves matter: the pill sits at the bottom of the screen so the panel
           has nowhere to go but up, and DOM order is what decides tab order and the order a
           screen reader reads - the trigger should come before the thing it opens. */
        .wc-panel{order:-1;display:flex;flex-direction:column;width:210px;background:#fcfdfa;border:1px solid #e8ecdf;border-top:3px solid #d1f470;border-radius:14px;box-shadow:0 14px 40px rgba(16,32,24,.18);overflow:hidden}

        .wc-search{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid #f1f3ec;background:#fff;transition:border-color .2s}
        /* The focus signal lives on the ROW, not on the input. Deliberate: the input is
           focused for the entire time the panel exists, so a ring around it conveys no
           information and just sits there - which is the "reads as permanently focused"
           defect this palette has already been burned by once. One lime hairline under the
           field says where the typing goes, and nothing shouts. */
        .wc-search:focus-within{border-bottom-color:#d1f470}
        .wc-search svg{width:15px;height:15px;flex:0 0 auto;fill:none;stroke:#1a3a2a;stroke-width:2.2;stroke-linecap:round;opacity:.45}

        /* THIS RULE IS MOSTLY UNDOING OTHER RULES, and each reset is here because the global
           stylesheet was measurably reaching into the panel:
             box-shadow  tokens.css gives every focused input a 3px lime glow. With the input
                         permanently focused that drew a heavy lime rounded box around the
                         search field - the single most visible thing in the panel, and not
                         designed.
             min-height  tokens.css sets 44px on every input. It made the field 44px, the
                         search row 65px and the whole panel 302px instead of ~230.
             radius      var(--radius-md) rounded the field inside an already-rounded panel.
           None of these needed !important to beat - the styled-jsx class pair simply has to
           name the property. Anything NOT named here silently keeps the global value, which
           is exactly how all three arrived.
           font-size:16px stays for iOS Safari, which zooms the viewport when a focused form
           control is under 16px and does not zoom back out on blur. Layout.css happens to
           force 16px on every input anyway, but this must not depend on that. */
        .wc-search input{width:100%;min-width:0;min-height:0;height:auto;border:0;border-radius:0;outline:0;box-shadow:none;padding:0;margin:0;background:transparent;font-family:inherit;font-size:16px;font-weight:600;color:#1a3a2a}
        .wc-search input:focus{border:0;box-shadow:none;outline:0}
        .wc-search input::placeholder{color:rgba(0,0,0,.36);font-weight:400}

        /* FIXED HEIGHT, NO SCROLLING. Five rows is the measured worst case for a two-letter
           query across the whole catalogue - the 'ma' cluster of Macedonian, Malay,
           Malayalam, Maltese, Marathi - so the panel never scrolls and never changes height
           once two characters are in. overflow is hidden rather than auto for that reason: an
           auto scroller here would be dead weight that occasionally flickers a scrollbar. */
        /* min-height:0 is load-bearing in a flex column: without it a flex item refuses to
           shrink below its content size, so max-height on the panel would be ignored and the
           rows would push straight through the header on a short screen. */
        .wc-rows{overflow-y:auto;min-height:0;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:rgba(26,58,42,.15) transparent}
        /* min-height is DECLARED, not inherited. Measured at 46px before this line, which
           came from a global min-height rule on every button in the shared stylesheet - the
           row happened to clear the touch-target floor by luck. Accidentally correct is how
           the WhatsApp circle ended up a 44x40 oval, so the floor is stated here: 44px,
           which also makes the panel's height predictable at 5 rows plus the search field. */
        .wc-row{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;min-height:44px;padding:9px 13px;border:0;border-radius:0;background:transparent;font-family:inherit;font-size:13.5px;font-weight:600;color:#1a3a2a;text-align:left;cursor:pointer;transition:background-color .12s}
        /* is-active is the keyboard/pointer highlight; is-on is the language currently
           showing. Solid lime for the current one, tint for the highlight - the same pairing
           as the header menu, where active==hover was itself a defect that had to be fixed. */
        .wc-row.is-active{background:rgba(209,244,112,.38)}
        .wc-row.is-on{background:#d1f470}
        .wc-row:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:-3px}
        .wc-row-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .wc-row-code{flex:0 0 auto;font-size:10px;font-weight:700;letter-spacing:.05em;color:rgba(0,0,0,.34)}
        .wc-row.is-on .wc-row-code{color:rgba(26,58,42,.55)}

        .wc-empty,.wc-more{margin:0;padding:10px 13px;font-size:11px;font-weight:500;color:rgba(0,0,0,.45);background:#fcfdfa}
        .wc-more{border-top:1px solid #f1f3ec}

        /* ===== TRANSLATING =====
           NO DARK INVERSION. The chip used to flip to a #1a3a2a fill while working, which
           put the single darkest object on the page in the corner of every translation and
           read as an error state rather than as progress. The busy signal is now entirely
           lime and stays on the light surface:
             1. a lime ring pulses around the chip
             2. a lime line sweeps left-to-right along the bottom edge of the whole pill
           Both are transform/opacity only, so neither causes layout on any frame. */
        .wc-chip.is-busy{background:rgba(209,244,112,.38);cursor:progress;animation:wc-ring 1.5s ease-in-out infinite}
        @keyframes wc-ring{
          0%,100%{box-shadow:0 0 0 0 rgba(209,244,112,.9)}
          50%{box-shadow:0 0 0 5px rgba(209,244,112,0)}
        }
        /* The sweep. scaleX on a pinned 2px bar - compositor-only, and clipped by the
           pill's overflow:hidden so it follows the rounded shape. It is the honest signal
           that batches are still in flight: translation is a sequence of network round
           trips over every text node, so it can take a couple of seconds on a long page. */
        .wc-sweep{position:absolute;left:0;right:0;bottom:0;height:2px;background:#d1f470;transform-origin:left center;animation:wc-sweep 1.1s cubic-bezier(.4,0,.2,1) infinite}
        @keyframes wc-sweep{
          0%{transform:scaleX(0);opacity:1}
          60%{transform:scaleX(1);opacity:1}
          100%{transform:scaleX(1);opacity:0}
        }

        .wc-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}

        /* ===== MOBILE =====
           TWO THINGS CHANGE BELOW 768px, AND THE OLD NOTE HERE WAS WRONG ON BOTH.
           It read: "the pill keeps its size - shrinking a support control on the device most
           likely to need it is the wrong trade... What changes is the bottom offset: the
           phone BottomNav is 60px plus the safe-area inset, so the pill sits above it."

           1. THE SIZE. 108px is 27% of a 390px screen, 33.7% of a 320px one and 38.6% of a
              folded 280px one - a quarter to well over a third of the width, permanently, for
              a control most visitors never touch. The chevron is what goes: it earns its
              place on desktop, where a pointer needs the hint that the chip opens something,
              but a tap on a phone opens the OS language picker whether or not an arrow is
              drawn. With it gone and the chip tightened the pill is ~90px, about 18px back.
              THE CONTROLS STAY 40px. The mockup for this shrank them to 36px, which would
              have taken the tap target below the 44px floor on the device where that matters
              most - and 40px is already a compromise held in place by the roundness fix
              above. Width was the complaint; width is what is spent.

           2. THE BOTTOM OFFSET WAS CLEARING A BAR THAT IS NOT THERE. 72px existed for the
              dashboard BottomNav, and BottomNav is rendered by Layout.tsx, which no public
              page uses. Checked at fourteen widths: absent at every one. So every public
              phone page floated the pill 72px above empty space while desktop sat at 20px.
              Public pages now match desktop at 20px; .is-appshell keeps the 72px for the
              dashboard, where the bar is real. */
        @media(max-width:767px){
          .wc-langbar{right:16px;left:auto;top:auto;bottom:calc(20px + env(safe-area-inset-bottom))}
          .wc-langbar.is-appshell{bottom:calc(72px + env(safe-area-inset-bottom))}
          .wc-pill{padding:3px;gap:0}
          /* The label alone, no arrow. min-width drops with it - "EN" at 13px needs about
             35px including padding, so 40px is the floor that keeps every language code the
             same width without reserving room for a glyph that is no longer drawn. */
          .wc-chip{min-width:40px;padding:0 8px;font-size:13px}
          .wc-arw{display:none}
          .wc-sep{height:20px}
        }
        @media print{.wc-langbar{display:none}}
        /* The sweep and the ring keep moving under reduced motion, slowed rather than
           stopped: they are the only indication that work is in flight, and freezing them
           would misreport a live translation as a stalled one. */
        @media(prefers-reduced-motion:reduce){
          .wc-chip.is-busy{animation-duration:3s}
          .wc-sweep{animation-duration:2.6s}
        }
      `}</style>

      <div className="wc-pill">
        {/* A real anchor, not a button with an onClick: this leaves the site, so it must be
            middle-clickable, long-pressable and copyable like any other link. The href is
            the retired external widget's own destination, read out of wecare-wa-widget.js
            rather than guessed, so retiring that script did not move where people land. */}
        <a
          className="wc-wa"
          href="https://wa.me/message/APDM5HUWH26SG1"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Chat with us on WhatsApp"
          title="Chat with us on WhatsApp"
        >
          {/* Official WhatsApp glyph, inlined. Inlined rather than loaded from the asset
              host because a remote SVG carries its own hardcoded fill, which CSS cannot
              reach - so it could not follow currentColor - and it adds a request that can
              leave the button empty while in flight. */}
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path fill="currentColor" d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.26-.46-2.4-1.48-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.91-2.21-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.03 1.02-1.03 2.48 0 1.46 1.06 2.87 1.21 3.07.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.62.71.23 1.36.2 1.87.12.57-.09 1.76-.72 2-1.41.25-.7.25-1.29.18-1.42-.08-.12-.28-.2-.57-.35M12.05 21.79h-.01a9.87 9.87 0 01-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 01-1.51-5.26C2.16 6.45 6.6 2.01 12.05 2.01c2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 012.89 6.99c0 5.45-4.44 9.89-9.88 9.89M20.46 3.49A11.82 11.82 0 0012.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.88 11.88 0 005.69 1.45c6.55 0 11.89-5.34 11.89-11.89 0-3.18-1.24-6.17-3.48-8.42z" />
          </svg>
        </a>

        { canTranslate && <span className="wc-sep" aria-hidden="true" /> }

        {/* THE CHIP USES aria-disabled, NOT disabled, and that was a real bug caught by
            driving the keyboard rather than looking at it. The disabled attribute was
            correct-looking and wrong: choosing a language sets busy, React re-renders, the
            chip becomes disabled - and a disabled element CANNOT HOLD FOCUS, so the browser
            drops focus to the body. A keyboard user who picked a language was thrown back to
            the top of the document, every time, silently. Escape kept focus correctly and
            Enter did not, which is exactly how it surfaced.
            aria-disabled announces the same state to a screen reader while leaving the
            element focusable; the click handler does the actual refusing.

            Note for future edits: this comment lives HERE, outside the parentheses, because
            a JSX comment placed inside `cond && ( ... )` is a second expression where only
            one is allowed, and Turbopack reports it as a parse error on the line after it. */}
        { canTranslate && (
          <button
            ref={ chipRef }
            type="button"
            className={ `wc-chip ${busy ? 'is-busy' : ''}`.trim() }
            aria-disabled={ busy }
            aria-expanded={ open }
            aria-haspopup="listbox"
            aria-controls="wc-lang-panel"
            aria-label={ `Language: ${langs.find( lang => lang.code === current )?.name || 'English'}. Choose another.` }
            onClick={ () => {
              // The refusal that `disabled` used to do for us, minus the focus loss.
              if ( busy ) return;
              if ( open ) closePanel( true );
              else { setQuery( '' ); setActive( 0 ); setOpen( true ); }
            } }
          >
            { chipLabel }
            <span className="wc-arw" aria-hidden="true" />
          </button>
        ) }

        { busy && <span className="wc-sweep" aria-hidden="true" /> }
      </div>

      { canTranslate && open && (
        <div
          className="wc-panel"
          id="wc-lang-panel"
          style={ panelMax === null ? undefined : { maxHeight: `${panelMax}px` } }
        >
          {/* The search row. A real <input>, so the platform still supplies text selection,
              dictation, paste and a mobile keyboard - the parts of the native control that
              were never worth reimplementing.
              The keyboard handler lives here rather than on the list because focus stays in
              the input the whole time: arrows move the highlight, they do not move focus.
              That is what aria-activedescendant is for, and it is why a screen reader can
              announce the highlighted row while the user is still typing. */}
          <div className="wc-search">
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-4.2-4.2" />
            </svg>
            <input
              ref={ inputRef }
              type="text"
              role="combobox"
              aria-expanded="true"
              aria-controls="wc-lang-list"
              aria-autocomplete="list"
              aria-activedescendant={ hits.length ? `wc-lang-${hits[ Math.min( active, hits.length - 1 ) ].code}` : undefined }
              aria-label="Search language"
              placeholder="Search language"
              value={ query }
              autoComplete="off"
              spellCheck={ false }
              onChange={ event => { setQuery( event.target.value ); setActive( 0 ); } }
              onKeyDown={ event => {
                if ( event.key === 'ArrowDown' || event.key === 'ArrowUp' ) {
                  // preventDefault so the caret does not jump to either end of the input,
                  // which is what the browser does with an arrow key in a text field.
                  event.preventDefault();
                  const shown = Math.min( hits.length, MAX_ROWS );
                  if ( !shown ) return;
                  setActive( prev => ( event.key === 'ArrowDown'
                    ? ( prev + 1 ) % shown
                    : ( prev - 1 + shown ) % shown ) );
                } else if ( event.key === 'Enter' ) {
                  event.preventDefault();
                  const pick = hits[ Math.min( active, hits.length - 1 ) ];
                  if ( pick ) { closePanel( true ); void applyLanguage( pick.code ); }
                } else if ( event.key === 'Escape' ) {
                  event.preventDefault();
                  closePanel( true );
                } else if ( event.key === 'Tab' ) {
                  // Tab closes rather than trapping. A three-element popover does not need a
                  // focus trap, and trapping would strand a keyboard user who opened it by
                  // accident.
                  closePanel( false );
                }
              } }
            />
          </div>

          <div className="wc-rows" id="wc-lang-list" role="listbox" aria-label="Languages" ref={ listRef }>
            { hits.slice( 0, MAX_ROWS ).map( ( lang, index ) => (
              <button
                key={ lang.code }
                id={ `wc-lang-${lang.code}` }
                type="button"
                role="option"
                aria-selected={ lang.code === current }
                className={ `wc-row ${lang.code === current ? 'is-on' : ''} ${index === Math.min( active, hits.length - 1 ) ? 'is-active' : ''}`.trim() }
                // onMouseDown, not onClick: the document mousedown listener that closes the
                // panel fires first in the capture phase, and onClick would then land on an
                // element that had already been unmounted.
                //
                // closePanel( false ) - focus is NOT returned to the chip on a pointer pick.
                // Returning it is right for the keyboard (Enter and Escape both do) but wrong
                // here: the programmatic focus inherited :focus-visible from the search input
                // on Windows Chrome, which left the chip looking permanently selected after a
                // mouse click. A pointer user has nothing to return focus to, so this drops it
                // and the chip renders in its resting state, which is what it is.
                onMouseDown={ event => { event.preventDefault(); closePanel( false ); void applyLanguage( lang.code ); } }
                onMouseEnter={ () => setActive( index ) }
              >
                {/* ONE WORD PER ROW. The native name where we have it, the English name
                    otherwise - both are single words, and a reader looking for their own
                    language scans for its own script, not for a Latin transliteration of it.
                    The code on the right is the second way in: search matches it too, so
                    somebody who knows 'bn' and somebody who knows 'Bengali' both arrive. */}
                <span className="wc-row-name">{ lang.native && lang.native !== lang.name ? lang.native : lang.name }</span>
                <span className="wc-row-code">{ lang.code.toUpperCase() }</span>
              </button>
            ) ) }
            { !hits.length && <p className="wc-empty">No language matches that.</p> }
          </div>

          {/* Only reachable on a one-letter or empty query: two letters never return more
              than five. Worth keeping for exactly that reason - the panel should say how
              much it is not showing rather than imply the list is complete. */}
          { hits.length > MAX_ROWS && (
            <p className="wc-more">{ hits.length - MAX_ROWS } more — keep typing</p>
          ) }
        </div>
      ) }

      <div className="wc-sr" role="status" aria-live="polite">{ status }</div>
    </div>
  );
};

export default SupportWidget;
