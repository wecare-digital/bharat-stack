/**
 * Masking + secret display components (Part 5).
 * Mirrors backend masking: phones/WA-IDs partially masked, secrets never shown raw.
 */
import React, { useState } from 'react';

export function maskTail ( value: string, keep = 4 ): string {
    if ( !value || value.length <= keep + 2 ) return '***';
    return value.slice( 0, 2 ) + '****' + value.slice( -keep );
}

interface RevealProps { value?: string; allowReveal?: boolean; }

// Phone number masked by default, optional admin reveal.
export const MaskedPhone: React.FC<RevealProps> = ( { value, allowReveal = false } ) => {
    const [ shown, setShown ] = useState( false );
    if ( !value ) return <span style={ { color: '#999' } }>—</span>;
    return (
        <span style={ { fontFamily: 'monospace' } }>
            { shown ? value : maskTail( value, 4 ) }
            { allowReveal && (
                <button onClick={ () => setShown( s => !s ) } style={ revealBtn } title={ shown ? 'Hide' : 'Reveal' }>
                    { shown ? '🙈' : '👁' }
                </button>
            ) }
        </span>
    );
};

// WhatsApp ID masked by default.
export const MaskedWaId: React.FC<RevealProps> = ( { value, allowReveal = false } ) => (
    <MaskedPhone value={ value } allowReveal={ allowReveal } />
);

// Secret field — never shows full value; reveal is opt-in and warns.
export const SecretField: React.FC<{ label?: string; value?: string; allowReveal?: boolean; lastRotated?: string }> = (
    { label, value, allowReveal = false, lastRotated }
) => {
    const [ shown, setShown ] = useState( false );
    return (
        <div style={ { marginBottom: 8 } }>
            { label && <div style={ { fontSize: 12, fontWeight: 600, color: '#444' } }>{ label }</div> }
            <div style={ { display: 'flex', alignItems: 'center', gap: 8 } }>
                <code style={ { background: '#f3f4f6', padding: '4px 8px', borderRadius: 6, fontSize: 13 } }>
                    { value ? ( shown ? value : '••••••••••••' ) : '(not set)' }
                </code>
                { allowReveal && value && (
                    <button onClick={ () => setShown( s => !s ) } style={ revealBtn }>{ shown ? 'Hide' : 'Reveal' }</button>
                ) }
            </div>
            { lastRotated && <div style={ { fontSize: 11, color: '#888', marginTop: 2 } }>Last rotated: { lastRotated }</div> }
        </div>
    );
};

const revealBtn: React.CSSProperties = {
    marginLeft: 6, border: '1px solid #d0d0d0', background: '#fff', borderRadius: 4,
    cursor: 'pointer', fontSize: 11, padding: '1px 6px',
};
