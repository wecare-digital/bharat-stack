import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// One endpoint, one response shape. There is deliberately no provider probing
// and no second URL here.
//
// This used to call a Cloud Run relay directly for translation and TTS, choosing
// between it and AWS at runtime. That relay held the Google API key server-side -
// which was the right instinct, since a browser widget can never hold a key - but
// it billed a Google project with no request cap, and it was reachable by anything
// that could set an Origin header. Provider selection now happens inside
// wecare-site-language, behind the API Gateway throttle and the DynamoDB cache,
// where the key lives in Secrets Manager. See
// amplify/functions/core/site-language/handler.py.
//
// Practical consequence: do NOT reintroduce a provider flag on the client. If
// Google fails, the Lambda degrades to Amazon Translate and reports which one it
// used in `provider` on the response. The widget does not need to care.
const API_BASE = ( process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital' ) + '/site-language';
const LS_LANG = 'wc:stack:lang';
const MAX_BATCH_ITEMS = 30;
const MAX_BATCH_BYTES = 20000;
const MAX_SPEAK_CHARS = 2600;

interface Lang { code: string; name: string; native?: string; canSpeak: boolean }

const NATIVE: Record<string, string> = {
  en: 'English', hi: 'हिन्दी', bn: 'বাংলা', ta: 'தமிழ்', te: 'తెలుగు', mr: 'मराठी',
  gu: 'ગુજરાતી', kn: 'ಕನ್ನಡ', ml: 'മലയാളം', pa: 'ਪੰਜਾਬੀ', ur: 'اردو',
};

// PRIMARY, the resting Indic list, is deliberately gone rather than left unused:
// the panel is search-only now. NATIVE below stays, because search results still
// lead with the native name.

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

function readableText ( root: HTMLElement ): string {
  const parts: string[] = [];
  for ( const node of collectTextNodes( root ) ) {
    const text = ( node.nodeValue || '' ).replace( /\s+/g, ' ' ).trim();
    if ( text && parts[ parts.length - 1 ] !== text ) parts.push( text );
    if ( parts.join( '. ' ).length >= MAX_SPEAK_CHARS ) break;
  }
  return parts.join( '. ' ).slice( 0, MAX_SPEAK_CHARS );
}

const LanguageBar: React.FC = () => {
  const [ langs, setLangs ] = useState<Lang[]>( [] );
  const [ current, setCurrent ] = useState( 'en' );
  const [ query, setQuery ] = useState( '' );
  const [ open, setOpen ] = useState( false );
  const [ busy, setBusy ] = useState( false );
  const [ speaking, setSpeaking ] = useState( false );
  const [ status, setStatus ] = useState( '' );
  // Which result the keyboard is on. Not "which language is applied" - that is
  // `current`. Reset by the handlers that change the result set rather than by an
  // effect watching `query`, because setting state in an effect body is the
  // react-hooks/set-state-in-effect error this file was already fixed for once.
  const [ activeIndex, setActiveIndex ] = useState( 0 );
  const originals = useRef<Map<Text, string> | null>( null );
  const rootRef = useRef<HTMLDivElement | null>( null );
  const audioRef = useRef<HTMLAudioElement | null>( null );
  const searchRef = useRef<HTMLInputElement | null>( null );
  const triggerRef = useRef<HTMLButtonElement | null>( null );
  // Distinguishes "panel closed" from "panel never opened", so the trigger is only
  // refocused after a real close and not on first mount.
  const hasOpened = useRef( false );
  // Latest-ref for applyLanguage, assigned by an effect further down. The saved
  // language restore has to call whatever applyLanguage currently is WITHOUT
  // subscribing to its identity - see the restore block in the catalogue effect.
  const applyLanguageRef = useRef<( ( code: string, label?: string ) => Promise<void> ) | null>( null );

  const contentRoot = useCallback( (): HTMLElement => (
    document.querySelector( '.page' ) as HTMLElement
      || document.querySelector( 'main' ) as HTMLElement
      || document.getElementById( '__next' ) as HTMLElement
      || document.body
  ), [] );

  useEffect( () => {
    let cancelled = false;
    ( async () => {
      try {
        const languageResponse = await fetch( `${API_BASE}/languages` );
        if ( !languageResponse.ok ) return;
        const rows: Array<{ code: string; name: string }> = ( await languageResponse.json() ).languages || [];
        // Speech is Amazon Polly in every case. Google Cloud Text-to-Speech is a
        // separate API with its own enablement and key scope, and Polly is both
        // cheaper and already wired, so translation moved to Google and audio did
        // not. /voices is therefore the single source of truth for "can this
        // language be read aloud".
        const speakable = new Set<string>();
        try {
          const voiceResponse = await fetch( `${API_BASE}/voices` );
          if ( voiceResponse.ok ) {
            const voices: Array<{ languageCode: string; additionalLanguageCodes?: string[] }> = ( await voiceResponse.json() ).voices || [];
            for ( const voice of voices ) {
              for ( const code of [ voice.languageCode, ...( voice.additionalLanguageCodes || [] ) ] ) {
                if ( code ) speakable.add( code.toLowerCase().split( '-' )[ 0 ] );
              }
            }
          }
        } catch { /* text translation remains available */ }
        const normalized = rows.map( row => {
          const base = row.code.toLowerCase().split( '-' )[ 0 ];
          return { code: row.code, name: row.name, native: NATIVE[ base ], canSpeak: speakable.has( base ) };
        } ).sort( ( a, b ) => {
          if ( a.code === 'en' ) return -1;
          if ( b.code === 'en' ) return 1;
          return a.name.localeCompare( b.name );
        } );
        if ( cancelled ) return;
        setLangs( normalized );

        // The saved-language restore lives here, in the flow that just produced
        // the catalogue, instead of in a second effect watching `langs`.
        //
        // That second effect was the react-hooks/set-state-in-effect error. It
        // called applyLanguage synchronously in an effect body, which cascades a
        // render, and it could not declare applyLanguage as a dependency because
        // applyLanguage's identity changes the moment `busy` flips - so listing it
        // honestly would have re-fired the restore in the middle of its own
        // translation. One flow split in two produced both the error and the
        // missing-dependency warning.
        //
        // Everything below runs after the awaits above, which is exactly where
        // React expects an effect to push state, and `normalized` is in scope, so
        // the saved code is validated against the list that was just fetched
        // rather than against a later render's copy of it.
        let saved = '';
        try { saved = localStorage.getItem( LS_LANG ) || ''; } catch { /* ignore */ }
        if ( !saved || saved === 'en' ) return;
        const savedLang = normalized.find( lang => lang.code === saved );
        if ( !savedLang ) return;
        // The label is passed in because this ref was captured on mount, when
        // `langs` was still empty - applyLanguage's own lookup would miss and the
        // status line would read the raw code instead of the language name.
        await applyLanguageRef.current?.( saved, savedLang.name );
      } catch { /* stay hidden if language services are unavailable */ }
    } )();
    return () => { cancelled = true; };
  }, [] );

  useEffect( () => {
    if ( !open ) return undefined;
    const close = ( event: MouseEvent ) => {
      if ( rootRef.current && !rootRef.current.contains( event.target as Node ) ) setOpen( false );
    };
    document.addEventListener( 'pointerdown', close );
    return () => document.removeEventListener( 'pointerdown', close );
  }, [ open ] );

  // Escape closes from ANYWHERE while the panel is open. It used to be handled only
  // by onKeyDown on the search input, so Escape did nothing once focus had moved to
  // the trigger, an option or the Listen button - the panel could be left open with
  // no keyboard way to dismiss it.
  useEffect( () => {
    if ( !open ) return undefined;
    const onKeyDown = ( event: KeyboardEvent ) => { if ( event.key === 'Escape' ) setOpen( false ); };
    document.addEventListener( 'keydown', onKeyDown );
    return () => document.removeEventListener( 'keydown', onKeyDown );
  }, [ open ] );

  // Focus into the field on open, and back onto the trigger on close.
  //
  // autoFocus could not do the first job: it is a mount-time prop, and the panel is
  // hidden with CSS rather than unmounted, so the input is never remounted and
  // autoFocus fired on the first render pass only - reopening the panel left focus
  // wherever it was. The second job was simply missing: closing the panel dropped
  // focus onto <body>, so a keyboard user had to tab from the top of the document
  // again.
  //
  // Nested requestAnimationFrame, not one: the panel is still hidden when this
  // effect runs, and focus() on a hidden element is silently a no-op. One frame was
  // measurably not enough - the panel's computed visibility was still `hidden` on
  // frames 0 and 1 and only flipped on frame 2. The CSS fix below (visibility at 0s
  // rather than over .18s) is what actually makes it focusable on the first frame;
  // the second frame here is belt-and-braces so this cannot silently regress if the
  // transition is ever retuned.
  useEffect( () => {
    if ( open ) {
      hasOpened.current = true;
      let inner = 0;
      const outer = window.requestAnimationFrame( () => {
        inner = window.requestAnimationFrame( () => searchRef.current?.focus() );
      } );
      return () => { window.cancelAnimationFrame( outer ); window.cancelAnimationFrame( inner ); };
    }
    if ( hasOpened.current ) triggerRef.current?.focus();
    return undefined;
  }, [ open ] );

  const restore = useCallback( () => {
    originals.current?.forEach( ( value, node ) => { if ( node.parentNode ) node.nodeValue = value; } );
  }, [] );

  const stopSpeaking = useCallback( () => {
    const audio = audioRef.current;
    if ( audio ) { try { audio.pause(); } catch { /* ignore */ } }
    audioRef.current = null;
    setSpeaking( false );
  }, [] );

  // `labelOverride` exists for the restore path only, which knows the language
  // name from the response it just parsed. Panel clicks omit it and fall through
  // to the lookup below.
  const applyLanguage = useCallback( async ( code: string, labelOverride?: string ) => {
    if ( busy ) return;
    setOpen( false );
    setQuery( '' );
    stopSpeaking();
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
  }, [ busy, contentRoot, langs, restore, stopSpeaking ] );

  // Keeps the restore above pointed at the current applyLanguage. Assigning in an
  // effect rather than during render is deliberate: a ref written mid-render is
  // its own hooks violation, and this only has to be current by the time the
  // catalogue fetch resolves - a network round trip after the first commit.
  useEffect( () => { applyLanguageRef.current = applyLanguage; }, [ applyLanguage ] );

  const speak = useCallback( async () => {
    if ( speaking ) { stopSpeaking(); setStatus( 'Stopped reading.' ); return; }
    const text = readableText( contentRoot() );
    if ( !text ) return;
    setSpeaking( true );
    setStatus( 'Preparing audio.' );
    try {
      const response = await fetch( `${API_BASE}/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify( { text, language: current } ),
      } );
      if ( !response.ok ) throw new Error( 'tts failed' );
      const body = await response.json();
      if ( !body.audioBase64 ) throw new Error( 'missing audio' );
      const src = `data:${body.mimeType || 'audio/mpeg'};base64,${body.audioBase64}`;
      const audio = new Audio( src );
      audioRef.current = audio;
      const finish = () => { setSpeaking( false ); };
      audio.addEventListener( 'ended', () => { finish(); setStatus( 'Finished reading.' ); } );
      audio.addEventListener( 'error', () => { finish(); setStatus( 'Playback failed.' ); } );
      await audio.play();
      setStatus( 'Reading this page.' );
    } catch { setSpeaking( false ); setStatus( 'Audio is unavailable right now.' ); }
  }, [ contentRoot, current, speaking, stopSpeaking ] );

  // Search-only: an empty query returns nothing and the panel lists no languages
  // until the visitor types. Owner's decision.
  //
  // THIS IS A ROUND TRIP, and the reason it was changed away from is still valid, so
  // it is recorded rather than deleted. The panel behaved exactly this way once. It
  // was changed to show the Indic set at rest because search-only means the visitor
  // has to guess their language is in here before seeing any evidence that it is -
  // and the Hindi or Tamil speaker this product is built for has to type in the Latin
  // alphabet to find their own script. Reverting to search-only reinstates that cost.
  //
  // The mitigation is the empty state below: it says what to do instead of showing a
  // blank box, and the input is autofocused when the panel opens, so typing is the
  // only action required. If the cost shows up in behaviour, the previous resting
  // list is one commit back in history.
  const filtered = useMemo( () => {
    const term = query.trim().toLocaleLowerCase();
    if ( !term ) return [];
    return langs
      .filter( lang => [ lang.code, lang.name, lang.native || '' ].some( value => value.toLocaleLowerCase().includes( term ) ) )
      .slice( 0, 14 );
  }, [ langs, query ] );

  const searching = query.trim().length > 0;

  const selected = langs.find( lang => lang.code === current );
  const canSpeak = selected?.canSpeak === true;

  // Clamped at point of use rather than corrected in an effect: `filtered` shrinks
  // as the visitor types, and an activeIndex left pointing past the end would make
  // aria-activedescendant reference a non-existent id.
  const active = filtered.length ? Math.min( activeIndex, filtered.length - 1 ) : 0;
  const optionId = ( index: number ) => `wc-lang-opt-${index}`;

  // Keeps the keyboard-active row in view when arrowing past the visible window.
  // No state is set here, so it is not a set-state-in-effect.
  useEffect( () => {
    if ( !open || !filtered.length ) return;
    document.getElementById( optionId( active ) )?.scrollIntoView( { block: 'nearest' } );
  }, [ active, open, filtered.length ] );

  const onSearchKeyDown = ( event: React.KeyboardEvent<HTMLInputElement> ) => {
    if ( event.key === 'Escape' ) { setOpen( false ); return; }
    if ( !filtered.length ) return;
    const last = filtered.length - 1;
    if ( event.key === 'ArrowDown' ) {
      event.preventDefault();
      setActiveIndex( active >= last ? 0 : active + 1 );
    } else if ( event.key === 'ArrowUp' ) {
      event.preventDefault();
      setActiveIndex( active <= 0 ? last : active - 1 );
    } else if ( event.key === 'Home' ) {
      event.preventDefault();
      setActiveIndex( 0 );
    } else if ( event.key === 'End' ) {
      event.preventDefault();
      setActiveIndex( last );
    } else if ( event.key === 'Enter' ) {
      event.preventDefault();
      const pick = filtered[ active ];
      if ( pick ) void applyLanguage( pick.code );
    }
  };

  /**
   * BOTH OF THE OLD EARLY RETURNS ARE GONE, and that is the point of this widget.
   *
   * It used to bail out entirely on two conditions:
   *   - `window.location.pathname === '/'`, which hid translation from the HOME PAGE,
   *     the single most visited route on the site.
   *   - `langs.length < 2`, which returned null whenever the language catalogue failed
   *     to load - and since this component now also owns the WhatsApp button, that would
   *     take customer support down with it. The translation API being unreachable is no
   *     reason to remove the way people contact us.
   *
   * So the widget always renders. What varies is whether the TRANSLATE half is offered:
   * `canTranslate` below gates that button alone, leaving WhatsApp in place.
   */
  const canTranslate = langs.length >= 2;

  return (
    <div ref={ rootRef } data-wc-no-translate="true" className="wc-langbar">
      <style jsx>{`
        /* Bottom corner, offset LEFT of the WhatsApp button. Two constraints drove
           this, both measured rather than guessed:
           1. At top:50% the trigger and its open panel sat directly on the hero
              mockup on /grahak-os, hiding the phone and the code panel.
           2. #wecarewa-widget (injected by the external wecare-wa-widget.js) is a
              64x64 button at right:16px bottom:120px with
              z-index: 2147483647 - the maximum 32-bit integer. Nothing can be
              stacked above it, so the panel cannot merely out-z-index it: any
              overlap means a green WhatsApp circle punches through the language
              list. Stacking this ABOVE the button instead pushed the panel off
              the top of a short viewport.
           That z-index fact still holds and still governs the PANEL. What changed is
           that the trigger no longer hides from the button - the owner asked for the two
           floating icons to read as one set, so they now share a column and a diameter,
           and only the panel steps aside.

           MEASURED GEOMETRY OF THE EXTERNAL BUTTON, which is the fixed point everything
           here is derived from. It is not ours to change: it lives in
           wecare-wa-widget.js on app.wecare.digital, outside this repo.
             desktop      box 64x64 at right:16 bottom:120, icon 56x56 centred in it,
                          so the VISIBLE circle is 56px spanning right 20..76,
                          centred on right:48
             <=767px      box 60x60 at right:14 bottom:80, icon 52x52,
                          visible circle 52px spanning right 18..70, centred on right:44

           So the trigger below is 56px centred on right:48 (20 + 28), and 52px centred
           on right:44 (18 + 26) on mobile - identical diameter, identical centre line.
           Its breakpoint is 767px, NOT the 600px this file used to use: between 601 and
           767px the external button is already on its mobile geometry, so a 600px
           breakpoint here left the pair mismatched across that whole band.

           Vertical: the external icon's bottom edge sits 124px up (120 + 4) on desktop,
           so a 56px trigger at bottom:52 leaves a 16px gap between the two circles
           (52 + 56 = 108, and 124 - 108 = 16). On mobile the icon bottom is at 84, and
           52 + 52 = 104... which would COLLIDE, so mobile keeps bottom:16 and accepts a
           16px gap measured the other way: 84 - 68 = 16. Both are 16px gaps.

           THE PANEL STILL MAY NOT TOUCH THAT COLUMN. Nothing can stack above
           z-index 2147483647, so the panel is absolutely positioned and shifted left
           until it is clear of the button in x - horizontal clearance alone is enough,
           which is why the panel may sit at any height. See the .panel rule. */
        /* WE OWN THE STACKING CONTEXT NOW, and that is what simplified this file.
           Everything above describes working around #wecarewa-widget - an externally
           injected button at z-index 2147483647, the maximum 32-bit integer, which
           nothing could be stacked above. Its geometry was a fixed point this component
           had to derive its own position from, and the panel had to be shoved sideways
           because overlap could only be avoided in x, never with z-index.
           That script is retired: the WhatsApp button is now the left half of the pill
           below, rendered by this component. So there is no foreign element to dodge,
           the panel can sit directly above the pill, and z-index only has to clear the
           mobile BottomNav (1200) and the header menu (1002) - 1300 does both.
           bottom clears the phone bottom bar, which is 60px plus the safe-area inset. */
        .wc-langbar{position:fixed;right:20px;left:auto;bottom:20px;top:auto;z-index:1300;display:flex;flex-direction:column;align-items:flex-end;gap:10px;font-family:inherit}

        /* THE PILL. One container, two actions, reading as a single object. 4px of padding
           around 40px controls makes it 48px tall; the lime hairline is the same 1.5px
           edge the editor panels use, and the radius is a full pill so it cannot be
           confused with the square-ish cards elsewhere. */
        .wc-pill{display:inline-flex;align-items:center;gap:2px;padding:4px;background:#fff;border:1.5px solid #d1f470;border-radius:9999px;box-shadow:0 6px 22px rgba(16,32,24,.14)}
        /* Full-strength lime with #1a3a2a type: the palette's own-surface pairing, and
           correct here because contacting us is the primary action. Deliberately NOT
           WhatsApp green - that is their brand, not ours, and it was the one off-palette
           colour on every public page. */
        .wc-wa{width:40px;height:40px;border-radius:50%;background:#d1f470;color:#1a3a2a;display:grid;place-items:center;text-decoration:none;transition:background-color .2s}
        .wc-wa:hover{background:#c5e866}
        .wc-wa:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:2px}
        .wc-wa svg{width:21px;height:21px;display:block}
        .wc-sep{width:1px;height:22px;background:#eef0e6;flex:0 0 auto}
        /* visibility + opacity rather than display:none, so opening can animate -
           display is not an animatable property. visibility:hidden still removes the
           panel from the accessibility tree and from tab order, which display:none
           was doing and which a plain opacity:0 would NOT do: an opacity-only panel
           stays focusable and a keyboard user tabs into an invisible language list.
           transform-origin is bottom right because the panel grows out of a trigger
           sitting at the bottom right of the viewport.

           NOTE the visibility timing: 0s with a DELAY, never over a duration.
           Transitioning visibility over .18s looks harmless and broke focus.
           visibility is a discrete property, so mid-transition it holds the START
           value - measured here, the panel's computed visibility was still hidden on
           frames 0 and 1 after opening and only flipped on frame 2. focus() on a
           hidden element is a silent no-op, so the search field was never focused
           and focus stayed on the trigger.
           Hence: 0s with no delay on .open (visible and focusable immediately), and
           0s with a .18s delay on the closed state, so the panel stays visible long
           enough for the opacity fade to finish. */
        /* position:absolute, and the right offset is the whole point. The trigger now
           shares the external WhatsApp button's column (right 20..76), and that button
           cannot be covered - z-index 2147483647. So the panel is taken out of the flex
           flow and pushed left until its right edge clears x=80: 76px inside a container
           whose own right edge is 20px from the viewport puts it at 96px, a 16px gap past
           the button. Once it is clear horizontally it can sit at any height, which is
           why bottom:0 (level with the trigger) is safe even though the button occupies
           y 120..184.
           Width leaves a 20px margin on the left: 100vw - 96 (the right offset) - 20. */
        /* DIRECTLY ABOVE THE PILL, which is only possible now that no foreign element
           outranks us in z-index. It used to be pushed 76px to the left to clear the
           external WhatsApp button in x; with that button gone the panel opens where the
           control is, which is where a popover belongs. right:0 aligns it to the pill's
           right edge, bottom:100% sits it above with a small gap from margin-bottom. */
        .panel{position:absolute;right:0;bottom:100%;margin-bottom:10px;visibility:hidden;opacity:0;transform:translateY(6px) scale(.98);transform-origin:bottom right;transition:opacity .18s cubic-bezier(.16,1,.3,1),transform .18s cubic-bezier(.16,1,.3,1),visibility 0s linear .18s;width:min(324px,calc(100vw - 40px));background:#fff;border:1px solid #e5e7eb;border-top:3px solid #d1f470;border-radius:14px;padding:8px;box-shadow:0 16px 48px rgba(16,32,24,.16),0 2px 8px rgba(16,32,24,.06)}
        .panel.open{visibility:visible;opacity:1;transform:none;transition:opacity .18s cubic-bezier(.16,1,.3,1),transform .18s cubic-bezier(.16,1,.3,1),visibility 0s}
        /* #e5e7eb at 1px: the contract's hairline value and weight for a STATIC
           edge, replacing rgba(0,0,0,.12). The focus ring is the lime
           rgba(209,244,112,.3) the sign-in fields use, so a focused field looks the
           same whether it is in this widget or on /access - it was
           rgba(26,58,42,.1), a fourth focus treatment nothing else shared. */
        .search{width:100%;min-height:42px;box-sizing:border-box;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;font-size:15px;font-weight:400;line-height:1.3;color:rgba(0,0,0,.898);outline:none}
        .search::placeholder{color:rgba(0,0,0,.42)}
        .search:focus{border-color:#1a3a2a;box-shadow:0 0 0 3px rgba(209,244,112,.3)}
        .group{padding:10px 10px 4px;font-size:12px;font-weight:500;color:rgba(0,0,0,.42)}
        .results{max-height:296px;overflow:auto;margin-top:2px}
        .hint{padding:12px 10px;color:rgba(0,0,0,.5);font-size:14px}
        .opt{width:100%;min-height:42px;border:0;border-radius:9px;background:transparent;padding:8px 10px;display:flex;align-items:baseline;gap:8px;text-align:left;color:rgba(0,0,0,.898);cursor:pointer;box-sizing:border-box}
        /* aria-selected is the KEYBOARD cursor, aria-current is the language actually
           applied to the page. They are different things and used to be conflated on
           one attribute, which meant arrowing through results moved no highlight at
           all. Pointer hover sets the same active index, so mouse and keyboard share
           one highlight instead of producing two competing ones.
           The applied-language rule comes second on purpose: when the cursor is on
           the row that is already applied, dark green wins over the grey wash. */
        /* Both states now come from the palette's three lime treatments instead of
           invented pale greens. The keyboard/hover cursor takes the TRANSIENT tint
           rgba(209,244,112,.22) - the same value the nav uses for hover - where it
           used to be #f4f7f5, a one-off grey-green that matched nothing else.
           The applied language takes the INVERTED treatment, #1a3a2a fill with
           #d1f470 type, which the contract measures at ~10:1. It was #1a3a2a with
           white type; white is not one of the three pairings, and the lime reads as
           the same object as BrandBadge and .msg.sent rather than as a generic
           selected row. */
        .opt[aria-selected='true']{background:rgba(209,244,112,.22)}
        .opt[aria-current='true']{background:#1a3a2a;color:#d1f470}
        .nat{font-size:15px;font-weight:500}
        .eng{font-size:13px;color:rgba(0,0,0,.54)}
        .opt[aria-current='true'] .eng{color:rgba(209,244,112,.72)}
        .meta{margin-left:auto;font-size:11px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:rgba(0,0,0,.42);white-space:nowrap}
        .opt[aria-current='true'] .meta{color:rgba(209,244,112,.6)}
        .panel-actions{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:8px;padding:8px 4px 2px;border-top:1px solid #e5e7eb}
        .current-language{font-size:13px;font-weight:500;color:rgba(0,0,0,.54);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        /* Three states, three documented treatments, escalating in voice:
           rest   -> .22 lime tint  (transient, quiet)
           hover  -> #d1f470 fill   (our own surface, full voice)
           on     -> #1a3a2a fill + #d1f470 type (inverted, dark)
           It was #f0f4f1 / #e6ece8 / white-on-green - two invented tints and a
           pairing that is not in the palette. Inventing in-between values is exactly
           how #f2fbf6 and #fbfff0 got into this codebase and had to be retired. */
        .listen-btn{min-height:34px;padding:7px 13px;border:0;border-radius:8px;background:rgba(209,244,112,.22);color:#1a3a2a;font-size:13px;font-weight:500;line-height:1;cursor:pointer;transition:background-color .2s,color .2s}
        .listen-btn:hover{background:#d1f470;color:#1a3a2a}
        .listen-btn.on{background:#1a3a2a;color:#d1f470}
        /* 56px, matching the external WhatsApp icon's visible 56px circle so the two read
           as one set rather than two unrelated widgets. Was 48px against its 56px. */
        .language-trigger{width:40px;height:40px;border:0;border-radius:50%;background:transparent;color:#1a3a2a;display:grid;place-items:center;cursor:pointer;padding:0}
        .language-trigger:hover{background:rgba(209,244,112,.38)}
        .language-trigger:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:2px}
        .language-trigger[aria-expanded='true']{background:#1a3a2a;color:#d1f470}
        /* Translating is the one action here that takes real time - it is a sequence
           of network round trips over every text node on the page. The trigger used
           to only fade to .55 and stop responding, which reads as "broken" rather
           than "working". aria-busy plus a visible spinner says which. */
        .language-trigger:disabled{cursor:progress}
        .language-trigger[aria-busy='true']{border-color:#1a3a2a}
        .spin{width:20px;height:20px;border:2px solid rgba(26,58,42,.22);border-top-color:#1a3a2a;border-radius:50%;animation:wc-spin .7s linear infinite}
        @keyframes wc-spin{to{transform:rotate(360deg)}}
        /* 28px keeps the glyph at the same half-of-diameter ratio it had at 24px in a
           48px circle. Leaving it at 24px inside a 56px circle reads as under-filled. */
        .language-trigger svg{width:21px;height:21px;display:block}
        .sr{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
        /* Same horizontal clearance on mobile, plus the safe-area inset for the iOS
           home indicator. The panel is capped against 104px for the same reason as
           the desktop rule. */
        /* 767px, not 600px - that is the external button's own breakpoint, and matching it
           is what keeps the pair the same size across 601..767px. Trigger 52px centred on
           right:44 (18 + 26); panel clears the button's mobile column (x 14..74) by
           sitting 72px inside a container whose right edge is 18px out, i.e. at 90px. */
        /* MOBILE. The pill keeps its size - 40px controls are already above the 44px
           touch-target floor once the 4px padding is counted, and shrinking a support
           button on the device most likely to need it is the wrong trade.
           The bottom offset is what changes: the phone BottomNav is 60px plus the
           safe-area inset, so the pill sits above it rather than on top of it. This is
           the clearance the old comment could only achieve geometrically against an
           un-stackable foreign button; now it is simply a margin. */
        @media(max-width:767px){
          .wc-langbar{right:16px;left:auto;top:auto;bottom:calc(72px + env(safe-area-inset-bottom))}
          .panel{width:min(300px,calc(100vw - 32px))}
        }
        @media print{.wc-langbar{display:none}}
        /* The spinner keeps turning - it is the only signal that work is in flight,
           and freezing it would misreport a live translation as a stalled one. It is
           slowed instead. The panel settles to its open state with no motion. */
        @media(prefers-reduced-motion:reduce){
          .panel{transition:none}
          .spin{animation-duration:2.4s}
        }
      `}</style>

      <div className={ `panel ${open ? 'open' : ''}` }>
        {/* A real combobox now. This is the pattern the markup was already implying -
            a text field that filters an owned listbox - but the wiring was missing:
            no aria-controls, no aria-activedescendant, and therefore no way for a
            screen reader to announce the highlighted result as the visitor arrows
            through it. autoFocus is gone; see the focus effect above for why it
            could not work against a CSS-hidden panel. */}
        <input
          ref={ searchRef }
          className="search"
          type="search"
          role="combobox"
          value={ query }
          placeholder="Search all languages"
          aria-label="Search languages"
          aria-expanded={ open }
          aria-controls="wc-lang-listbox"
          aria-autocomplete="list"
          aria-activedescendant={ filtered.length ? optionId( active ) : undefined }
          onChange={ event => { setQuery( event.target.value ); setActiveIndex( 0 ); } }
          onKeyDown={ onSearchKeyDown }
        />
        {/* Heading only while there is something to head. At rest the panel is the
            field and the prompt, with no empty section label above them. */}
        { searching && <div className="group">Results</div> }
        <div className="results" id="wc-lang-listbox" role="listbox" aria-label="Language results">
          {/* Not decoration. With no resting list this is the only thing telling the
              visitor the catalogue exists at all, so the panel never opens blank. */}
          { !searching && <div className="hint">Type a language name to translate this page.</div> }
          { searching && !filtered.length && <div className="hint">No matching language.</div> }
          {/* role="option" on a div, NOT on a button. A focusable button inside a
              listbox is an invalid ARIA pairing - screen readers announce "button"
              where an option is expected, and Tab became the only way to move
              through results. In the combobox pattern the options are not focusable
              at all: focus stays in the field and aria-activedescendant points at
              the highlighted row, which is what makes Arrow keys work. */}
          { filtered.map( ( lang, index ) => (
            <div
              key={ lang.code }
              id={ optionId( index ) }
              role="option"
              className="opt"
              aria-selected={ index === active }
              aria-current={ lang.code === current ? 'true' : 'false' }
              onPointerEnter={ () => setActiveIndex( index ) }
              onClick={ () => { void applyLanguage( lang.code ); } }
            >
              {/* Native name leads. Someone looking for Malayalam scans for
                  മലയാളം, not for the word "Malayalam" - and no flags, because a
                  flag is a country and these are languages. */}
              <span className="nat">{ lang.native || lang.name }</span>
              { lang.native && lang.native !== lang.name && <span className="eng">{ lang.name }</span> }
              <span className="meta">{ lang.code }</span>
            </div>
          ) ) }
        </div>
        <div className="panel-actions">
          <span className="current-language">{ selected ? ( selected.native || selected.name ) : current.toUpperCase() }</span>
          { canSpeak && (
            <button type="button" className={ `listen-btn ${speaking ? 'on' : ''}` } aria-pressed={ speaking } onClick={ () => { void speak(); } }>
              { speaking ? 'Stop' : 'Listen' }
            </button>
          ) }
        </div>
      </div>

      {/* ONE WIDE PILL HOLDING BOTH ACTIONS.
          This replaces two unrelated floating circles: a green 56px WhatsApp button
          injected by an external script, and this component's own white 56px translate
          circle. They shared no colour, no shape and no container, and the green was
          WhatsApp's brand rather than ours.
          WhatsApp takes the lime fill because it is the primary action; translate sits
          beside it behind a hairline. Both are 40px inside a 48px pill - smaller than
          the 56px pair they replace, which is what was asked for. */}
      <div className="wc-pill">
        {/* A real anchor, not a button with an onClick: this leaves the site, so it must
            be middle-clickable, long-pressable and copyable like any other link.
            rel="noopener" because it opens cross-origin.
            The href is the external widget's own destination, read out of
            wecare-wa-widget.js rather than guessed, so retiring that script does not
            change where people land. */}
        <a
          className="wc-wa"
          href="https://wa.me/message/APDM5HUWH26SG1"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Chat with us on WhatsApp"
          title="Chat with us on WhatsApp"
        >
          {/* Official WhatsApp glyph, inlined. Inlined rather than loaded from the asset
              host for the reason the translate mark below records: a remote SVG carries
              its own hardcoded fill, which CSS cannot reach, so it cannot follow
              currentColor through hover and inverted states - and it adds a request that
              can leave the button empty while in flight. */}
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path fill="currentColor" d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.26-.46-2.4-1.48-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.91-2.21-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.03 1.02-1.03 2.48 0 1.46 1.06 2.87 1.21 3.07.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.62.71.23 1.36.2 1.87.12.57-.09 1.76-.72 2-1.41.25-.7.25-1.29.18-1.42-.08-.12-.28-.2-.57-.35M12.05 21.79h-.01a9.87 9.87 0 01-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 01-1.51-5.26C2.16 6.45 6.6 2.01 12.05 2.01c2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 012.89 6.99c0 5.45-4.44 9.89-9.88 9.89M20.46 3.49A11.82 11.82 0 0012.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.88 11.88 0 005.69 1.45c6.55 0 11.89-5.34 11.89-11.89 0-3.18-1.24-6.17-3.48-8.42z" />
          </svg>
        </a>

        { canTranslate && <span className="wc-sep" aria-hidden="true" /> }

        { canTranslate && (
      <button
        ref={ triggerRef }
        type="button"
        className="language-trigger"
        aria-expanded={ open }
        aria-label="Choose language"
        aria-busy={ busy }
        disabled={ busy }
        onClick={ () => { setActiveIndex( 0 ); setOpen( value => !value ); } }
      >
        {/* Owner-supplied translate mark, replacing a hand-drawn globe.
            Source: https://app.wecare.digital/stream/media/m/translate_indic.svg
            (given as s3://app.wecare.digital/... - the s3 scheme is not fetchable by
            a browser, and every other asset here uses this https host, so that is
            the form used.)

            INLINED rather than loaded through an img, for the same reason BrandMark
            is: the source hardcodes fill="#1f1f1f" on its root svg, and a fill
            inside the file cannot be reached by CSS. This trigger inverts on open -
            #1a3a2a on white at rest, white on #1a3a2a when expanded - so the glyph
            has to follow currentColor or it stays near-black on dark green and
            effectively disappears. #1f1f1f is also not a palette value.
            Inlining also drops a network request on every public page, and with it
            the chance of an empty trigger while the file is in flight.

            viewBox is the source's own 0 -960 960 960 (Material's baseline-relative
            box); the negative Y is correct, not a typo. Only the root fill was
            dropped and fill="currentColor" moved onto the path. */}
        { busy
          ? <span className="spin" aria-hidden="true" />
          : (
            <svg viewBox="0 -960 960 960" aria-hidden="true" focusable="false">
              <path
                fill="currentColor"
                d="m475-80 185-480h79L924-80h-65l-45-117H584L539-80h-64Zm130-172h188l-94-248-94 248Zm-358-88q-63 0-110-35.5T63-470l54-27q21 42 52.5 69.5T247-400q46 0 74.5-26.5T350-491q0-37-26-63t-64-26h-50v-60h50q29 0 49.5-21t20.5-53q0-26-16.5-46T265-780q-26 0-44.5 13.5T188-735l-47-37q23-28 53.5-48t72.5-20q57 0 90 37.5t33 88.5q0 31-14 55.5T332-616q20 12 34 26t24 30h140v-220h-80v-60h220v60h-80v235l-18 45H410v12q0 61-45.5 104.5T247-340Z"
              />
            </svg>
          ) }
      </button>
        ) }
      </div>
      <div className="sr" role="status" aria-live="polite">{ status }</div>
    </div>
  );
};

export default LanguageBar;
