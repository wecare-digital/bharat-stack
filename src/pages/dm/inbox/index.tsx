/**
 * Unified Inbox — conversation-grouped view across ALL channels.
 *
 * Reads the single canonical MessagesTable (via api.listMessages channel=ALL), groups
 * by contact, and shows a threaded conversation with per-message channel badges.
 * Sending is channel-specific, so replies deep-link to the channel's own tool.
 *
 * WhatsApp's dedicated inbox (/dm/whatsapp) stays as-is for full WhatsApp send features.
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import { colors, shadow } from '../../../lib/design-tokens';

interface PageProps {
    signOut?: () => void;
    user?: any;
    embedded?: boolean;
}

// Channel identity (distinct, on-brand) + reply deep-link target.
const CHANNEL: Record<string, { label: string; fg: string; bg: string; reply: string }> = {
    whatsapp: { label: 'WhatsApp', fg: '#15803d', bg: '#f0fdf4', reply: '/dm/whatsapp' },
    sms: { label: 'SMS', fg: '#1d4ed8', bg: '#eff6ff', reply: '/dm/sms' },
    email: { label: 'Email', fg: '#b45309', bg: '#fffbeb', reply: '/dm/ses' },
    rcs: { label: 'RCS', fg: '#0f766e', bg: '#f0fdfa', reply: '/dm/rcs' },
    voice: { label: 'Voice', fg: '#6d28d9', bg: '#f5f3ff', reply: '/dm/voice' },
};

const chMeta = ( c?: string ) => CHANNEL[ ( c || 'whatsapp' ).toLowerCase() ] || { label: c || '?', fg: colors.textMuted, bg: colors.bgSecondary, reply: '/dm' };

interface Conversation {
    contactId: string;
    name: string;
    channels: Set<string>;
    lastContent: string;
    lastTs: number;
    lastChannel: string;
}

const fmtTime = ( ts: string | number ) => {
    const d = new Date( typeof ts === 'number' ? ts : ts );
    if ( isNaN( d.getTime() ) ) return '';
    const now = Date.now();
    const diff = now - d.getTime();
    if ( diff < 86400000 ) return d.toLocaleTimeString( 'en-IN', { hour: '2-digit', minute: '2-digit' } );
    return d.toLocaleDateString( 'en-IN', { day: '2-digit', month: 'short' } );
};

const UnifiedInbox: React.FC<PageProps> = ( { signOut, user, embedded } ) => {
    const toast = useToastContext();
    const [ messages, setMessages ] = useState<api.Message[]>( [] );
    const [ contactNames, setContactNames ] = useState<Record<string, string>>( {} );
    const [ selected, setSelected ] = useState<string | null>( null );
    const [ channelFilter, setChannelFilter ] = useState<string>( 'ALL' );
    const [ search, setSearch ] = useState( '' );
    const [ loading, setLoading ] = useState( true );
    const [ replyText, setReplyText ] = useState( '' );
    const [ sending, setSending ] = useState( false );

    const loadData = useCallback( async () => {
        try
        {
            const [ msgs, contacts ] = await Promise.all( [
                api.listMessages( undefined, 'ALL', 2000 ),
                api.listContacts(),
            ] );
            const names: Record<string, string> = {};
            contacts.forEach( c => { names[ c.contactId ] = c.name || c.phone || c.email || c.contactId; } );
            setContactNames( names );
            setMessages( msgs );
        } catch
        {
            toast.error( 'Failed to load inbox' );
        } finally
        {
            setLoading( false );
        }
    }, [ toast ] );

    useEffect( () => {
        loadData();
        const t = setInterval( loadData, 15000 );
        return () => clearInterval( t );
    }, [ loadData ] );

    // Group messages into conversations by contact.
    const conversations = useMemo<Conversation[]>( () => {
        const map = new Map<string, Conversation>();
        for ( const m of messages )
        {
            const ch = ( m.channel || 'whatsapp' ).toLowerCase();
            if ( channelFilter !== 'ALL' && ch !== channelFilter ) continue;
            const cid = m.contactId || m.senderPhone || m.receivingPhone || 'unknown';
            const ts = new Date( m.timestamp ).getTime() || 0;
            const existing = map.get( cid );
            if ( !existing )
            {
                map.set( cid, {
                    contactId: cid,
                    name: contactNames[ cid ] || m.senderName || m.senderPhone || m.receivingPhone || cid,
                    channels: new Set( [ ch ] ),
                    lastContent: m.content || `[${m.messageType || ch}]`,
                    lastTs: ts,
                    lastChannel: ch,
                } );
            } else
            {
                existing.channels.add( ch );
                if ( ts > existing.lastTs )
                {
                    existing.lastTs = ts;
                    existing.lastContent = m.content || `[${m.messageType || ch}]`;
                    existing.lastChannel = ch;
                }
            }
        }
        let list = Array.from( map.values() );
        if ( search.trim() )
        {
            const q = search.toLowerCase();
            list = list.filter( c => c.name.toLowerCase().includes( q ) || c.lastContent.toLowerCase().includes( q ) );
        }
        return list.sort( ( a, b ) => b.lastTs - a.lastTs );
    }, [ messages, contactNames, channelFilter, search ] );

    // Thread for the selected conversation (chronological).
    const thread = useMemo( () => {
        if ( !selected ) return [];
        return messages
            .filter( m => ( m.contactId || m.senderPhone || m.receivingPhone || 'unknown' ) === selected )
            .filter( m => channelFilter === 'ALL' || ( m.channel || 'whatsapp' ).toLowerCase() === channelFilter )
            .sort( ( a, b ) => ( new Date( a.timestamp ).getTime() || 0 ) - ( new Date( b.timestamp ).getTime() || 0 ) );
    }, [ messages, selected, channelFilter ] );

    const selectedConv = conversations.find( c => c.contactId === selected );
    const replyChannel = thread.length ? ( thread[ thread.length - 1 ].channel || 'whatsapp' ).toLowerCase() : 'whatsapp';

    // Derive the reply target (recipient phone, WABA, contactId) from the thread.
    const replyTarget = useMemo( () => {
        let phone = '';
        let waba = '';
        for ( let i = thread.length - 1; i >= 0; i-- )
        {
            const m = thread[ i ];
            if ( !phone )
            {
                phone = ( ( m.direction || '' ).toUpperCase() === 'INBOUND' ? m.senderPhone : m.receivingPhone )
                    || m.senderPhone || m.receivingPhone || '';
            }
            if ( !waba && m.awsPhoneNumberId ) waba = m.awsPhoneNumberId;
            if ( phone && waba ) break;
        }
        const isPhone = /^\+?\d{6,}$/.test( selected || '' );
        const contactId = isPhone ? '' : ( selected || '' );
        if ( isPhone && !phone ) phone = selected || '';
        return { phone, waba, contactId };
    }, [ thread, selected ] );

    const handleReply = useCallback( async () => {
        const text = replyText.trim();
        if ( !text || sending ) return;
        const { phone, waba, contactId } = replyTarget;
        setSending( true );
        try
        {
            let ok = false;
            if ( replyChannel === 'whatsapp' )
            {
                if ( !contactId ) { toast.error( 'WhatsApp reply needs a saved contact — open the WhatsApp inbox' ); setSending( false ); return; }
                const r = await api.sendWhatsAppMessage( { contactId, content: text, phoneNumberId: waba || undefined } );
                ok = !!r;
            } else if ( replyChannel === 'sms' )
            {
                if ( !phone ) { toast.error( 'No phone number for this conversation' ); setSending( false ); return; }
                const r = await api.sendSmsAws( { contactId: contactId || undefined, phoneNumber: phone, content: text, messageType: 'TRANSACTIONAL' } );
                ok = !!( r && ( r.messageId || r.status === 'sent' ) );
            } else if ( replyChannel === 'rcs' )
            {
                if ( !phone ) { toast.error( 'No phone number for this conversation' ); setSending( false ); return; }
                const r = await api.sendRcs( { phoneNumber: phone, text } );
                ok = !!( r && ( r.success || r.messageId ) );
            } else if ( replyChannel === 'email' )
            {
                if ( !contactId ) { toast.error( 'Email reply needs a saved contact' ); setSending( false ); return; }
                const r = await api.sendEmailMessage( contactId, 'Re: your conversation', text );
                ok = !!r;
            }
            if ( ok )
            {
                setReplyText( '' );
                toast.success( `Sent via ${chMeta( replyChannel ).label}` );
                setTimeout( loadData, 800 );
            } else
            {
                toast.error( 'Failed to send' );
            }
        } catch
        {
            toast.error( 'Failed to send' );
        } finally
        {
            setSending( false );
        }
    }, [ replyText, sending, replyTarget, replyChannel, toast, loadData ] );

    const content = (
        <>
            <div className="ui-wrap">

                <PageHeader title="Unified Inbox" subtitle="All channels in one place — WhatsApp, SMS, Email, RCS, Voice" icon="message" />

                <div className="ui-toolbar">
                    <input className="ui-search" placeholder="Search conversations…" value={ search } onChange={ e => setSearch( e.target.value ) } />
                    <select className="ui-filter" value={ channelFilter } onChange={ e => setChannelFilter( e.target.value ) }>
                        <option value="ALL">All channels</option>
                        <option value="whatsapp">WhatsApp</option>
                        <option value="sms">SMS</option>
                        <option value="email">Email</option>
                        <option value="rcs">RCS</option>
                        <option value="voice">Voice</option>
                    </select>
                </div>

                <div className="ui-panes">
                    <div className="ui-list">
                        { loading ? (
                            <div className="ui-empty">Loading…</div>
                        ) : conversations.length === 0 ? (
                            <div className="ui-empty">No conversations</div>
                        ) : conversations.map( c => {
                            const m = chMeta( c.lastChannel );
                            return (
                                <button key={ c.contactId } className={ `ui-conv ${selected === c.contactId ? 'active' : ''}` } onClick={ () => setSelected( c.contactId ) }>
                                    <div className="ui-conv-top">
                                        <span className="ui-conv-name">{ c.name }</span>
                                        <span className="ui-conv-time">{ fmtTime( c.lastTs ) }</span>
                                    </div>
                                    <div className="ui-conv-bottom">
                                        <span className="ui-conv-preview">{ c.lastContent.slice( 0, 48 ) }</span>
                                        <span className="ui-badges">
                                            { Array.from( c.channels ).map( ch => {
                                                const cm = chMeta( ch );
                                                return <span key={ ch } className="ui-badge" style={ { color: cm.fg, background: cm.bg } }>{ cm.label }</span>;
                                            } ) }
                                        </span>
                                    </div>
                                </button>
                            );
                        } ) }
                    </div>

                    <div className="ui-thread">
                        { !selected ? (
                            <div className="ui-empty">Select a conversation</div>
                        ) : (
                            <>
                                <div className="ui-thread-head">
                                    <span className="ui-thread-name">{ selectedConv?.name }</span>
                                    <span className="ui-badges">
                                        { selectedConv && Array.from( selectedConv.channels ).map( ch => {
                                            const cm = chMeta( ch );
                                            return <span key={ ch } className="ui-badge" style={ { color: cm.fg, background: cm.bg } }>{ cm.label }</span>;
                                        } ) }
                                    </span>
                                </div>
                                <div className="ui-thread-body">
                                    { thread.map( m => {
                                        const ch = ( m.channel || 'whatsapp' ).toLowerCase();
                                        const cm = chMeta( ch );
                                        const out = ( m.direction || '' ).toUpperCase() === 'OUTBOUND';
                                        return (
                                            <div key={ m.messageId } className={ `ui-msg ${out ? 'out' : 'in'}` }>
                                                <div className="ui-msg-bubble">
                                                    <span className="ui-badge" style={ { color: cm.fg, background: cm.bg } }>{ cm.label }</span>
                                                    <span className="ui-msg-text">{ m.content || `[${m.messageType || ch}]` }</span>
                                                    <span className="ui-msg-meta">{ fmtTime( m.timestamp ) } · { ( m.status || '' ).toLowerCase() }</span>
                                                </div>
                                            </div>
                                        );
                                    } ) }
                                </div>
                                <div className="ui-reply">
                                    { replyChannel === 'voice' ? (
                                        <div className="ui-reply-voice">
                                            <span>This is a call — reply by calling back.</span>
                                            <Link href={ chMeta( 'voice' ).reply } className="ui-reply-link">Open Voice →</Link>
                                        </div>
                                    ) : (
                                        <>
                                            <textarea
                                                className="ui-reply-input"
                                                placeholder={ `Reply via ${chMeta( replyChannel ).label}…` }
                                                value={ replyText }
                                                onChange={ e => setReplyText( e.target.value ) }
                                                onKeyDown={ e => { if ( e.key === 'Enter' && ( e.ctrlKey || e.metaKey ) ) handleReply(); } }
                                                rows={ 2 }
                                            />
                                            <div className="ui-reply-actions">
                                                <span className="ui-reply-via" style={ { color: chMeta( replyChannel ).fg, background: chMeta( replyChannel ).bg } }>via { chMeta( replyChannel ).label }</span>
                                                <Link href={ chMeta( replyChannel ).reply } className="ui-reply-link">Full tool →</Link>
                                                <button className="ui-reply-btn" disabled={ sending || !replyText.trim() } onClick={ handleReply }>{ sending ? 'Sending…' : 'Send' }</button>
                                            </div>
                                        </>
                                    ) }
                                </div>
                            </>
                        ) }
                    </div>
                </div>
            </div>

            <style jsx>{ `
        .ui-wrap { padding: 20px; max-width: 1200px; margin: 0 auto; }
        .ui-toolbar { display: flex; gap: 12px; margin: 12px 0; }
        .ui-search { flex: 1; padding: 9px 14px; border: 1px solid ${colors.border}; border-radius: 10px; font-size: 14px; }
        .ui-filter { padding: 9px 12px; border: 1px solid ${colors.border}; border-radius: 10px; font-size: 13px; background: #fff; }
        .ui-panes { display: grid; grid-template-columns: 340px 1fr; gap: 16px; height: 70vh; }
        .ui-list { border: 1px solid ${colors.border}; border-radius: 12px; overflow-y: auto; background: #fff; }
        .ui-conv { display: block; width: 100%; text-align: left; padding: 12px 14px; border: none; border-bottom: 1px solid ${colors.borderLight}; background: #fff; cursor: pointer; }
        .ui-conv:hover { background: ${colors.bgHover}; }
        .ui-conv.active { background: ${colors.bgActive}; }
        .ui-conv-top { display: flex; justify-content: space-between; align-items: center; }
        .ui-conv-name { font-weight: 600; font-size: 14px; color: ${colors.text}; }
        .ui-conv-time { font-size: 11px; color: ${colors.textMuted}; }
        .ui-conv-bottom { display: flex; justify-content: space-between; align-items: center; margin-top: 4px; gap: 8px; }
        .ui-conv-preview { font-size: 12px; color: ${colors.textSecondary}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ui-badges { display: flex; gap: 4px; flex-shrink: 0; }
        .ui-badge { font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 9999px; white-space: nowrap; }
        .ui-thread { border: 1px solid ${colors.border}; border-radius: 12px; display: flex; flex-direction: column; background: #fff; overflow: hidden; }
        .ui-thread-head { padding: 12px 16px; border-bottom: 1px solid ${colors.border}; display: flex; justify-content: space-between; align-items: center; }
        .ui-thread-name { font-weight: 700; font-size: 15px; color: ${colors.text}; }
        .ui-thread-body { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; background: ${colors.bgSecondary}; }
        .ui-msg { display: flex; }
        .ui-msg.out { justify-content: flex-end; }
        .ui-msg-bubble { max-width: 70%; background: #fff; border: 1px solid ${colors.border}; border-radius: 12px; padding: 8px 12px; display: flex; flex-direction: column; gap: 4px; }
        .ui-msg.out .ui-msg-bubble { background: ${colors.lime}; border-color: ${colors.lime}; }
        .ui-msg-text { font-size: 14px; color: ${colors.text}; white-space: pre-wrap; word-break: break-word; }
        .ui-msg-meta { font-size: 10px; color: ${colors.textMuted}; }
        .ui-reply { padding: 12px 16px; border-top: 1px solid ${colors.border}; display: flex; flex-direction: column; gap: 8px; }
        .ui-reply-input { width: 100%; resize: vertical; padding: 9px 12px; border: 1px solid ${colors.border}; border-radius: 10px; font-size: 14px; font-family: inherit; }
        .ui-reply-input:focus { outline: none; border-color: ${colors.primary}; box-shadow: ${shadow.focus}; }
        .ui-reply-actions { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
        .ui-reply-via { font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 9999px; margin-right: auto; }
        .ui-reply-link { font-size: 12px; color: ${colors.textMuted}; text-decoration: none; }
        .ui-reply-link:hover { color: ${colors.primary}; }
        .ui-reply-voice { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: ${colors.textMuted}; width: 100%; }
        .ui-reply-btn { background: ${colors.primary}; color: #fff; padding: 8px 18px; border: none; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; }
        .ui-reply-btn:hover:not(:disabled) { background: ${colors.primaryHover}; }
        .ui-reply-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .ui-empty { display: flex; align-items: center; justify-content: center; height: 100%; color: ${colors.textMuted}; font-size: 14px; }
        @media (max-width: 800px) { .ui-panes { grid-template-columns: 1fr; height: auto; } }
      ` }</style>
        </>
    );

    if ( embedded ) return content;
    return <Layout user={ user } onSignOut={ signOut }>{ content }</Layout>;
};

export default UnifiedInbox;
