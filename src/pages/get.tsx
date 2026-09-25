/**
 * Customer file collection: verify over WhatsApp, pay, download.
 *
 * Design
 * ------
 * Matches the home page's language rather than inventing one: the #d1f470 lime with
 * #1a3a2a on top of it, 14px-radius panels with 2px borders, the 50px pill CTA, and
 * the site's section-heading rung clamp(28px,3.2vw,40px)/700/1.08/-1.2px - byte for
 * byte the declaration used by .home-flow-title, .home-close-title, .cl-h2 and the
 * rest. Body copy sits on the one body level, 20px/400/1.4/-.125px. If those rungs
 * are retuned site-wide, retune this too; `node tools/browser/typecheck.js` reports
 * the gaps.
 *
 * Why this page is at /files and not under /get
 * ---------------------------------------------
 * `/get/<*>` is an Amplify 200-rewrite onto the CloudFront distribution in front of
 * the file bucket, so nothing under that path reaches Next.js at all.
 *
 * It also has to be in the public allowlist in `_app.tsx`. Without that entry it
 * renders the staff Authenticator at HTTP 200 - which is how it shipped the first
 * time.
 *
 * The trust model, which is the whole point
 * -----------------------------------------
 * Razorpay Checkout's success callback fires in the browser and is therefore
 * forgeable - anyone can call it. So it is used only to stop showing the spinner.
 * Entitlement comes from the server: the redeem call succeeds only once the payment
 * is confirmed, either by the signature-verified webhook or by the backend asking
 * Razorpay directly. That is why this polls after checkout instead of downloading
 * straight from the callback.
 *
 * A grant is single use. A failed redeem must not be retried blindly - a second call
 * on a spent grant is indistinguishable from an unpaid one, by design.
 */

import React, { useCallback, useEffect, useState } from 'react';
import SEO from '../components/SEO';
import * as api from '../api/client';
import type { SecureFile } from '../api/client';
import {
    requestOtp, submitOtp, getSession, clearSession, normaliseMobile,
} from '../lib/customerAuth';

function formatBytes ( bytes: number ): string {
    if ( !bytes ) return '0 B';
    const units = [ 'B', 'KB', 'MB', 'GB' ];
    const i = Math.min( Math.floor( Math.log( bytes ) / Math.log( 1024 ) ), units.length - 1 );
    return `${( bytes / Math.pow( 1024, i ) ).toFixed( i === 0 ? 0 : 1 )} ${units[ i ]}`;
}

const rupees = ( paise: number ) => `₹${( ( paise || 0 ) / 100 ).toFixed( 0 )}`;

type Stage = 'mobile' | 'otp' | 'files';

export default function FilesPage () {
    const [ stage, setStage ] = useState<Stage>( 'mobile' );
    const [ mobile, setMobile ] = useState( '' );
    const [ code, setCode ] = useState( '' );
    const [ session, setSession ] = useState( '' );
    const [ destination, setDestination ] = useState( '' );
    const [ busy, setBusy ] = useState( false );
    const [ message, setMessage ] = useState( '' );
    const [ error, setError ] = useState( '' );

    const [ files, setFiles ] = useState<SecureFile[]>( [] );
    const [ price, setPrice ] = useState( 4900 );
    const [ working, setWorking ] = useState<string>( '' );

    const loadFiles = useCallback( async () => {
        const result = await api.listMySecureFiles();
        if ( result.ok )
        {
            setFiles( result.data.files || [] );
            setPrice( result.data.pricePaise || 4900 );
            setStage( 'files' );
            setError( '' );
        } else if ( result.failure.status === 401 )
        {
            clearSession();
            setStage( 'mobile' );
            setError( 'Your session expired. Please verify again.' );
        } else
        {
            setError( result.failure.message || 'Could not load your files' );
        }
    }, [] );

    // Resume an existing tab session rather than making the customer re-verify.
    useEffect( () => {
        if ( !getSession() ) return;
        api.listMySecureFiles().then( result => {
            if ( result.ok )
            {
                setFiles( result.data.files || [] );
                setPrice( result.data.pricePaise || 4900 );
                setStage( 'files' );
            } else
            {
                clearSession();
            }
        } );
    }, [] );

    const handleRequestOtp = async () => {
        setError( '' );
        setBusy( true );
        try
        {
            normaliseMobile( mobile ); // fail fast on an obviously bad number
            const challenge = await requestOtp( mobile );

            // Stop here rather than showing a code screen no code will ever satisfy.
            // Cognito issues a challenge for an unknown number too, so without this
            // the person waits indefinitely for a message that was never sent.
            if ( !challenge.registered )
            {
                setError(
                    'No files are registered to this number. '
                    + 'Check the number, or contact us if you were expecting a file.',
                );
                return;
            }

            setSession( challenge.session );
            setDestination( challenge.destination );
            setStage( 'otp' );
            setMessage( 'Code sent on WhatsApp.' );
        } catch ( err: any )
        {
            setError( err?.message || 'Could not start verification' );
        } finally
        {
            setBusy( false );
        }
    };

    const handleSubmitOtp = async () => {
        setError( '' );
        setBusy( true );
        try
        {
            const result = await submitOtp( mobile, code, session );
            if ( !result )
            {
                setError( 'That code was not correct. Try again.' );
                setCode( '' );
                return;
            }
            setMessage( '' );
            await loadFiles();
        } catch ( err: any )
        {
            if ( err?.name === 'NotAuthorizedException' )
            {
                setError( 'Too many incorrect attempts. Start again.' );
                setStage( 'mobile' );
                setCode( '' );
            } else
            {
                setError( err?.message || 'Verification failed' );
            }
        } finally
        {
            setBusy( false );
        }
    };

    /**
     * Hand the payment off to WhatsApp and stop.
     *
     * Everything after this happens on the handset: the customer pays through the
     * `wecare_pay` template's ORDER_DETAILS button, the Razorpay webhook verifies the
     * signature, and the file is delivered as a WhatsApp document. So this page has
     * nothing to poll for and no download to trigger — which is why there is no
     * Razorpay Checkout script here any more.
     */
    const handlePayOnWhatsApp = async ( file: SecureFile ) => {
        setError( '' );
        setMessage( '' );
        setWorking( file.fileId );
        try
        {
            const sent = await api.requestFilePaymentOnWhatsApp( file.fileId );
            if ( !sent.ok )
            {
                setError(
                    sent.failure.status === 503
                        ? 'Paid downloads are not switched on yet. Please contact us.'
                        : sent.failure.message || 'Could not send the payment request',
                );
                return;
            }
            setMessage(
                `Payment request sent to ${sent.data.sentTo} on WhatsApp. `
                + 'Pay there and your file will arrive in the same chat.',
            );
        } catch ( err: any )
        {
            setError( err?.message || 'Could not send the payment request' );
        } finally
        {
            setWorking( '' );
        }
    };

    return (
        <>
            {/* noindex: a personal collection point, not a marketing page. There is
                nothing here for a crawler, and an indexed URL inviting a phone number
                is a phishing template waiting to be copied. */}
            <SEO
                title="Your files"
                description="Collect files shared with you by WECARE.DIGITAL"
                noindex
            />

            <main className="sf-shell" aria-label="Your files">
                <div className="sf-panel">
                    <p className="sf-eyebrow">WECARE.DIGITAL</p>
                    <h1 className="sf-title">
                        { stage === 'files' ? 'Your files' : 'Collect your files' }
                    </h1>
                    <p className="sf-lead">
                        { stage === 'files'
                            ? 'Shared with your number.'
                            : 'Verify your mobile number on WhatsApp to collect files shared with you.' }
                    </p>

                    { error && (
                        <div className="sf-note sf-note-bad" role="alert">{ error }</div>
                    ) }
                    { message && !error && (
                        <div className="sf-note sf-note-ok" role="status">{ message }</div>
                    ) }

                    { stage === 'mobile' && (
                        <div className="sf-form">
                            <label className="sf-label" htmlFor="mobile">Mobile number</label>
                            <input
                                id="mobile"
                                className="sf-input"
                                value={ mobile }
                                onChange={ e => setMobile( e.target.value ) }
                                placeholder="8100640044"
                                inputMode="tel"
                                autoComplete="tel"
                                disabled={ busy }
                            />
                            <button className="sf-cta" onClick={ handleRequestOtp } disabled={ busy }>
                                { busy ? 'Sending…' : 'Send code on WhatsApp' }
                            </button>
                        </div>
                    ) }

                    { stage === 'otp' && (
                        <div className="sf-form">
                            <label className="sf-label" htmlFor="code">
                                Code sent to { destination || 'your number' }
                            </label>
                            <input
                                id="code"
                                className="sf-input sf-input-code"
                                value={ code }
                                onChange={ e => setCode( e.target.value.replace( /\D/g, '' ).slice( 0, 6 ) ) }
                                placeholder="——————"
                                inputMode="numeric"
                                autoComplete="one-time-code"
                                disabled={ busy }
                            />
                            <button
                                className="sf-cta"
                                onClick={ handleSubmitOtp }
                                disabled={ busy || code.length < 4 }
                            >
                                { busy ? 'Verifying…' : 'Verify' }
                            </button>
                            <button
                                className="sf-quiet"
                                onClick={ () => { setStage( 'mobile' ); setCode( '' ); setMessage( '' ); } }
                                disabled={ busy }
                            >
                                Use a different number
                            </button>
                        </div>
                    ) }

                    { stage === 'files' && (
                        <div className="sf-form">
                            { files.length === 0 && (
                                <p className="sf-empty">
                                    There are no files shared with your number right now.
                                </p>
                            ) }

                            { files.map( file => (
                                <div key={ file.fileId } className="sf-file">
                                    <div className="sf-file-name">{ file.displayName }</div>
                                    <div className="sf-file-meta">
                                        { formatBytes( file.sizeBytes ) }
                                        { file.downloadCount > 0
                                            && ` · downloaded ${file.downloadCount} time${file.downloadCount === 1 ? '' : 's'}` }
                                    </div>
                                    <button
                                        className="sf-cta"
                                        onClick={ () => handlePayOnWhatsApp( file ) }
                                        disabled={ !!working }
                                    >
                                        { working === file.fileId
                                            ? 'Sending…'
                                            : `Pay ${rupees( file.pricePaise || price )} on WhatsApp` }
                                    </button>
                                </div>
                            ) ) }

                            <p className="sf-fine">
                                Each download is charged separately. Payment and the file
                                both happen on WhatsApp, on the number you verified.
                            </p>
                            <button
                                className="sf-quiet"
                                onClick={ () => { clearSession(); setStage( 'mobile' ); setFiles( [] ); } }
                            >
                                Sign out
                            </button>
                        </div>
                    ) }
                </div>
            </main>

            <style jsx>{ `
                /* Centred single panel. The public header is fixed at 108px, dropping to
                   96px below 768px, so the shell pads for it rather than sliding under. */
                .sf-shell{
                  min-height:100vh;display:grid;place-items:center;
                  padding:calc(108px + 32px) 20px 64px;
                }
                @media(max-width:768px){ .sf-shell{padding:calc(96px + 24px) 16px 48px} }

                /* Same panel treatment as .home-close-panel: 2px lime border, 14px
                   radius, the tint at .22 alpha. */
                .sf-panel{
                  width:100%;max-width:560px;
                  padding:clamp(28px,4vw,56px);
                  border:2px solid #d1f470;border-radius:14px;
                  background:rgba(209,244,112,.22);
                }

                .sf-eyebrow{
                  margin:0 0 14px;font-size:12px;font-weight:700;
                  letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a;
                }
                /* The site's section-heading rung, identical to .home-close-title. */
                .sf-title{
                  margin:0 0 16px;font-size:clamp(28px,3.2vw,40px);font-weight:700;
                  line-height:1.08;letter-spacing:-1.2px;color:rgba(0,0,0,.95);
                }
                /* The one body level. */
                .sf-lead{
                  margin:0 0 28px;font-size:20px;font-weight:400;line-height:1.4;
                  letter-spacing:-.125px;color:rgba(0,0,0,.898);
                }

                .sf-form{display:block}

                .sf-label{
                  display:block;margin:0 0 8px;font-size:14px;font-weight:600;
                  letter-spacing:-.1px;color:#1a3a2a;
                }
                /* 16px minimum: anything smaller makes iOS Safari zoom the viewport on
                   focus, which on a one-field form looks like the page jumping. */
                .sf-input{
                  width:100%;box-sizing:border-box;min-height:52px;padding:0 16px;
                  margin:0 0 18px;font-size:16px;color:rgba(0,0,0,.95);
                  background:#fff;border:2px solid rgba(26,58,42,.18);border-radius:12px;
                  transition:border-color .2s;
                }
                .sf-input:focus{outline:none;border-color:#1a3a2a}
                .sf-input:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:2px}
                .sf-input:disabled{opacity:.6}
                .sf-input-code{
                  letter-spacing:.34em;font-size:22px;font-weight:600;text-align:center;
                }

                /* The home page CTA: 52px, 50px pill, lime fill, inverting to white. */
                .sf-cta{
                  display:inline-flex;align-items:center;justify-content:center;
                  width:100%;min-height:52px;padding:0 28px;
                  border:2px solid #d1f470;border-radius:50px;background:#d1f470;
                  color:#1a3a2a;font-size:17px;font-weight:600;cursor:pointer;
                  transition:background-color .2s,transform .2s,box-shadow .2s;
                }
                .sf-cta:hover:not(:disabled){
                  background:#fff;transform:translateY(-2px);
                  box-shadow:0 4px 12px rgba(26,58,42,.12);
                }
                .sf-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
                .sf-cta:disabled{opacity:.55;cursor:default}

                .sf-quiet{
                  display:block;width:100%;margin-top:12px;padding:10px;
                  border:0;background:transparent;color:rgba(26,58,42,.72);
                  font-size:15px;cursor:pointer;
                }
                .sf-quiet:hover{color:#1a3a2a;text-decoration:underline}
                .sf-quiet:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:2px}

                /* White card on the tinted panel, so each file reads as its own object. */
                .sf-file{
                  padding:20px;margin:0 0 14px;background:#fff;
                  border:2px solid rgba(26,58,42,.12);border-radius:12px;
                }
                .sf-file-name{
                  font-size:17px;font-weight:600;letter-spacing:-.2px;color:rgba(0,0,0,.95);
                }
                .sf-file-meta{
                  margin:6px 0 16px;font-size:14px;color:rgba(26,58,42,.68);
                }

                .sf-empty,.sf-fine{
                  font-size:15px;line-height:1.5;color:rgba(26,58,42,.72);margin:0;
                }
                .sf-fine{margin-top:18px;font-size:13px}

                /* Status banners. Colour is never the only signal - each carries role
                   alert or status, so a screen reader announces them regardless. */
                .sf-note{
                  margin:0 0 20px;padding:12px 16px;border-radius:12px;
                  font-size:15px;line-height:1.45;border:2px solid;
                }
                .sf-note-bad{background:#fee2e2;border-color:#ef4444;color:#7f1d1d}
                .sf-note-ok{background:#fff;border-color:#1a3a2a;color:#1a3a2a}

                @media(prefers-reduced-motion:reduce){
                  .sf-cta,.sf-input{transition:none}
                  .sf-cta:hover:not(:disabled){transform:none}
                }
            ` }</style>
        </>
    );
}
