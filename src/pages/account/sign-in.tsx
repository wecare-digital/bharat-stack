/**
 * /account/sign-in/ - the customer OTP sign-in / register step that gates checkout.
 *
 * WHAT THIS IS. A minimal WhatsApp-OTP sign-in built on src/lib/customerAuth.ts, reached when a
 * shopper proceeds from the cart without a session. It signs the shopper in and returns them to
 * the cart (or wherever `return` in the query string points) with the cart intact - the cart lives
 * in localStorage (src/lib/cart.ts), so it survives this hop untouched.
 *
 * WHAT THIS IS NOT. It does not reimplement any OTP crypto: requestOtp / submitOtp talk to Cognito
 * directly and the code is delivered over WhatsApp by the pool trigger. This page only collects a
 * number and a code and calls those functions.
 *
 * THE COUNTRY CODE IS AN EXPLICIT, REQUIRED FIELD, on owner instruction.
 * customerAuth.normaliseMobile() infers +91 for any ten digits beginning 6-9, which is right for
 * this market and silent everywhere else: a ten-digit number from another country was accepted and
 * then signed in as an Indian one. That function is NOT changed - its docblock requires it to match
 * the backend's normalisation byte for byte, and a disagreement means a customer signs in
 * successfully and owns nothing. So the dial code is composed here instead, ahead of it: this page
 * always hands over a string that already carries a country code, which leaves normaliseMobile
 * nothing to infer and reduces it to the length check it also performs on the server. The select
 * defaults to +91 because that is the market, not because the field is optional - it is `required`,
 * always submitted, and always applied.
 *
 * THE "NOT A WHATSAPP NUMBER" ERROR IS WIRED TO THE ONLY SIGNAL THAT EXISTS, and is worded for what
 * that signal actually proves. The registration front door answers 502 {status:'send_failed'} when
 * the challenge was stored but the WhatsApp message did not go - which is what happens when the
 * number is not reachable on WhatsApp, and ALSO what happens when Meta's send fails transiently.
 * So the copy says the number could not be reached and asks the shopper to check it, rather than
 * asserting it is not a WhatsApp number. Telling someone their number is invalid when the real
 * cause was our own outage is the kind of confident wrong answer this repo keeps removing. A
 * definitive message needs the recipient-not-found code from Meta surfaced by the backend; see
 * docs/execution/website-payment-handover.md.
 *
 * THE HONEST UNREGISTERED-NUMBER HANDLING. customerAuth.ts documents that Cognito returns a masked
 * challenge for an UNKNOWN number too (PreventUserExistenceErrors), and no code is ever sent to
 * one - so claiming "we sent you a code" would be a lie for a number that is not a customer. When
 * requestOtp reports `registered: false` this page does NOT show an OTP box; it routes the shopper
 * through the registration front door (POST /auth/customer-registration {action:'request'|'verify'})
 * to create the customer, then completes sign-in via customerAuth.submitOtp.
 *
 * TWO CODES, NOT ONE, ON THE REGISTER PATH. The registration handler never returns a session
 * credential - "the session credential comes from the Cognito sign-in, not from here." So once
 * `verify` provisions the login, the shopper still has to complete the ordinary WhatsApp-OTP
 * CUSTOM_AUTH sign-in, and that Cognito challenge sends its OWN, second code. This page treats that
 * as its own step (the `signin-code` phase): it starts the Cognito challenge, says a fresh code is
 * on its way, and answers the challenge with THAT code - it never replays the registration code,
 * which Cognito would reject.
 *
 * CHROME AND INDEXING. This is a customer-session route registered in the _app.tsx isPublic chain
 * beside /checkout/status and /checkout/success; it is noindex and imports no Layout/Header/Footer/
 * SupportWidget (those are mounted centrally). It is intentionally absent from PUBLIC_PAGE_META,
 * the sitemap and the browser route lists.
 */

import Head from 'next/head';
import Link from 'next/link';
import React, { useCallback, useEffect, useState } from 'react';

import PageTopBand from '../../components/PageTopBand';
import {
  requestOtp, submitOtp, normaliseMobile, getSession, nextSessionFrom,
} from '../../lib/customerAuth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
const REGISTRATION_URL = `${API_BASE}/auth/customer-registration`;

/**
 * The dial codes this store sells into.
 *
 * SHORT AND NAMED, not a generated list of all 249 calling codes. A select a shopper has to scroll
 * through to find the one they almost certainly want is worse than a short list plus a clear way to
 * ask us; these are India plus the places this catalogue's customers write in from. Each entry is
 * the dial code and the country, so the option text says which is which rather than leaving a bare
 * +1 ambiguous. The option LABEL is a text node, so it translates; the dial code is a number and
 * carries data-wc-no-translate on the control for the same reason prices do.
 */
const DIAL_CODES: { code: string; label: string }[] = [
  { code: '91', label: 'India +91' },
  { code: '971', label: 'United Arab Emirates +971' },
  { code: '966', label: 'Saudi Arabia +966' },
  { code: '65', label: 'Singapore +65' },
  { code: '44', label: 'United Kingdom +44' },
  { code: '1', label: 'United States / Canada +1' },
  { code: '61', label: 'Australia +61' },
];

/** The market. The field is required, not optional - this is its starting value, not a fallback. */
const DEFAULT_DIAL_CODE = '91';

/** Where to send the shopper once signed in. Defaults to the cart. */
function returnPathFromUrl (): string {
  if ( typeof window === 'undefined' ) return '/cart/';
  const raw = String( new URLSearchParams( window.location.search ).get( 'return' ) || '' ).trim();
  // Only same-site absolute paths, so this can never be turned into an open redirect.
  return /^\/[a-zA-Z0-9/_-]*\/?$/.test( raw ) ? raw : '/cart/';
}

/**
 * The step the form is on.
 *   'phone'         collect the country code and the number.
 *   'code'          registered path: answer the live Cognito challenge from requestOtp.
 *   'register-code' unregistered path: answer the registration front-door OTP (creates the customer).
 *   'signin-code'   unregistered path, second leg: answer the SECOND, Cognito sign-in code that the
 *                   CUSTOM_AUTH challenge sends after the customer is provisioned.
 */
type Phase = 'phone' | 'code' | 'register-code' | 'signin-code';

export default function CustomerSignIn (): React.ReactElement {
  const [ phase, setPhase ] = useState<Phase>( 'phone' );
  const [ dialCode, setDialCode ] = useState<string>( DEFAULT_DIAL_CODE );
  const [ mobile, setMobile ] = useState<string>( '' );
  const [ normalised, setNormalised ] = useState<string>( '' );
  const [ code, setCode ] = useState<string>( '' );
  const [ session, setSession ] = useState<string>( '' );
  const [ destination, setDestination ] = useState<string>( '' );
  const [ error, setError ] = useState<string>( '' );
  const [ busy, setBusy ] = useState<boolean>( false );

  // Already signed in: nothing to do here, go straight back.
  useEffect( () => {
    if ( getSession() ) window.location.replace( returnPathFromUrl() );
  }, [] );

  /**
   * Dial code + the typed number, as the E.164 string the backend will key the customer on.
   *
   * A LEADING + OR 00 IS THE ONLY THING THAT MAKES A TYPED PREFIX A COUNTRY CODE, and the
   * distinction is load-bearing rather than fussy. "+91 98765 43210" with India selected must not
   * become +919198765..., so the selected code is stripped back off when the shopper has pasted a
   * full international number. But a BARE "9198765432" is a perfectly valid ten-digit Indian
   * number, and stripping "91" off that would sign in a different, non-existent customer - so the
   * prefix is only ever removed when the shopper typed it as one.
   */
  const composeE164 = useCallback( (): string => {
    const raw = String( mobile || '' ).trim();
    const typedInternational = /^(\+|00)/.test( raw );
    let digits = raw.replace( /\D/g, '' );
    if ( typedInternational )
    {
      digits = digits.replace( /^0+/, '' );
      if ( digits.startsWith( dialCode ) ) digits = digits.slice( dialCode.length );
    }
    if ( !digits ) throw new Error( 'Enter your mobile number' );
    // normaliseMobile is the single source of the E.164 rule and the length bound, and is NOT
    // changed - it has to match the backend byte for byte. It is handed a string that already
    // carries the country code, so its ten-digit +91 inference cannot fire.
    return normaliseMobile( `${dialCode}${digits}` );
  }, [ dialCode, mobile ] );

  const startPhone = useCallback( async ( event: React.FormEvent ): Promise<void> => {
    event.preventDefault();
    setError( '' );
    let e164 = '';
    try
    {
      e164 = composeE164();
    }
    catch ( err )
    {
      setError( ( err as Error ).message );
      return;
    }
    setBusy( true );
    try
    {
      const challenge = await requestOtp( e164 );
      setNormalised( e164 );
      if ( challenge.registered )
      {
        // A real customer: Cognito's challenge is live, so the code was genuinely sent.
        setSession( challenge.session );
        setDestination( challenge.destination );
        setPhase( 'code' );
      }
      else
      {
        // Unknown number. NO code was sent (see customerAuth.ts), so do not pretend one was -
        // register the number through the front door, which sends its own WhatsApp OTP.
        //
        // SAFETY CONTRACT: this branch discards `challenge.session` and pushes the shopper into
        // registration. That is only correct while the CreateAuthChallenge trigger guarantees it
        // sends NO WhatsApp code when it reports `registered:false` - i.e. `registered:false`
        // means "no live code is outstanding," never "a code was sent to a real customer." If the
        // trigger ever changes to send a code alongside `registered:false`, this branch would
        // strand that real customer (their live Cognito code is thrown away and they are asked to
        // register instead), and it must switch to honouring `challenge.session` here.
        const response = await fetch( REGISTRATION_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify( { action: 'request', phone: e164 } ),
        } );
        if ( !response.ok )
        {
          // 502 send_failed is the one signal that distinguishes "we could not deliver to this
          // number over WhatsApp" from any other refusal. It cannot prove the number is not on
          // WhatsApp - a Meta outage looks identical from here - so the copy asks rather than
          // asserts. Anything else is a generic failure and says so.
          const data = ( await response.json().catch( () => ( {} ) ) ) as { status?: string };
          const sendFailed = response.status === 502
            || String( data.status || '' ).toLowerCase() === 'send_failed';
          setError( sendFailed
            ? 'We could not reach that number on WhatsApp. Check the country code and that it is your WhatsApp number.'
            : 'We could not send a code. Please try again.' );
          return;
        }
        setDestination( '' );
        setPhase( 'register-code' );
      }
    }
    catch ( err )
    {
      setError( ( err as Error ).message || 'We could not send a code. Please try again.' );
    }
    finally
    {
      setBusy( false );
    }
  }, [ composeE164 ] );

  const submitCode = useCallback( async ( event: React.FormEvent ): Promise<void> => {
    event.preventDefault();
    setError( '' );
    setBusy( true );
    try
    {
      if ( phase === 'register-code' )
      {
        // Leg one of the register path: verify the FRONT-DOOR code, which provisions the login.
        // This does NOT sign the shopper in - the registration handler never returns a session.
        const response = await fetch( REGISTRATION_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify( { action: 'verify', phone: normalised, code: code.trim() } ),
        } );
        if ( !response.ok )
        {
          setError( 'That code was not accepted. Please try again.' );
          return;
        }
        // Leg two: start the Cognito CUSTOM_AUTH sign-in, which sends its own, SECOND code. Move to
        // a fresh code step and clear the input so the shopper enters that new code, not the old one.
        const challenge = await requestOtp( normalised );
        setSession( challenge.session );
        setDestination( challenge.destination );
        setCode( '' );
        setPhase( 'signin-code' );
        return;
      }

      // Registered path AND the second leg of the register path both answer a live Cognito
      // challenge with the code the shopper just entered against the session we hold.
      let result;
      try
      {
        result = await submitOtp( normalised, code, session );
      }
      catch ( err )
      {
        // Cognito failed the whole attempt but may hand back a session for a retry.
        const next = nextSessionFrom( err );
        if ( next ) setSession( next );
        setError( 'That code was not accepted. Please request a new code.' );
        return;
      }
      if ( !result )
      {
        // Wrong code, attempts remain.
        setError( 'That code was not right. Please try again.' );
        return;
      }
      window.location.replace( returnPathFromUrl() );
    }
    catch ( err )
    {
      setError( ( err as Error ).message || 'Something went wrong. Please try again.' );
    }
    finally
    {
      setBusy( false );
    }
  }, [ phase, normalised, code, session ] );

  return (
    <>
      <Head>
        <title>Sign in — WECARE.DIGITAL</title>
        {/* Customer-session, per-person, transactional: never indexed. */}
        <meta name="robots" content="noindex,nofollow" />
      </Head>
      <PageTopBand
        heading="Sign in to check out"
        sub="We confirm it is you with a code on WhatsApp. New here? Same step sets you up."
        ariaLabel="Customer sign in"
      >
        <div className="si-card">
          {phase === 'phone' && (
            <form className="si-form" onSubmit={ startPhone }>
              {/* The country code is its own labelled, required control rather than something
                  guessed from the digits. */}
              <label className="si-label" htmlFor="si-dial">Country code</label>
              <select
                id="si-dial"
                className="si-input si-select"
                value={ dialCode }
                required
                data-wc-no-translate="true"
                onChange={ e => setDialCode( e.target.value ) }
                disabled={ busy }
              >
                { DIAL_CODES.map( entry => (
                  <option key={ entry.code } value={ entry.code }>{ entry.label }</option>
                ) ) }
              </select>

              <label className="si-label" htmlFor="si-mobile">Mobile number</label>
              <input
                id="si-mobile"
                className="si-input"
                type="tel"
                inputMode="tel"
                autoComplete="tel-national"
                required
                value={ mobile }
                onChange={ e => setMobile( e.target.value ) }
                disabled={ busy }
              />
              {/* A text node, so it translates. It is also the only place this form says the code
                  arrives on WhatsApp before asking for a number that has to be one. */}
              <p className="si-hint">Use the number WhatsApp is on.</p>
              <button className="si-cta" type="submit" disabled={ busy }>
                { busy ? 'Sending…' : 'Send code' }
              </button>
            </form>
          )}

          {( phase === 'code' || phase === 'register-code' || phase === 'signin-code' ) && (
            <form className="si-form" onSubmit={ submitCode }>
              <p className="si-body">
                { phase === 'signin-code'
                  ? ( destination
                    ? `You're all set up. We've sent a new code over WhatsApp to ${destination} to sign you in. Enter it below.`
                    : "You're all set up. We've sent a new code over WhatsApp to sign you in. Enter it below." )
                  : ( phase === 'code' && destination
                    ? `We sent a code over WhatsApp to ${destination}. Enter it below.`
                    : 'We sent a code over WhatsApp. Enter it below to continue.' ) }
              </p>
              <label className="si-label" htmlFor="si-code">WhatsApp code</label>
              <input
                id="si-code"
                className="si-input"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={ code }
                onChange={ e => setCode( e.target.value ) }
                disabled={ busy }
              />
              <button className="si-cta" type="submit" disabled={ busy }>
                { busy ? 'Checking…' : 'Confirm code' }
              </button>
            </form>
          )}

          {error && <p className="si-error" role="alert">{ error }</p>}

          <p className="si-back"><Link href="/cart/">Back to your cart</Link></p>
        </div>

        <style jsx>{`
          /* No top padding, no measure, no font stack: PageTopBand owns all three. 460px is the
             form's own measure, inside the band's 1300px. */
          .si-card{width:100%;max-width:460px;margin:0}
          .si-form{display:flex;flex-direction:column}
          /* The body rung, 20px/400/1.4/-.125px at rgba(0,0,0,.898). It was 16px at .7 alpha,
             which is neither rung this site has. */
          .si-body{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0 0 24px;
          }
          .si-label{font-size:14px;font-weight:700;color:#1a3a2a;margin-bottom:8px}
          /* 52px, matching the CTA below it, so the field and the button it feeds are the same
             height. 1px #e5e7eb is the static hairline. */
          .si-input{
            min-height:52px;padding:0 16px;border:1px solid #e5e7eb;border-radius:10px;
            font-family:inherit;font-size:17px;color:#1a1a1a;background:#fff;margin-bottom:20px;
            box-sizing:border-box;
          }
          /* The select keeps the platform's own disclosure arrow - a CSS-drawn one would be a
             second chevron on a page that already has the header's, drawn by different means. */
          .si-select{width:100%;appearance:none;-webkit-appearance:none;padding-inline-end:40px}
          .si-input:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}
          .si-hint{
            margin:0 0 20px;font-size:16px;line-height:1.55;color:rgba(0,0,0,.54);
          }
          /* The single LIME actionable surface on this page: 52px, #d1f470 with #1a3a2a type, a
             2px border because 2px means hoverable, the 50px pill radius. */
          .si-cta{
            display:inline-flex;align-items:center;justify-content:center;min-height:52px;
            padding:0 26px;border:2px solid #d1f470;border-radius:50px;
            background:#d1f470;color:#1a3a2a;font-family:inherit;font-size:17px;font-weight:600;
            cursor:pointer;
            transition:background-color .2s,transform .2s,box-shadow .2s;
          }
          .si-cta:hover:not(:disabled){background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          .si-cta:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}
          .si-cta:disabled{opacity:.6;cursor:default}

          /* NO RED, ON OWNER INSTRUCTION. This was #fbe9e9 on #f0c0c0 with #8a1f1f text - three
             colours the home design does not contain, on a site whose only red is the full stop in
             the wordmark. It is now the lime state tint behind a 4px #d1f470 inline-start edge with
             #1a3a2a type at weight 700, which is .shop-asof's treatment for "read this first".
             Colour is not carrying the meaning: role=alert announces it, and the sentence states
             the problem. The 4px edge and the weight are a luminance and weight step rather than a
             hue change, so they survive forced-colors and reduced colour discrimination.
             Logical inline-start, so the edge follows the reading direction. */
          .si-error{
            margin:20px 0 0;padding:14px 16px;border-radius:10px;
            background:rgba(209,244,112,.22);border-inline-start:4px solid #d1f470;
            font-size:16px;font-weight:700;line-height:1.5;color:#1a3a2a;
          }
          /* 44px, so the way back off this page is a real target. */
          .si-back{margin:28px 0 0;font-size:16px;line-height:1.55}
          .si-back :global(a){
            display:inline-flex;align-items:center;min-height:44px;
            color:#1a3a2a;font-weight:700;text-underline-offset:3px;
          }
          .si-back :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}
          @media(max-width:767px){
            .si-body{font-size:18px}
          }
          @media(prefers-reduced-motion:reduce){
            .si-cta{transition:none}
            .si-cta:hover:not(:disabled){transform:none;box-shadow:none}
          }
        `}</style>
      </PageTopBand>
    </>
  );
}
