/**
 * WhatsApp Send Test Console (Part 4 E + tools)
 * Exercises the live /wa-business/messages/send/* routes plus the
 * TTL rules/validate, template validate, and preset endpoints.
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import { WHATSAPP_PHONES } from '../../../config/constants';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const PHONES = [
    { key: 'primary', ...WHATSAPP_PHONES.primary },
    { key: 'secondary', ...WHATSAPP_PHONES.secondary },
];

type SendTab = 'text' | 'template' | 'media' | 'flow' | 'tools';

const card: React.CSSProperties = { background: '#fff', border: '1px solid #e5e5e5', borderRadius: 8, padding: 16, marginBottom: 16 };
const input: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid #d0d0d0', borderRadius: 6, marginTop: 4, marginBottom: 10, fontSize: 14 };
const label: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#444' };
const btn: React.CSSProperties = { padding: '9px 16px', background: '#1a1a1a', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 14, fontWeight: 600 };
const tabBtn = ( active: boolean ): React.CSSProperties => ( { padding: '8px 14px', border: 'none', borderBottom: active ? '2px solid #1a1a1a' : '2px solid transparent', background: 'none', cursor: 'pointer', fontWeight: active ? 700 : 500, color: active ? '#1a1a1a' : '#777' } );

const SendTestConsole: React.FC<PageProps> = ( { signOut, user, embedded = false } ) => {
    const toast = useToastContext();
    const [ phoneIdx, setPhoneIdx ] = useState( 0 );
    const [ to, setTo ] = useState( '' );
    const [ tab, setTab ] = useState<SendTab>( 'text' );
    const [ busy, setBusy ] = useState( false );

    const phone = PHONES[ phoneIdx ];

    // text
    const [ text, setText ] = useState( '' );
    // template
    const [ tplName, setTplName ] = useState( '' );
    const [ tplLang, setTplLang ] = useState( 'en' );
    // media
    const [ mediaType, setMediaType ] = useState<'image' | 'video' | 'document' | 'audio' | 'sticker'>( 'image' );
    const [ mediaUrl, setMediaUrl ] = useState( '' );
    const [ caption, setCaption ] = useState( '' );
    // flow
    const [ flowName, setFlowName ] = useState( '' );
    const [ flowScreen, setFlowScreen ] = useState( 'WELCOME' );
    const [ flowMode, setFlowMode ] = useState<'published' | 'draft'>( 'published' );
    const [ flowCta, setFlowCta ] = useState( 'Open' );
    const [ flowBody, setFlowBody ] = useState( 'Tap below to continue' );

    // tools
    const [ ttlRules, setTtlRules ] = useState<api.TtlRules | null>( null );
    const [ ttlCategory, setTtlCategory ] = useState( 'UTILITY' );
    const [ ttlSeconds, setTtlSeconds ] = useState( 43200 );
    const [ ttlResult, setTtlResult ] = useState<api.TtlValidationResult | null>( null );
    const [ presets, setPresets ] = useState<api.TemplatePresetSummary[]>( [] );
    const [ validateJson, setValidateJson ] = useState( '' );
    const [ validateResult, setValidateResult ] = useState<api.TemplateValidationResult | null>( null );

    const loadTools = useCallback( async () => {
        try
        {
            const [ rules, ps ] = await Promise.all( [ api.getTemplateTtlRules(), api.listTemplatePresets() ] );
            setTtlRules( rules );
            setPresets( ps );
        } catch ( e: any )
        {
            toast.error( e?.message || 'Failed to load tools' );
        }
    }, [ toast ] );

    useEffect( () => { if ( tab === 'tools' ) loadTools(); }, [ tab, loadTools ] );

    const requireTo = (): boolean => {
        if ( !to.trim() ) { toast.error( 'Recipient (to) is required, e.g. 919900000000' ); return false; }
        return true;
    };

    const report = ( r: { success?: boolean; messageId?: string; error?: string } ) => {
        if ( r?.success && r.messageId ) toast.success( `Sent — ${r.messageId}` );
        else if ( r?.success ) toast.success( 'Sent' );
        else toast.error( r?.error || 'Send failed' );
    };

    const doSend = async ( fn: () => Promise<any> ) => {
        setBusy( true );
        try { report( await fn() ); }
        catch ( e: any ) { toast.error( e?.message || 'Request failed' ); }
        finally { setBusy( false ); }
    };

    const sendText = () => requireTo() && doSend( () => api.sendTestText( to, text, { phoneId: phone.metaPhoneId } ) );
    const sendTpl = () => requireTo() && doSend( () => api.sendTestTemplate( to, tplName, { language: tplLang, phoneId: phone.metaPhoneId } ) );
    const sendMedia = () => requireTo() && doSend( () => api.sendTestMedia( to, mediaType, { mediaUrl, caption, phoneId: phone.metaPhoneId } ) );
    const sendFlow = () => requireTo() && doSend( () => api.sendTestFlow( to, { flowName, screen: flowScreen, mode: flowMode, flowCta, bodyText: flowBody, phoneId: phone.metaPhoneId } ) );

    const runValidateTtl = async () => {
        try { setTtlResult( await api.validateTemplateTtl( ttlCategory, Number( ttlSeconds ) ) ); }
        catch ( e: any ) { toast.error( e?.message || 'Validation failed' ); }
    };

    const runValidateTemplate = async () => {
        let def: any;
        try { def = JSON.parse( validateJson ); }
        catch { toast.error( 'Invalid JSON' ); return; }
        try { setValidateResult( await api.validateTemplateDefinition( def ) ); }
        catch ( e: any ) { toast.error( e?.message || 'Validation failed' ); }
    };

    const loadPreset = async ( name: string ) => {
        const p = await api.getTemplatePreset( name );
        if ( p ) { setValidateJson( JSON.stringify( p, null, 2 ) ); toast.success( `Loaded preset ${name}` ); }
    };

    const content = (
        <div style={ { maxWidth: 820, margin: '0 auto', padding: 16 } }>
            <SEO title="WhatsApp Send Test Console" description="Send live WhatsApp test messages and validate templates/TTL." noindex />
            <h1 style={ { fontSize: 22, fontWeight: 700, marginBottom: 4 } }>Send Test Console</h1>
            <p style={ { color: '#777', fontSize: 13, marginBottom: 16 } }>Send live test messages and validate templates/TTL against the deployed WhatsApp Business API.</p>

            <div style={ card }>
                <div style={ { display: 'flex', gap: 16, flexWrap: 'wrap' } }>
                    <div style={ { flex: 1, minWidth: 220 } }>
                        <div style={ label }>From (phone)</div>
                        <select style={ input } value={ phoneIdx } onChange={ e => setPhoneIdx( Number( e.target.value ) ) }>
                            { PHONES.map( ( p, i ) => <option key={ p.key } value={ i }>{ p.name } — { p.display }</option> ) }
                        </select>
                    </div>
                    <div style={ { flex: 1, minWidth: 220 } }>
                        <div style={ label }>To (E.164, no +)</div>
                        <input style={ input } value={ to } onChange={ e => setTo( e.target.value ) } placeholder="919900000000" />
                    </div>
                </div>
            </div>

            <div style={ { display: 'flex', gap: 4, borderBottom: '1px solid #e5e5e5', marginBottom: 16 } }>
                { ( [ 'text', 'template', 'media', 'flow', 'tools' ] as SendTab[] ).map( t => (
                    <button key={ t } style={ tabBtn( tab === t ) } onClick={ () => setTab( t ) }>{ t[ 0 ].toUpperCase() + t.slice( 1 ) }</button>
                ) ) }
            </div>

            { tab === 'text' && (
                <div style={ card }>
                    <div style={ label }>Message text</div>
                    <textarea style={ { ...input, minHeight: 90 } } value={ text } onChange={ e => setText( e.target.value ) } placeholder="Hello from WECARE.DIGITAL" />
                    <button style={ btn } disabled={ busy } onClick={ sendText }>Send text</button>
                </div>
            ) }

            { tab === 'template' && (
                <div style={ card }>
                    <div style={ label }>Template name</div>
                    <input style={ input } value={ tplName } onChange={ e => setTplName( e.target.value ) } placeholder="order_confirmation" />
                    <div style={ label }>Language code</div>
                    <input style={ input } value={ tplLang } onChange={ e => setTplLang( e.target.value ) } placeholder="en" />
                    <button style={ btn } disabled={ busy } onClick={ sendTpl }>Send template</button>
                </div>
            ) }

            { tab === 'media' && (
                <div style={ card }>
                    <div style={ label }>Media type</div>
                    <select style={ input } value={ mediaType } onChange={ e => setMediaType( e.target.value as any ) }>
                        { [ 'image', 'video', 'document', 'audio', 'sticker' ].map( t => <option key={ t } value={ t }>{ t }</option> ) }
                    </select>
                    <div style={ label }>Media URL (public)</div>
                    <input style={ input } value={ mediaUrl } onChange={ e => setMediaUrl( e.target.value ) } placeholder="https://app.wecare.digital/stream/media/..." />
                    <div style={ label }>Caption (image/video/document)</div>
                    <input style={ input } value={ caption } onChange={ e => setCaption( e.target.value ) } />
                    <button style={ btn } disabled={ busy } onClick={ sendMedia }>Send media</button>
                </div>
            ) }

            { tab === 'flow' && (
                <div style={ card }>
                    <div style={ label }>Flow name</div>
                    <input style={ input } value={ flowName } onChange={ e => setFlowName( e.target.value ) } placeholder="lead-generation-flow" />
                    <div style={ { display: 'flex', gap: 12 } }>
                        <div style={ { flex: 1 } }>
                            <div style={ label }>Initial screen</div>
                            <input style={ input } value={ flowScreen } onChange={ e => setFlowScreen( e.target.value ) } />
                        </div>
                        <div style={ { flex: 1 } }>
                            <div style={ label }>Mode</div>
                            <select style={ input } value={ flowMode } onChange={ e => setFlowMode( e.target.value as any ) }>
                                <option value="published">published</option>
                                <option value="draft">draft</option>
                            </select>
                        </div>
                    </div>
                    <div style={ label }>CTA label</div>
                    <input style={ input } value={ flowCta } onChange={ e => setFlowCta( e.target.value ) } />
                    <div style={ label }>Body text</div>
                    <input style={ input } value={ flowBody } onChange={ e => setFlowBody( e.target.value ) } />
                    <button style={ btn } disabled={ busy } onClick={ sendFlow }>Send flow</button>
                </div>
            ) }

            { tab === 'tools' && (
                <>
                    <div style={ card }>
                        <h3 style={ { marginTop: 0, fontSize: 15 } }>Template TTL</h3>
                        { ttlRules && (
                            <div style={ { fontSize: 12, color: '#666', marginBottom: 8 } }>
                                { Object.entries( ttlRules.categories ).map( ( [ c, r ] ) => <div key={ c }>{ r.description }</div> ) }
                            </div>
                        ) }
                        <div style={ { display: 'flex', gap: 12 } }>
                            <div style={ { flex: 1 } }>
                                <div style={ label }>Category</div>
                                <select style={ input } value={ ttlCategory } onChange={ e => setTtlCategory( e.target.value ) }>
                                    { [ 'AUTHENTICATION', 'UTILITY', 'MARKETING' ].map( c => <option key={ c } value={ c }>{ c }</option> ) }
                                </select>
                            </div>
                            <div style={ { flex: 1 } }>
                                <div style={ label }>TTL seconds (-1 = 30 days)</div>
                                <input style={ input } type="number" value={ ttlSeconds } onChange={ e => setTtlSeconds( Number( e.target.value ) ) } />
                            </div>
                        </div>
                        <button style={ btn } onClick={ runValidateTtl }>Validate TTL</button>
                        { ttlResult && (
                            <div style={ { marginTop: 10, fontSize: 13, color: ttlResult.ok ? '#1a3a2a' : '#a11' } }>
                                { ttlResult.ok ? `Valid — ${ttlResult.human}` : ttlResult.error }
                                { ttlResult.warnings?.map( ( w, i ) => <div key={ i } style={ { color: '#a60' } }>{ w }</div> ) }
                            </div>
                        ) }
                    </div>

                    <div style={ card }>
                        <h3 style={ { marginTop: 0, fontSize: 15 } }>Template validation</h3>
                        <div style={ { fontSize: 12, color: '#666', marginBottom: 8 } }>
                            Presets:{ ' ' }
                            { presets.map( p => (
                                <button key={ p.name } onClick={ () => loadPreset( p.name ) } style={ { ...btn, padding: '3px 8px', fontSize: 11, marginRight: 6, background: '#444' } }>{ p.name }{ p.hasFlowButton ? ' (flow)' : '' }</button>
                            ) ) }
                        </div>
                        <textarea style={ { ...input, minHeight: 140, fontFamily: 'monospace', fontSize: 12 } } value={ validateJson } onChange={ e => setValidateJson( e.target.value ) } placeholder='{"name":"order_ok","language":"en","category":"UTILITY","components":[...]}' />
                        <button style={ btn } onClick={ runValidateTemplate }>Validate template</button>
                        { validateResult && (
                            <div style={ { marginTop: 10, fontSize: 13 } }>
                                <div style={ { color: validateResult.ok ? '#1a3a2a' : '#a11', fontWeight: 600 } }>{ validateResult.ok ? 'Valid' : 'Invalid' }</div>
                                { validateResult.errors?.map( ( e, i ) => <div key={ i } style={ { color: '#a11' } }>• { e }</div> ) }
                                { validateResult.warnings?.map( ( w, i ) => <div key={ i } style={ { color: '#a60' } }>⚠ { w }</div> ) }
                            </div>
                        ) }
                    </div>
                </>
            ) }
        </div>
    );

    if ( embedded ) return content;
    return <Layout user={ user } onSignOut={ signOut }>{ content }</Layout>;
};

export default SendTestConsole;
