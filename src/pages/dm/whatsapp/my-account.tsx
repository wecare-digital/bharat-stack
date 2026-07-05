/**
 * My WhatsApp Account — CUSTOMER limited view (protected)
 *
 * Read-only self-view for an onboarded business customer. Shows ONLY their own
 * linked WhatsApp Business Account (scoped server-side by the caller's
 * custom:partner_waba_id Cognito attribute via GET /partners/me).
 *
 * Customers get no admin controls — no tenant list, no onboarding of others,
 * no disconnect. Those live on the admin-only /dm/whatsapp/connected-accounts/.
 */
import React, { useEffect, useState } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import { authFetch } from '../../../api/client';
import { API_BASE } from '../../../config/constants';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const card: React.CSSProperties = { background: '#fff', border: '1px solid #e5e5e5', borderRadius: 8, padding: 20, marginBottom: 16 };
const row: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f0f0f0', fontSize: 14 };
const key: React.CSSProperties = { color: '#777' };

const MyAccountPage: React.FC<PageProps> = ( { signOut, user, embedded = false } ) => {
    const toast = useToastContext();
    const [ tenant, setTenant ] = useState<any>( null );
    const [ isAdmin, setIsAdmin ] = useState( false );
    const [ linked, setLinked ] = useState<boolean | null>( null );
    const [ wallet, setWallet ] = useState<any>( null );
    const [ ledger, setLedger ] = useState<any[]>( [] );
    const [ loading, setLoading ] = useState( true );

    useEffect( () => {
        ( async () => {
            try
            {
                const [ meRes, billRes ] = await Promise.all( [
                    authFetch( `${API_BASE}/partners/me` ),
                    authFetch( `${API_BASE}/partners/billing` ),
                ] );
                const data = await meRes.json();
                if ( !meRes.ok ) throw new Error( data?.error || 'Failed to load' );
                setTenant( data.tenant || null );
                setIsAdmin( !!data.isAdmin );
                setLinked( data.linked ?? !!data.tenant );
                if ( billRes.ok )
                {
                    const bd = await billRes.json();
                    setWallet( bd.wallet || null );
                    setLedger( Array.isArray( bd.ledger ) ? bd.ledger : [] );
                }
            } catch ( e: any )
            {
                toast.error( e?.message || 'Failed to load your account' );
            } finally
            {
                setLoading( false );
            }
        } )();
    }, [ toast ] );

    const p = tenant?.details?.phone || {};
    const w = tenant?.details?.waba || {};

    const content = (
        <div style={ { maxWidth: 720, margin: '0 auto', padding: 16 } }>
            <SEO title="My WhatsApp Account" description="Your linked WhatsApp Business Account." noindex />
            <h1 style={ { fontSize: 22, fontWeight: 700, marginBottom: 4 } }>My WhatsApp Account</h1>
            <p style={ { color: '#777', fontSize: 13, marginBottom: 16 } }>Your linked WhatsApp Business Account and its status.</p>

            { loading ? <div style={ { color: '#777' } }>Loading…</div>
                : isAdmin ? (
                    <div style={ card }>
                        <p style={ { fontSize: 14, margin: 0 } }>You’re signed in as an admin. Manage all connected accounts on the <strong>Connected Accounts</strong> page.</p>
                    </div>
                ) : !linked ? (
                    <div style={ card }>
                        <p style={ { fontSize: 14, margin: 0 } }>No WhatsApp Business Account is linked to your login yet. Please contact WECARE.DIGITAL to complete onboarding.</p>
                    </div>
                ) : (
                    <div style={ card }>
                        <div style={ row }><span style={ key }>Business name</span><span>{ p.name || w.name || '—' }</span></div>
                        <div style={ row }><span style={ key }>Phone number</span><span>{ p.display || '—' }</span></div>
                        <div style={ row }><span style={ key }>Quality rating</span><span>{ p.quality || '—' }</span></div>
                        <div style={ row }><span style={ key }>WABA review status</span><span>{ w.reviewStatus || '—' }</span></div>
                        <div style={ row }><span style={ key }>Status</span><span>{ tenant?.status || '—' }</span></div>
                        <div style={ { ...row, borderBottom: 'none' } }><span style={ key }>Connected on</span><span>{ tenant?.connectedAt ? new Date( tenant.connectedAt ).toLocaleString() : '—' }</span></div>
                    </div>
                ) }

            { !loading && !isAdmin && linked && (
                <div style={ card }>
                    <h3 style={ { marginTop: 0, fontSize: 16 } }>Wallet & Usage</h3>
                    <div style={ row }>
                        <span style={ key }>Prepaid balance</span>
                        <span style={ { fontWeight: 700 } }>{ wallet ? `${wallet.balance} ${wallet.currency}` : '—' }
                            { wallet?.status === 'SUSPENDED' && <span style={ { color: '#a11', marginLeft: 8, fontSize: 12 } }>SUSPENDED — top up to resume</span> }
                        </span>
                    </div>
                    <div style={ { marginTop: 10, fontSize: 13, color: '#555' } }>Recent activity</div>
                    { ledger.length === 0 ? <div style={ { fontSize: 13, color: '#999', marginTop: 4 } }>No usage yet.</div>
                        : (
                            <div style={ { marginTop: 6 } }>
                                { ledger.slice( 0, 10 ).map( ( l, i ) => (
                                    <div key={ i } style={ { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: '1px solid #f5f5f5' } }>
                                        <span style={ { color: '#666' } }>{ l.ts ? new Date( l.ts ).toLocaleString() : '' } · { l.type }{ l.category ? ` (${l.category})` : '' }</span>
                                        <span style={ { color: l.type === 'topup' ? '#1a3a2a' : '#a11' } }>{ l.type === 'topup' ? '+' : '−' }{ l.amount } · bal { l.balanceAfter }</span>
                                    </div>
                                ) ) }
                            </div>
                        ) }
                    <p style={ { fontSize: 12, color: '#999', marginTop: 10 } }>To add funds, contact WECARE.DIGITAL.</p>
                </div>
            ) }
        </div>
    );

    if ( embedded ) return content;
    return <Layout user={ user } onSignOut={ signOut }>{ content }</Layout>;
};

export default MyAccountPage;
