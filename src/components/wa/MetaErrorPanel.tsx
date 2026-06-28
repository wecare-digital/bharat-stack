/**
 * MetaErrorPanel (Part 5) — renders a Meta Graph API error safely:
 * human message + code/subcode + fbtrace_id (copyable) + raw JSON drawer.
 */
import React from 'react';
import { FbTraceIdCopy } from './copy';
import { RawJsonDrawer } from './json';

interface MetaError {
    message?: string;
    type?: string;
    code?: number | string;
    error_subcode?: number | string;
    error_user_title?: string;
    error_user_msg?: string;
    fbtrace_id?: string;
}

// Accepts either { error: {...} } envelope or a raw error object.
export const MetaErrorPanel: React.FC<{ error: any; title?: string }> = ( { error, title = 'Meta API Error' } ) => {
    if ( !error ) return null;
    const err: MetaError = ( error.error && typeof error.error === 'object' ) ? error.error : error;
    const friendly = err.error_user_msg || err.message || ( typeof error === 'string' ? error : 'Unknown error' );

    return (
        <div style={ { border: '1px solid #f3c2c2', background: '#fdf3f3', borderRadius: 8, padding: 12, marginTop: 10 } }>
            <div style={ { fontWeight: 700, color: '#a11', fontSize: 13, marginBottom: 4 } }>
                ⚠ { err.error_user_title || title }
            </div>
            <div style={ { fontSize: 13, color: '#7a1a1a', marginBottom: 6 } }>{ friendly }</div>
            <div style={ { display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12, color: '#9a4a4a', marginBottom: 4 } }>
                { err.code !== undefined && <span>code: { err.code }</span> }
                { err.error_subcode !== undefined && <span>subcode: { err.error_subcode }</span> }
                { err.type && <span>type: { err.type }</span> }
            </div>
            <FbTraceIdCopy traceId={ err.fbtrace_id } />
            <RawJsonDrawer data={ error } label="Raw error JSON" />
        </div>
    );
};
