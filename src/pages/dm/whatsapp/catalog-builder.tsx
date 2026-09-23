/**
 * Catalog & Flow Builder — add products to a Meta WhatsApp catalog and create
 * WhatsApp Flows from one place. Styled with the app "subscribe" theme
 * (forest-green #1a3a2a / lime #d1f470, mirrors forms/selfservice.tsx).
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import { useToastContext } from '../../../contexts/ToastContext';
import { useConfirm } from '../../../contexts/ConfirmContext';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }

// Per-WABA catalog + flow identifiers (source of truth for the builder).
const ACCOUNTS = [
    { key: 'waba1', label: 'WABA 1 · WECARE.DIGITAL', wabaId: '2094615664435155', catalogId: '1607047307067517' },
    { key: 'waba2', label: 'WABA 2 · Catalogue_Products', wabaId: '2513394156072604', catalogId: '1424934879646296' },
];

const FLOW_CATEGORIES = [ 'SIGN_UP', 'SIGN_IN', 'APPOINTMENT_BOOKING', 'LEAD_GENERATION',
    'CONTACT_US', 'CUSTOMER_SUPPORT', 'SURVEY', 'OTHER' ];

const S = {
    tab: ( active: boolean ): React.CSSProperties => ( {
        padding: '8px 16px', border: 'none', borderBottom: active ? '2px solid #1a3a2a' : '2px solid transparent',
        background: 'none', cursor: 'pointer', fontSize: 13, fontWeight: active ? 600 : 400, color: active ? '#1a3a2a' : '#6b7280',
    } ),
    card: { border: '1px solid #e5e7eb', borderRadius: 10, padding: 16, background: '#fff', marginBottom: 16 } as React.CSSProperties,
    label: { fontSize: 12, color: '#6b7280', display: 'block', marginBottom: 4, fontWeight: 500 } as React.CSSProperties,
    input: { width: '100%', padding: '8px 12px', border: '1.5px solid #d1f470', borderRadius: 8, fontSize: 13, marginBottom: 12 } as React.CSSProperties,
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 } as React.CSSProperties,
    pill: ( bg: string, c: string ): React.CSSProperties => ( { background: bg, color: c, padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600 } ),
};

export default function CatalogBuilderPage ( { signOut, user }: PageProps ) {
    const toast = useToastContext();
    const confirm = useConfirm();
    const [ tab, setTab ] = useState<'product' | 'flow'>( 'product' );
    const [ acctIdx, setAcctIdx ] = useState( 0 );
    const acct = ACCOUNTS[ acctIdx ];

    return (
        <Layout user={ user } onSignOut={ signOut }>
            <SEO title="Catalog & Flow Builder" description="Add catalog products and create WhatsApp Flows" />
            <div className="inner-page" style={ { padding: '20px 24px', maxWidth: 1100 } }>
                <div style={ { marginBottom: 16 } }>
                    <h2 style={ { margin: 0, fontSize: 20, color: '#1a3a2a' } }>Catalog &amp; Flow Builder</h2>
                    <p style={ { margin: '4px 0 0', fontSize: 12, color: '#6b7280' } }>
                        Add products to your WhatsApp catalog and create Flows — one place, secure server-side calls.
                    </p>
                </div>

                <div style={ S.card }>
                    <label style={ S.label }>Account</label>
                    <select value={ acctIdx } onChange={ e => setAcctIdx( Number( e.target.value ) ) } style={ { ...S.input, maxWidth: 360, marginBottom: 0 } }>
                        { ACCOUNTS.map( ( a, i ) => <option key={ a.key } value={ i }>{ a.label }</option> ) }
                    </select>
                    <span style={ { marginLeft: 12, fontSize: 11, color: '#9ca3af' } }>
                        catalog { acct.catalogId } · waba { acct.wabaId }
                    </span>
                </div>

                <div style={ { borderBottom: '1px solid #e5e7eb', marginBottom: 16, display: 'flex', gap: 4 } }>
                    <button style={ S.tab( tab === 'product' ) } onClick={ () => setTab( 'product' ) }>Add Product</button>
                    <button style={ S.tab( tab === 'flow' ) } onClick={ () => setTab( 'flow' ) }>Create Flow</button>
                </div>

                { tab === 'product' && <ProductTab acct={ acct } toast={ toast } confirm={ confirm } /> }
                { tab === 'flow' && <FlowTab acct={ acct } toast={ toast } /> }
            </div>
        </Layout>
    );
}

// ─────────────────────────────── Add Product ───────────────────────────────
function ProductTab ( { acct, toast, confirm }: { acct: typeof ACCOUNTS[ number ]; toast: any; confirm: any } ) {
    const empty = { retailerId: '', name: '', price: '', salePrice: '', description: '', imageUrl: '', url: '', brand: 'WECARE.DIGITAL', availability: 'in stock' };
    const [ form, setForm ] = useState<Record<string, string>>( empty );
    const [ saving, setSaving ] = useState( false );
    const [ products, setProducts ] = useState<any[]>( [] );
    const [ loading, setLoading ] = useState( false );

    const load = useCallback( async () => {
        setLoading( true );
        try { setProducts( await api.listCatalogProductsAdmin( acct.catalogId ) ); }
        catch { toast.error( 'Failed to load products' ); }
        finally { setLoading( false ); }
    }, [ acct.catalogId, toast ] );

    useEffect( () => { load(); }, [ load ] );

    const set = ( k: string, v: string ) => setForm( f => ( { ...f, [ k ]: v } ) );

    const handleCreate = async () => {
        if ( !form.retailerId.trim() || !form.name.trim() || !form.price )
        {
            toast.error( 'SKU (retailer id), name and price are required' ); return;
        }
        setSaving( true );
        try
        {
            const r = await api.createCatalogProduct( {
                catalogId: acct.catalogId,
                retailerId: form.retailerId.trim(),
                name: form.name.trim(),
                price: Number( form.price ),
                salePrice: form.salePrice ? Number( form.salePrice ) : undefined,
                description: form.description || undefined,
                imageUrl: form.imageUrl || undefined,
                url: form.url || undefined,
                brand: form.brand || undefined,
                availability: form.availability || undefined,
            } );
            if ( r.success )
            {
                if ( r.imageFetchStatus === 'FETCH_FAILED' )
                {
                    toast.error( 'Product created but the image failed to fetch — use a public https image URL (e.g. app.wecare.digital/...)' );
                } else
                {
                    toast.success( `Product created (${r.productId || 'ok'})` );
                }
                setForm( empty );
                load();
            } else
            {
                toast.error( r.error || 'Create failed' );
            }
        } catch ( e: any ) { toast.error( e?.message || 'Create failed' ); }
        finally { setSaving( false ); }
    };

    const handleDelete = async ( p: any ) => {
        const ok = await confirm( { title: 'Delete product?', message: `Remove "${p.name}" (${p.retailerId}) from the catalog?`, confirmText: 'Delete', danger: true } );
        if ( !ok ) return;
        // list endpoint returns retailerId/name but not the product id; delete by re-fetching id
        const prods = await api.getCatalogProducts( { catalogId: acct.catalogId, limit: 200 } );
        const match = ( prods?.products || [] ).find( ( x: any ) => x.retailer_id === p.retailerId || x.retailerId === p.retailerId );
        const pid = match?.id;
        if ( !pid ) { toast.error( 'Could not resolve product id' ); return; }
        const done = await api.deleteCatalogProduct( pid );
        if ( done ) { toast.success( 'Product deleted' ); load(); }
        else toast.error( 'Delete failed' );
    };

    return (
        <div>
            <div style={ S.card }>
                <h3 style={ { margin: '0 0 12px', fontSize: 15, color: '#1a3a2a' } }>New product</h3>
                <div style={ S.grid }>
                    <div><label style={ S.label }>SKU / Retailer ID *</label><input style={ S.input } value={ form.retailerId } onChange={ e => set( 'retailerId', e.target.value ) } placeholder="WD-PARTNER-UP" /></div>
                    <div><label style={ S.label }>Name *</label><input style={ S.input } value={ form.name } onChange={ e => set( 'name', e.target.value ) } placeholder="Partner Up" /></div>
                    <div><label style={ S.label }>Price (₹) *</label><input style={ S.input } type="number" value={ form.price } onChange={ e => set( 'price', e.target.value ) } placeholder="6999" /></div>
                    <div><label style={ S.label }>Sale price (₹)</label><input style={ S.input } type="number" value={ form.salePrice } onChange={ e => set( 'salePrice', e.target.value ) } placeholder="4599" /></div>
                    <div><label style={ S.label }>Brand</label><input style={ S.input } value={ form.brand } onChange={ e => set( 'brand', e.target.value ) } /></div>
                    <div><label style={ S.label }>Availability</label>
                        <select style={ S.input } value={ form.availability } onChange={ e => set( 'availability', e.target.value ) }>
                            <option value="in stock">in stock</option><option value="out of stock">out of stock</option>
                        </select>
                    </div>
                    <div style={ { gridColumn: '1 / -1' } }><label style={ S.label }>Image URL (public https)</label><input style={ S.input } value={ form.imageUrl } onChange={ e => set( 'imageUrl', e.target.value ) } placeholder="https://app.wecare.digital/stream/media/m/wecare-digital.png" /></div>
                    <div style={ { gridColumn: '1 / -1' } }><label style={ S.label }>Product link</label><input style={ S.input } value={ form.url } onChange={ e => set( 'url', e.target.value ) } placeholder="https://wecare.digital/product-page/partner-up" /></div>
                    <div style={ { gridColumn: '1 / -1' } }><label style={ S.label }>Description</label><input style={ S.input } value={ form.description } onChange={ e => set( 'description', e.target.value ) } placeholder="Short description" /></div>
                </div>
                <Button variant="primary" onClick={ handleCreate } loading={ saving }>Create product</Button>
                <p style={ { fontSize: 11, color: '#9ca3af', marginTop: 8 } }>
                    New products need Meta&apos;s automated WhatsApp commerce review (NO_REVIEW → APPROVED) before they appear in the catalog browse. Use a public https image or it will fail review.
                </p>
            </div>

            <div style={ S.card }>
                <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 } }>
                    <h3 style={ { margin: 0, fontSize: 15, color: '#1a3a2a' } }>Products in catalog { loading ? '' : `(${products.length})` }</h3>
                    <Button variant="secondary" size="sm" onClick={ load } loading={ loading }>Refresh</Button>
                </div>
                { products.length === 0 && !loading && <p style={ { fontSize: 13, color: '#9ca3af' } }>No products yet.</p> }
                <div style={ S.grid }>
                    { products.map( ( p, i ) => (
                        <div key={ i } style={ { border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 } }>
                            <div style={ { fontWeight: 600, fontSize: 13, color: '#1a3a2a' } }>{ p.name }</div>
                            <div style={ { fontSize: 11, color: '#6b7280', margin: '2px 0' } }>{ p.retailerId }</div>
                            <div style={ { fontSize: 13, marginBottom: 8 } }>{ p.price } <span style={ S.pill( '#e0f2fe', '#0369a1' ) }>{ p.availability }</span></div>
                            <Button variant="danger" size="sm" onClick={ () => handleDelete( p ) }>Delete</Button>
                        </div>
                    ) ) }
                </div>
            </div>
        </div>
    );
}

// ─────────────────────────────── Create Flow ───────────────────────────────
function FlowTab ( { acct, toast }: { acct: typeof ACCOUNTS[ number ]; toast: any } ) {
    const [ name, setName ] = useState( '' );
    const [ category, setCategory ] = useState( 'OTHER' );
    const [ creating, setCreating ] = useState( false );
    const [ flows, setFlows ] = useState<any[]>( [] );
    const [ loading, setLoading ] = useState( false );

    const load = useCallback( async () => {
        setLoading( true );
        try { setFlows( await api.listFlows( acct.wabaId ) ); }
        catch { toast.error( 'Failed to load flows' ); }
        finally { setLoading( false ); }
    }, [ acct.wabaId, toast ] );

    useEffect( () => { load(); }, [ load ] );

    const handleCreate = async () => {
        if ( !name.trim() ) { toast.error( 'Flow name is required' ); return; }
        setCreating( true );
        try
        {
            const flow = await api.createFlow( acct.wabaId, name.trim(), [ category ] );
            if ( flow?.id ) { toast.success( `Flow created (${flow.id}) — add screens in Flow Builder, then publish` ); setName( '' ); load(); }
            else toast.error( 'Create failed' );
        } catch ( e: any ) { toast.error( e?.message || 'Create failed' ); }
        finally { setCreating( false ); }
    };

    const handlePublish = async ( flowId: string ) => {
        const ok = await api.publishFlow( flowId );
        if ( ok ) { toast.success( 'Flow published' ); load(); }
        else toast.error( 'Publish failed (flow must have valid screens)' );
    };

    const statusPill = ( s: string ) => {
        if ( s === 'PUBLISHED' ) return S.pill( '#d1f470', '#1a3a2a' );
        if ( s === 'DRAFT' ) return S.pill( '#fef3c7', '#92400e' );
        return S.pill( '#f3f4f6', '#6b7280' );
    };

    return (
        <div>
            <div style={ S.card }>
                <h3 style={ { margin: '0 0 12px', fontSize: 15, color: '#1a3a2a' } }>New flow</h3>
                <div style={ S.grid }>
                    <div style={ { gridColumn: '1 / -1' } }><label style={ S.label }>Flow name *</label><input style={ S.input } value={ name } onChange={ e => setName( e.target.value ) } placeholder="03.WD_POSTPAY_REQUEST" /></div>
                    <div><label style={ S.label }>Category</label>
                        <select style={ S.input } value={ category } onChange={ e => setCategory( e.target.value ) }>
                            { FLOW_CATEGORIES.map( c => <option key={ c } value={ c }>{ c }</option> ) }
                        </select>
                    </div>
                </div>
                <Button variant="primary" onClick={ handleCreate } loading={ creating }>Create flow</Button>
                <p style={ { fontSize: 11, color: '#9ca3af', marginTop: 8 } }>
                    Creates a DRAFT flow on { acct.label }. Add screens/JSON in the Flow Builder, then publish it here or in Flow Hub.
                </p>
            </div>

            <div style={ S.card }>
                <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 } }>
                    <h3 style={ { margin: 0, fontSize: 15, color: '#1a3a2a' } }>Flows { loading ? '' : `(${flows.length})` }</h3>
                    <Button variant="secondary" size="sm" onClick={ load } loading={ loading }>Refresh</Button>
                </div>
                <div className="table-container">
                    <table className="inner-table" style={ { width: '100%' } }>
                        <thead><tr><th style={ { textAlign: 'left' } }>Name</th><th style={ { textAlign: 'left' } }>Status</th><th style={ { textAlign: 'left' } }>ID</th><th></th></tr></thead>
                        <tbody>
                            { flows.map( ( f: any ) => (
                                <tr key={ f.id }>
                                    <td>{ f.name }</td>
                                    <td><span style={ statusPill( f.status ) }>{ f.status }</span></td>
                                    <td style={ { fontFamily: 'monospace', fontSize: 11 } }>{ f.id }</td>
                                    <td>{ f.status === 'DRAFT' && <Button variant="secondary" size="sm" onClick={ () => handlePublish( f.id ) }>Publish</Button> }</td>
                                </tr>
                            ) ) }
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
