/**
 * Translation + read-aloud for the public pages of stack.wecare.digital.
 *
 * Backed by the AWS site-language service, not the Cloud Run relay. Two reasons:
 * the relay's CORS allow-list admits only wecare.digital and www.wecare.digital
 * and answers stack.wecare.digital with a hard 403, and the AWS side caches
 * translations in DynamoDB so the same string is not paid for twice.
 *
 * Contract, verified live against api.wecare.digital:
 *
 *   GET  /site-language/languages
 *        -> { languages: [{ code, name }, ...] }            76 languages
 *   GET  /site-language/voices
 *        -> { voices: [{ id, languageCode, additionalLanguageCodes, ... }] }
 *   POST /site-language/translate
 *        { texts: [...], targetLanguage, sourceLanguage? }
 *        -> { translations: [{ translatedText, sourceLanguage, cached }] }
 *   POST /site-language/tts
 *        { text, language }
 *        -> { audioBase64, mimeType, voice, locale, engine }
 *
 * Note the shapes differ from the Cloud Run relay: translations are NOT wrapped
 * in a `data` envelope here, and audio arrives base64-encoded in JSON rather
 * than as a raw audio/mpeg body.
 *
 * Amazon Polly speaks far fewer languages than Amazon Translate can translate -
 * measured, only en and hi of the eleven Indian languages, with the other nine
 * returning 422. So speech availability is discovered from /voices at runtime
 * rather than assumed, and the Listen control simply does not appear for a
 * language Polly cannot voice.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const API_BASE =
  ( process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital' ) + '/site-language';

const LS_LANG = 'wc:stack:lang';

/** Handler caps: MAX_TEXTS 40, MAX_TOTAL_BYTES 30000. Kept under both. */
const MAX_BATCH_ITEMS = 30;
const MAX_BATCH_BYTES = 20000;
/** Handler cap: MAX_TTS_CHARS 2800. */
const MAX_SPEAK_CHARS = 2600;

/** Languages surfaced first, with native labels. Anything else the API reports
 *  is still offered, just under its English name. Escapes keep this file ASCII. */
const PREFERRED: Array<{ code: string; native: string }> = [
  { code: 'hi', native: '\u0939\u093f\u0928\u094d\u0926\u0940' },
  { code: 'bn', native: '\u09ac\u09be\u0982\u09b2\u09be' },
  { code: 'ta', native: '\u0ba4\u0bae\u0bbf\u0bb4\u0bcd' },
  { code: 'te', native: '\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41' },
  { code: 'mr', native: '\u092e\u0930\u093e\u0920\u0940' },
  { code: 'gu', native: '\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0' },
  { code: 'kn', native: '\u0c95\u0ca8\u0ccd\u0ca8\u0ca1' },
  { code: 'ml', native: '\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02' },
  { code: 'pa', native: '\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40' },
  { code: 'ur', native: '\u0627\u0631\u062f\u0648' },
];

const SKIP_TAGS = new Set( [
  'SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SVG', 'CANVAS', 'VIDEO', 'AUDIO',
  'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'CODE', 'PRE', 'HEAD', 'META', 'LINK',
] );

interface Lang { code: string; name: string; native?: string; canSpeak: boolean }

/** Text nodes worth translating, in document order. */
function collectTextNodes ( root: HTMLElement ): Text[] {
  const nodes: Text[] = [];
  let walker: TreeWalker;
  try
  {
    walker = document.createTreeWalker( root, NodeFilter.SHOW_TEXT, {
      acceptNode ( node: Node ) {
        const raw = node.nodeValue;
        if ( !raw ) return NodeFilter.FILTER_REJECT;
        const t = raw.trim();
        if ( t.length < 2 ) return NodeFilter.FILTER_REJECT;
        // Nothing to translate in pure numbers, punctuation or icon glyphs.
        if ( !/[A-Za-z\u0900-\u0DFF\u0600-\u06FF]/.test( t ) ) return NodeFilter.FILTER_REJECT;
        let el = node.parentElement;
        let depth = 0;
        while ( el && depth < 40 )
        {
          if ( SKIP_TAGS.has( el.tagName ) ) return NodeFilter.FILTER_REJECT;
          if ( el.dataset && el.dataset.wcNoTranslate === 'true' ) return NodeFilter.FILTER_REJECT;
          if ( el.getAttribute && el.getAttribute( 'aria-hidden' ) === 'true' ) return NodeFilter.FILTER_REJECT;
          el = el.parentElement;
          depth += 1;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    } );
  } catch
  {
    return nodes;
  }
  let n = walker.nextNode();
  while ( n )
  {
    nodes.push( n as Text );
    n = walker.nextNode();
  }
  return nodes;
}

/** Group nodes so no request exceeds either handler cap. Empty and oversized
 *  strings are dropped rather than sent, because the handler rejects the whole
 *  batch if any member is invalid. */
function buildBatches ( nodes: Text[] ): Array<Array<{ node: Text; text: string }>> {
  const batches: Array<Array<{ node: Text; text: string }>> = [];
  let current: Array<{ node: Text; text: string }> = [];
  let bytes = 0;

  for ( const node of nodes )
  {
    const text = ( node.nodeValue || '' ).trim();
    if ( !text ) continue;
    const size = new Blob( [ text ] ).size;
    if ( size > MAX_BATCH_BYTES ) continue;

    if ( current.length >= MAX_BATCH_ITEMS || bytes + size > MAX_BATCH_BYTES )
    {
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
  let total = 0;
  for ( const node of collectTextNodes( root ) )
  {
    const t = ( node.nodeValue || '' ).replace( /\s+/g, ' ' ).trim();
    if ( !t ) continue;
    if ( parts.length && parts[ parts.length - 1 ] === t ) continue;
    parts.push( t );
    total += t.length + 2;
    if ( total >= MAX_SPEAK_CHARS ) break;
  }
  return parts.join( '. ' ).slice( 0, MAX_SPEAK_CHARS );
}

const LanguageBar: React.FC = () => {
  const [ langs, setLangs ] = useState<Lang[]>( [] );
  const [ current, setCurrent ] = useState( 'en' );
  const [ open, setOpen ] = useState( false );
  const [ busy, setBusy ] = useState( false );
  const [ speaking, setSpeaking ] = useState( false );
  const [ status, setStatus ] = useState( '' );

  const originals = useRef<Map<Text, string> | null>( null );
  const audioRef = useRef<HTMLAudioElement | null>( null );
  const abortRef = useRef<AbortController | null>( null );
  const rootRef = useRef<HTMLDivElement | null>( null );

  // ---- discover what the service can actually do -------------------------
  useEffect( () => {
    let cancelled = false;

    ( async () => {
      try
      {
        const [ lr, vr ] = await Promise.all( [
          fetch( `${API_BASE}/languages` ),
          fetch( `${API_BASE}/voices` ),
        ] );
        if ( !lr.ok || !vr.ok ) return;

        const languages: Array<{ code: string; name: string }> = ( await lr.json() ).languages || [];
        const voices: Array<{ languageCode: string; additionalLanguageCodes?: string[] }> =
          ( await vr.json() ).voices || [];

        const speakable = new Set<string>();
        for ( const v of voices )
        {
          for ( const code of [ v.languageCode, ...( v.additionalLanguageCodes || [] ) ] )
          {
            if ( !code ) continue;
            speakable.add( String( code ).toLowerCase().split( '-' )[ 0 ] );
          }
        }

        const byCode = new Map( languages.map( ( l ) => [ l.code, l.name ] ) );
        const ordered: Lang[] = [];

        ordered.push( {
          code: 'en',
          name: 'English',
          native: 'English',
          canSpeak: speakable.has( 'en' ),
        } );
        for ( const p of PREFERRED )
        {
          const name = byCode.get( p.code );
          if ( !name ) continue;
          ordered.push( { code: p.code, name, native: p.native, canSpeak: speakable.has( p.code ) } );
        }

        if ( !cancelled ) setLangs( ordered );
      } catch
      {
        // Service unreachable: render nothing rather than a dead control.
      }
    } )();

    return () => { cancelled = true; };
  }, [] );

  // Restore a saved choice once the catalogue is known.
  useEffect( () => {
    if ( !langs.length ) return;
    let saved: string | null = null;
    try { saved = localStorage.getItem( LS_LANG ); } catch { /* storage may be blocked */ }
    if ( saved && saved !== 'en' && langs.some( ( l ) => l.code === saved ) )
    {
      const timer = setTimeout( () => { void applyLanguage( saved as string ); }, 500 );
      return () => clearTimeout( timer );
    }
    return undefined;
  }, [ langs ] );

  // Close the menu on an outside click.
  useEffect( () => {
    if ( !open ) return undefined;
    const onDoc = ( e: MouseEvent ) => {
      if ( rootRef.current && !rootRef.current.contains( e.target as Node ) ) setOpen( false );
    };
    document.addEventListener( 'click', onDoc, true );
    return () => document.removeEventListener( 'click', onDoc, true );
  }, [ open ] );

  const contentRoot = useCallback( (): HTMLElement => {
    return ( document.querySelector( 'main' ) as HTMLElement )
      || ( document.getElementById( '__next' ) as HTMLElement )
      || document.body;
  }, [] );

  const restore = useCallback( () => {
    const map = originals.current;
    if ( !map ) return;
    map.forEach( ( value, node ) => {
      try { if ( node.parentNode ) node.nodeValue = value; } catch { /* node detached */ }
    } );
  }, [] );

  const stopSpeaking = useCallback( () => {
    try { abortRef.current?.abort(); } catch { /* already settled */ }
    abortRef.current = null;
    const a = audioRef.current;
    if ( a )
    {
      try { a.pause(); a.removeAttribute( 'src' ); a.load(); } catch { /* ignore */ }
    }
    audioRef.current = null;
    setSpeaking( false );
  }, [] );

  // ---- translate ---------------------------------------------------------
  const applyLanguage = useCallback( async ( code: string ) => {
    setOpen( false );
    stopSpeaking();
    if ( busy ) return;

    setCurrent( code );
    try { localStorage.setItem( LS_LANG, code ); } catch { /* storage may be blocked */ }

    if ( code === 'en' )
    {
      restore();
      document.documentElement.lang = 'en';
      setStatus( 'Showing the original English text.' );
      return;
    }

    const label = langs.find( ( l ) => l.code === code )?.name || code;
    setBusy( true );
    setStatus( `Translating to ${label}.` );

    try
    {
      const nodes = collectTextNodes( contentRoot() );
      if ( !originals.current )
      {
        originals.current = new Map();
        for ( const n of nodes ) originals.current.set( n, n.nodeValue || '' );
      }
      // Always translate from the English source, never from a translation.
      restore();

      const batches = buildBatches( nodes );
      let done = 0;

      for ( const batch of batches )
      {
        const res = await fetch( `${API_BASE}/translate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify( {
            texts: batch.map( ( b ) => b.text ),
            targetLanguage: code,
            sourceLanguage: 'en',
          } ),
        } );
        if ( !res.ok )
        {
          if ( done === 0 )
          {
            restore();
            setCurrent( 'en' );
            setStatus( 'Translation is unavailable right now.' );
            return;
          }
          break;
        }
        const rows: Array<{ translatedText?: string }> = ( await res.json() ).translations || [];
        if ( rows.length !== batch.length ) break;
        for ( let i = 0; i < batch.length; i += 1 )
        {
          const t = rows[ i ]?.translatedText;
          try { if ( t ) batch[ i ].node.nodeValue = t; } catch { /* node detached */ }
        }
        done += batch.length;
      }

      document.documentElement.lang = code;
      setStatus( `Page translated to ${label}.` );
    } catch
    {
      setStatus( 'Translation failed.' );
    } finally
    {
      setBusy( false );
    }
  }, [ busy, contentRoot, langs, restore, stopSpeaking ] );

  // ---- read aloud --------------------------------------------------------
  const speak = useCallback( async () => {
    if ( speaking ) { stopSpeaking(); setStatus( 'Stopped reading.' ); return; }

    const text = readableText( contentRoot() );
    if ( !text ) { setStatus( 'Nothing on this page can be read aloud.' ); return; }

    const controller = new AbortController();
    abortRef.current = controller;
    setSpeaking( true );
    setStatus( 'Preparing audio.' );

    try
    {
      const res = await fetch( `${API_BASE}/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify( { text, language: current } ),
        signal: controller.signal,
      } );
      if ( !res.ok )
      {
        // 422 means Polly has no voice for this language.
        setStatus( res.status === 422
          ? 'Audio is not available in this language.'
          : 'Audio is unavailable right now.' );
        setSpeaking( false );
        return;
      }

      const body = await res.json();
      if ( !body.audioBase64 ) { setStatus( 'Audio is unavailable right now.' ); setSpeaking( false ); return; }

      // The service returns base64 in JSON rather than a raw audio body.
      const audio = new Audio( `data:${body.mimeType || 'audio/mpeg'};base64,${body.audioBase64}` );
      audioRef.current = audio;
      audio.addEventListener( 'ended', () => { setSpeaking( false ); setStatus( 'Finished reading.' ); } );
      audio.addEventListener( 'error', () => { setSpeaking( false ); setStatus( 'Playback failed.' ); } );
      await audio.play();
      setStatus( 'Reading this page.' );
    } catch ( err )
    {
      if ( ( err as Error )?.name !== 'AbortError' ) setStatus( 'Audio stopped unexpectedly.' );
      setSpeaking( false );
    }
  }, [ contentRoot, current, speaking, stopSpeaking ] );

  const canSpeakNow = useMemo(
    () => langs.find( ( l ) => l.code === current )?.canSpeak === true,
    [ current, langs ]
  );
  const currentLabel = useMemo( () => {
    const l = langs.find( ( x ) => x.code === current );
    return l?.native || l?.name || 'English';
  }, [ current, langs ] );

  // Nothing discovered means the service is unreachable; stay invisible.
  if ( langs.length < 2 ) return null;

  return (
    <div ref={ rootRef } data-wc-no-translate="true" className="wc-langbar">
      <style jsx>{ `
        .wc-langbar {
          position: fixed; left: 16px; bottom: 16px; z-index: 900;
          display: flex; flex-direction: column; align-items: flex-start; gap: 8px;
          font-family: inherit;
        }
        .bar {
          display: flex; align-items: center; gap: 6px; background: #fff;
          border: 1px solid #e5e7eb; border-radius: 13px; padding: 6px;
          box-shadow: 0 4px 16px rgba(16, 32, 24, 0.14);
        }
        .btn {
          display: inline-flex; align-items: center; gap: 6px; min-height: 40px;
          padding: 8px 12px; border: 0; border-radius: 9px; background: #f4f7f5;
          color: #1a3a2a; font-size: 14px; font-weight: 600; line-height: 1; cursor: pointer;
        }
        .btn:hover:not(:disabled) { background: #e6ece8; }
        .btn:focus-visible { outline: 3px solid #1a3a2a; outline-offset: 2px; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn.on { background: #1a3a2a; color: #fff; }
        .menu {
          display: none; max-height: min(60vh, 380px); overflow-y: auto; background: #fff;
          border: 1px solid #e5e7eb; border-radius: 13px; padding: 6px; min-width: 200px;
          box-shadow: 0 8px 28px rgba(16, 32, 24, 0.18);
        }
        .menu.open { display: block; }
        .opt {
          display: flex; justify-content: space-between; align-items: center; gap: 10px;
          width: 100%; min-height: 40px; padding: 9px 11px; border: 0; border-radius: 9px;
          background: transparent; color: #1a3a2a; font-size: 14px; text-align: left; cursor: pointer;
        }
        .opt:hover { background: #f4f7f5; }
        .opt:focus-visible { outline: 3px solid #1a3a2a; outline-offset: -3px; }
        .opt[aria-current='true'] { background: #1a3a2a; color: #fff; font-weight: 600; }
        .muted { opacity: 0.65; font-size: 12px; }
        .sr {
          position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0;
          overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
        }
        @media (max-width: 600px) { .wc-langbar { left: 10px; bottom: 10px; } }
        @media print { .wc-langbar { display: none; } }
      ` }</style>

      <div className={ `menu ${open ? 'open' : ''}` } role="menu" id="wc-langbar-menu" aria-label="Choose a language">
        { langs.map( ( l ) => (
          <button
            key={ l.code }
            type="button"
            role="menuitem"
            className="opt"
            aria-current={ l.code === current ? 'true' : 'false' }
            onClick={ () => { void applyLanguage( l.code ); } }
          >
            <span>{ l.native || l.name }</span>
            <span className="muted">{ l.canSpeak ? l.name : `${l.name} - text only` }</span>
          </button>
        ) ) }
      </div>

      <div className="bar">
        <button
          type="button"
          className="btn"
          aria-expanded={ open }
          aria-haspopup="menu"
          aria-controls="wc-langbar-menu"
          disabled={ busy }
          onClick={ () => setOpen( ( v ) => !v ) }
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
            <path d="M3 12h18M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18"
              stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
          <span>{ busy ? 'Translating...' : currentLabel }</span>
        </button>

        { canSpeakNow && (
          <button
            type="button"
            className={ `btn ${speaking ? 'on' : ''}` }
            aria-pressed={ speaking }
            aria-label={ speaking ? 'Stop reading this page' : 'Read this page aloud' }
            onClick={ () => { void speak(); } }
          >
            { speaking ? (
              <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true">
                <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
              </svg>
            ) : (
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M11 5 6 9H3v6h3l5 4V5Z" stroke="currentColor" strokeWidth="1.7"
                  strokeLinecap="round" strokeLinejoin="round" />
                <path d="M16 9a4 4 0 0 1 0 6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
              </svg>
            ) }
            <span>{ speaking ? 'Stop' : 'Listen' }</span>
          </button>
        ) }
      </div>

      <div className="sr" role="status" aria-live="polite">{ status }</div>
    </div>
  );
};

export default LanguageBar;
