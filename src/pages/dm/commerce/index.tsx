/**
 * Commerce — /dm/commerce
 * Admin UI for WhatsApp native commerce: send the catalog, compose & send a
 * native order_details (Review & Pay) bill, view orders/payments, and see the
 * live Razorpay payment configs per WABA. Backed by:
 *   POST /whatsapp/send            (catalog_message / isInteractivePayment order_details)
 *   GET  /wa-business/orders       + PATCH /wa-business/orders/{id}
 *   GET  /payments                 (recent payments)
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import { useToastContext } from '../../../contexts/ToastContext';
import { fetchAuthSession } from 'aws-amplify/auth';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';

const WABAS = [
    { label: 'WABA1 · +91 93309 94400', phoneId: 'phone-number-id-waba1-direct-1016149501586345', catalog: 'wecare_catalog', catalogId: '1607047307067517', payConfig: 'Razorpay_wecare.digital' },
    { label: 'WABA2 · +91 99033 00044', phoneId: 'phone-number-id-waba-t-direct-1055232054343117', catalog: 'Catalogue_Products', catalogId: '1424934879646296', payConfig: 'Razorpay_ManishAgarwal' },
];

interface LineItem { name: string; amount: string; quantity: string; }

const CommercePage: React.FC<PageProps> = ( { signOut, user, embedded = false } ) => {
    const toast = useToastContext();
    const [ phoneId, setPhoneId ] = useState( WABAS[ 0 ].phoneId );
    const [ toPhone, setToPhone ] = useState( '' );
    const [ busy, setBusy ] = useState( '' );
    const [ items, setItems ] = useState<LineItem[]>( [ { name: '', amount: '', quantity: '1' } ] );
    const [ goodsType, setGoodsType ] = useState<'physical-goods' | 'digital-goods'>( 'physical-goods' );
    const [ orders, setOrders ] = useState<any[]>( [] );
    const [ payments, setPayments ] = useState<any[]>( [] );
    const [ products, setProducts ] = useState<any[]>( [] );
    const [ productSearch, setProductSearch ] = useState( '' );

    const call = async ( path: string, method = 'GET', body?: any ) => {
        let token: string | null = null;
        try { token = ( await fetchAuthSession() ).tokens?.accessToken?.toString() ?? null; } catch { token = null; }
        const res = await fetch( `${API_BASE}${path}`, {
            method,
            headers: { 'Content-Type': 'application/json', ...( token ? { Authorization: `Bearer ${token}` } : {} ) },
            body: body ? JSON.stringify( body ) : undefined,
        } );
        if ( res.status === 401 || res.status === 403 ) { toast.error( 'Not authorized — sign in again' ); return null; }
        try { return await res.json(); } catch { return null; }
    };

    const digits = ( p: string ) => p.replace( /\D/g, '' );

    const sendCatalog = async () => {
        if ( !digits( toPhone ) ) { toast.error( 'Enter a customer phone' ); return; }
        setBusy( 'catalog' );
        try
        {
            const r = await call( '/whatsapp/send', 'POST', {
                recipientPhone: digits( toPhone ), phoneNumberId: phoneId,
                isInteractive: true, interactiveType: 'catalog_message',
                interactiveData: { body: 'Browse our catalog and add items to your cart.', footer: 'WECARE.DIGITAL' },
            } );
            if ( r ) toast.success( 'Catalog sent' ); else toast.error( 'Send failed' );
        } finally { setBusy( '' ); }
    };

    const sendBill = async () => {
        // Backend (/whatsapp/send isInteractivePayment) reads orderDetails.order.items[]
        // where each item = { name, amount:{value(paise),offset:100}, quantity, gstRate, retailer_id }.
        // Backend auto-adds 18% GST (per item gstRate) + 2% convenience fee and computes totals.
        const li = items
            .filter( i => i.name.trim() && Number( i.amount ) > 0 )
            .map( ( i, idx ) => ( {
                retailer_id: `ADMIN_${idx + 1}`,
                name: i.name.trim(),
                amount: { value: Math.round( Number( i.amount ) * 100 ), offset: 100 },
                quantity: Math.max( 1, Number( i.quantity ) || 1 ),
                gstRate: 18,
            } ) );
        if ( !digits( toPhone ) ) { toast.error( 'Enter a customer phone' ); return; }
        if ( !li.length ) { toast.error( 'Add at least one line item with amount' ); return; }
        const subtotal = li.reduce( ( s, i ) => s + ( i.amount.value / 100 ) * i.quantity, 0 );
        setBusy( 'bill' );
        try
        {
            const r = await call( '/whatsapp/send', 'POST', {
                recipientPhone: digits( toPhone ), phoneNumberId: phoneId,
                isInteractivePayment: true,
                orderDetails: {
                    type: goodsType,
                    currency: 'INR',
                    gstin: '19AADFW7431N1ZK',
                    reference_id: `ADMINBILL-${Date.now()}`,
                    order: { items: li },
                },
            } );
            if ( r ) toast.success( `Bill sent (subtotal ₹${subtotal.toFixed( 2 )} + 18% GST + 2% convenience)` );
            else toast.error( 'Send failed' );
        } finally { setBusy( '' ); }
    };

    const loadOrders = useCallback( async () => {
        const r = await call( '/wa-business/orders' );
        setOrders( Array.isArray( r?.orders ) ? r.orders : ( Array.isArray( r ) ? r : ( r?.data || [] ) ) );
    }, [] );
    const loadPayments = useCallback( async () => {
        const r = await call( '/payments' );
        setPayments( Array.isArray( r?.payments ) ? r.payments : ( Array.isArray( r ) ? r : ( r?.data || [] ) ) );
    }, [] );

    const loadProducts = useCallback( async () => {
        const waba = WABAS.find( w => w.phoneId === phoneId ) || WABAS[ 0 ];
        const qs = `?catalogId=${encodeURIComponent( waba.catalogId )}${productSearch.trim() ? `&search=${encodeURIComponent( productSearch.trim() )}` : ''}`;
        const r = await call( `/wa-business/catalog-products${qs}` );
        setProducts( Array.isArray( r?.products ) ? r.products : [] );
    }, [ phoneId, productSearch ] );

    useEffect( () => { loadOrders(); loadPayments(); }, [ loadOrders, loadPayments ] );
    useEffect( () => { loadProducts(); }, [ loadProducts ] );

    const addProductToBill = ( p: any ) => {
        // price like "100.00 INR" or "₹100.00"; extract the numeric rupee value
        const num = ( String( p.price || '' ).match( /[\d.]+/ ) || [ '' ] )[ 0 ];
        const first = items[ 0 ];
        const empty = items.length === 1 && !first.name.trim() && !first.amount;
        const next = { name: p.name || p.retailerId, amount: num, quantity: '1' };
        setItems( empty ? [ next ] : [ ...items, next ] );
        toast.success( `Added "${next.name}" to bill` );
    };

    const setItem = ( idx: number, k: keyof LineItem, v: string ) =>
        setItems( items.map( ( it, i ) => ( i === idx ? { ...it, [ k ]: v } : it ) ) );
    const addItem = () => setItems( [ ...items, { name: '', amount: '', quantity: '1' } ] );
    const delItem = ( idx: number ) => setItems( items.filter( ( _, i ) => i !== idx ) );

    const patchOrderStatus = async ( orderId: string, status: string ) => {
        const r = await call( `/wa-business/orders/${orderId}`, 'PATCH', { status } );
        if ( r ) { toast.success( `Order → ${status}` ); loadOrders(); } else toast.error( 'Update failed' );
    };

    const activeWaba = WABAS.find( w => w.phoneId === phoneId ) || WABAS[ 0 ];

    const body = (
        <>
            <SEO title="Commerce" description="WhatsApp catalog, orders & native payments" />
            <div style={ { padding: embedded ? 0 : 'var(--space-6)', maxWidth: 900 } }>
                <h1 style={ { fontSize: 'var(--h2)', fontWeight: 700, margin: '0 0 var(--space-4)', color: 'var(--text)' } }>Commerce</h1>

                <div style={ card }>
                    <label style={ lbl }>Business number</label>
                    <select value={ phoneId } onChange={ e => setPhoneId( e.target.value ) } style={ { width: '100%' } }>
                        { WABAS.map( w => <option key={ w.phoneId } value={ w.phoneId }>{ w.label }</option> ) }
                    </select>
                    <p style={ { fontSize: 12, color: 'var(--text-muted)', margin: '8px 0 0' } }>
                        Catalog: <b>{ activeWaba.catalog }</b> · Payments: <b>{ activeWaba.payConfig }</b> (Razorpay)
                    </p>
                    <label style={ { ...lbl, marginTop: 12 } }>Customer phone (E.164 digits)</label>
                    <input value={ toPhone } onChange={ e => setToPhone( e.target.value ) } placeholder="918100640044" style={ { width: '100%' } } />
                    <div style={ { marginTop: 12 } }>
                        <Button onClick={ sendCatalog } disabled={ busy !== '' }>{ busy === 'catalog' ? 'Sending…' : 'Send catalog' }</Button>
                    </div>
                </div>

                <div style={ card }>
                    <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 } }>
                        <h2 style={ h2 }>Catalog — { activeWaba.catalog }</h2>
                        <Button variant="secondary" onClick={ loadProducts }>Refresh</Button>
                    </div>
                    <div style={ { display: 'flex', gap: 6, marginBottom: 10 } }>
                        <input value={ productSearch } onChange={ e => setProductSearch( e.target.value ) } placeholder="Search products…" style={ { flex: 1 } } />
                    </div>
                    { products.length === 0 ? <p style={ muted }>No products found in this catalog.</p> : (
                        <ul style={ list }>
                            { products.slice( 0, 50 ).map( ( p: any, i: number ) => (
                                <li key={ p.retailerId || i } style={ row }>
                                    <span style={ { fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 } }>
                                        { p.imageUrl && <img src={ p.imageUrl } alt="" style={ { width: 32, height: 32, objectFit: 'cover', borderRadius: 4 } } /> }
                                        <span>{ p.name || p.retailerId } · { p.price || '—' }{ p.availability ? ` · ${p.availability}` : '' }</span>
                                    </span>
                                    <span style={ { display: 'flex', gap: 4 } }>
                                        <button onClick={ () => addProductToBill( p ) } style={ pill }>+ Bill</button>
                                    </span>
                                </li>
                            ) ) }
                        </ul>
                    ) }
                </div>

                <div style={ card }>
                    <h2 style={ h2 }>Compose a bill (native Review &amp; Pay)</h2>
                    <div style={ { display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10 } }>
                        <label style={ { fontSize: 13, color: 'var(--text-secondary)' } }>Goods:</label>
                        <select value={ goodsType } onChange={ e => setGoodsType( e.target.value as any ) }>
                            <option value="physical-goods">Physical goods (collect address)</option>
                            <option value="digital-goods">Digital goods</option>
                        </select>
                    </div>
                    { items.map( ( it, idx ) => (
                        <div key={ idx } style={ { display: 'flex', gap: 6, marginBottom: 6 } }>
                            <input value={ it.name } onChange={ e => setItem( idx, 'name', e.target.value ) } placeholder="Item name" style={ { flex: 3 } } />
                            <input value={ it.amount } onChange={ e => setItem( idx, 'amount', e.target.value ) } placeholder="₹ price" style={ { flex: 1 } } type="number" />
                            <input value={ it.quantity } onChange={ e => setItem( idx, 'quantity', e.target.value ) } placeholder="Qty" style={ { width: 60 } } type="number" />
                            { items.length > 1 && <button onClick={ () => delItem( idx ) } style={ delBtn }>✕</button> }
                        </div>
                    ) ) }
                    <div style={ { display: 'flex', gap: 8, marginTop: 8 } }>
                        <Button variant="secondary" onClick={ addItem } disabled={ busy !== '' }>+ Item</Button>
                        <Button onClick={ sendBill } disabled={ busy !== '' }>{ busy === 'bill' ? 'Sending…' : 'Send bill (Review & Pay)' }</Button>
                    </div>
                    <p style={ { fontSize: 12, color: 'var(--text-muted)', margin: '8px 0 0' } }>18% GST + 2% convenience fee are added automatically; a GST invoice is generated on payment.</p>
                </div>

                <div style={ card }>
                    <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 } }>
                        <h2 style={ h2 }>Orders</h2>
                        <Button variant="secondary" onClick={ loadOrders }>Refresh</Button>
                    </div>
                    { orders.length === 0 ? <p style={ muted }>No orders yet.</p> : (
                        <ul style={ list }>
                            { orders.slice( 0, 25 ).map( ( o: any, i: number ) => (
                                <li key={ o.orderId || o.id || i } style={ row }>
                                    <span style={ { fontSize: 13 } }>{ o.orderId || o.referenceId || o.id }{ o.customerName ? ` · ${o.customerName}` : '' } · ₹{ o.total ?? o.amount ?? '—' } · <b>{ o.orderStatus || o.status || 'pending' }</b></span>
                                    <span style={ { display: 'flex', gap: 4 } }>
                                        { [ 'processing', 'shipped', 'completed', 'canceled' ].map( s => (
                                            <button key={ s } onClick={ () => patchOrderStatus( o.orderId || o.id, s ) } style={ pill }>{ s }</button>
                                        ) ) }
                                    </span>
                                </li>
                            ) ) }
                        </ul>
                    ) }
                </div>

                <div style={ card }>
                    <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 } }>
                        <h2 style={ h2 }>Recent payments</h2>
                        <Button variant="secondary" onClick={ loadPayments }>Refresh</Button>
                    </div>
                    { payments.length === 0 ? <p style={ muted }>No payments yet.</p> : (
                        <ul style={ list }>
                            { payments.slice( 0, 25 ).map( ( p: any, i: number ) => (
                                <li key={ p.id || p.paymentId || p.referenceId || i } style={ row }>
                                    <span style={ { fontSize: 13 } }>{ p.referenceId || p.paymentId || p.id } · ₹{ p.amountInRupees ?? p.amount ?? '—' } · <b>{ p.status || '—' }</b></span>
                                    <span style={ { fontSize: 12, color: 'var(--text-muted)' } }>{ p.method || p.source || 'razorpay' }</span>
                                </li>
                            ) ) }
                        </ul>
                    ) }
                </div>
            </div>
        </>
    );

    return embedded ? body : <Layout user={ user } onSignOut={ signOut }>{ body }</Layout>;
};

const card: React.CSSProperties = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', marginBottom: 'var(--space-4)', boxShadow: 'var(--shadow-sm)' };
const h2: React.CSSProperties = { fontSize: 'var(--h4)', fontWeight: 600, margin: 0, color: 'var(--text)' };
const lbl: React.CSSProperties = { display: 'block', fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 };
const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: 13 };
const list: React.CSSProperties = { listStyle: 'none', padding: 0, margin: 0 };
const row: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border)' };
const pill: React.CSSProperties = { fontSize: 11, padding: '2px 6px', border: '1px solid var(--border)', borderRadius: 999, background: '#fff', cursor: 'pointer' };
const delBtn: React.CSSProperties = { border: 'none', background: 'none', color: 'var(--danger, #dc2626)', cursor: 'pointer', fontSize: 14 };

export default CommercePage;
