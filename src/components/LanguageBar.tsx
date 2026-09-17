import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const API_BASE = ( process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital' ) + '/site-language';
const RELAY = 'https://wecare-translation-relay-hrkl3sncxq-el.a.run.app';
const LS_LANG = 'wc:stack:lang';
const SS_PROVIDER = 'wc:stack:langprovider';
const MAX_BATCH_ITEMS = 30;
const MAX_BATCH_BYTES = 20000;
const MAX_SPEAK_CHARS = 2600;

type Provider = 'google' | 'aws';
interface Lang { code: string; name: string; native?: string; canSpeak: boolean }

const NATIVE: Record<string, string> = {
  en: 'English', hi: 'हिन्दी', bn: 'বাংলা', ta: 'தமிழ்', te: 'తెలుగు', mr: 'मराठी',
  gu: 'ગુજરાતી', kn: 'ಕನ್ನಡ', ml: 'മലയാളം', pa: 'ਪੰਜਾਬੀ', ur: 'اردو',
};

const GOOGLE_VOICE: Record<string, string> = {
  en: 'en-IN', hi: 'hi-IN', bn: 'bn-IN', ta: 'ta-IN', te: 'te-IN', mr: 'mr-IN',
  gu: 'gu-IN', kn: 'kn-IN', ml: 'ml-IN', pa: 'pa-IN', ur: 'ur-IN',
};

const SKIP_TAGS = new Set( [
  'SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SVG', 'CANVAS', 'VIDEO', 'AUDIO',
  'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'CODE', 'PRE', 'HEAD', 'META', 'LINK',
] );

async function probeGoogle (): Promise<boolean> {
  try {
    const saved = sessionStorage.getItem( SS_PROVIDER );
    if ( saved === 'google' ) return true;
    if ( saved === 'aws' ) return false;
  } catch { /* storage may be unavailable */ }

  let works = false;
  try {
    const response = await fetch( RELAY, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify( { texts: [ 'ok' ], targetLanguage: 'hi', sourceLanguage: 'en' } ),
    } );
    works = response.ok;
  } catch { works = false; }

  try { sessionStorage.setItem( SS_PROVIDER, works ? 'google' : 'aws' ); } catch { /* ignore */ }
  return works;
}

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
  const providerRef = useRef<Provider>( 'aws' );

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
        const google = await probeGoogle();
        providerRef.current = google ? 'google' : 'aws';
        const languageResponse = await fetch( `${API_BASE}/languages` );
        if ( !languageResponse.ok ) return;
        const rows: Array<{ code: string; name: string }> = ( await languageResponse.json() ).languages || [];
        let speakable = new Set<string>();
        if ( google ) {
          speakable = new Set( Object.keys( GOOGLE_VOICE ) );
        } else {
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
        }
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
      const google = providerRef.current === 'google';
      for ( const batch of buildBatches( nodes ) ) {
        const response = await fetch( google ? RELAY : `${API_BASE}/translate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify( { texts: batch.map( item => item.text ), targetLanguage: code, sourceLanguage: 'en' } ),
        } );
        if ( !response.ok ) throw new Error( 'translate failed' );
        const payload = await response.json();
        const translated: Array<{ translatedText?: string }> = ( google ? payload?.data?.translations : payload?.translations ) || [];
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
      const google = providerRef.current === 'google';
      const base = current.toLowerCase().split( '-' )[ 0 ];
      const response = await fetch( google ? RELAY : `${API_BASE}/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify( google ? { text, languageCode: GOOGLE_VOICE[ base ] || 'en-IN' } : { text, language: current } ),
      } );
      if ( !response.ok ) throw new Error( 'tts failed' );
      let src = '';
      let revoke = false;
      if ( google ) {
        src = URL.createObjectURL( await response.blob() );
        revoke = true;
      } else {
        const body = await response.json();
        if ( !body.audioBase64 ) throw new Error( 'missing audio' );
        src = `data:${body.mimeType || 'audio/mpeg'};base64,${body.audioBase64}`;
      }
      const audio = new Audio( src );
      audioRef.current = audio;
      const finish = () => { if ( revoke ) URL.revokeObjectURL( src ); setSpeaking( false ); };
      audio.addEventListener( 'ended', () => { finish(); setStatus( 'Finished reading.' ); } );
      audio.addEventListener( 'error', () => { finish(); setStatus( 'Playback failed.' ); } );
      await audio.play();
      setStatus( 'Reading this page.' );
    } catch { setSpeaking( false ); setStatus( 'Audio is unavailable right now.' ); }
  }, [ contentRoot, current, speaking, stopSpeaking ] );

  const filtered = useMemo( () => {
    const term = query.trim().toLocaleLowerCase();
    if ( !term ) return [];
    return langs.filter( lang => [ lang.code, lang.name, lang.native || '' ].some( value => value.toLocaleLowerCase().includes( term ) ) ).slice( 0, 12 );
  }, [ langs, query ] );

  const selected = langs.find( lang => lang.code === current );
  const canSpeak = selected?.canSpeak === true;

  if ( typeof window !== 'undefined' && window.location.pathname === '/' ) return null;
  if ( langs.length < 2 ) return null;

  return (
    <div ref={ rootRef } data-wc-no-translate="true" className="wc-langbar">
      <style jsx>{`
        .wc-langbar{position:fixed;left:16px;top:50%;transform:translateY(-50%);z-index:900;display:flex;flex-direction:column;align-items:flex-start;gap:8px;font-family:inherit}
        .panel{display:none;width:min(320px,calc(100vw - 32px));background:#fff;border:1px solid #e5e7eb;border-radius:15px;padding:10px;box-shadow:0 12px 36px rgba(16,32,24,.18)}
        .panel.open{display:block}
        .search{width:100%;min-height:44px;box-sizing:border-box;border:1px solid #d1d5db;border-radius:10px;padding:10px 12px;font:600 15px/1.2 inherit;color:#1a3a2a;outline:none}
        .search:focus{border-color:#1a3a2a;box-shadow:0 0 0 3px rgba(26,58,42,.12)}
        .results{max-height:310px;overflow:auto;margin-top:8px}
        .hint{padding:12px;color:#6b7280;font-size:14px}
        .opt{width:100%;min-height:44px;border:0;border-radius:9px;background:transparent;padding:9px 10px;display:flex;justify-content:space-between;gap:12px;align-items:center;text-align:left;color:#1a3a2a;cursor:pointer}
        .opt:hover,.opt:focus-visible{background:#f4f7f5;outline:none}
        .opt[aria-current='true']{background:#1a3a2a;color:#fff}
        .meta{opacity:.65;font-size:12px;white-space:nowrap}
        .bar{display:flex;align-items:center;gap:6px;background:#fff;border:1px solid #e5e7eb;border-radius:13px;padding:6px;box-shadow:0 4px 16px rgba(16,32,24,.14)}
        .btn{display:inline-flex;align-items:center;gap:7px;min-height:44px;padding:9px 12px;border:0;border-radius:9px;background:#f4f7f5;color:#1a3a2a;font-size:14px;font-weight:700;cursor:pointer}
        .btn:hover:not(:disabled){background:#e6ece8}.btn:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}.btn:disabled{opacity:.5;cursor:not-allowed}.btn.on{background:#1a3a2a;color:#fff}
        .sr{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
        @media(max-width:600px){.wc-langbar{left:10px;top:auto;bottom:calc(10px + env(safe-area-inset-bottom));transform:none}.panel{width:min(300px,calc(100vw - 20px))}}
        @media print{.wc-langbar{display:none}}
      `}</style>

      <div className={ `panel ${open ? 'open' : ''}` }>
        <input
          className="search"
          type="search"
          value={ query }
          placeholder="Search language..."
          aria-label="Search languages"
          autoFocus={ open }
          onChange={ event => setQuery( event.target.value ) }
          onKeyDown={ event => { if ( event.key === 'Escape' ) setOpen( false ); } }
        />
        <div className="results" role="listbox" aria-label="Language results">
          { !query.trim() && <div className="hint">Type a language name or code.</div> }
          { query.trim() && !filtered.length && <div className="hint">No matching language.</div> }
          { filtered.map( lang => (
            <button key={ lang.code } type="button" className="opt" role="option" aria-selected={ lang.code === current } aria-current={ lang.code === current ? 'true' : 'false' } onClick={ () => { void applyLanguage( lang.code ); } }>
              <span>{ lang.native ? `${lang.native} · ${lang.name}` : lang.name }</span>
              <span className="meta">{ lang.code }</span>
            </button>
          ) ) }
        </div>
      </div>

      <div className="bar">
        <button type="button" className="btn" aria-expanded={ open } aria-label="Choose language" disabled={ busy } onClick={ () => setOpen( value => !value ) }>
          <span aria-hidden="true">◎</span>
          <span>{ busy ? 'Translating...' : ( selected?.native || selected?.name || 'English' ) }</span>
        </button>
        { canSpeak && (
          <button type="button" className={ `btn ${speaking ? 'on' : ''}` } aria-pressed={ speaking } onClick={ () => { void speak(); } }>
            { speaking ? 'Stop' : 'Listen' }
          </button>
        ) }
      </div>
      <div className="sr" role="status" aria-live="polite">{ status }</div>
    </div>
  );
};

export default LanguageBar;
