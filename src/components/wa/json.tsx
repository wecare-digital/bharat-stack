/**
 * JSON viewer + collapsible raw JSON drawer (Part 5 global UX rule).
 */
import React, { useState } from 'react';
import { CopyToClipboardButton } from './copy';

export const JsonViewer: React.FC<{ data: any; maxHeight?: number }> = ( { data, maxHeight = 320 } ) => {
    const text = typeof data === 'string' ? data : JSON.stringify( data, null, 2 );
    return (
        <div style={ { position: 'relative' } }>
            <div style={ { position: 'absolute', top: 6, right: 6 } }>
                <CopyToClipboardButton text={ text } />
            </div>
            <pre style={ {
                background: '#1e1e1e', color: '#d4d4d4', padding: 12, borderRadius: 8,
                fontSize: 12, lineHeight: 1.5, overflow: 'auto', maxHeight, margin: 0,
            } }>{ text }</pre>
        </div>
    );
};

// Collapsible "Raw JSON" drawer — every API response can be inspected.
export const RawJsonDrawer: React.FC<{ data: any; label?: string; defaultOpen?: boolean }> = (
    { data, label = 'Raw JSON', defaultOpen = false }
) => {
    const [ open, setOpen ] = useState( defaultOpen );
    if ( data === undefined || data === null ) return null;
    return (
        <div style={ { marginTop: 10, border: '1px solid #e5e5e5', borderRadius: 8 } }>
            <button onClick={ () => setOpen( o => !o ) } style={ {
                width: '100%', textAlign: 'left', padding: '8px 12px', background: '#fafafa',
                border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600, color: '#444',
            } }>
                { open ? '▾' : '▸' } { label }
            </button>
            { open && <div style={ { padding: 10 } }><JsonViewer data={ data } /></div> }
        </div>
    );
};
