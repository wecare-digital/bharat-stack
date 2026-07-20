/**
 * Meta Business AI Agent — management console
 * Control where the AI's answers come from and how it behaves:
 *   - Status & Settings (enable/disable, audience, handoff, follow-up)
 *   - Business Info (structured knowledge)
 *   - FAQs (authored Q&A — the answers the AI gives)
 *   - Allowlist (controlled rollout)
 * Backend: POST ${API_BASE}/meta-agent  (wecare-meta-business-agent)
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../../../api/client';
import { useToastContext } from '../../../contexts/ToastContext';
import Spinner from '../../../components/ui/Spinner';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

type WabaKey = api.WabaKey;
type Tab = 'settings' | 'business' | 'faqs' | 'allowlist';

const WABAS: { key: WabaKey; label: string }[] = [
    { key: 'WABA1', label: 'WABA1 · WECARE.DIGITAL (+91 93309 94400)' },
    { key: 'WABA2', label: 'WABA2 · Manish Agarwal (+91 99033 00044)' },
];
const INTERVALS = [ 0, 300, 900, 1800, 3600, 7200, 28800, 86400 ];
const intervalLabel = ( s: number ) =>
    s === 0 ? 'Off' : s < 3600 ? `${s / 60} min` : s < 86400 ? `${s / 3600} hr` : '1 day';

const card: React.CSSProperties = { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 16 };
const label: React.CSSProperties = { display: 'block', fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' };
const input: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14, marginBottom: 12 };
const btn = ( bg: string ): React.CSSProperties => ( { padding: '8px 16px', background: bg, color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' } );

export default function AiAgentPage ( { }: PageProps ) {
    const toast = useToastContext();
    const [ waba, setWaba ] = useState<WabaKey>( 'WABA1' );
    const [ tab, setTab ] = useState<Tab>( 'settings' );

    // Settings + eligibility
    const [ eligible, setEligible ] = useState<boolean | null>( null );
    const [ settings, setSettings ] = useState<api.AgentSettings | null>( null );
    const [ settingsLoading, setSettingsLoading ] = useState( false );
    const [ saving, setSaving ] = useState( false );

    // Business info
    const [ info, setInfo ] = useState<api.AgentBusinessInfo>( {} );
    const [ infoLoading, setInfoLoading ] = useState( false );

    // FAQs
    const [ faqs, setFaqs ] = useState<api.AgentFaq[]>( [] );
    const [ faqsLoading, setFaqsLoading ] = useState( false );
    const [ newQ, setNewQ ] = useState( '' );
    const [ newA, setNewA ] = useState( '' );

    // Allowlist
    const [ allow, setAllow ] = useState<api.AgentAllowlistEntry[]>( [] );
    const [ allowLoading, setAllowLoading ] = useState( false );
    const [ newPhone, setNewPhone ] = useState( '' );

    // ── loaders ──
    const loadSettings = useCallback( async () => {
        setSettingsLoading( true );
        try
        {
            const [ el, st ] = await Promise.all( [ api.aiAgentApi.eligibility( waba ), api.aiAgentApi.getSettings( waba ) ] );
            setEligible( el?.eligibility?.is_eligible ?? null );
            const s = st?.settings;
            setSettings( Array.isArray( s ) ? ( s[ 0 ] ?? null ) : ( s ?? null ) );
        } catch { toast.error( 'Failed to load agent settings' ); }
        finally { setSettingsLoading( false ); }
    }, [ waba, toast ] );

    const loadInfo = useCallback( async () => {
        setInfoLoading( true );
        try { const r = await api.aiAgentApi.getBusinessInfo( waba ); setInfo( r?.business_info ?? {} ); }
        catch { toast.error( 'Failed to load business info' ); }
        finally { setInfoLoading( false ); }
    }, [ waba, toast ] );

    const loadFaqs = useCallback( async () => {
        setFaqsLoading( true );
        try { const r = await api.aiAgentApi.listFaqs( waba ); setFaqs( Array.isArray( r?.faqs ) ? r!.faqs : [] ); }
        catch { toast.error( 'Failed to load FAQs' ); }
        finally { setFaqsLoading( false ); }
    }, [ waba, toast ] );

    const loadAllow = useCallback( async () => {
        setAllowLoading( true );
        try { const r = await api.aiAgentApi.listAllowlist( waba ); setAllow( Array.isArray( r?.allowlist ) ? r!.allowlist : [] ); }
        catch { toast.error( 'Failed to load allowlist' ); }
        finally { setAllowLoading( false ); }
    }, [ waba, toast ] );

    useEffect( () => {
        if ( tab === 'settings' ) loadSettings();
        else if ( tab === 'business' ) loadInfo();
        else if ( tab === 'faqs' ) loadFaqs();
        else if ( tab === 'allowlist' ) loadAllow();
    }, [ tab, waba, loadSettings, loadInfo, loadFaqs, loadAllow ] );

    // ── settings mutators ──
    const saveSettings = async ( patch: Partial<api.AgentSettings> & { enabled?: boolean; aiAudience?: string } ) => {
        setSaving( true );
        try
        {
            const r = await api.aiAgentApi.updateSettings( waba, patch );
            if ( r?.settings ) { setSettings( r.settings ); toast.success( 'Agent settings updated' ); }
            else toast.error( 'Update failed (check terms accepted)' );
        } catch { toast.error( 'Update failed' ); }
        finally { setSaving( false ); }
    };

    const enabled = !!settings?.rollout?.enabled;
    const audience = settings?.ai_audience ?? 'EVERYONE';

    // ── render helpers ──
    const TabBtn = ( { id, children }: { id: Tab; children: React.ReactNode } ) => (
        <button onClick={ () => setTab( id ) } style={ {
            padding: '8px 14px', border: 'none', borderBottom: tab === id ? '2px solid #059669' : '2px solid transparent',
            background: 'none', color: tab === id ? '#059669' : '#6b7280', fontWeight: 600, fontSize: 14, cursor: 'pointer',
        } }>{ children }</button>
    );

    return (
        <div style={ { padding: '4px 4px 40px' } }>
            {/* WABA selector + eligibility */ }
            <div style={ { display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' } }>
                <select value={ waba } onChange={ e => setWaba( e.target.value as WabaKey ) }
                    style={ { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14, fontWeight: 600 } }>
                    { WABAS.map( w => <option key={ w.key } value={ w.key }>{ w.label }</option> ) }
                </select>
                { eligible !== null && (
                    <span style={ {
                        fontSize: 12, fontWeight: 600, padding: '4px 10px', borderRadius: 10,
                        background: eligible ? '#f0fdf4' : '#fef2f2', color: eligible ? '#059669' : '#dc2626'
                    } }>
                        { eligible ? '● Eligible (terms accepted)' : '● Not eligible — accept AI terms in WhatsApp Manager' }
                    </span>
                ) }
                { enabled && <span style={ { fontSize: 12, fontWeight: 700, padding: '4px 10px', borderRadius: 10, background: '#ecfdf5', color: '#047857' } }>AI ON · { audience }</span> }
            </div>

            <div style={ { borderBottom: '1px solid #e5e7eb', marginBottom: 20, display: 'flex', gap: 4, flexWrap: 'wrap' } }>
                <TabBtn id="settings">Status & Settings</TabBtn>
                <TabBtn id="business">Business Info</TabBtn>
                <TabBtn id="faqs">FAQs</TabBtn>
                <TabBtn id="allowlist">Allowlist</TabBtn>
            </div>

            {/* ── SETTINGS ── */ }
            { tab === 'settings' && ( settingsLoading ? <Spinner /> : (
                <div style={ card }>
                    <h3 style={ { margin: '0 0 16px', fontSize: 16, color: '#111827' } }>Agent behaviour</h3>
                    <div style={ { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid #f3f4f6' } }>
                        <div><b>AI responder</b><div style={ { fontSize: 12, color: '#6b7280' } }>When on, the AI answers customers directly.</div></div>
                        <button disabled={ saving } onClick={ () => saveSettings( { enabled: !enabled } ) }
                            style={ btn( enabled ? '#dc2626' : '#059669' ) }>{ enabled ? 'Turn OFF' : 'Turn ON' }</button>
                    </div>
                    <div style={ { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid #f3f4f6' } }>
                        <div><b>Audience</b><div style={ { fontSize: 12, color: '#6b7280' } }>Who the AI replies to.</div></div>
                        <select value={ audience } disabled={ saving } onChange={ e => saveSettings( { aiAudience: e.target.value } ) }
                            style={ { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 } }>
                            <option value="EVERYONE">Everyone</option>
                            <option value="ALLOWLISTED_ONLY">Allowlisted only</option>
                        </select>
                    </div>
                    <div style={ { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid #f3f4f6' } }>
                        <div><b>Handoff to human</b><div style={ { fontSize: 12, color: '#6b7280' } }>{ settings?.handoff?.message || 'Connecting you to our team.' }</div></div>
                        <button disabled={ saving } onClick={ () => saveSettings( { handoff: { enabled: !settings?.handoff?.enabled, message: settings?.handoff?.message || 'Connecting you to our team.' } } ) }
                            style={ btn( settings?.handoff?.enabled ? '#6b7280' : '#059669' ) }>{ settings?.handoff?.enabled ? 'Enabled' : 'Disabled' }</button>
                    </div>
                    <div style={ { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0' } }>
                        <div><b>Follow-up after inactivity</b></div>
                        <select value={ settings?.followup?.followup_interval_in_seconds ?? 0 } disabled={ saving }
                            onChange={ e => saveSettings( { followup: { enabled: Number( e.target.value ) > 0, followup_interval_in_seconds: Number( e.target.value ) } } ) }
                            style={ { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 } }>
                            { INTERVALS.map( s => <option key={ s } value={ s }>{ intervalLabel( s ) }</option> ) }
                        </select>
                    </div>
                </div>
            ) ) }

            {/* ── BUSINESS INFO ── */ }
            { tab === 'business' && ( infoLoading ? <Spinner /> : (
                <div style={ card }>
                    <h3 style={ { margin: '0 0 16px', fontSize: 16, color: '#111827' } }>Business info the AI can reference</h3>
                    <label style={ label }>Business description</label>
                    <textarea style={ { ...input, minHeight: 70 } } value={ info.business_description || '' } onChange={ e => setInfo( { ...info, business_description: e.target.value } ) } />
                    <label style={ label }>How to purchase</label>
                    <textarea style={ { ...input, minHeight: 50 } } value={ info.purchase_info || '' } onChange={ e => setInfo( { ...info, purchase_info: e.target.value } ) } />
                    <label style={ label }>Payment method</label>
                    <textarea style={ { ...input, minHeight: 50 } } value={ info.payment_method || '' } onChange={ e => setInfo( { ...info, payment_method: e.target.value } ) } />
                    <label style={ label }>Delivery & shipping</label>
                    <textarea style={ { ...input, minHeight: 50 } } value={ info.delivery_and_shipping || '' } onChange={ e => setInfo( { ...info, delivery_and_shipping: e.target.value } ) } />
                    <label style={ label }>Return policy</label>
                    <textarea style={ { ...input, minHeight: 50 } } value={ info.return_policy || '' } onChange={ e => setInfo( { ...info, return_policy: e.target.value } ) } />
                    <div style={ { display: 'flex', gap: 12 } }>
                        <div style={ { flex: 1 } }><label style={ label }>Contact email</label>
                            <input style={ input } value={ info.contact_info?.email || '' } onChange={ e => setInfo( { ...info, contact_info: { ...info.contact_info, email: e.target.value } } ) } /></div>
                        <div style={ { flex: 1 } }><label style={ label }>Hours</label>
                            <input style={ input } value={ info.contact_info?.hours_of_operation || '' } onChange={ e => setInfo( { ...info, contact_info: { ...info.contact_info, hours_of_operation: e.target.value } } ) } /></div>
                    </div>
                    <label style={ label }>Address</label>
                    <input style={ input } value={ info.contact_info?.address || '' } onChange={ e => setInfo( { ...info, contact_info: { ...info.contact_info, address: e.target.value } } ) } />
                    <button disabled={ saving } onClick={ async () => {
                        setSaving( true );
                        try { const r = await api.aiAgentApi.updateBusinessInfo( waba, info ); if ( r?.business_info ) { setInfo( r.business_info ); toast.success( 'Business info saved' ); } else toast.error( 'Save failed' ); }
                        finally { setSaving( false ); }
                    } } style={ btn( '#059669' ) }>Save business info</button>
                </div>
            ) ) }

            {/* ── FAQs ── */ }
            { tab === 'faqs' && (
                <div>
                    <div style={ card }>
                        <h3 style={ { margin: '0 0 12px', fontSize: 16, color: '#111827' } }>Add an FAQ (this becomes the AI's answer)</h3>
                        <label style={ label }>Question (as a customer would ask)</label>
                        <input style={ input } value={ newQ } onChange={ e => setNewQ( e.target.value ) } placeholder="What is your return policy?" />
                        <label style={ label }>Answer (complete & self-contained)</label>
                        <textarea style={ { ...input, minHeight: 70 } } value={ newA } onChange={ e => setNewA( e.target.value ) } />
                        <button disabled={ saving || !newQ.trim() || !newA.trim() } onClick={ async () => {
                            setSaving( true );
                            try { const r = await api.aiAgentApi.createFaq( waba, newQ.trim(), newA.trim() ); if ( r?.faq ) { setNewQ( '' ); setNewA( '' ); toast.success( 'FAQ added' ); loadFaqs(); } else toast.error( 'Add failed' ); }
                            finally { setSaving( false ); }
                        } } style={ btn( '#059669' ) }>Add FAQ</button>
                    </div>
                    { faqsLoading ? <Spinner /> : (
                        <div style={ card }>
                            <h3 style={ { margin: '0 0 12px', fontSize: 16, color: '#111827' } }>FAQs ({ faqs.length })</h3>
                            { faqs.length === 0 && <div style={ { color: '#9ca3af', fontSize: 14 } }>No FAQs yet.</div> }
                            { faqs.map( f => (
                                <div key={ f.id } style={ { borderBottom: '1px solid #f3f4f6', padding: '10px 0' } }>
                                    <div style={ { fontWeight: 600, color: '#111827' } }>{ f.question }</div>
                                    <div style={ { fontSize: 13, color: '#4b5563', margin: '4px 0' } }>{ f.answer }</div>
                                    <button onClick={ async () => {
                                        if ( !f.id ) return;
                                        const ok = await api.aiAgentApi.deleteFaq( waba, f.id );
                                        if ( ok?.deleted ) { toast.success( 'Deleted' ); loadFaqs(); } else toast.error( 'Delete failed' );
                                    } } style={ { ...btn( '#fef2f2' ), color: '#dc2626', padding: '4px 10px', fontSize: 12 } }>Delete</button>
                                </div>
                            ) ) }
                        </div>
                    ) }
                </div>
            ) }

            {/* ── ALLOWLIST ── */ }
            { tab === 'allowlist' && (
                <div>
                    <div style={ card }>
                        <h3 style={ { margin: '0 0 8px', fontSize: 16, color: '#111827' } }>Allowlist</h3>
                        <p style={ { fontSize: 12, color: '#6b7280', margin: '0 0 12px' } }>Only used when Audience = "Allowlisted only". Add consumer numbers in E.164 (e.g. +918100640044).</p>
                        <div style={ { display: 'flex', gap: 8 } }>
                            <input style={ { ...input, marginBottom: 0 } } value={ newPhone } onChange={ e => setNewPhone( e.target.value ) } placeholder="+918100640044" />
                            <button disabled={ saving || !newPhone.trim() } onClick={ async () => {
                                setSaving( true );
                                try { const r = await api.aiAgentApi.addAllowlist( waba, newPhone.trim() ); if ( r?.entry ) { setNewPhone( '' ); toast.success( 'Added' ); loadAllow(); } else toast.error( 'Add failed' ); }
                                finally { setSaving( false ); }
                            } } style={ btn( '#059669' ) }>Add</button>
                        </div>
                    </div>
                    { allowLoading ? <Spinner /> : (
                        <div style={ card }>
                            { allow.length === 0 && <div style={ { color: '#9ca3af', fontSize: 14 } }>No numbers allowlisted.</div> }
                            { allow.map( a => (
                                <div key={ a.id } style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f3f4f6', padding: '8px 0' } }>
                                    <span style={ { fontFamily: 'monospace', fontSize: 14 } }>{ a.consumer_phone_number }</span>
                                    <button onClick={ async () => {
                                        const ok = await api.aiAgentApi.removeAllowlist( waba, a.id );
                                        if ( ok?.deleted ) { toast.success( 'Removed' ); loadAllow(); } else toast.error( 'Remove failed' );
                                    } } style={ { ...btn( '#fef2f2' ), color: '#dc2626', padding: '4px 10px', fontSize: 12 } }>Remove</button>
                                </div>
                            ) ) }
                        </div>
                    ) }
                </div>
            ) }
        </div>
    );
}
