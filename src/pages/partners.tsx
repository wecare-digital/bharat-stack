/**
 * Partners / Onboarding — PUBLIC page (future: Option B, Tech-Provider model)
 *
 * Hosts the WhatsApp Embedded Signup (Facebook Login for Business) flow so that,
 * in the future, external businesses can connect THEIR own WhatsApp Business
 * Account to WECARE.DIGITAL. This is dormant until enabled via env:
 *
 *   NEXT_PUBLIC_ENABLE_PARTNER_SIGNUP = "true"     // reveal the live CTA
 *   NEXT_PUBLIC_FB_APP_ID             = <app id>   // already used app-wide
 *   NEXT_PUBLIC_FB_ES_CONFIG_ID       = <config>   // Tech Provider / ES config id
 *   NEXT_PUBLIC_FB_GRAPH_VERSION      = "v25.0"    // optional
 *
 * The final code->token exchange MUST happen server-side (needs the app secret),
 * so the captured auth code is POSTed to a backend route to be built later:
 *   POST {API_BASE}/partners/embedded-signup  { code, wabaId, phoneNumberId }
 *
 * Until that route exists, the page captures and displays the signup result but
 * does not complete onboarding.
 */
import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { API_BASE } from '../config/constants';

const GREEN = '#1a3a2a';
const LIME = '#d1f470';

const ENABLED = process.env.NEXT_PUBLIC_ENABLE_PARTNER_SIGNUP === 'true';
const FB_APP_ID = process.env.NEXT_PUBLIC_FB_APP_ID || '';
const ES_CONFIG_ID = process.env.NEXT_PUBLIC_FB_ES_CONFIG_ID || '';
const GRAPH_VERSION = process.env.NEXT_PUBLIC_FB_GRAPH_VERSION || 'v25.0';

type Status = 'idle' | 'launching' | 'captured' | 'exchanging' | 'done' | 'error';

interface SignupResult {
    wabaId?: string;
    phoneNumberId?: string;
    businessId?: string;
}

const wrap: React.CSSProperties = { maxWidth: 980, margin: '0 auto', padding: '48px 20px' };
const card: React.CSSProperties = { background: '#fff', border: '1px solid #e8e8e8', borderRadius: 14, padding: 28, marginBottom: 20 };
const h1: React.CSSProperties = { fontSize: 34, fontWeight: 800, color: GREEN, margin: '0 0 10px', lineHeight: 1.15 };
const sub: React.CSSProperties = { fontSize: 16, color: '#555', margin: '0 0 28px', maxWidth: 640 };
const cta: React.CSSProperties = { padding: '14px 26px', background: LIME, color: GREEN, border: 'none', borderRadius: 12, fontSize: 16, fontWeight: 700, cursor: 'pointer' };
const ctaDisabled: React.CSSProperties = { ...cta, background: '#eee', color: '#999', cursor: 'not-allowed' };
const featureRow: React.CSSProperties = { display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 8 };
const feature: React.CSSProperties = { flex: '1 1 220px', background: '#fff', border: '1px solid #eee', borderRadius: 12, padding: 20 };

const FEATURES = [
    { t: 'Connect in minutes', d: 'Securely link your WhatsApp Business Account through Meta’s official Embedded Signup — no manual token handling.' },
    { t: 'One unified inbox', d: 'Manage conversations, templates, and delivery status across all your numbers from a single console.' },
    { t: 'Templates & automation', d: 'Create approved templates, run campaigns, and automate replies while staying policy-compliant.' },
    { t: 'You stay in control', d: 'You own your WABA and data. Disconnect any time from your Meta Business settings.' },
];

const PartnersPage: React.FC = () => {
    const [ status, setStatus ] = useState<Status>( 'idle' );
    const [ result, setResult ] = useState<SignupResult>( {} );
    const [ message, setMessage ] = useState<string>( '' );

    // Listen for the Embedded Signup session info posted by Meta’s window.
    useEffect( () => {
        if ( !ENABLED ) return;
        const onMessage = ( event: MessageEvent ) => {
            if ( event.origin !== 'https://www.facebook.com' && event.origin !== 'https://web.facebook.com' ) return;
            try
            {
                const data = typeof event.data === 'string' ? JSON.parse( event.data ) : event.data;
                if ( data?.type === 'WA_EMBEDDED_SIGNUP' )
                {
                    if ( data.event === 'FINISH' || data.event === 'FINISH_ONLY_WABA' )
                    {
                        setResult( ( r ) => ( { ...r, wabaId: data.data?.waba_id, phoneNumberId: data.data?.phone_number_id, businessId: data.data?.business_id } ) );
                        setStatus( 'captured' );
                    } else if ( data.event === 'CANCEL' )
                    {
                        setStatus( 'idle' );
                        setMessage( 'Signup was cancelled before completion.' );
                    }
                }
            } catch
            {
                /* non-JSON messages are ignored */
            }
        };
        window.addEventListener( 'message', onMessage );
        return () => window.removeEventListener( 'message', onMessage );
    }, [] );

    const exchange = useCallback( async ( code: string, r: SignupResult ) => {
        setStatus( 'exchanging' );
        try
        {
            const res = await fetch( `${API_BASE}/partners/embedded-signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify( { code, wabaId: r.wabaId, phoneNumberId: r.phoneNumberId, businessId: r.businessId } ),
            } );
            if ( !res.ok ) throw new Error( `Onboarding service returned ${res.status}` );
            setStatus( 'done' );
            setMessage( 'Your WhatsApp Business Account is connected. Our team will reach out with next steps.' );
        } catch ( e: any )
        {
            setStatus( 'error' );
            setMessage( e?.message || 'Could not complete onboarding. Please try again or contact support.' );
        }
    }, [] );

    const launch = useCallback( () => {
        const FB = ( typeof window !== 'undefined' && ( window as any ).FB ) || null;
        if ( !FB || !ES_CONFIG_ID )
        {
            setStatus( 'error' );
            setMessage( 'Signup is not fully configured yet. Please check back soon.' );
            return;
        }
        setStatus( 'launching' );
        setMessage( '' );
        FB.login(
            ( response: any ) => {
                const code = response?.authResponse?.code;
                if ( code )
                {
                    setResult( ( r ) => {
                        exchange( code, r );
                        return r;
                    } );
                } else
                {
                    setStatus( 'idle' );
                    setMessage( 'No authorization was returned. Please try again.' );
                }
            },
            {
                config_id: ES_CONFIG_ID,
                response_type: 'code',
                override_default_response_type: true,
                extras: { setup: {}, featureType: '', sessionInfoVersion: '3' },
            }
        );
    }, [ exchange ] );

    return (
        <>
            <Head>
                <title>Partner with WECARE.DIGITAL — Connect your WhatsApp Business</title>
                <meta name="description" content="Connect your WhatsApp Business Account to WECARE.DIGITAL and manage messaging, templates, and automation from one console." />
                <meta name="robots" content={ ENABLED ? 'index, follow' : 'noindex, nofollow' } />
                <link rel="canonical" href="https://stack.wecare.digital/partners/" />
            </Head>

            <div style={ { minHeight: '100vh', background: '#f7f8f6', paddingTop: 96 } }>
                <div style={ wrap }>
                    <h1 style={ h1 }>Connect your WhatsApp Business Account</h1>
                    <p style={ sub }>
                        Bring your own WhatsApp Business number onto WECARE.DIGITAL and manage conversations,
                        templates, campaigns, and automation from a single, secure console — powered by the
                        official WhatsApp Business Platform.
                    </p>

                    <div style={ card }>
                        { ENABLED ? (
                            <>
                                <button
                                    style={ status === 'launching' || status === 'exchanging' ? ctaDisabled : cta }
                                    onClick={ launch }
                                    disabled={ status === 'launching' || status === 'exchanging' }
                                >
                                    { status === 'launching' ? 'Opening Meta signup…'
                                        : status === 'exchanging' ? 'Finishing setup…'
                                            : 'Connect WhatsApp Business' }
                                </button>
                                <p style={ { fontSize: 13, color: '#777', marginTop: 12 } }>
                                    You’ll be guided through Meta’s secure Embedded Signup. WECARE.DIGITAL never sees your Facebook password.
                                </p>

                                { status === 'captured' && (
                                    <div style={ { marginTop: 16, fontSize: 14, color: GREEN } }>
                                        Account received (WABA { result.wabaId || '—' }). Finalizing…
                                    </div>
                                ) }
                                { ( status === 'done' || status === 'error' ) && (
                                    <div style={ { marginTop: 16, fontSize: 14, color: status === 'done' ? GREEN : '#a11' } }>
                                        { message }
                                    </div>
                                ) }
                                { status === 'idle' && message && (
                                    <div style={ { marginTop: 16, fontSize: 14, color: '#a60' } }>{ message }</div>
                                ) }
                            </>
                        ) : (
                            <>
                                <button style={ ctaDisabled } disabled>Connect WhatsApp Business — coming soon</button>
                                <p style={ { fontSize: 13, color: '#777', marginTop: 12 } }>
                                    Partner onboarding is launching soon. Want early access?{ ' ' }
                                    <a href="https://wa.me/919903300044" style={ { color: GREEN, fontWeight: 600 } }>Message us on WhatsApp</a>.
                                </p>
                            </>
                        ) }
                    </div>

                    <div style={ featureRow }>
                        { FEATURES.map( ( f ) => (
                            <div key={ f.t } style={ feature }>
                                <div style={ { fontWeight: 700, color: GREEN, marginBottom: 6 } }>{ f.t }</div>
                                <div style={ { fontSize: 14, color: '#555' } }>{ f.d }</div>
                            </div>
                        ) ) }
                    </div>

                    <p style={ { fontSize: 12, color: '#999', marginTop: 28 } }>
                        WECARE.DIGITAL integrates with the WhatsApp Business Platform. WhatsApp is a trademark of Meta Platforms, Inc.
                        By connecting, you agree to our Terms and Privacy Policy and Meta’s WhatsApp Business Messaging Policy.
                    </p>
                </div>
            </div>
        </>
    );
};

export default PartnersPage;
