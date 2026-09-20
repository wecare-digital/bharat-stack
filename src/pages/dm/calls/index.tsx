/**
 * Unified Calls — one call log across all voice sources.
 *
 * Reads the canonical MessagesTable channel=voice breadcrumbs (written by voice-aws,
 * voice-in-cdr, and whatsapp-calling), so AWS / Airtel / WhatsApp calls all appear in
 * one place with provider, direction, duration, status, and recording link.
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import { colors } from '../../../lib/design-tokens';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

// Keyed on the `callType` written by put_call_breadcrumb. `plivo` is the current
// PSTN provider. `airtel` is retained ONLY so historical breadcrumbs keep their
// label instead of falling through to the generic "Voice" - nothing writes it any
// more. An unmapped value is not an error, it just renders unlabelled, which is
// why adding a writer without adding an entry here goes unnoticed.
const PROVIDER: Record<string, { label: string; fg: string; bg: string }> = {
    aws: { label: 'AWS', fg: '#1d4ed8', bg: '#eff6ff' },
    plivo: { label: 'Plivo', fg: '#0e7490', bg: '#ecfeff' },
    whatsapp: { label: 'WhatsApp', fg: '#15803d', bg: '#f0fdf4' },
    airtel: { label: 'Airtel (historical)', fg: '#6b7280', bg: '#f9fafb' },
};
const provMeta = ( t?: string ) => PROVIDER[ ( t || '' ).toLowerCase() ] || { label: t || 'Voice', fg: colors.textMuted, bg: colors.bgSecondary };

const fmtDur = ( s?: number ) => {
    if ( !s ) return '—';
    const m = Math.floor( s / 60 ), sec = s % 60;
    return `${m}:${String( sec ).padStart( 2, '0' )}`;
};
const fmtTime = ( ts: string ) => {
    const d = new Date( ts );
    return isNaN( d.getTime() ) ? '' : d.toLocaleString( 'en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' } );
};

const CallsPage: React.FC<PageProps> = ( { signOut, user, embedded } ) => {
    const toast = useToastContext();
    const [ calls, setCalls ] = useState<api.Message[]>( [] );
    const [ names, setNames ] = useState<Record<string, string>>( {} );
    const [ loading, setLoading ] = useState( true );
    const [ provFilter, setProvFilter ] = useState( 'all' );
    const [ dirFilter, setDirFilter ] = useState( 'all' );
    const [ search, setSearch ] = useState( '' );

    const load = useCallback( async () => {
        try
        {
            const [ msgs, contacts ] = await Promise.all( [
                api.listMessages( undefined, 'VOICE', 2000 ),
                api.listContacts(),
            ] );
            const nm: Record<string, string> = {};
            contacts.forEach( c => { nm[ c.contactId ] = c.name || c.phone || c.contactId; } );
            setNames( nm );
            setCalls( msgs );
        } catch { toast.error( 'Failed to load calls' ); }
        finally { setLoading( false ); }
    }, [ toast ] );

    useEffect( () => { load(); const t = setInterval( load, 20000 ); return () => clearInterval( t ); }, [ load ] );

    const rows = useMemo( () => {
        const q = search.trim().toLowerCase();
        return calls
            .filter( c => provFilter === 'all' || ( c.callType || '' ).toLowerCase() === provFilter )
            .filter( c => dirFilter === 'all' || ( c.direction || '' ).toUpperCase() === dirFilter )
            .filter( c => { const who = names[ c.contactId ] || c.senderPhone || c.receivingPhone || ''; return !q || who.toLowerCase().includes( q ) || ( c.content || '' ).toLowerCase().includes( q ); } )
            .sort( ( a, b ) => ( new Date( b.timestamp ).getTime() || 0 ) - ( new Date( a.timestamp ).getTime() || 0 ) );
    }, [ calls, provFilter, dirFilter, search, names ] );

    const content = (
        <>
            <div className="cv-wrap">
                <PageHeader title="Calls" subtitle="Unified call log — AWS, Airtel & WhatsApp calling in one view" icon="voice" />

                <div className="cv-toolbar">
                    <input className="cv-search" placeholder="Search by contact or number…" value={ search } onChange={ e => setSearch( e.target.value ) } />
                    <select className="cv-filter" value={ provFilter } onChange={ e => setProvFilter( e.target.value ) }>
                        {/* Must stay in step with the PROVIDER map above and with
                            the call_type values put_call_breadcrumb actually
                            writes. This list offered Airtel (retired, no longer
                            written) and omitted Plivo, so PSTN calls - the
                            majority - could not be filtered at all. */}
                        <option value="all">All channels</option>
                        <option value="plivo">Phone (PSTN)</option>
                        <option value="whatsapp">WhatsApp</option>
                        <option value="aws">SMS &amp; Voice</option>
                        <option value="elevenlabs">Voice AI (historical)</option>
                        <option value="airtel">Archived (historical)</option>
                    </select>
                    <select className="cv-filter" value={ dirFilter } onChange={ e => setDirFilter( e.target.value ) }>
                        <option value="all">All directions</option>
                        <option value="INBOUND">Incoming</option>
                        <option value="OUTBOUND">Outgoing</option>
                    </select>
                </div>

                <div className="cv-table-wrap">
                    <table className="cv-table">
                        <thead><tr><th>Provider</th><th>Dir</th><th>Contact / Number</th><th>Call</th><th>Duration</th><th>Status</th><th>When</th><th>Rec</th></tr></thead>
                        <tbody>
                            { loading ? <tr><td colSpan={ 8 } className="cv-empty">Loading…</td></tr> :
                                rows.length === 0 ? <tr><td colSpan={ 8 } className="cv-empty">No calls</td></tr> :
                                    rows.map( c => {
                                        const pm = provMeta( c.callType );
                                        const inbound = ( c.direction || '' ).toUpperCase() === 'INBOUND';
                                        return (
                                            <tr key={ c.messageId }>
                                                <td><span className="cv-pill" style={ { color: pm.fg, background: pm.bg } }>{ pm.label }</span></td>
                                                <td>{ inbound ? '↓' : '↑' }</td>
                                                <td className="cv-who">{ names[ c.contactId ] || c.senderPhone || c.receivingPhone || c.contactId || '—' }</td>
                                                <td className="cv-label">{ c.content || '📞 Call' }</td>
                                                <td>{ fmtDur( c.duration ) }</td>
                                                <td className="cv-status">{ ( c.status || '' ).toLowerCase() }</td>
                                                <td className="cv-when">{ fmtTime( c.timestamp ) }</td>
                                                <td>{ c.recordingUrl ? <a href={ c.recordingUrl } target="_blank" rel="noopener noreferrer" className="cv-rec">▶</a> : '—' }</td>
                                            </tr>
                                        );
                                    } ) }
                        </tbody>
                    </table>
                </div>
            </div>

            <style jsx>{ `
                .cv-wrap { padding: 20px; max-width: 1100px; margin: 0 auto; }
                .cv-toolbar { display: flex; gap: 10px; margin: 12px 0; flex-wrap: wrap; }
                .cv-search { flex: 1; min-width: 200px; padding: 9px 14px; border: 1px solid ${colors.border}; border-radius: 10px; font-size: 14px; }
                .cv-filter { padding: 9px 12px; border: 1px solid ${colors.border}; border-radius: 10px; font-size: 13px; background: #fff; }
                .cv-table-wrap { border: 1px solid ${colors.border}; border-radius: 12px; overflow: hidden; background: #fff; overflow-x: auto; }
                .cv-table { width: 100%; border-collapse: collapse; }
                .cv-table th { background: ${colors.bgSecondary}; padding: 10px 14px; text-align: left; font-size: 11px; font-weight: 700; color: ${colors.textMuted}; text-transform: uppercase; }
                .cv-table td { padding: 10px 14px; border-top: 1px solid ${colors.borderLight}; font-size: 13px; color: ${colors.text}; }
                .cv-pill { font-size: 10px; font-weight: 700; padding: 3px 9px; border-radius: 9999px; }
                .cv-who { font-weight: 600; }
                .cv-label { color: ${colors.textSecondary}; }
                .cv-status { text-transform: capitalize; color: ${colors.textSecondary}; }
                .cv-when { color: ${colors.textMuted}; font-size: 12px; white-space: nowrap; }
                .cv-rec { color: ${colors.primary}; text-decoration: none; font-size: 14px; }
                .cv-empty { text-align: center; padding: 40px; color: ${colors.textMuted}; }
            ` }</style>
        </>
    );

    if ( embedded ) return content;
    return (
        <Layout user={ user } onSignOut={ signOut }>
            <SEO title="Calls | WECARE.DIGITAL" description="Unified call log across providers" noindex={ true } />
            { content }
        </Layout>
    );
};

export default CallsPage;
