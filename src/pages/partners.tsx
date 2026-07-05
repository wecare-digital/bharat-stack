/**
 * Partners / Onboarding — PUBLIC page (Option B, Tech-Provider model)
 *
 * Hosts WhatsApp Embedded Signup (Facebook Login for Business) so external
 * businesses can connect their own WhatsApp Business Account to WECARE.DIGITAL.
 * The Embedded Signup logic lives in the shared <EmbeddedSignupPanel/>.
 *
 * Config (env):
 *   NEXT_PUBLIC_ENABLE_PARTNER_SIGNUP = "true"
 *   NEXT_PUBLIC_FB_APP_ID             = <app id>   (loaded app-wide)
 *   NEXT_PUBLIC_FB_ES_CONFIG_ID       = 1023561327204288
 */
import React from 'react';
import Head from 'next/head';
import EmbeddedSignupPanel from '../components/EmbeddedSignupPanel';

const GREEN = '#1a3a2a';

const wrap: React.CSSProperties = { maxWidth: 980, margin: '0 auto', padding: '48px 20px' };
const card: React.CSSProperties = { background: '#fff', border: '1px solid #e8e8e8', borderRadius: 14, padding: 28, marginBottom: 20 };
const h1: React.CSSProperties = { fontSize: 34, fontWeight: 800, color: GREEN, margin: '0 0 10px', lineHeight: 1.15 };
const sub: React.CSSProperties = { fontSize: 16, color: '#555', margin: '0 0 28px', maxWidth: 640 };
const featureRow: React.CSSProperties = { display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 8 };
const feature: React.CSSProperties = { flex: '1 1 220px', background: '#fff', border: '1px solid #eee', borderRadius: 12, padding: 20 };

const FEATURES = [
    { t: 'Connect in minutes', d: 'Securely link your WhatsApp Business Account through Meta’s official Embedded Signup — no manual token handling.' },
    { t: 'One unified inbox', d: 'Manage conversations, templates, and delivery status across all your numbers from a single console.' },
    { t: 'Templates & automation', d: 'Create approved templates, run campaigns, and automate replies while staying policy-compliant.' },
    { t: 'You stay in control', d: 'You own your WABA and data. Disconnect any time from your Meta Business settings.' },
];

const PartnersPage: React.FC = () => (
    <>
        <Head>
            <title>Partner with WECARE.DIGITAL — Connect your WhatsApp Business</title>
            <meta name="description" content="Connect your WhatsApp Business Account to WECARE.DIGITAL and manage messaging, templates, and automation from one console." />
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
                    <EmbeddedSignupPanel />
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

export default PartnersPage;
