import React, { useCallback, useEffect, useRef, useState } from 'react';
import { whatsappShareHref } from '../config/share';

/**
 * SHARE THIS PAGE: WhatsApp, the OS share sheet, and copy-link.
 *
 * THE BASELINE WORKS WITH NO JAVASCRIPT AT ALL. The WhatsApp control is a real anchor with a
 * real href, rendered into the static export, so it is a working link in the HTML before any
 * bundle arrives. The other two cannot be - a share sheet and a clipboard write are both
 * script-only - so they are rendered but hidden, and revealed by class once the page has
 * confirmed the browser actually has the API. A control that is visible and does nothing is
 * worse than one that is absent.
 *
 * FEATURE DETECTION, NEVER DEVICE DETECTION. Nothing here reads a user agent, a screen width or
 * a touch capability. navigator.share is absent on most desktop browsers and present on iOS
 * Safari, Safari on macOS and Chrome on Android, and that set does not map onto "is this a
 * phone" - a desktop Safari user gets a share sheet and a desktop Firefox user does not. Asking
 * for the API is the only question that answers itself correctly, and it keeps working as the
 * support matrix moves without anyone editing a list of devices.
 *
 * THE DETECTION WRITES A CLASS, NOT STATE, and that is deliberate on two counts. It is a visual
 * side effect that does not change what React renders, which is the documented use for an effect
 * and what the home page's reveal already does. And setState in an effect is what
 * react-hooks/set-state-in-effect exists to prevent - BlogIndexView already carries one such
 * error and this file does not add a second. `copied` IS state, because it is set from a click
 * handler rather than an effect, which is the case the rule permits.
 *
 * NO HYDRATION MISMATCH BY CONSTRUCTION: the markup is identical on the server and the client,
 * and only a className on the wrapper changes afterwards. Nothing is conditionally rendered on a
 * value the server cannot know.
 */

type Props = {
  /** Absolute, canonical URL. A share target that receives a relative path shares nothing. */
  url: string;
  /** Plain text. It becomes the first line of a WhatsApp message and the share-sheet title. */
  title: string;
  /** Labels the row. The post page passes its own so the eyebrow matches the page's furniture. */
  label?: string;
};

const ShareLinks: React.FC<Props> = ( { url, title, label = 'Share' } ) => {
  const rowRef = useRef<HTMLDivElement | null>( null );
  const timer = useRef<ReturnType<typeof setTimeout> | null>( null );
  const [ copied, setCopied ] = useState( false );

  useEffect( () => {
    const el = rowRef.current;
    if ( !el ) return;
    // navigator.share can exist and still be unusable: it is gated by the web-share permission
    // policy, so an embedded document can carry the method and reject the call. canShare is the
    // question that accounts for that, with a plain existence check as the fallback for browsers
    // that shipped share() before canShare().
    const payload = { title, text: title, url };
    const canNative = typeof navigator !== 'undefined' && typeof navigator.share === 'function'
      && ( typeof navigator.canShare !== 'function' || navigator.canShare( payload ) );
    if ( canNative ) el.classList.add( 'is-native' );
    // Clipboard writes need a secure context. The site is HTTPS-only, but a file:// or http://
    // preview is a real way to open this page and the button should not appear there.
    if ( typeof navigator !== 'undefined' && navigator.clipboard && window.isSecureContext ) {
      el.classList.add( 'is-clip' );
    }
  }, [ title, url ] );

  // Clearing the timer on unmount is not hygiene theatre: navigating away from a post inside the
  // two-second window would otherwise set state on an unmounted component.
  useEffect( () => () => { if ( timer.current ) clearTimeout( timer.current ); }, [] );

  const onNative = useCallback( () => {
    // Fired from a click so the call still holds transient user activation, which the API
    // requires. A share() invoked from a timeout or a promise chain is rejected.
    navigator.share( { title, text: title, url } ).catch( () => {
      // AbortError is the normal path: it is what the browser throws when the reader closes the
      // sheet without choosing a target. Nothing to report and nothing to recover.
    } );
  }, [ title, url ] );

  const onCopy = useCallback( async () => {
    try {
      await navigator.clipboard.writeText( url );
      setCopied( true );
      if ( timer.current ) clearTimeout( timer.current );
      timer.current = setTimeout( () => setCopied( false ), 2000 );
    } catch {
      // A rejected clipboard write is usually a denied permission. Saying nothing would leave
      // the reader pressing a dead button, so the link is selected instead and they can copy it
      // with the keyboard.
      const field = document.getElementById( 'share-url-fallback' ) as HTMLInputElement | null;
      if ( field ) { field.hidden = false; field.select(); }
    }
  }, [ url ] );

  return (
    <div className="share-row" ref={ rowRef }>
      <span className="share-label">{ label }</span>

      {/* WhatsApp. target=_blank with rel=noopener: api.whatsapp.com hands off to the app or to
          WhatsApp Web, and neither should be able to reach back into this page through
          window.opener. The mark is the same path SupportWidget draws, filled with currentColor
          so it inherits the button's colour in every state instead of carrying its own. */}
      <a
        className="share-btn"
        href={ whatsappShareHref( title, url ) }
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Share this page on WhatsApp"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path fill="currentColor" d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.26-.46-2.4-1.48-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.91-2.21-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.03 1.02-1.03 2.48 0 1.46 1.06 2.87 1.21 3.07.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.62.71.23 1.36.2 1.87.12.57-.09 1.76-.72 2-1.41.25-.7.25-1.29.18-1.42-.08-.12-.28-.2-.57-.35M12.05 21.79h-.01a9.87 9.87 0 01-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 01-1.51-5.26C2.16 6.45 6.6 2.01 12.05 2.01c2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 012.89 6.99c0 5.45-4.44 9.89-9.88 9.89M20.46 3.49A11.82 11.82 0 0012.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.88 11.88 0 005.69 1.45c6.55 0 11.89-5.34 11.89-11.89 0-3.18-1.24-6.17-3.48-8.42z" />
        </svg>
        WhatsApp
      </a>

      {/* The OS share sheet. Hidden until the effect above confirms the API, so it never appears
          as a button that cannot work. Three dots joined by two lines - drawn from circles and
          lines rather than set as a character, for the reason the pager's arrow is drawn: a
          glyph that the webfont does not cover renders as tofu. */}
      <button type="button" className="share-btn share-native" onClick={ onNative }>
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="18" cy="5" r="2.6" /><circle cx="6" cy="12" r="2.6" /><circle cx="18" cy="19" r="2.6" />
          <line x1="8.4" y1="13.4" x2="15.6" y2="17.6" /><line x1="15.6" y1="6.4" x2="8.4" y2="10.6" />
        </svg>
        Share
      </button>

      {/* Copy link. aria-live on the confirmation rather than on the button: announcing the whole
          button would re-read its label every time the label changed, and what a reader needs to
          hear is the outcome. It is polite so it waits for a gap rather than interrupting. */}
      <button type="button" className="share-btn share-copy" onClick={ onCopy }>
        { copied
          ? <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><polyline points="20 6 9 17 4 12" /></svg>
          : (
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M9 17H7.5a5 5 0 0 1 0-10H9" /><path d="M15 7h1.5a5 5 0 0 1 0 10H15" /><line x1="8" y1="12" x2="16" y2="12" />
            </svg>
          ) }
        { copied ? 'Copied' : 'Copy link' }
      </button>
      <span className="share-status" role="status" aria-live="polite">{ copied ? 'Link copied to clipboard' : '' }</span>

      {/* Only ever shown if a clipboard write is refused - see onCopy. readOnly rather than
          disabled, because a disabled field cannot be selected, which is the whole point. */}
      <input id="share-url-fallback" className="share-fallback" type="text" value={ url } readOnly hidden />

      <style jsx>{`
        /* THE ROW. 12px/700/.08em uppercase on the label is the site's eyebrow rung - the same
           declaration Breadcrumbs, the post pager and the related heading use - because this is
           furniture rather than a claim. */
        .share-row{display:flex;align-items:center;flex-wrap:wrap;gap:10px}
        .share-label{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a;margin-inline-end:2px}
        /* THE BUTTONS ARE THE HOME CTA AT A SMALLER RUNG. 2px edge because they are hoverable and
           the contract reserves 2px for that, 999px radius to match the category pills rather
           than the 50px of the full-size CTA, and the lime tint plus 2px lift plus the single
           permitted shadow on hover. 44px min-height is the WCAG 2.5.8 floor and every control
           on this page holds it.
           font:inherit on a button is not optional: a bare button takes the UA's font, which on
           Chrome is 13.33px Arial, so without it these would be the only text on the page not
           set in Inter. */
        .share-btn{
          display:inline-flex;align-items:center;gap:8px;
          min-height:44px;padding:0 16px;box-sizing:border-box;
          border:2px solid #e5e7eb;border-radius:999px;background:#fff;
          color:#1a3a2a;font:inherit;font-size:14px;font-weight:600;
          text-decoration:none;cursor:pointer;
          transition:background-color .2s,border-color .2s,transform .2s,box-shadow .2s;
        }
        .share-btn:hover{
          border-color:#d1f470;background:rgba(209,244,112,.28);
          transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12);
        }
        /* Opaque, not rgba(26,58,42,.25). The translucent ring measures 1.51:1 against white and
           fails WCAG 1.4.11; the home page moved off it and so does everything new. */
        .share-btn:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}
        .share-btn svg{width:17px;height:17px;flex:0 0 auto;display:block}
        /* The two drawn icons are stroked; the WhatsApp mark is filled and sets its own fill on
           the path, so a blanket fill here would flatten it. */
        .share-btn svg circle,.share-btn svg line,.share-btn svg polyline,.share-btn svg path:not([fill]){
          fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;
        }
        /* HIDDEN UNTIL THE API IS CONFIRMED. display:none rather than visibility or opacity, so
           the control is out of the tab order as well as out of sight - a focusable button that
           cannot work is worse for a keyboard reader than for anyone else. */
        .share-native,.share-copy{display:none}
        .share-row.is-native .share-native{display:inline-flex}
        .share-row.is-clip .share-copy{display:inline-flex}
        /* The confirmation is for screen readers; the button's own label already changed to
           "Copied" for everyone else. Same clip technique as the pager's .pager-sr. */
        .share-status{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
        .share-fallback{
          flex:1 1 220px;min-width:0;min-height:44px;padding:0 12px;
          border:2px solid #d1f470;border-radius:12px;background:#fff;
          color:#1a3a2a;font:inherit;font-size:14px;
        }
        @media(prefers-reduced-motion:reduce){
          .share-btn{transition:none}
          .share-btn:hover{transform:none;box-shadow:none}
        }
      `}</style>
    </div>
  );
};

export default ShareLinks;
