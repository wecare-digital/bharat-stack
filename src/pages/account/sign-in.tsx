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
 * THE HONEST UNREGISTERED-NUMBER HANDLING. customerAuth.ts documents that Cognito returns a masked
 * challenge for an UNKNOWN number too (PreventUserExistenceErrors), and no code is ever sent to
 * one - so claiming "we sent you a code" would be a lie for a number that is not a customer. When
 * requestOtp reports `registered: false` this page does NOT show an OTP box; it routes the shopper
 * through the registration front door (POST /auth/customer-registration {action:'request'|'verify'})
 * to create the customer, then completes sign-in via customerAuth.submitOtp. See the registration
 * handler for the request/verify contract.
 *
 * TWO CODES, NOT ONE, ON THE REGISTER PATH. The registration handler's docblock is explicit that it
 * never returns a session credential: "the session credential comes from the Cognito sign-in, not
 * from here." So once `verify` provisions the login, the shopper still has to complete the ordinary
 * WhatsApp-OTP CUSTOM_AUTH sign-in, and that Cognito challenge sends its OWN, second code. This page
 * treats that as its own step (the `signin-code` phase): it starts the Cognito challenge, tells the
 * shopper a fresh code is on its way, and answers the challenge with THAT code - it never replays
 * the registration code, which Cognito would reject.
 *
 * CHROME AND INDEXING. This is a customer-session route registered in the _app.tsx isPublic chain
 * beside /checkout/status and /checkout/success; it is noindex and imports no Layout/Header/Footer/
 * SupportWidget (those are mounted centrally). It is intentionally absent from PUBLIC_PAGE_META,
 * the sitemap and the browser route lists.
 */

import Head from 'next/head';
import Link from 'next/link';
import React, { useCallback, useEffect, useState } from 'react';

import {
  requestOtp, submitOtp, normaliseMobile, getSession, nextSessionFrom,
} from '../../lib/customerAuth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
const REGISTRATION_URL = `${API_BASE}/auth/customer-registration`;

/** Where to send the shopper once signed in. Defaults to the cart. */
function returnPathFromUrl (): string {
  if ( typeof window === 'undefined' ) return '/cart/';
  const raw = String( new URLSearchParams( window.location.search ).get( 'return' ) || '' ).trim();
  // Only same-site absolute paths, so this can never be turned into an open redirect.
  return /^\/[a-zA-Z0-9/_-]*\/?$/.test( raw ) ? raw : '/cart/';
}

/**
 * The step the form is on.
 *   'phone'         collect the number.
 *   'code'          registered path: answer the live Cognito challenge from requestOtp.
 *   'register-code' unregistered path: answer the registration front-door OTP (creates the customer).
 *   'signin-code'   unregistered path, second leg: answer the SECOND, Cognito sign-in code that the
 *                   CUSTOM_AUTH challenge sends after the customer is provisioned.
 */
type Phase = 'phone' | 'code' | 'register-code' | 'signin-code';

export default function CustomerSignIn (): React.ReactElement {
  const [ phase, setPhase ] = useState<Phase>( 'phone' );
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

  const startPhone = useCallback( async ( event: React.FormEvent ): Promise<void> => {
    event.preventDefault();
    setError( '' );
    let e164 = '';
    try
    {
      e164 = normaliseMobile( mobile );
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
          setError( 'We could not send a code. Please try again.' );
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
  }, [ mobile ] );

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
      <main className="si-wrap">
        <section className="si-card">
          <h1 className="si-title">Sign in to check out</h1>

          {phase === 'phone' && (
            <form className="si-form" onSubmit={ startPhone }>
              <p className="si-body">
                Enter your mobile number and we&apos;ll send a code to WhatsApp to confirm it&apos;s
                you. If you&apos;re new, we&apos;ll set you up in the same step.
              </p>
              <label className="si-label" htmlFor="si-mobile">Mobile number</label>
              <input
                id="si-mobile"
                className="si-input"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                value={ mobile }
                onChange={ e => setMobile( e.target.value ) }
                disabled={ busy }
              />
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
        </section>
      </main>

      <style jsx>{`
        .si-wrap{
          min-height:calc(100vh - 69px);
          padding-top:108px;box-sizing:border-box;background:#fff;
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          color:#1a1a1a;display:flex;justify-content:center;
        }
        .si-card{width:100%;max-width:460px;padding:48px 24px 96px;box-sizing:border-box}
        .si-title{
          font-size:clamp(28px,4vw,40px);font-weight:600;line-height:1.08;
          letter-spacing:-0.03em;color:rgba(0,0,0,.95);margin:0 0 20px;
        }
        .si-body{font-size:16px;line-height:1.55;color:rgba(0,0,0,.7);margin:0 0 24px}
        .si-form{display:flex;flex-direction:column}
        .si-label{font-size:14px;font-weight:600;color:#1a3a2a;margin-bottom:8px}
        .si-input{
          min-height:52px;padding:0 16px;border:1px solid #e5e7eb;border-radius:10px;
          font-size:17px;color:#1a1a1a;margin-bottom:20px;
        }
        .si-input:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}
        /* The single LIME actionable surface on this page. */
        .si-cta{
          display:inline-flex;align-items:center;justify-content:center;min-height:52px;
          padding:0 26px;border:2px solid #d1f470;border-radius:50px;
          background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;cursor:pointer;
          transition:background-color .2s,transform .2s,box-shadow .2s;
        }
        .si-cta:hover:not(:disabled){background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
        .si-cta:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}
        .si-cta:disabled{opacity:.6;cursor:default}
        .si-error{
          margin:20px 0 0;padding:12px 16px;border:1px solid #f0c0c0;border-radius:10px;
          background:#fbe9e9;font-size:15px;line-height:1.5;color:#8a1f1f;
        }
        .si-back{margin:28px 0 0;font-size:16px}
        .si-back :global(a){color:#1a3a2a;font-weight:600;text-underline-offset:3px}
        .si-back :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}
        @media(max-width:767px){
          .si-wrap{min-height:calc(100vh - 85px);padding-top:96px}
          .si-card{padding:32px 16px 64px}
        }
        @media(prefers-reduced-motion:reduce){
          .si-cta{transition:none}
          .si-cta:hover:not(:disabled){transform:none;box-shadow:none}
        }
      `}</style>
    </>
  );
}
