/**
 * RCS Send Page - Send RCS messages (text or template)
 */
import React, { useState, useEffect } from 'react';
import Button from '../../../components/ui/Button';
import { useToastContext } from '../../../contexts/ToastContext';
import { API_BASE } from '../../../config/constants';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const RcsSendPage: React.FC<PageProps> = ( { embedded } ) => {
    const [ phone, setPhone ] = useState( '' );
    const [ messageType, setMessageType ] = useState<'text' | 'template'>( 'template' );
    const [ text, setText ] = useState( '' );
    const [ templateId, setTemplateId ] = useState( 'test16' );
    const [ parameters, setParameters ] = useState( '' );
    const [ sending, setSending ] = useState( false );
    const [ result, setResult ] = useState<any>( null );
    const [ templates, setTemplates ] = useState<any[]>( [] );
    const toast = useToastContext();

    useEffect( () => {
        // Load templates
        fetch( `${API_BASE}/rcs/send`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify( { action: 'templates' } ),
        } ).then( r => r.json() ).then( d => setTemplates( d.templates || [] ) ).catch( () => { } );
    }, [] );

    const handleSend = async () => {
        if ( !phone ) { toast.error( 'Phone number required' ); return; }
        if ( messageType === 'text' && !text ) { toast.error( 'Message text required' ); return; }
        setSending( true ); setResult( null );
        try
        {
            const payload: any = { phoneNumber: phone };
            if ( messageType === 'text' )
            {
                payload.text = text;
            } else
            {
                payload.templateId = templateId;
                payload.language = 'en';
                if ( parameters.trim() )
                {
                    try { payload.parameters = JSON.parse( parameters ); } catch { payload.parameters = {}; }
                } else { payload.parameters = {}; }
            }
            const res = await fetch( `${API_BASE}/rcs/send`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify( payload ),
            } );
            const data = await res.json();
            setResult( data );
            if ( data.success || data.messageId || data.message_id )
            {
                toast.success( `RCS sent! ID: ${data.messageId || data.message_id}` );
            } else
            {
                toast.error( data.error || 'Failed to send' );
            }
        } catch ( err: any ) { toast.error( err.message || 'Send failed' ); } finally { setSending( false ); }
    };

    return (
        <div style={ { padding: '16px', maxWidth: 600 } }>
            <div style={ { background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 13 } }>
                <strong>Sinch RCS</strong> — Project: c8114d03 | App: 01KQSB792X | Bot: WECARE.DIGITAL (Transactional)
            </div>

            <div style={ { marginBottom: 12 } }>
                <label style={ { display: 'block', fontWeight: 500, marginBottom: 4 } }>Phone Number *</label>
                <input type="tel" value={ phone } onChange={ e => setPhone( e.target.value ) } placeholder="+919903300044" style={ { width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6 } } />
            </div>

            <div style={ { marginBottom: 12 } }>
                <label style={ { display: 'block', fontWeight: 500, marginBottom: 4 } }>Message Type</label>
                <div style={ { display: 'flex', gap: 8 } }>
                    <button onClick={ () => setMessageType( 'template' ) } style={ { padding: '6px 16px', borderRadius: 6, border: messageType === 'template' ? '2px solid #1a3a2a' : '1px solid #d1d5db', background: messageType === 'template' ? '#f0fdf4' : '#fff', cursor: 'pointer' } }>Template</button>
                    <button onClick={ () => setMessageType( 'text' ) } style={ { padding: '6px 16px', borderRadius: 6, border: messageType === 'text' ? '2px solid #1a3a2a' : '1px solid #d1d5db', background: messageType === 'text' ? '#f0fdf4' : '#fff', cursor: 'pointer' } }>Text</button>
                </div>
            </div>

            { messageType === 'template' ? (
                <>
                    <div style={ { marginBottom: 12 } }>
                        <label style={ { display: 'block', fontWeight: 500, marginBottom: 4 } }>Template</label>
                        <select value={ templateId } onChange={ e => setTemplateId( e.target.value ) } style={ { width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6 } }>
                            { templates.length > 0 ? templates.map( t => (
                                <option key={ t.name } value={ t.name }>{ t.name } — { t.textMessageContent?.substring( 0, 50 ) }...</option>
                            ) ) : (
                                <>
                                    <option value="test16">test16</option>
                                    <option value="test17">test17</option>
                                </>
                            ) }
                        </select>
                    </div>
                    <div style={ { marginBottom: 12 } }>
                        <label style={ { display: 'block', fontWeight: 500, marginBottom: 4 } }>Parameters (JSON, optional)</label>
                        <textarea value={ parameters } onChange={ e => setParameters( e.target.value ) } placeholder='{"cust_name": "John"}' rows={ 2 } style={ { width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6, fontFamily: 'monospace', fontSize: 12 } } />
                    </div>
                </>
            ) : (
                <div style={ { marginBottom: 12 } }>
                    <label style={ { display: 'block', fontWeight: 500, marginBottom: 4 } }>Message Text *</label>
                    <textarea value={ text } onChange={ e => setText( e.target.value ) } placeholder="Enter RCS message..." rows={ 4 } style={ { width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6 } } />
                    <div style={ { fontSize: 11, color: '#6b7280', marginTop: 4 } }>{ text.length }/2500 characters</div>
                </div>
            ) }

            <Button variant="primary" onClick={ handleSend } loading={ sending } disabled={ sending || !phone }>Send RCS</Button>

            { result && (
                <div style={ { marginTop: 16, padding: 12, background: result.success || result.messageId || result.message_id ? '#f0fdf4' : '#fef2f2', border: `1px solid ${result.success || result.messageId || result.message_id ? '#bbf7d0' : '#fecaca'}`, borderRadius: 8, fontSize: 12, fontFamily: 'monospace', whiteSpace: 'pre-wrap' } }>
                    { JSON.stringify( result, null, 2 ) }
                </div>
            ) }
        </div>
    );
};

export default RcsSendPage;
