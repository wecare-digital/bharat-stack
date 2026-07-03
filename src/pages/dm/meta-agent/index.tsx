/**
 * Meta Business Agent — /dm/meta-agent
 * Onboard + configure Meta's Business AI Agent on WhatsApp (per WABA phone number).
 * Backed by the wecare-meta-business-agent Lambda (POST /meta-agent).
 * API: https://api.facebook.com/{entity_id}/agent_onboarding + /agent_config/settings
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import { useToastContext } from '../../../contexts/ToastContext';
import { useConfirm } from '../../../contexts/ConfirmContext';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';

// WhatsApp Business phone-number IDs (entity_id) — from backend `entities` action
const WABAS = [
    { label: 'WABA 1 (+91 93309 94400)', id: '1016149501586345' },
    { label: 'WABA-T (+91 99033 00044)', id: '1055232054343117' },
];
const INTERVALS = [ 0, 300, 900, 1800, 3600, 7200, 28800, 86400 ];

interface Settings {
    agent_id?: string; channel?: string;
    rollout?: { enabled: boolean };
    handoff?: { enabled: boolean; message?: string } | null;
    followup?: { enabled: boolean; followup_interval_in_seconds?: number; message?: string } | null;
    ai_audience?: 'ALLOWLISTED_ONLY' | 'EVERYONE' | null;
}

const MetaAgentPage: React.FC<PageProps> = ( { signOut, user, embedded = false } ) => {
    const toast = useToastContext();
    const confirm = useConfirm();
    const [ entityId, setEntityId ] = useState( WABAS[ 0 ].id );
    const [ settings, setSettings ] = useState<Settings | null>( null );
    const [ loading, setLoading ] = useState( false );
    const [ busy, setBusy ] = useState( '' );

    const call = async ( action: string, extra: Record<string, any> = {} ) => {
        const res = await fetch( `${API_BASE}/meta-agent`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify( { action, entityId, ...extra } ),
        } );
        return res.json();
    };

    const loadSettings = useCallback( async () => {
        setLoading( true );
        try
        {
            const data = await call( 'settings' );
            const s = Array.isArray( data.settings ) ? data.settings[ 0 ] : data.settings;
            setSettings( s || null );
        } catch { toast.error( 'Failed to load agent settings' ); }
        finally { setLoading( false ); }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ entityId ] );

    useEffect( () => { loadSettings(); }, [ loadSettings ] );

    const onboard = async () => {
        if ( !( await confirm( 'Trigger Meta Business Agent onboarding for this WhatsApp number? This creates the agent and schedules data-prep jobs.' ) ) ) return;
        setBusy( 'onboard' );
        try
        {
            const d = await call( 'onboard', { channel: 'whatsapp' } );
            if ( d.onboarding?.agent_id ) toast.success( `Onboarding triggered — agent ${d.onboarding.agent_id}` );
            else toast.error( `Onboarding: ${JSON.stringify( d.onboarding?.error || d )}` );
            loadSettings();
        } finally { setBusy( '' ); }
    };

    const toggle = async ( enabled: boolean ) => {
        setBusy( 'toggle' );
        try
        {
            await call( enabled ? 'enable' : 'disable' );
            toast.success( enabled ? 'Agent enabled — it will respond to new conversations' : 'Agent disabled' );
            loadSettings();
        } finally { setBusy( '' ); }
    };

    const save = async ( patch: Record<string, any> ) => {
        setBusy( 'save' );
        try { await call( 'settings_update', patch ); toast.success( 'Settings saved' ); loadSettings(); }
        finally { setBusy( '' ); }
    };

    const enabled = !!settings?.rollout?.enabled;

    const body = (
        <>
            <SEO title="Meta Business Agent" description="Onboard and configure Meta's WhatsApp Business AI agent" />
            <div style={ { padding: embedded ? 0 : 'var(--space-6)', maxWidth: 820 } }>
                <h1 style={ { fontSize: 'var(--h2)', fontWeight: 700, margin: '0 0 var(--space-4)', color: 'var(--text)' } }>Meta Business Agent</h1>

                <div style={ card }>
                    <label style={ lbl }>WhatsApp Business number</label>
                    <select value={ entityId } onChange={ e => setEntityId( e.target.value ) } style={ { width: '100%' } }>
                        { WABAS.map( w => <option key={ w.id } value={ w.id }>{ w.label }</option> ) }
                    </select>
                    <div style={ { marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-2)' } }>
                        <Button onClick={ onboard } disabled={ busy !== '' }>{ busy === 'onboard' ? 'Onboarding…' : 'Trigger onboarding' }</Button>
                        <Button variant="secondary" onClick={ loadSettings } disabled={ loading }>Refresh</Button>
                    </div>
                </div>

                <div style={ card }>
                    <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center' } }>
                        <h2 style={ h2 }>Agent status</h2>
                        <span className={ `status-pill ${enabled ? 'status-read' : 'status-queued'}` }>{ enabled ? 'ON' : 'OFF' }</span>
                    </div>
                    { loading ? <p style={ { color: 'var(--text-muted)' } }>Loading…</p> : !settings ? (
                        <p style={ { color: 'var(--text-muted)' } }>No agent settings yet — run onboarding first.</p>
                    ) : (
                        <>
                            <p style={ { color: 'var(--text-muted)', fontSize: 13, margin: '4px 0 12px' } }>
                                Agent ID: { settings.agent_id || '—' } · Channel: { settings.channel || 'whatsapp' }
                            </p>
                            <div style={ { display: 'flex', gap: 'var(--space-2)' } }>
                                <Button onClick={ () => toggle( true ) } disabled={ enabled || busy !== '' }>Enable</Button>
                                <Button variant="secondary" onClick={ () => toggle( false ) } disabled={ !enabled || busy !== '' }>Disable</Button>
                            </div>
                        </>
                    ) }
                </div>

                { settings && (
                    <div style={ card }>
                        <h2 style={ h2 }>Audience</h2>
                        <select defaultValue={ settings.ai_audience || 'EVERYONE' }
                            onChange={ e => save( { aiAudience: e.target.value } ) } style={ { width: '100%' } }>
                            <option value="EVERYONE">Everyone</option>
                            <option value="ALLOWLISTED_ONLY">Allowlisted numbers only (controlled rollout)</option>
                        </select>
                    </div>
                ) }
            </div>
        </>
    );

    return embedded ? body : <Layout user={ user } onSignOut={ signOut }>{ body }</Layout>;
};

const card: React.CSSProperties = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', marginBottom: 'var(--space-4)', boxShadow: 'var(--shadow-sm)' };
const h2: React.CSSProperties = { fontSize: 'var(--h4)', fontWeight: 600, margin: '0 0 var(--space-2)', color: 'var(--text)' };
const lbl: React.CSSProperties = { display: 'block', fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 };

export default MetaAgentPage;
