/**
 * Copy-to-clipboard helpers (Part 5).
 */
import React, { useState, useCallback } from 'react';

export const CopyToClipboardButton: React.FC<{ text: string; label?: string; size?: 'sm' | 'md' }> = (
    { text, label = 'Copy', size = 'sm' }
) => {
    const [ copied, setCopied ] = useState( false );
    const copy = useCallback( async () => {
        try
        {
            await navigator.clipboard.writeText( text );
            setCopied( true );
            setTimeout( () => setCopied( false ), 1500 );
        } catch { /* clipboard unavailable */ }
    }, [ text ] );
    return (
        <button onClick={ copy } style={ {
            border: '1px solid #d0d0d0', background: copied ? '#e6f4ea' : '#fff',
            color: copied ? '#1a7a3a' : '#333', borderRadius: 6, cursor: 'pointer',
            fontSize: size === 'sm' ? 11 : 13, padding: size === 'sm' ? '2px 8px' : '6px 12px', fontWeight: 600,
        } }>
            { copied ? '✓ Copied' : label }
        </button>
    );
};

// fbtrace_id display + copy — surfaced from Meta error responses for support tickets.
export const FbTraceIdCopy: React.FC<{ traceId?: string }> = ( { traceId } ) => {
    if ( !traceId ) return null;
    return (
        <div style={ { display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#666' } }>
            <span>fbtrace_id:</span>
            <code style={ { background: '#f3f4f6', padding: '2px 6px', borderRadius: 4 } }>{ traceId }</code>
            <CopyToClipboardButton text={ traceId } label="Copy" />
        </div>
    );
};
