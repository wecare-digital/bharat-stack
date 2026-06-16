/**
 * Unified Inbox — conversation-grouped view across ALL channels.
 *
 * Reads the single canonical MessagesTable (via api.listMessages channel=ALL), groups
 * by contact, and shows a threaded conversation with per-message channel badges.
 * Sending is channel-specific, so replies deep-link to the channel's own tool.
 *
 * WhatsApp's dedicated inbox (/dm/whatsapp) stays as-is for full WhatsApp send features.
 */

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import InteractiveMessageComposer from '../../../components/InteractiveMessageComposer';
import ContactMessageComposer from '../../../components/ContactMessageComposer';
import LocationSendComposer from '../../../components/LocationSendComposer';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import { colors, shadow } from '../../../lib/design-tokens';
import { WHATSAPP_PHONES } from '../../../config/constants';

const WABAS = [
    { id: WHATSAPP_PHONES.primary.id, name: WHATSAPP_PHONES.primary.name, display: WHATSAPP_PHONES.primary.display },
    { id: WHATSAPP_PHONES.secondary.id, name: WHATSAPP_PHONES.secondary.name, display: WHATSAPP_PHONES.secondary.display },
];

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

const QUICK_EMOJIS = [ '👍', '🙏', '✅', '😊', '❤️', '🎉', '⭐', '📎', '👋', '🔥' ];

// Themed line icons for the composer toolbar (outlined, currentColor — matches theme).
const ICON_PATHS: Record<string, string> = {
    emoji: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM9 10h.01M15 10h.01M8.5 14a4 4 0 0 0 7 0',
    chat: 'M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12Z',
    attach: 'M21 11.5 12.6 19.9a5 5 0 0 1-7.1-7.1l8-8a3.3 3.3 0 0 1 4.7 4.7l-8 8a1.6 1.6 0 1 1-2.3-2.3l7-7',
    list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
    pin: 'M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11ZM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
    user: 'M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
    mic: 'M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3ZM5 11a7 7 0 0 0 14 0M12 18v3',
    sparkle: 'M12 3l1.8 4.9L18.7 10l-4.9 1.8L12 17l-1.8-5.2L5.3 10l4.9-1.1L12 3Z',
    pay: 'M3 7h18v10H3zM3 11h18M7 15h3',
};
const Icon: React.FC<{ name: string; size?: number }> = ( { name, size = 18 } ) => (
    <svg width={ size } height={ size } viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" style={ { display: 'block' } }>
        <path d={ ICON_PATHS[ name ] } />
    </svg>
);

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
    const [ replyingTo, setReplyingTo ] = useState<api.Message | null>( null );
    const [ deletingId, setDeletingId ] = useState<string | null>( null );
    const [ visibleCount, setVisibleCount ] = useState( 50 );
    const [ selectedWaba, setSelectedWaba ] = useState( WABAS[ 0 ].id );
    const [ templates, setTemplates ] = useState<api.WhatsAppTemplate[]>( [] );
    const [ showTemplates, setShowTemplates ] = useState( false );
    const [ aiSuggesting, setAiSuggesting ] = useState( false );
    const [ summary, setSummary ] = useState( '' );
    const [ summarizing, setSummarizing ] = useState( false );
    const [ quickReplies, setQuickReplies ] = useState<string[]>( [] );
    const [ showQuick, setShowQuick ] = useState( false );
    const [ meta, setMeta ] = useState<api.ConversationMeta | null>( null );
    const [ noteText, setNoteText ] = useState( '' );
    const [ showNotes, setShowNotes ] = useState( false );
    const [ showEmoji, setShowEmoji ] = useState( false );
    const [ uploading, setUploading ] = useState( false );
    const [ composer, setComposer ] = useState<null | 'interactive' | 'contact' | 'location' | 'pay'>( null );
    const [ payItem, setPayItem ] = useState( '' );
    const [ payAmount, setPayAmount ] = useState( '' );
    const [ payQty, setPayQty ] = useState( '1' );
    // Per-channel editor state
    const [ smsType, setSmsType ] = useState<'TRANSACTIONAL' | 'PROMOTIONAL'>( 'TRANSACTIONAL' );
    const [ emailSubject, setEmailSubject ] = useState( '' );
    const [ rcsTemplates, setRcsTemplates ] = useState<any[]>( [] );
    const [ showRcsTemplates, setShowRcsTemplates ] = useState( false );
    const fileRef = useRef<HTMLInputElement | null>( null );
    const threadBodyRef = useRef<HTMLDivElement | null>( null );
    const threadEndRef = useRef<HTMLDivElement | null>( null );
    const pendingScrollRestore = useRef( false );
    const prevThreadLen = useRef( 0 );
    const [ loadingOlder, setLoadingOlder ] = useState( false );

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

    // Load approved WhatsApp templates once (for the template send button).
    useEffect( () => {
        api.listTemplates().then( t => setTemplates( ( t || [] ).filter( x => x.status === 'APPROVED' ) ) ).catch( () => { } );
        api.listRcsTemplates().then( t => setRcsTemplates( t || [] ) ).catch( () => { } );
        api.listAutomationRules().then( rs => setQuickReplies(
            ( rs || [] ).filter( r => r.enabled && r.actionType === 'reply' && r.actionValue ).map( r => r.actionValue )
        ) ).catch( () => { } );
    }, [] );

    // Reset composer context when switching conversations.
    useEffect( () => { setReplyingTo( null ); setReplyText( '' ); setVisibleCount( 50 ); setShowTemplates( false ); setShowRcsTemplates( false ); setEmailSubject( '' ); setSummary( '' ); }, [ selected ] );

    // Load team-inbox meta for the selected conversation.
    useEffect( () => {
        setMeta( null ); setShowNotes( false ); setNoteText( '' );
        if ( selected ) api.getConversationMeta( selected ).then( setMeta ).catch( () => { } );
    }, [ selected ] );

    const saveMeta = useCallback( async ( updates: { status?: string; assignee?: string; tags?: string[] } ) => {
        if ( !selected ) return;
        const m = await api.updateConversationMeta( selected, updates );
        if ( m ) setMeta( m );
    }, [ selected ] );

    const addNote = useCallback( async () => {
        const t = noteText.trim();
        if ( !t || !selected ) return;
        const m = await api.addConversationNote( selected, t, user?.username || user?.signInDetails?.loginId || 'agent' );
        if ( m ) { setMeta( m ); setNoteText( '' ); }
    }, [ noteText, selected, user ] );

    const handleDelete = useCallback( async ( m: api.Message ) => {
        if ( deletingId ) return;
        setDeletingId( m.messageId );
        try
        {
            const ok = await api.deleteMessage( m.messageId, ( ( m.direction || '' ).toUpperCase() === 'OUTBOUND' ? 'OUTBOUND' : 'INBOUND' ) );
            if ( ok )
            {
                setMessages( prev => prev.filter( x => x.messageId !== m.messageId ) );
                toast.success( 'Message deleted' );
            } else toast.error( 'Delete failed' );
        } catch { toast.error( 'Delete failed' ); }
        finally { setDeletingId( null ); }
    }, [ deletingId, toast ] );

    const handleSendTemplate = useCallback( async ( templateName: string ) => {
        const isPhone = /^\+?\d{6,}$/.test( selected || '' );
        const contactId = isPhone ? '' : ( selected || '' );
        if ( !contactId ) { toast.error( 'Template send needs a saved contact' ); return; }
        setSending( true );
        try
        {
            const r = await api.sendWhatsAppTemplateMessage( { contactId, templateName, phoneNumberId: selectedWaba } );
            if ( r ) { toast.success( 'Template sent' ); setShowTemplates( false ); setTimeout( loadData, 800 ); }
            else toast.error( 'Template send failed' );
        } catch { toast.error( 'Template send failed' ); }
        finally { setSending( false ); }
    }, [ selected, selectedWaba, toast, loadData ] );

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

    const handleSendRcsTemplate = useCallback( async ( templateId: string ) => {
        const { phone } = replyTarget;
        if ( !phone ) { toast.error( 'No phone number for this conversation' ); return; }
        setSending( true );
        try
        {
            const r = await api.sendRcs( { phoneNumber: phone, templateId } );
            if ( r && ( r.success || r.messageId ) ) { toast.success( 'RCS template sent' ); setShowRcsTemplates( false ); setTimeout( loadData, 800 ); }
            else toast.error( 'RCS template send failed' );
        } catch { toast.error( 'RCS template send failed' ); }
        finally { setSending( false ); }
    }, [ replyTarget, toast, loadData ] );

    const handleReply = useCallback( async () => {
        const base = replyText.trim();
        if ( !base || sending ) return;
        const text = replyingTo ? `> ${( replyingTo.content || '' ).slice( 0, 120 )}\n\n${base}` : base;
        const { phone, waba, contactId } = replyTarget;
        setSending( true );
        try
        {
            let ok = false;
            if ( replyChannel === 'whatsapp' )
            {
                if ( !contactId ) { toast.error( 'WhatsApp reply needs a saved contact — open the WhatsApp inbox' ); setSending( false ); return; }
                const r = await api.sendWhatsAppMessage( { contactId, content: text, phoneNumberId: selectedWaba || waba || undefined } );
                ok = !!r;
            } else if ( replyChannel === 'sms' )
            {
                if ( !phone ) { toast.error( 'No phone number for this conversation' ); setSending( false ); return; }
                const r = await api.sendSmsAws( { contactId: contactId || undefined, phoneNumber: phone, content: text, messageType: smsType } );
                ok = !!( r && ( r.messageId || r.status === 'sent' ) );
            } else if ( replyChannel === 'rcs' )
            {
                if ( !phone ) { toast.error( 'No phone number for this conversation' ); setSending( false ); return; }
                const r = await api.sendRcs( { phoneNumber: phone, text } );
                ok = !!( r && ( r.success || r.messageId ) );
            } else if ( replyChannel === 'email' )
            {
                if ( !contactId ) { toast.error( 'Email reply needs a saved contact' ); setSending( false ); return; }
                const r = await api.sendEmailMessage( contactId, emailSubject.trim() || 'Re: your conversation', text );
                ok = !!r;
            }
            if ( ok )
            {
                setReplyText( '' );
                setReplyingTo( null );
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
    }, [ replyText, sending, replyingTo, replyTarget, replyChannel, selectedWaba, smsType, emailSubject, toast, loadData ] );

    const handleSuggest = useCallback( async () => {
        if ( aiSuggesting || !thread.length ) return;
        const lastInbound = [ ...thread ].reverse().find( m => ( m.direction || '' ).toUpperCase() === 'INBOUND' );
        const seed = lastInbound?.content || thread[ thread.length - 1 ]?.content || '';
        if ( !seed ) { toast.error( 'Nothing to reply to yet' ); return; }
        setAiSuggesting( true );
        try
        {
            const history = thread.slice( -8 ).map( m => `${( m.direction || '' ).toUpperCase() === 'INBOUND' ? 'Customer' : 'Us'}: ${m.content || ''}` );
            const r = await api.generateAIResponse( seed, { channel: replyChannel, conversationHistory: history, contactName: selectedConv?.name } );
            if ( r?.response ) { setReplyText( r.response ); toast.success( 'AI suggestion ready' ); }
            else toast.error( 'No suggestion' );
        } catch { toast.error( 'AI suggest failed' ); }
        finally { setAiSuggesting( false ); }
    }, [ aiSuggesting, thread, replyChannel, selectedConv, toast ] );

    const handleSummarize = useCallback( async () => {
        if ( summarizing || !thread.length ) return;
        setSummarizing( true );
        try
        {
            const convo = thread.slice( -30 ).map( m => `${( m.direction || '' ).toUpperCase() === 'INBOUND' ? 'Customer' : 'Us'}: ${m.content || '[' + ( m.messageType || 'media' ) + ']'}` ).join( '\n' );
            const r = await api.generateAIResponse( `Summarize this customer conversation in 2-3 short bullet points (key intent, status, next action):\n\n${convo}`, { channel: replyChannel } );
            if ( r?.response ) setSummary( r.response ); else toast.error( 'No summary' );
        } catch { toast.error( 'Summarize failed' ); }
        finally { setSummarizing( false ); }
    }, [ summarizing, thread, replyChannel, toast ] );

    const handleAttach = useCallback( async ( e: React.ChangeEvent<HTMLInputElement> ) => {
        const file = e.target.files?.[ 0 ];
        if ( e.target ) e.target.value = '';  // allow re-selecting same file
        if ( !file ) return;
        if ( replyChannel !== 'whatsapp' ) { toast.error( `Attachments are supported on WhatsApp (not ${chMeta( replyChannel ).label} yet)` ); return; }
        const { contactId } = replyTarget;
        if ( !contactId ) { toast.error( 'Attachment needs a saved contact' ); return; }
        setUploading( true );
        try
        {
            const type = file.type || 'application/octet-stream';
            const s3Key = await api.uploadMediaForSend( file, type, file.name );
            if ( !s3Key ) { toast.error( 'Upload failed' ); return; }
            const r = await api.sendWhatsAppMessage( {
                contactId, content: replyText.trim() || '', phoneNumberId: selectedWaba,
                mediaFile: s3Key, mediaType: type, mediaFileName: file.name,
            } );
            if ( r ) { setReplyText( '' ); toast.success( 'Attachment sent' ); setTimeout( loadData, 800 ); }
            else toast.error( 'Send failed' );
        } catch { toast.error( 'Attachment failed' ); }
        finally { setUploading( false ); }
    }, [ replyChannel, replyTarget, replyText, selectedWaba, toast, loadData ] );

    const handleVoice = useCallback( async () => {
        if ( replyChannel !== 'whatsapp' ) { toast.error( 'Voice notes are WhatsApp-only' ); return; }
        const text = replyText.trim();
        if ( !text ) { toast.error( 'Type the message to convert to a voice note' ); return; }
        const { contactId } = replyTarget;
        if ( !contactId ) { toast.error( 'Voice note needs a saved contact' ); return; }
        setSending( true );
        try
        {
            const r = await api.sendWhatsAppTTS( { contactId, messageText: text, phoneNumberId: selectedWaba } );
            if ( r ) { setReplyText( '' ); toast.success( 'Voice note sent' ); setTimeout( loadData, 800 ); }
            else toast.error( 'Voice note failed' );
        } catch { toast.error( 'Voice note failed' ); }
        finally { setSending( false ); }
    }, [ replyChannel, replyText, replyTarget, selectedWaba, toast, loadData ] );

    const handlePay = useCallback( async () => {
        const amt = parseFloat( payAmount );
        const qty = parseInt( payQty ) || 1;
        const { contactId } = replyTarget;
        if ( !contactId ) { toast.error( 'Payment needs a saved contact' ); return; }
        if ( !payItem.trim() || !amt || amt <= 0 ) { toast.error( 'Enter item name and amount' ); return; }
        setSending( true );
        try
        {
            const r = await api.sendWhatsAppPaymentMessage( {
                contactId, phoneNumberId: selectedWaba,
                referenceId: `WD-PAY-${Date.now()}`,
                items: [ { name: payItem.trim(), amount: Math.round( amt * 100 ), quantity: qty, gstRate: 0 } ],
            } );
            if ( r ) { toast.success( 'Payment request sent' ); setComposer( null ); setPayItem( '' ); setPayAmount( '' ); setPayQty( '1' ); setTimeout( loadData, 800 ); }
            else toast.error( 'Payment send failed' );
        } catch { toast.error( 'Payment send failed' ); }
        finally { setSending( false ); }
    }, [ payItem, payAmount, payQty, replyTarget, selectedWaba, toast, loadData ] );

    // Auto-scroll to the latest message when a conversation is opened.
    useEffect( () => {
        if ( !selected ) return;
        prevThreadLen.current = 0;
        const t = setTimeout( () => threadEndRef.current?.scrollIntoView( { behavior: 'auto' } ), 60 );
        return () => clearTimeout( t );
    }, [ selected ] );

    // Auto-scroll on new messages — only if the user is already near the bottom
    // (so reading older history isn't interrupted). WhatsApp-style.
    useEffect( () => {
        if ( pendingScrollRestore.current ) { prevThreadLen.current = thread.length; return; }
        const area = threadBodyRef.current;
        if ( area && thread.length > prevThreadLen.current && prevThreadLen.current > 0 )
        {
            const nearBottom = area.scrollHeight - area.scrollTop - area.clientHeight < 220;
            if ( nearBottom ) threadEndRef.current?.scrollIntoView( { behavior: 'smooth' } );
        }
        prevThreadLen.current = thread.length;
    }, [ thread ] );

    // Infinite scroll up: reveal older messages when scrolled near the top,
    // restoring scroll position so the view doesn't jump.
    useEffect( () => {
        const area = threadBodyRef.current;
        if ( !area ) return;
        const onScroll = () => {
            if ( area.scrollTop < 80 && thread.length > visibleCount && !pendingScrollRestore.current )
            {
                const prevH = area.scrollHeight;
                const prevTop = area.scrollTop;
                pendingScrollRestore.current = true;
                setLoadingOlder( true );
                setVisibleCount( c => c + 50 );
                setTimeout( () => {
                    area.scrollTop = prevTop + ( area.scrollHeight - prevH );
                    pendingScrollRestore.current = false;
                    setLoadingOlder( false );
                }, 60 );
            }
        };
        area.addEventListener( 'scroll', onScroll, { passive: true } );
        return () => area.removeEventListener( 'scroll', onScroll );
    }, [ selected, thread.length, visibleCount ] );

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

                <div className={ `ui-panes ${selected ? 'has-selection' : ''}` }>
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
                                    <button className="ui-back" onClick={ () => setSelected( null ) } title="Back to conversations">←</button>
                                    <span className="ui-thread-name">{ selectedConv?.name }</span>
                                    <span className="ui-badges">
                                        { selectedConv && Array.from( selectedConv.channels ).map( ch => {
                                            const cm = chMeta( ch );
                                            return <span key={ ch } className="ui-badge" style={ { color: cm.fg, background: cm.bg } }>{ cm.label }</span>;
                                        } ) }
                                    </span>
                                    <button className="ui-summarize" disabled={ summarizing } onClick={ handleSummarize } title="AI summary of this conversation"><Icon name="sparkle" size={ 14 } /> { summarizing ? '…' : 'Summarize' }</button>
                                </div>
                                { summary && (
                                    <div className="ui-summary">
                                        <span className="ui-summary-text">{ summary }</span>
                                        <button className="ui-summary-x" onClick={ () => setSummary( '' ) }>✕</button>
                                    </div>
                                ) }
                                <div className="ui-meta-bar">
                                    <select className="ui-meta-status" value={ meta?.status || 'open' } onChange={ e => saveMeta( { status: e.target.value } ) }>
                                        <option value="open">🟢 Open</option>
                                        <option value="pending">🟡 Pending</option>
                                        <option value="resolved">⚪ Resolved</option>
                                    </select>
                                    <input className="ui-meta-assignee" placeholder="Assign to…" defaultValue={ meta?.assignee || '' } key={ ( meta?.assignee || '' ) + ( selected || '' ) }
                                        onBlur={ e => { if ( e.target.value !== ( meta?.assignee || '' ) ) saveMeta( { assignee: e.target.value } ); } } />
                                    <input className="ui-meta-tags" placeholder="tags (comma sep)" defaultValue={ ( meta?.tags || [] ).join( ', ' ) } key={ 'tags' + ( selected || '' ) + ( meta?.tags || [] ).join() }
                                        onBlur={ e => { const tags = e.target.value.split( ',' ).map( t => t.trim() ).filter( Boolean ); saveMeta( { tags } ); } } />
                                    <button className="ui-meta-notes-btn" onClick={ () => setShowNotes( s => !s ) }>🗒 Notes{ meta?.notes?.length ? ` (${meta.notes.length})` : '' }</button>
                                </div>
                                { showNotes && (
                                    <div className="ui-notes">
                                        { ( meta?.notes || [] ).slice( -20 ).map( ( n, i ) => (
                                            <div key={ i } className="ui-note"><span className="ui-note-text">{ n.text }</span><span className="ui-note-by">{ n.by } · { fmtTime( ( n.at || 0 ) * 1000 ) }</span></div>
                                        ) ) }
                                        <div className="ui-note-add">
                                            <input className="ui-note-input" placeholder="Add internal note (team-only)…" value={ noteText } onChange={ e => setNoteText( e.target.value ) } onKeyDown={ e => { if ( e.key === 'Enter' ) addNote(); } } />
                                            <button className="ui-note-btn" onClick={ addNote } disabled={ !noteText.trim() }>Add</button>
                                        </div>
                                    </div>
                                ) }
                                <div className="ui-thread-body" ref={ threadBodyRef }>
                                    { thread.length > visibleCount && (
                                        <button className="ui-load-more" onClick={ () => setVisibleCount( v => v + 50 ) }>{ loadingOlder ? 'Loading…' : `↑ Load older (${thread.length - visibleCount})` }</button>
                                    ) }
                                    { thread.slice( -visibleCount ).map( m => {
                                        const ch = ( m.channel || 'whatsapp' ).toLowerCase();
                                        const cm = chMeta( ch );
                                        const out = ( m.direction || '' ).toUpperCase() === 'OUTBOUND';
                                        if ( ( m.messageType || '' ).toLowerCase() === 'reaction' )
                                        {
                                            const emoji = ( m.content || '' ).replace( /\[reaction\]?/i, '' ).trim() || '👍';
                                            return (
                                                <div key={ m.messageId } className={ `ui-react ${out ? 'out' : 'in'}` }>
                                                    <span className="ui-react-pill">{ out ? 'You reacted' : 'Reacted' } { emoji }</span>
                                                </div>
                                            );
                                        }
                                        return (
                                            <div key={ m.messageId } className={ `ui-msg ${out ? 'out' : 'in'}` }>
                                                <div className="ui-msg-bubble">
                                                    <span className="ui-badge" style={ { color: cm.fg, background: cm.bg } }>{ cm.label }</span>
                                                    { ( () => {
                                                        const mt = ( m.messageType || '' ).toLowerCase();
                                                        const url = m.mediaUrl || '';
                                                        if ( url && ( mt === 'image' || mt === 'sticker' ) ) return <img className="ui-msg-img" src={ url } alt="image" />;
                                                        if ( url && mt === 'video' ) return <video className="ui-msg-img" src={ url } controls />;
                                                        if ( url && ( mt === 'audio' || mt === 'voice' ) ) return <audio src={ url } controls style={ { maxWidth: '100%' } } />;
                                                        if ( url && mt === 'document' ) return <a className="ui-msg-doc" href={ url } target="_blank" rel="noopener noreferrer">📄 { ( m as any ).displayFilename || 'Document' }</a>;
                                                        return null;
                                                    } )() }
                                                    { ( m.content || !m.mediaUrl ) && <span className="ui-msg-text">{ m.content || `[${m.messageType || ch}]` }</span> }
                                                    { m.transcription && <span className="ui-msg-transcript">📝 { m.transcription }</span> }
                                                    <span className="ui-msg-meta">
                                                        { fmtTime( m.timestamp ) } · { ( m.status || '' ).toLowerCase() }
                                                        <button className="ui-msg-act" title="Reply" onClick={ () => setReplyingTo( m ) }>↩</button>
                                                        <button className="ui-msg-act" title="Delete" disabled={ deletingId === m.messageId } onClick={ () => handleDelete( m ) }>🗑</button>
                                                    </span>
                                                </div>
                                            </div>
                                        );
                                    } ) }
                                    <div ref={ threadEndRef } />
                                </div>
                                <div className="ui-reply">
                                    { replyChannel === 'voice' ? (
                                        <div className="ui-reply-voice">
                                            <span>This is a call — reply by calling back.</span>
                                            <Link href={ chMeta( 'voice' ).reply } className="ui-reply-link">Open Voice →</Link>
                                        </div>
                                    ) : (
                                        <>
                                            { replyingTo && (
                                                <div className="ui-replying">
                                                    <span className="ui-replying-text">↩ { ( replyingTo.content || '' ).slice( 0, 60 ) }</span>
                                                    <button className="ui-replying-x" onClick={ () => setReplyingTo( null ) }>✕</button>
                                                </div>
                                            ) }
                                            { replyChannel === 'whatsapp' && (
                                                <div className="ui-wa-bar">
                                                    <span className="ui-wa-from">Send from:</span>
                                                    <select className="ui-wa-waba" value={ selectedWaba } onChange={ e => setSelectedWaba( e.target.value ) }>
                                                        { WABAS.map( w => <option key={ w.id } value={ w.id }>{ w.name } ({ w.display })</option> ) }
                                                    </select>
                                                    <button className="ui-tpl-btn" onClick={ () => setShowTemplates( s => !s ) }>Send template ▾</button>
                                                </div>
                                            ) }
                                            { showTemplates && replyChannel === 'whatsapp' && (
                                                <div className="ui-tpl-list">
                                                    { templates.length === 0 ? <div className="ui-tpl-empty">No approved templates</div> :
                                                        templates.map( t => (
                                                            <button key={ t.name } className="ui-tpl-item" disabled={ sending } onClick={ () => handleSendTemplate( t.name ) }>
                                                                <span className="ui-tpl-name">{ t.name }</span>
                                                                <span className="ui-tpl-cat">{ t.category }</span>
                                                            </button>
                                                        ) ) }
                                                </div>
                                            ) }
                                            { replyChannel === 'rcs' && (
                                                <div className="ui-wa-bar">
                                                    <span className="ui-wa-from" style={ { color: chMeta( 'rcs' ).fg } }>RCS · { replyTarget.phone || '—' }</span>
                                                    <button className="ui-tpl-btn" onClick={ () => setShowRcsTemplates( s => !s ) }>RCS templates ▾</button>
                                                </div>
                                            ) }
                                            { showRcsTemplates && replyChannel === 'rcs' && (
                                                <div className="ui-tpl-list">
                                                    { rcsTemplates.length === 0 ? <div className="ui-tpl-empty">No RCS templates</div> :
                                                        rcsTemplates.map( ( t: any, i: number ) => (
                                                            <button key={ t.name || t.id || i } className="ui-tpl-item" disabled={ sending } onClick={ () => handleSendRcsTemplate( t.name || t.id ) }>
                                                                <span className="ui-tpl-name">{ t.name || t.id }</span>
                                                                <span className="ui-tpl-cat">{ t.type || 'rcs' }</span>
                                                            </button>
                                                        ) ) }
                                                </div>
                                            ) }
                                            { replyChannel === 'sms' && (
                                                <div className="ui-wa-bar">
                                                    <span className="ui-wa-from" style={ { color: chMeta( 'sms' ).fg } }>SMS · { replyTarget.phone || '—' }</span>
                                                    <select className="ui-wa-waba" value={ smsType } onChange={ e => setSmsType( e.target.value as 'TRANSACTIONAL' | 'PROMOTIONAL' ) }>
                                                        <option value="TRANSACTIONAL">Transactional</option>
                                                        <option value="PROMOTIONAL">Promotional</option>
                                                    </select>
                                                </div>
                                            ) }
                                            { replyChannel === 'email' && (
                                                <div className="ui-wa-bar">
                                                    <span className="ui-wa-from" style={ { color: chMeta( 'email' ).fg } }>Email</span>
                                                    <input className="ui-email-subject" placeholder="Subject…" value={ emailSubject } onChange={ e => setEmailSubject( e.target.value ) } />
                                                </div>
                                            ) }
                                            <textarea
                                                className="ui-reply-input"
                                                placeholder={ `Reply via ${chMeta( replyChannel ).label}…` }
                                                value={ replyText }
                                                onChange={ e => setReplyText( e.target.value ) }
                                                onKeyDown={ e => { if ( e.key === 'Enter' && !e.shiftKey ) { e.preventDefault(); handleReply(); } } }
                                                rows={ 2 }
                                            />
                                            { showEmoji && (
                                                <div className="ui-emoji-row">
                                                    { QUICK_EMOJIS.map( e => (
                                                        <button key={ e } type="button" className="ui-emoji" onClick={ () => { setReplyText( t => t + e ); } }>{ e }</button>
                                                    ) ) }
                                                </div>
                                            ) }
                                            { showQuick && (
                                                <div className="ui-quick-list">
                                                    { quickReplies.map( ( q, i ) => (
                                                        <button key={ i } type="button" className="ui-quick-item" onClick={ () => { setReplyText( q ); setShowQuick( false ); } }>{ q.slice( 0, 80 ) }</button>
                                                    ) ) }
                                                </div>
                                            ) }
                                            <div className="ui-reply-actions">
                                                <span className="ui-reply-via" style={ { color: chMeta( replyChannel ).fg, background: chMeta( replyChannel ).bg } }>via { chMeta( replyChannel ).label }</span>
                                                { ( replyChannel === 'whatsapp' || replyChannel === 'rcs' ) && (
                                                    <span className="ui-fmt-hint">Enter to send · Shift+Enter newline · *bold* _italic_ ~strike~</span>
                                                ) }
                                                { replyChannel === 'sms' && (
                                                    <span className="ui-fmt-hint">{ replyText.length } chars · { Math.max( 1, Math.ceil( replyText.length / 160 ) ) } SMS segment{ replyText.length > 160 ? 's' : '' }</span>
                                                ) }
                                                { replyChannel === 'email' && (
                                                    <span className="ui-fmt-hint">Enter to send · Shift+Enter newline</span>
                                                ) }
                                                <button type="button" className="ui-tool-btn" onClick={ () => setShowEmoji( s => !s ) } title="Emoji"><Icon name="emoji" /></button>
                                                { quickReplies.length > 0 && (
                                                    <button type="button" className="ui-tool-btn" onClick={ () => setShowQuick( s => !s ) } title="Quick replies"><Icon name="chat" /></button>
                                                ) }
                                                { replyChannel === 'whatsapp' && (
                                                    <>
                                                        <button type="button" className="ui-tool-btn" disabled={ uploading } onClick={ () => fileRef.current?.click() } title="Attach image / document / video / audio"><Icon name="attach" /></button>
                                                        { replyTarget.contactId && (
                                                            <>
                                                                <button type="button" className="ui-tool-btn" onClick={ () => setComposer( 'interactive' ) } title="Interactive: list / buttons / CTA / flow"><Icon name="list" /></button>
                                                                <button type="button" className="ui-tool-btn" onClick={ () => setComposer( 'location' ) } title="Send location"><Icon name="pin" /></button>
                                                                <button type="button" className="ui-tool-btn" onClick={ () => setComposer( 'contact' ) } title="Send contact card"><Icon name="user" /></button>
                                                                <button type="button" className="ui-tool-btn" disabled={ sending || !replyText.trim() } onClick={ handleVoice } title="Send as voice note (TTS)"><Icon name="mic" /></button>
                                                                <button type="button" className="ui-tool-btn" onClick={ () => setComposer( 'pay' ) } title="Request payment"><Icon name="pay" /></button>
                                                            </>
                                                        ) }
                                                    </>
                                                ) }
                                                <button className="ui-ai-btn" disabled={ aiSuggesting } onClick={ handleSuggest } title="AI suggest reply"><Icon name="sparkle" size={ 15 } /> { aiSuggesting ? '…' : 'Suggest' }</button>
                                                <button className="ui-reply-btn" disabled={ sending || !replyText.trim() } onClick={ handleReply }>{ sending ? 'Sending…' : 'Send' }</button>
                                            </div>
                                            { replyChannel === 'whatsapp' && (
                                                <input ref={ fileRef } type="file" hidden accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt" onChange={ handleAttach } />
                                            ) }
                                        </>
                                    ) }
                                </div>
                            </>
                        ) }
                    </div>
                </div>
            </div>

            { composer && replyTarget.contactId && (
                <div className="ui-modal-backdrop" onClick={ () => setComposer( null ) }>
                    <div className="ui-modal" onClick={ e => e.stopPropagation() }>
                        { composer === 'interactive' && (
                            <InteractiveMessageComposer contactId={ replyTarget.contactId } phoneNumberId={ selectedWaba }
                                onClose={ () => setComposer( null ) }
                                onSent={ () => { setComposer( null ); toast.success( 'Interactive message sent' ); setTimeout( loadData, 800 ); } }
                                onError={ ( m: string ) => toast.error( m ) } />
                        ) }
                        { composer === 'location' && (
                            <LocationSendComposer contactId={ replyTarget.contactId } phoneNumberId={ selectedWaba }
                                onClose={ () => setComposer( null ) }
                                onSent={ () => { setComposer( null ); toast.success( 'Location sent' ); setTimeout( loadData, 800 ); } }
                                onError={ ( m: string ) => toast.error( m ) } />
                        ) }
                        { composer === 'contact' && (
                            <ContactMessageComposer contactId={ replyTarget.contactId } phoneNumberId={ selectedWaba }
                                onClose={ () => setComposer( null ) }
                                onSent={ () => { setComposer( null ); toast.success( 'Contact card sent' ); setTimeout( loadData, 800 ); } }
                                onError={ ( m: string ) => toast.error( m ) } />
                        ) }
                        { composer === 'pay' && (
                            <div className="ui-pay">
                                <div className="ui-pay-title">Request payment</div>
                                <input className="ui-pay-in" placeholder="Item / service name" value={ payItem } onChange={ e => setPayItem( e.target.value ) } />
                                <div className="ui-pay-row">
                                    <input className="ui-pay-in" type="number" min="1" step="0.01" placeholder="Amount (₹)" value={ payAmount } onChange={ e => setPayAmount( e.target.value ) } />
                                    <input className="ui-pay-in ui-pay-qty" type="number" min="1" placeholder="Qty" value={ payQty } onChange={ e => setPayQty( e.target.value ) } />
                                </div>
                                <div className="ui-pay-total">Total: ₹{ ( ( parseFloat( payAmount ) || 0 ) * ( parseInt( payQty ) || 1 ) ).toFixed( 2 ) }</div>
                                <div className="ui-pay-actions">
                                    <button className="ui-pay-cancel" onClick={ () => setComposer( null ) }>Cancel</button>
                                    <button className="ui-pay-send" disabled={ sending } onClick={ handlePay }>{ sending ? 'Sending…' : 'Send payment request' }</button>
                                </div>
                            </div>
                        ) }
                    </div>
                </div>
            ) }

            <style jsx>{ `
        .ui-wrap { padding: 18px 20px; max-width: 1360px; margin: 0 auto; display: flex; flex-direction: column; height: calc(100vh - 70px); box-sizing: border-box; }
        .ui-toolbar { display: flex; gap: 12px; margin: 12px 0; flex-shrink: 0; }
        .ui-search { flex: 1; padding: 9px 14px; border: 1px solid ${colors.border}; border-radius: 10px; font-size: 14px; }
        .ui-filter { padding: 9px 12px; border: 1px solid ${colors.border}; border-radius: 10px; font-size: 13px; background: #fff; }
        .ui-panes { display: grid; grid-template-columns: 340px 1fr; gap: 16px; flex: 1; min-height: 420px; overflow: hidden; }
        .ui-list { border: 1px solid ${colors.border}; border-radius: 12px; overflow-y: auto; background: #fff; min-height: 0; }
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
        .ui-thread { border: 1px solid ${colors.border}; border-radius: 12px; display: flex; flex-direction: column; background: #fff; overflow: hidden; min-height: 0; }
        .ui-thread-head { padding: 12px 16px; border-bottom: 1px solid ${colors.border}; display: flex; justify-content: space-between; align-items: center; gap: 8px; }
        .ui-back { display: none; align-items: center; justify-content: center; width: 32px; height: 32px; border: 1px solid ${colors.border}; border-radius: 8px; background: #fff; color: ${colors.primary}; font-size: 18px; cursor: pointer; flex-shrink: 0; }
        .ui-thread-name { font-weight: 700; font-size: 15px; color: ${colors.text}; }
        .ui-summarize { display: inline-flex; align-items: center; gap: 5px; margin-left: auto; background: #f0fdf4; color: ${colors.primary}; border: 1px solid #bbf7d0; padding: 6px 12px; border-radius: 9px; font-size: 12px; font-weight: 600; cursor: pointer; }
        .ui-summarize:disabled { opacity: 0.6; cursor: not-allowed; }
        .ui-summary { display: flex; gap: 8px; align-items: flex-start; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 10px; padding: 10px 12px; margin: 8px 16px 0; }
        .ui-summary-text { font-size: 13px; color: ${colors.text}; white-space: pre-wrap; flex: 1; }
        .ui-summary-x { background: none; border: none; cursor: pointer; color: ${colors.textMuted}; }
        .ui-meta-bar { display: flex; gap: 8px; align-items: center; padding: 8px 16px; border-bottom: 1px solid ${colors.borderLight}; flex-wrap: wrap; }
        .ui-meta-status { padding: 6px 10px; border: 1px solid ${colors.border}; border-radius: 8px; font-size: 12px; background: #fff; }
        .ui-meta-assignee { width: 130px; padding: 6px 10px; border: 1px solid ${colors.border}; border-radius: 8px; font-size: 12px; }
        .ui-meta-tags { flex: 1; min-width: 120px; padding: 6px 10px; border: 1px solid ${colors.border}; border-radius: 8px; font-size: 12px; }
        .ui-meta-notes-btn { padding: 6px 12px; border: 1px solid ${colors.border}; border-radius: 8px; background: #fff; font-size: 12px; cursor: pointer; }
        .ui-notes { padding: 10px 16px; border-bottom: 1px solid ${colors.borderLight}; background: ${colors.bgSecondary}; display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto; }
        .ui-note { display: flex; flex-direction: column; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 6px 10px; }
        .ui-note-text { font-size: 13px; color: ${colors.text}; }
        .ui-note-by { font-size: 10px; color: ${colors.textMuted}; margin-top: 2px; }
        .ui-note-add { display: flex; gap: 8px; }
        .ui-note-input { flex: 1; padding: 7px 10px; border: 1px solid ${colors.border}; border-radius: 8px; font-size: 13px; }
        .ui-note-btn { padding: 7px 14px; background: ${colors.primary}; color: #fff; border: none; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; }
        .ui-note-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .ui-thread-body { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; background: ${colors.bgSecondary}; }
        .ui-msg { display: flex; }
        .ui-msg.out { justify-content: flex-end; }
        .ui-msg-bubble { max-width: 70%; background: #fff; border: 1px solid ${colors.border}; border-radius: 12px; padding: 8px 12px; display: flex; flex-direction: column; gap: 4px; }
        .ui-msg.out .ui-msg-bubble { background: ${colors.lime}; border-color: ${colors.lime}; }
        .ui-msg-text { font-size: 14px; color: ${colors.text}; white-space: pre-wrap; word-break: break-word; }
        .ui-msg-img { max-width: 220px; max-height: 220px; border-radius: 8px; object-fit: cover; }
        .ui-msg-doc { font-size: 13px; color: ${colors.primary}; text-decoration: none; font-weight: 600; }
        .ui-msg-transcript { font-size: 12px; color: ${colors.textSecondary}; font-style: italic; border-left: 2px solid ${colors.border}; padding-left: 6px; }
        .ui-react { display: flex; padding: 2px 0; }
        .ui-react.out { justify-content: flex-end; }
        .ui-react-pill { font-size: 11px; color: ${colors.textMuted}; background: ${colors.bgSecondary}; border: 1px solid ${colors.borderLight}; border-radius: 9999px; padding: 2px 10px; }
        .ui-msg-meta { font-size: 10px; color: ${colors.textMuted}; display: flex; align-items: center; gap: 8px; }
        .ui-msg-act { background: none; border: none; cursor: pointer; font-size: 11px; opacity: 0.5; padding: 0 2px; }
        .ui-msg-act:hover { opacity: 1; }
        .ui-msg-act:disabled { opacity: 0.2; cursor: not-allowed; }
        .ui-load-more { align-self: center; background: #fff; border: 1px solid ${colors.border}; border-radius: 9999px; padding: 6px 16px; font-size: 12px; cursor: pointer; color: ${colors.textSecondary}; }
        .ui-load-more:hover { background: ${colors.bgHover}; }
        .ui-replying { display: flex; align-items: center; justify-content: space-between; background: ${colors.bgSecondary}; border-left: 3px solid ${colors.primary}; border-radius: 6px; padding: 6px 10px; }
        .ui-replying-text { font-size: 12px; color: ${colors.textSecondary}; }
        .ui-replying-x { background: none; border: none; cursor: pointer; color: ${colors.textMuted}; font-size: 12px; }
        .ui-wa-bar { display: flex; align-items: center; gap: 8px; }
        .ui-wa-from { font-size: 12px; color: ${colors.textMuted}; }
        .ui-wa-waba { padding: 6px 10px; border: 1px solid ${colors.border}; border-radius: 8px; font-size: 12px; background: #fff; }
        .ui-email-subject { flex: 1; padding: 6px 10px; border: 1px solid ${colors.border}; border-radius: 8px; font-size: 12px; }
        .ui-tpl-btn { margin-left: auto; padding: 6px 12px; border: 1px solid ${colors.border}; border-radius: 8px; background: #fff; font-size: 12px; font-weight: 600; cursor: pointer; color: ${colors.primary}; }
        .ui-tpl-list { max-height: 180px; overflow-y: auto; border: 1px solid ${colors.border}; border-radius: 10px; }
        .ui-tpl-item { display: flex; width: 100%; justify-content: space-between; align-items: center; padding: 8px 12px; border: none; border-bottom: 1px solid ${colors.borderLight}; background: #fff; cursor: pointer; text-align: left; }
        .ui-tpl-item:hover { background: ${colors.bgHover}; }
        .ui-tpl-name { font-size: 13px; font-weight: 600; color: ${colors.text}; }
        .ui-tpl-cat { font-size: 10px; color: ${colors.textMuted}; text-transform: capitalize; }
        .ui-tpl-empty { padding: 14px; text-align: center; font-size: 12px; color: ${colors.textMuted}; }
        .ui-fmt-hint { font-size: 10px; color: ${colors.textLight}; margin-right: auto; }
        .ui-ai-btn { display: inline-flex; align-items: center; gap: 5px; background: #f0fdf4; color: ${colors.primary}; border: 1px solid #bbf7d0; padding: 6px 11px; border-radius: 9px; font-size: 12px; font-weight: 600; cursor: pointer; }
        .ui-ai-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .ui-tool-btn { display: inline-flex; align-items: center; justify-content: center; background: #fff; border: 1px solid ${colors.border}; border-radius: 9px; padding: 7px; color: ${colors.primary}; cursor: pointer; }
        .ui-tool-btn:hover:not(:disabled) { background: ${colors.bgHover}; border-color: ${colors.primary}; }
        .ui-tool-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .ui-emoji-row { display: flex; gap: 4px; flex-wrap: wrap; padding: 6px 0; }
        .ui-emoji { background: ${colors.bgSecondary}; border: 1px solid ${colors.borderLight}; border-radius: 8px; padding: 4px 8px; font-size: 16px; cursor: pointer; }
        .ui-emoji:hover { background: ${colors.bgActive}; }
        .ui-quick-list { display: flex; flex-direction: column; gap: 4px; max-height: 160px; overflow-y: auto; border: 1px solid ${colors.border}; border-radius: 10px; padding: 4px; }
        .ui-quick-item { text-align: left; background: ${colors.bgSecondary}; border: 1px solid ${colors.borderLight}; border-radius: 8px; padding: 6px 10px; font-size: 13px; color: ${colors.text}; cursor: pointer; }
        .ui-quick-item:hover { background: ${colors.bgActive}; }
        .ui-modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1410; padding: 20px; }
        .ui-modal { background: #fff; border-radius: 14px; max-width: 560px; width: 100%; max-height: 85vh; overflow-y: auto; box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
        .ui-pay { padding: 20px; display: flex; flex-direction: column; gap: 12px; }
        .ui-pay-title { font-size: 16px; font-weight: 700; color: ${colors.text}; }
        .ui-pay-in { width: 100%; padding: 9px 12px; border: 1px solid ${colors.border}; border-radius: 10px; font-size: 14px; font-family: inherit; }
        .ui-pay-in:focus { outline: none; border-color: ${colors.primary}; box-shadow: ${shadow.focus}; }
        .ui-pay-row { display: flex; gap: 10px; }
        .ui-pay-qty { max-width: 90px; }
        .ui-pay-total { font-size: 14px; font-weight: 600; color: ${colors.primary}; }
        .ui-pay-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
        .ui-pay-cancel { background: #fff; border: 1px solid ${colors.border}; border-radius: 10px; padding: 8px 16px; font-size: 13px; cursor: pointer; color: ${colors.textSecondary}; }
        .ui-pay-send { background: ${colors.primary}; color: #fff; border: none; border-radius: 10px; padding: 8px 18px; font-size: 13px; font-weight: 600; cursor: pointer; }
        .ui-pay-send:disabled { opacity: 0.5; cursor: not-allowed; }
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
        @media (max-width: 800px) {
          .ui-wrap { height: calc(100vh - 56px); padding: 10px 12px; }
          .ui-toolbar { margin: 8px 0; }
          .ui-panes { grid-template-columns: 1fr; min-height: 0; }
          /* Master/detail: show the list OR the thread, not both. */
          .ui-panes .ui-thread { display: none; }
          .ui-panes .ui-list { display: block; }
          .ui-panes.has-selection .ui-list { display: none; }
          .ui-panes.has-selection .ui-thread { display: flex; }
          .ui-back { display: inline-flex; }
          .ui-msg-bubble { max-width: 85%; }
          .ui-meta-bar { gap: 6px; }
          .ui-meta-assignee, .ui-meta-tags { width: auto; flex: 1; min-width: 90px; }
        }
      ` }</style>
        </>
    );

    if ( embedded ) return content;
    return <Layout user={ user } onSignOut={ signOut }>{ content }</Layout>;
};

export default UnifiedInbox;
