/**
 * WABA / phone / graph-version / field selectors (Part 5).
 */
import React from 'react';
import { WHATSAPP_PHONES } from '../../config/constants';

const sel: React.CSSProperties = { padding: '8px 10px', border: '1px solid #d0d0d0', borderRadius: 6, fontSize: 14 };
const lbl: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#444', marginBottom: 4, display: 'block' };

export interface WabaOption { wabaId: string; name: string; display?: string; metaPhoneId?: string; }

export const WABA_OPTIONS: WabaOption[] = [
    { wabaId: WHATSAPP_PHONES.primary.wabaId, name: WHATSAPP_PHONES.primary.name, display: WHATSAPP_PHONES.primary.display, metaPhoneId: WHATSAPP_PHONES.primary.metaPhoneId },
    { wabaId: WHATSAPP_PHONES.secondary.wabaId, name: WHATSAPP_PHONES.secondary.name, display: WHATSAPP_PHONES.secondary.display, metaPhoneId: WHATSAPP_PHONES.secondary.metaPhoneId },
];

export const WabaSelector: React.FC<{ value: string; onChange: ( wabaId: string ) => void; label?: string }> = (
    { value, onChange, label = 'WABA' }
) => (
    <div>
        <label style={ lbl }>{ label }</label>
        <select style={ sel } value={ value } onChange={ e => onChange( e.target.value ) }>
            { WABA_OPTIONS.map( o => <option key={ o.wabaId } value={ o.wabaId }>{ o.name }</option> ) }
        </select>
    </div>
);

export const PhoneNumberSelector: React.FC<{ value: string; onChange: ( metaPhoneId: string ) => void; label?: string }> = (
    { value, onChange, label = 'Phone number' }
) => (
    <div>
        <label style={ lbl }>{ label }</label>
        <select style={ sel } value={ value } onChange={ e => onChange( e.target.value ) }>
            { WABA_OPTIONS.map( o => <option key={ o.metaPhoneId } value={ o.metaPhoneId }>{ o.name } — { o.display }</option> ) }
        </select>
    </div>
);

const GRAPH_VERSIONS = [ 'v25.0', 'v24.0', 'v23.0', 'v22.0', 'v21.0', 'v20.0' ];
export const GraphVersionSelector: React.FC<{ value: string; onChange: ( v: string ) => void; label?: string }> = (
    { value, onChange, label = 'Graph API version' }
) => (
    <div>
        <label style={ lbl }>{ label }</label>
        <select style={ sel } value={ value } onChange={ e => onChange( e.target.value ) }>
            { GRAPH_VERSIONS.map( v => <option key={ v } value={ v }>{ v }</option> ) }
        </select>
    </div>
);

// Multi-select field picker (e.g. Graph API ?fields=).
export const FieldSelector: React.FC<{ options: string[]; selected: string[]; onChange: ( fields: string[] ) => void; label?: string }> = (
    { options, selected, onChange, label = 'Fields' }
) => {
    const toggle = ( f: string ) => onChange( selected.includes( f ) ? selected.filter( x => x !== f ) : [ ...selected, f ] );
    return (
        <div>
            <label style={ lbl }>{ label }</label>
            <div style={ { display: 'flex', flexWrap: 'wrap', gap: 6 } }>
                { options.map( f => (
                    <button key={ f } onClick={ () => toggle( f ) } style={ {
                        padding: '3px 10px', borderRadius: 999, fontSize: 12, cursor: 'pointer', fontWeight: 600,
                        border: '1px solid ' + ( selected.includes( f ) ? '#1a3a2a' : '#d0d0d0' ),
                        background: selected.includes( f ) ? '#1a3a2a' : '#fff',
                        color: selected.includes( f ) ? '#d1f470' : '#555',
                    } }>{ f }</button>
                ) ) }
            </div>
        </div>
    );
};
