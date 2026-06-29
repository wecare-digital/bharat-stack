/**
 * BSUID & Usernames console (Meta usernames/BSUID rollout 2026)
 * - Subscribe to business_username_updates / user_id_update webhook fields
 * - Delete a Contact Book entry by BSUID
 * - View Parent BSUID account + enrolled portfolios
 * - Claim-status guidance (gated until Meta enables the feature)
 */
import React, { useState } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import { WHATSAPP_PHONES } from '../../../config/constants';
import { useConfirmDanger, RawJsonDrawer } from '../../../components/wa';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const PHONES = [
    { key: 'primary', ...WHATSAPP_PHONES.primary },
    { key: 'secondary', ...WHATSAPP_PHONES.secondary },
];

const WEBHOOK_FIELDS = [
    { field: 'business_username_updates', desc: 'Business username status changes (reserved → approved/deleted)' },
    { field: 'user_id_update', desc: 'A user\u2019s BSUID changed — track identity continuity' },
    { field: 'messages', desc: 'Incoming messages (now carry user_id/BSUID + optional username)' },
];

const card: React.CSSProperties = { background: '#fff', border: '1px solid #e5e5e5', borderRadius: 8, padding: 16, marginBottom: 16 };
const input: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid #d0d0d0', borderRadius: 6, marginTop: 4, marginBottom: 10, fontSize: 14 };
const label: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#444' };
const btn: React.CSSProperties = { padding: '9px 16px', background: '#1a3a2a', color: '#d1f470', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 14, fontWeight: 600 };

const BsuidConsole: React.FC<PageProps> = ( { signOut, user, embedded = false } ) => {
    const toast = useToastContext();
    const confirmDanger = useConfirmDanger();

    const [ phoneIdx, setPhoneIdx ] = useState( 0 );
    const phone = PHONES[ phoneIdx ];

    // Webhook subscription
    const [ selectedFields, setSelectedFields ] = useState<string[]>( [ 'business_username_updates', 'user_id_update' ] );
    const [ subBusy, setSubBusy ] = useState( false );

    // Contact book
    const [ cbBsuid, setCbBsuid ] = useState( '' );
    const [ cbBusy, setCbBusy ] = useState( false );

    // Parent BSUID
    const [ businessId, setBusinessId ] = useState( '' );
    const [ parentResult, setParentResult ] = useState<any>( null );
    const [ parentBusy, setParentBusy ] = useState( false );

    const toggleField = ( f: string ) =>
        setSelectedFields( s => s.includes( f ) ? s.filter( x => x !== f ) : [ ...s, f ] );

    const subscribe = async () => {
        if ( !selectedFields.length ) { toast.error( 'Select at least one field' ); return; }
        setSubBusy( true );
        const res = await api.subscribeWebhookFields( phone.wabaId, selectedFields );
        if ( res.success ) toast.success( 'Subscribed to ' + selectedFields.join( ', ' ) );
        else toast.error( res.error || 'Subscribe failed' );
        setSubBusy( false );
    };

    const deleteContact = async () => {
        if ( !cbBsuid.trim() ) { toast.error( 'Enter a BSUID' ); return; }
        if ( !( await confirmDanger( 'delete', `Delete contact-book entry for BSUID ${cbBsuid}? Their phone number will stop appearing in webhooks (subject to the 30-day cache).` ) ) ) return;
        setCbBusy( true );
        const res = await api.deleteContactBookEntry( phone.metaPhoneId, cbBsuid.trim() );
        if ( res.success ) toast.success( res.deleted ? 'Contact-book entry deleted' : 'No entry found for that BSUID' );
        else toast.error( res.error || 'Delete failed' );
        setCbBusy( false );
    };

    const loadParent = async () => {
        if ( !businessId.trim() ) { toast.error( 'Enter a Business Portfolio ID' ); return; }
        setParentBusy( true );
        const res = await api.getParentBsuidAccounts( businessId.trim() );
        if ( res.error ) { toast.error( res.error ); setParentResult( null ); }
        else setParentResult( res );
        setParentBusy( false );
    };

    const content = (
        <div style={ { maxWidth: 760, margin: '0 auto', padding: 16 } }>
            <SEO title="BSUID & Usernames" description="WhatsApp BSUID and username tooling" noindex />
            <h1 style={ { fontSize: 22, fontWeight: 700, marginBottom: 4 } }>BSUID &amp; Usernames</h1>
            <p style={ { color: '#777', fontSize: 13, marginBottom: 16 } }>
                Manage WhatsApp username/BSUID webhooks and contact-book entries. BSUIDs appear in webhooks (early Apr 2026) and can be messaged (from May 2026); phone numbers may be hidden for username-adopters.
            </p>

            <div style={ card }>
                <label style={ label }>WABA / phone context</label>
                <select style={ input } value={ phoneIdx } onChange={ e => setPhoneIdx( Number( e.target.value ) ) }>
                    { PHONES.map( ( p, i ) => <option key={ p.key } value={ i }>{ p.name } — { p.display } (WABA { p.wabaId })</option> ) }
                </select>
            </div>

            <div style={ card }>
                <h3 style={ { marginTop: 0, fontSize: 15 } }>Webhook subscriptions</h3>
                <p style={ { fontSize: 12, color: '#777' } }>Subscribe this WABA\u2019s app to username/BSUID webhook fields.</p>
                { WEBHOOK_FIELDS.map( f => (
                    <label key={ f.field } style={ { display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 8, fontSize: 13, cursor: 'pointer' } }>
                        <input type="checkbox" checked={ selectedFields.includes( f.field ) } onChange={ () => toggleField( f.field ) } />
                        <span><code>{ f.field }</code> — <span style={ { color: '#666' } }>{ f.desc }</span></span>
                    </label>
                ) ) }
                <button style={ btn } disabled={ subBusy } onClick={ subscribe }>{ subBusy ? 'Subscribing…' : 'Subscribe fields' }</button>
            </div>

            <div style={ card }>
                <h3 style={ { marginTop: 0, fontSize: 15 } }>Contact book — delete entry</h3>
                <p style={ { fontSize: 12, color: '#777' } }>Remove a user\u2019s phone+BSUID from the portfolio contact book.</p>
                <label style={ label }>BSUID (e.g. US.13491208655302741918)</label>
                <input style={ input } value={ cbBsuid } onChange={ e => setCbBsuid( e.target.value ) } placeholder="CC.alphanumeric" />
                <button style={ { ...btn, background: '#fee2e2', color: '#991b1b' } } disabled={ cbBusy } onClick={ deleteContact }>{ cbBusy ? 'Deleting…' : 'Delete contact-book entry' }</button>
            </div>

            <div style={ card }>
                <h3 style={ { marginTop: 0, fontSize: 15 } }>Parent BSUID account</h3>
                <p style={ { fontSize: 12, color: '#777' } }>For managed businesses with multiple portfolios enrolled in a parent BSUID account.</p>
                <label style={ label }>Business Portfolio ID</label>
                <input style={ input } value={ businessId } onChange={ e => setBusinessId( e.target.value ) } placeholder="Business ID" />
                <button style={ btn } disabled={ parentBusy } onClick={ loadParent }>{ parentBusy ? 'Loading…' : 'Get parent BSUID account' }</button>
                { parentResult && (
                    <div style={ { marginTop: 10, fontSize: 13 } }>
                        <div><strong>Account ID:</strong> { parentResult.parentBsuidAccountId || '(none)' }</div>
                        <div><strong>Enrolled portfolios:</strong> { ( parentResult.enrolledBusinessPortfolios || [] ).join( ', ' ) || '(none)' }</div>
                        <RawJsonDrawer data={ parentResult } label="Raw response" />
                    </div>
                ) }
            </div>

            <div style={ { ...card, background: '#f0f9ff', border: '1px solid #bae6fd' } }>
                <h3 style={ { marginTop: 0, fontSize: 15, color: '#0369a1' } }>Business username claim</h3>
                <p style={ { fontSize: 13, color: '#0369a1', margin: 0 } }>
                    The username feature is currently <strong>gated</strong> for these accounts (Meta error 147000). Claim via the API once enabled: run <code>scripts/_claim_username.py --phone { phone.metaPhoneId } --suggest</code>. See <code>docs/META_USERNAME_ACCESS_REQUEST.md</code> for the access-request email.
                </p>
            </div>
        </div>
    );

    if ( embedded ) return content;
    return <Layout user={ user } onSignOut={ signOut }>{ content }</Layout>;
};

export default BsuidConsole;
