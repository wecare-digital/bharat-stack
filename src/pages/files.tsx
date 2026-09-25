/**
 * Customer file collection: verify over WhatsApp, pay, download.
 *
 * Why this page is at /files and not under /get
 * ---------------------------------------------
 * `/get/<*>` is an Amplify 200-rewrite onto the CloudFront distribution that serves
 * the file bucket, so nothing under that path ever reaches Next.js. This page has
 * to live on a path Amplify still routes to the app.
 *
 * The trust model, which is the whole point
 * -----------------------------------------
 * Razorpay Checkout's success callback fires in the browser and is therefore
 * forgeable - anyone can call it. So it is used only to stop showing the spinner.
 * Entitlement comes from the server: the Razorpay webhook verifies its HMAC
 * signature and sets `paid` on the grant, and only then does the redeem call
 * succeed. That is why this polls after checkout instead of downloading straight
 * from the callback.
 *
 * A grant is single use. The redeem endpoint spends it with a conditional write, so
 * a failed redeem must not be retried blindly - a second call on a spent grant is
 * indistinguishable from an unpaid one, by design.
 */

import React, { useCallback, useEffect, useState } from 'react';
import SEO from '../components/SEO';
import * as api from '../api/client';
import type { SecureFile } from '../api/client';
import {
    requestOtp, submitOtp, getSession, clearSession, normaliseMobile,
} from '../lib/customerAuth';

declare global {
    interface Window { Razorpay?: new ( options: Record<string, unknown> ) => { open: () => void }; }
}

const CHECKOUT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';

/** Load Checkout once, on demand. Not in _document, so the script costs nothing
 *  for the majority of visitors who never reach the payment step. */
function loadCheckout (): Promise<void> {
    return new Promise( ( resolve, reject ) => {
        if ( typeof window === 'undefined' ) { reject( new Error( 'no window' ) ); return; }
        if ( window.Razorpay ) { resolve(); return; }
        const existing = document.querySelector<HTMLScriptElement>( `script[src="${CHECKOUT_SRC}"]` );
        if ( existing )
        {
            existing.addEventListener( 'load', () => resolve() );
            existing.addEventListener( 'error', () => reject( new Error( 'Checkout failed to load' ) ) );
            return;
        }
        const script = document.createElement( 'script' );
        script.src = CHECKOUT_SRC;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => reject( new Error( 'Checkout failed to load' ) );
        document.body.appendChild( script );
    } );
}

function formatBytes ( bytes: number ): string {
    if ( !bytes ) return '0 B';
    const units = [ 'B', 'KB', 'MB', 'GB' ];
    const i = Math.min( Math.floor( Math.log( bytes ) / Math.log( 1024 ) ), units.length - 1 );
    return `${( bytes / Math.pow( 1024, i ) ).toFixed( i === 0 ? 0 : 1 )} ${units[ i ]}`;
}

const rupees = ( paise: number ) => `₹${( ( paise || 0 ) / 100 ).toFixed( 0 )}`;

/**
 * Poll redeem until the webhook has marked the grant paid.
 *
 * Razorpay's callback means "the customer submitted payment", not "we have been told
 * it captured". The webhook normally lands within a second or two; this gives it
 * ~40s before admitting defeat.
 *
 * A 403 here means "not payable yet" far more often than "already spent", because
 * this is the first redeem attempt on a fresh grant - the backend deliberately
 * returns the same answer for both, so waiting is the only sensible reading.
 *
 * Lives at module scope, not in the component: it touches no state, and `Date.now()`
 * inside a function defined in the render body is treated as an impure call during
 * render.
 */
async function pollForDownload ( fileId: string, grantId: string ): Promise<string> {
    const deadline = Date.now() + 40_000;
    let wait = 1500;
    while ( Date.now() < deadline )
    {
        const result = await api.redeemSecureFileDownload( fileId, grantId );
        if ( result.ok ) return result.data.downloadUrl;
        await new Promise( resolve => setTimeout( resolve, wait ) );
        wait = Math.min( wait * 1.4, 5000 );
    }
    throw new Error(
        'Payment received but the confirmation has not arrived yet. '
        + 'Your file will be available shortly - please reload this page.',
    );
}

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
            setSession( challenge.session );
            setDestination( challenge.destination );
            setStage( 'otp' );
            // Deliberately hedged. PreventUserExistenceErrors is on, so an unknown
            // number returns a challenge too - promising "we sent a code" would be a
            // lie for anyone not registered.
            setMessage( 'If this number is registered, a code has been sent on WhatsApp.' );
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

    const handlePayAndDownload = async ( file: SecureFile ) => {
        setError( '' );
        setWorking( file.fileId );
        try
        {
            const order = await api.createSecureFileOrder( file.fileId );
            if ( !order.ok )
            {
                setError(
                    order.failure.status === 503
                        ? 'Paid downloads are not switched on yet. Please contact us.'
                        : order.failure.message || 'Could not start the payment',
                );
                return;
            }

            await loadCheckout();
            const RazorpayCtor = window.Razorpay;
            if ( !RazorpayCtor ) throw new Error( 'Checkout unavailable' );

            await new Promise<void>( ( resolve, reject ) => {
                const checkout = new RazorpayCtor( {
                    key: order.data.keyId,
                    amount: order.data.amountPaise,
                    currency: order.data.currency || 'INR',
                    order_id: order.data.orderId,
                    name: 'WECARE.DIGITAL',
                    description: file.displayName,
                    // Forgeable, so it only ends the wait. Entitlement is decided
                    // server-side by the signed webhook.
                    handler: () => resolve(),
                    modal: { ondismiss: () => reject( new Error( 'Payment cancelled' ) ) },
                    theme: { color: '#0b6' },
                } );
                checkout.open();
            } );

            setMessage( 'Payment received. Preparing your download…' );
            const url = await pollForDownload( file.fileId, order.data.grantId );
            setMessage( '' );
            // assign(), not `location.href = url`: the presigned URL responds with
            // Content-Disposition: attachment, so the browser downloads it and stays
            // on this page rather than navigating away.
            window.location.assign( url );
            await loadFiles();
        } catch ( err: any )
        {
            setMessage( '' );
            setError( err?.message || 'Payment could not be completed' );
        } finally
        {
            setWorking( '' );
        }
    };

    const shell: React.CSSProperties = {
        minHeight: '100vh', display: 'grid', placeItems: 'center',
        padding: '24px', background: 'var(--bg, #fafafa)',
    };
    const card: React.CSSProperties = {
        width: '100%', maxWidth: '520px', background: 'var(--surface, #fff)',
        border: '1px solid var(--border, #e5e5e5)', borderRadius: '14px', padding: '28px',
    };
    const input: React.CSSProperties = {
        width: '100%', padding: '12px 14px', borderRadius: '8px', fontSize: '16px',
        border: '1px solid var(--border, #d4d4d4)', marginBottom: '14px',
    };
    const button: React.CSSProperties = {
        width: '100%', padding: '12px 16px', borderRadius: '8px', border: 0,
        background: '#0b6', color: '#fff', fontSize: '16px', fontWeight: 600,
        cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1,
    };

    return (
        <>
            <SEO title="Your files" description="Collect files shared with you by WECARE.DIGITAL" />
            <main style={ shell }>
                <div style={ card }>
                    <h1 style={ { fontSize: '20px', margin: '0 0 6px' } }>Your files</h1>
                    <p style={ { color: '#666', fontSize: '14px', margin: '0 0 22px' } }>
                        { stage === 'files'
                            ? 'Files shared with your number.'
                            : 'Verify your mobile number on WhatsApp to collect files shared with you.' }
                    </p>

                    { error && (
                        <div role="alert" style={ {
                            background: '#fee2e2', border: '1px solid #ef4444', color: '#991b1b',
                            borderRadius: '8px', padding: '10px 14px', marginBottom: '16px', fontSize: '14px',
                        } }>
                            { error }
                        </div>
                    ) }
                    { message && !error && (
                        <div role="status" style={ {
                            background: '#dcfce7', border: '1px solid #16a34a', color: '#166534',
                            borderRadius: '8px', padding: '10px 14px', marginBottom: '16px', fontSize: '14px',
                        } }>
                            { message }
                        </div>
                    ) }

                    { stage === 'mobile' && (
                        <>
                            <label htmlFor="mobile" style={ { fontSize: '14px', color: '#555' } }>
                                Mobile number
                            </label>
                            <input
                                id="mobile"
                                style={ { ...input, marginTop: '6px' } }
                                value={ mobile }
                                onChange={ e => setMobile( e.target.value ) }
                                placeholder="8100640044"
                                inputMode="tel"
                                autoComplete="tel"
                                disabled={ busy }
                            />
                            <button style={ button } onClick={ handleRequestOtp } disabled={ busy }>
                                { busy ? 'Sending…' : 'Send code on WhatsApp' }
                            </button>
                        </>
                    ) }

                    { stage === 'otp' && (
                        <>
                            <p style={ { fontSize: '14px', color: '#555', margin: '0 0 12px' } }>
                                Enter the 6-digit code sent to { destination || 'your number' }.
                            </p>
                            <label htmlFor="code" style={ { fontSize: '14px', color: '#555' } }>
                                Verification code
                            </label>
                            <input
                                id="code"
                                style={ { ...input, marginTop: '6px', letterSpacing: '0.3em', fontSize: '20px' } }
                                value={ code }
                                onChange={ e => setCode( e.target.value.replace( /\D/g, '' ).slice( 0, 6 ) ) }
                                placeholder="------"
                                inputMode="numeric"
                                autoComplete="one-time-code"
                                disabled={ busy }
                            />
                            <button
                                style={ button }
                                onClick={ handleSubmitOtp }
                                disabled={ busy || code.length < 4 }
                            >
                                { busy ? 'Verifying…' : 'Verify' }
                            </button>
                            <button
                                style={ {
                                    width: '100%', marginTop: '10px', padding: '10px', border: 0,
                                    background: 'transparent', color: '#666', cursor: 'pointer', fontSize: '14px',
                                } }
                                onClick={ () => { setStage( 'mobile' ); setCode( '' ); setMessage( '' ); } }
                                disabled={ busy }
                            >
                                Use a different number
                            </button>
                        </>
                    ) }

                    { stage === 'files' && (
                        <>
                            { files.length === 0 && (
                                <p style={ { color: '#666', fontSize: '14px' } }>
                                    There are no files shared with your number right now.
                                </p>
                            ) }

                            { files.map( file => (
                                <div key={ file.fileId } style={ {
                                    border: '1px solid var(--border, #e5e5e5)', borderRadius: '10px',
                                    padding: '16px', marginBottom: '12px',
                                } }>
                                    <div style={ { fontWeight: 600, fontSize: '15px' } }>
                                        { file.displayName }
                                    </div>
                                    <div style={ { color: '#777', fontSize: '13px', margin: '4px 0 12px' } }>
                                        { formatBytes( file.sizeBytes ) }
                                        { file.downloadCount > 0
                                            && ` · downloaded ${file.downloadCount} time${file.downloadCount === 1 ? '' : 's'}` }
                                    </div>
                                    <button
                                        style={ { ...button, opacity: working ? 0.6 : 1 } }
                                        onClick={ () => handlePayAndDownload( file ) }
                                        disabled={ !!working }
                                    >
                                        { working === file.fileId
                                            ? 'Processing…'
                                            : `Pay ${rupees( file.pricePaise || price )} and download` }
                                    </button>
                                </div>
                            ) ) }

                            <p style={ { color: '#888', fontSize: '12px', marginTop: '18px' } }>
                                Each download is charged separately.
                            </p>
                            <button
                                style={ {
                                    width: '100%', marginTop: '6px', padding: '10px', border: 0,
                                    background: 'transparent', color: '#666', cursor: 'pointer', fontSize: '14px',
                                } }
                                onClick={ () => { clearSession(); setStage( 'mobile' ); setFiles( [] ); } }
                            >
                                Sign out
                            </button>
                        </>
                    ) }
                </div>
            </main>
        </>
    );
}
