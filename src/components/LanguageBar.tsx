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

// Shown immediately when the panel opens, in rough order of speakers. The
// service returns ~75 languages from Amazon Translate, but this is a product for
// Bharat: surfacing the Indic set first means the common case is one tap and no
// typing. Search still reaches the full catalogue.
const PRIMARY = [ 'en', 'hi', 'bn', 'mr', 'te', 'ta', 'gu', 'kn', 'ml', 'pa', 'ur' ];

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
  const originals = useRef<Map<Text, string> | null>( null );
  const rootRef = useRef<HTMLDivElement | null>( null );
  const audioRef = useRef<HTMLAudioElement | null>( null );

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
        if ( !cancelled ) setLangs( normalized );
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

  const restore = useCallback( () => {
    originals.current?.forEach( ( value, node ) => { if ( node.parentNode ) node.nodeValue = value; } );
  }, [] );

  const stopSpeaking = useCallback( () => {
    const audio = audioRef.current;
    if ( audio ) { try { audio.pause(); } catch { /* ignore */ } }
    audioRef.current = null;
    setSpeaking( false );
  }, [] );

  const applyLanguage = useCallback( async ( code: string ) => {
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
    const label = langs.find( lang => lang.code === code )?.name || code;
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

  useEffect( () => {
    if ( !langs.length ) return;
    let saved = '';
    try { saved = localStorage.getItem( LS_LANG ) || ''; } catch { /* ignore */ }
    if ( saved && saved !== 'en' && langs.some( lang => lang.code === saved ) ) void applyLanguage( saved );
  }, [ langs ] );

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

  // An empty query used to return an empty array, so opening the panel showed
  // nothing but "Type a language name or code." - the visitor had to guess that
  // their language was in there before seeing any evidence of it. Now the Indic
  // set is the resting state and typing widens the search to everything.
  const filtered = useMemo( () => {
    const term = query.trim().toLocaleLowerCase();
    if ( !term ) {
      return PRIMARY
        .map( code => langs.find( lang => lang.code === code ) )
        .filter( ( lang ): lang is Lang => Boolean( lang ) );
    }
    return langs
      .filter( lang => [ lang.code, lang.name, lang.native || '' ].some( value => value.toLocaleLowerCase().includes( term ) ) )
      .slice( 0, 14 );
  }, [ langs, query ] );

  const searching = query.trim().length > 0;

  const selected = langs.find( lang => lang.code === current );
  const canSpeak = selected?.canSpeak === true;

  if ( typeof window !== 'undefined' && window.location.pathname === '/' ) return null;
  if ( langs.length < 2 ) return null;

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
           So the whole cluster clears the button horizontally: right:96px leaves a
           16px gap beside its right:16px..80px column, and the panel width is
           capped against the same 108px so it can never grow back into it. */
        .wc-langbar{position:fixed;right:96px;left:auto;bottom:16px;top:auto;z-index:900;display:flex;flex-direction:column;align-items:flex-end;gap:10px;font-family:inherit}
        .panel{display:none;width:min(324px,calc(100vw - 108px));background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:14px;padding:8px;box-shadow:0 16px 48px rgba(16,32,24,.16),0 2px 8px rgba(16,32,24,.06)}
        .panel.open{display:block}
        .search{width:100%;min-height:42px;box-sizing:border-box;border:1px solid rgba(0,0,0,.12);border-radius:10px;padding:10px 12px;font-size:15px;font-weight:400;line-height:1.3;color:rgba(0,0,0,.898);outline:none}
        .search::placeholder{color:rgba(0,0,0,.42)}
        .search:focus{border-color:#1a3a2a;box-shadow:0 0 0 3px rgba(26,58,42,.1)}
        .group{padding:10px 10px 4px;font-size:12px;font-weight:500;color:rgba(0,0,0,.42)}
        .results{max-height:296px;overflow:auto;margin-top:2px}
        .hint{padding:12px 10px;color:rgba(0,0,0,.5);font-size:14px}
        .opt{width:100%;min-height:42px;border:0;border-radius:9px;background:transparent;padding:8px 10px;display:flex;align-items:baseline;gap:8px;text-align:left;color:rgba(0,0,0,.898);cursor:pointer}
        .opt:hover,.opt:focus-visible{background:#f4f7f5;outline:none}
        .opt[aria-current='true']{background:#1a3a2a;color:#fff}
        .nat{font-size:15px;font-weight:500}
        .eng{font-size:13px;color:rgba(0,0,0,.5)}
        .opt[aria-current='true'] .eng{color:rgba(255,255,255,.7)}
        .meta{margin-left:auto;font-size:11px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:rgba(0,0,0,.35);white-space:nowrap}
        .opt[aria-current='true'] .meta{color:rgba(255,255,255,.6)}
        .panel-actions{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:8px;padding:8px 4px 2px;border-top:1px solid rgba(0,0,0,.07)}
        .current-language{font-size:13px;font-weight:500;color:rgba(0,0,0,.5);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .listen-btn{min-height:34px;padding:7px 13px;border:0;border-radius:8px;background:#f0f4f1;color:#1a3a2a;font-size:13px;font-weight:500;line-height:1;cursor:pointer}
        .listen-btn:hover{background:#e6ece8}
        .listen-btn.on{background:#1a3a2a;color:#fff}
        .language-trigger{width:48px;height:48px;border:1px solid rgba(0,0,0,.1);border-radius:50%;background:#fff;color:#1a3a2a;display:grid;place-items:center;cursor:pointer;box-shadow:0 6px 20px rgba(16,32,24,.14)}
        .language-trigger:hover{border-color:#1a3a2a;background:#f4f7f5}
        .language-trigger:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:2px}
        .language-trigger[aria-expanded='true']{background:#1a3a2a;border-color:#1a3a2a;color:#fff}
        .language-trigger:disabled{opacity:.55;cursor:not-allowed}
        .language-trigger svg{width:24px;height:24px}
        .sr{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
        /* Same horizontal clearance on mobile, plus the safe-area inset for the iOS
           home indicator. The panel is capped against 104px for the same reason as
           the desktop rule. */
        @media(max-width:600px){.wc-langbar{right:92px;left:auto;top:auto;bottom:calc(16px + env(safe-area-inset-bottom))}.panel{width:min(300px,calc(100vw - 104px))}}
        @media print{.wc-langbar{display:none}}
      `}</style>

      <div className={ `panel ${open ? 'open' : ''}` }>
        <input
          className="search"
          type="search"
          value={ query }
          placeholder="Search all languages"
          aria-label="Search languages"
          autoFocus={ open }
          onChange={ event => setQuery( event.target.value ) }
          onKeyDown={ event => { if ( event.key === 'Escape' ) setOpen( false ); } }
        />
        <div className="group">{ searching ? 'Results' : 'Indian languages' }</div>
        <div className="results" role="listbox" aria-label="Language results">
          { searching && !filtered.length && <div className="hint">No matching language.</div> }
          { filtered.map( lang => (
            <button key={ lang.code } type="button" className="opt" role="option" aria-selected={ lang.code === current } aria-current={ lang.code === current ? 'true' : 'false' } onClick={ () => { void applyLanguage( lang.code ); } }>
              {/* Native name leads. Someone looking for Malayalam scans for
                  മലയാളം, not for the word "Malayalam" - and no flags, because a
                  flag is a country and these are languages. */}
              <span className="nat">{ lang.native || lang.name }</span>
              { lang.native && lang.native !== lang.name && <span className="eng">{ lang.name }</span> }
              <span className="meta">{ lang.code }</span>
            </button>
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

      <button type="button" className="language-trigger" aria-expanded={ open } aria-label="Choose language" disabled={ busy } onClick={ () => setOpen( value => !value ) }>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.8" />
          <path d="M3.5 12h17M12 3c2.5 2.6 3.7 5.6 3.7 9S14.5 18.4 12 21M12 3C9.5 5.6 8.3 8.6 8.3 12s1.2 6.4 3.7 9" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>
      <div className="sr" role="status" aria-live="polite">{ status }</div>
    </div>
  );
};

export default LanguageBar;
