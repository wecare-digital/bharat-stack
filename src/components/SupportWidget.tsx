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

const SupportWidget: React.FC = () => {
  const [ langs, setLangs ] = useState<Lang[]>( [] );
  const [ current, setCurrent ] = useState( 'en' );
  const [ busy, setBusy ] = useState( false );
  const [ status, setStatus ] = useState( '' );
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
        const normalized = rows.map( row => {
          const base = row.code.toLowerCase().split( '-' )[ 0 ];
          return { code: row.code, name: row.name, native: NATIVE[ base ] };
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
   * The widget ALWAYS renders. Two early returns used to sit here and both were bugs:
   *  - `pathname === '/'` hid translation from the home page, the most visited route
   *  - `langs.length < 2` returned null when the catalogue failed to load, which would now
   *    take the WhatsApp button down with the translation API
   * The catalogue failing hides the language chip alone.
   */
  const canTranslate = langs.length >= 2;
  // Uppercased base code - "EN", "HI", "TA". Short enough to sit in the pill without the
  // chip changing width between languages, which a full name would do on every switch.
  const chipLabel = ( current.split( '-' )[ 0 ] || 'en' ).toUpperCase();

  return (
    <div data-wc-no-translate="true" className="wc-langbar">
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

        /* THE LANGUAGE CHIP IS A REAL <select>, NOT A CUSTOM PANEL.
           This replaces a 324px panel with a search field, an ARIA combobox, a scrolling
           listbox, keyboard navigation and aria-activedescendant wiring - about 150 lines.
           A native control gets all of that from the platform, and on a phone it opens the
           OS language picker, which is searchable, familiar and accessible for free.
           The <select> is transparent and stretched over the chip, so the visible label is
           ours while every interaction is the browser's. font-size:16px on it is not
           cosmetic: iOS Safari zooms the viewport when a focused form control is under
           16px. */
        .wc-chip{position:relative;display:inline-flex;align-items:center;height:40px;min-width:52px;justify-content:center;padding:0 9px 0 11px;border-radius:9999px;background:transparent;color:#1a3a2a;font-size:14px;font-weight:700;letter-spacing:.02em;cursor:pointer;transition:background-color .2s}
        .wc-chip:hover{background:rgba(209,244,112,.38)}
        .wc-chip:focus-within{background:rgba(209,244,112,.38);outline:3px solid rgba(26,58,42,.22);outline-offset:2px}
        .wc-chip select{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer;font-size:16px;border:0;padding:0;margin:0;-webkit-appearance:none;appearance:none}
        .wc-arw{width:6px;height:6px;box-sizing:border-box;border-right:2px solid #1a3a2a;border-bottom:2px solid #1a3a2a;transform:translateY(-2px) rotate(45deg);margin-left:7px;opacity:.7}

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

        /* MOBILE. The pill keeps its size - shrinking a support control on the device most
           likely to need it is the wrong trade, and 40px inside 4px padding already clears
           the 44px touch-target floor. What changes is the bottom offset: the phone
           BottomNav is 60px plus the safe-area inset, so the pill sits above it. */
        @media(max-width:767px){
          .wc-langbar{right:16px;left:auto;top:auto;bottom:calc(72px + env(safe-area-inset-bottom))}
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

        { canTranslate && (
          <span className={ `wc-chip ${busy ? 'is-busy' : ''}`.trim() }>
            { chipLabel }
            <span className="wc-arw" aria-hidden="true" />
            <select
              aria-label="Choose language"
              value={ current }
              disabled={ busy }
              onChange={ event => { void applyLanguage( event.target.value ); } }
            >
              { langs.map( lang => (
                <option key={ lang.code } value={ lang.code }>
                  { lang.native && lang.native !== lang.name ? `${lang.native} — ${lang.name}` : lang.name }
                </option>
              ) ) }
            </select>
          </span>
        ) }

        { busy && <span className="wc-sweep" aria-hidden="true" /> }
      </div>
      <div className="wc-sr" role="status" aria-live="polite">{ status }</div>
    </div>
  );
};

export default SupportWidget;
