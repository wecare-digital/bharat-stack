/**
 * Store Page - WECARE.DIGITAL
 * Wix Store Integration — Products, Orders, Collections, Inventory
 * URL: https://stack.wecare.digital/store
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import SEO from '../../components/SEO';
import Tabs, { TabItem } from '../../components/ui/Tabs';
import Table from '../../components/ui/Table';
import Modal from '../../components/ui/Modal';
import Spinner from '../../components/ui/Spinner';
import EmptyState from '../../components/ui/EmptyState';
import * as api from '../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'products' | 'orders' | 'collections' | 'manage' | 'admin' | 'settings';

const TABS: TabItem[] = [
  { id: 'products', label: 'Products' },
  { id: 'orders', label: 'Orders' },
  { id: 'collections', label: 'Collections' },
  { id: 'manage', label: 'Product Manager' },
  { id: 'admin', label: 'Store Admin' },
  { id: 'settings', label: 'Settings' },
];

const StorePage: React.FC<PageProps> = ( { signOut, user } ) => {
  const [ activeTab, setActiveTab ] = useState<TabType>( 'products' );
  const [ loading, setLoading ] = useState( false );
  const [ syncing, setSyncing ] = useState( false );

  // Products
  const [ products, setProducts ] = useState<api.WixProduct[]>( [] );
  const [ productCount, setProductCount ] = useState( 0 );
  const [ productSearch, setProductSearch ] = useState( '' );
  const [ selectedProduct, setSelectedProduct ] = useState<api.WixProduct | null>( null );

  // Orders
  const [ orders, setOrders ] = useState<api.WixOrder[]>( [] );
  const [ orderCount, setOrderCount ] = useState( 0 );
  const [ orderSearch, setOrderSearch ] = useState( '' );
  const [ orderStatusFilter, setOrderStatusFilter ] = useState( '' );
  const [ selectedOrder, setSelectedOrder ] = useState<api.WixOrder | null>( null );

  // Collections
  const [ collections, setCollections ] = useState<api.WixCollection[]>( [] );
  const [ collectionCount, setCollectionCount ] = useState( 0 );
  const [ selectedCollectionId, setSelectedCollectionId ] = useState<string>( '' );

  // Sites (settings)
  const [ sites, setSites ] = useState<any[]>( [] );

  // Product Manager
  const [ manageMode, setManageMode ] = useState<'single' | 'bulk'>( 'single' );
  const [ creating, setCreating ] = useState( false );
  const [ createResult, setCreateResult ] = useState<any>( null );
  const [ sampleProducts, setSampleProducts ] = useState<any[]>( [] );
  const [ newProduct, setNewProduct ] = useState( {
    name: '',
    productType: 'digital' as 'digital' | 'physical',
    description: '',
    price: '',
    currency: 'INR',
    sku: '',
    ribbon: 'BNB CLUB',
    brand: 'WECARE.DIGITAL',
    weight: '0',
  } );
  const [ bulkJson, setBulkJson ] = useState( '' );

  // ---- Data fetching ----
  const fetchProducts = useCallback( async () => {
    setLoading( true );
    try
    {
      const data = await api.listWixProducts( {
        limit: 100,
        search: productSearch || undefined,
        collectionId: selectedCollectionId || undefined,
      } );
      setProducts( data.products );
      setProductCount( data.totalCount );
    } catch ( e )
    {
      console.error( 'Failed to fetch products:', e );
    }
    setLoading( false );
  }, [ productSearch, selectedCollectionId ] );

  const fetchOrders = useCallback( async () => {
    setLoading( true );
    try
    {
      const params: any = { limit: 50 };
      if ( orderStatusFilter ) params.paymentStatus = orderStatusFilter;
      if ( orderSearch )
      {
        // Search: try as WD custom order number first, then email
        if ( orderSearch.startsWith( 'WD' ) )
        {
          params.customOrderNumber = orderSearch;
        } else if ( orderSearch.includes( '@' ) )
        {
          params.email = orderSearch;
        } else
        {
          params.customOrderNumber = orderSearch;
        }
      }
      const data = await api.listWixOrders( params );
      setOrders( data.orders );
      setOrderCount( data.totalCount );
    } catch ( e )
    {
      console.error( 'Failed to fetch orders:', e );
    }
    setLoading( false );
  }, [ orderSearch, orderStatusFilter ] );

  const fetchCollections = useCallback( async () => {
    setLoading( true );
    try
    {
      const data = await api.listWixCollections( 100 );
      setCollections( data.collections );
      setCollectionCount( data.totalCount );
    } catch ( e )
    {
      console.error( 'Failed to fetch collections:', e );
    }
    setLoading( false );
  }, [] );

  const fetchSites = useCallback( async () => {
    setLoading( true );
    try
    {
      const data = await api.listWixSites();
      setSites( data );
    } catch ( e )
    {
      console.error( 'Failed to fetch sites:', e );
    }
    setLoading( false );
  }, [] );

  const fetchSamples = useCallback( async () => {
    try
    {
      const data = await api.getWixSampleProducts();
      setSampleProducts( data.products || [] );
    } catch ( e )
    {
      console.error( 'Failed to fetch samples:', e );
    }
  }, [] );

  useEffect( () => {
    if ( activeTab === 'products' ) fetchProducts();
    else if ( activeTab === 'orders' ) fetchOrders();
    else if ( activeTab === 'collections' ) fetchCollections();
    else if ( activeTab === 'settings' ) fetchSites();
    else if ( activeTab === 'manage' ) fetchSamples();
  }, [ activeTab, fetchProducts, fetchOrders, fetchCollections, fetchSites, fetchSamples ] );

  const handleSync = async ( type: 'products' | 'orders' ) => {
    setSyncing( true );
    try
    {
      if ( type === 'products' )
      {
        await api.syncWixProducts();
        await fetchProducts();
      } else
      {
        await api.syncWixOrders();
        await fetchOrders();
      }
    } catch ( e )
    {
      console.error( 'Sync failed:', e );
    }
    setSyncing( false );
  };

  const handleProductClick = async ( product: api.WixProduct ) => {
    try
    {
      const full = await api.getWixProduct( product._id );
      setSelectedProduct( full || product );
    } catch
    {
      setSelectedProduct( product );
    }
  };

  const handleCreateProduct = async () => {
    if ( !newProduct.name || !newProduct.price ) return;
    setCreating( true );
    setCreateResult( null );
    try
    {
      const productData: any = {
        name: newProduct.name,
        productType: newProduct.productType,
        description: newProduct.description,
        priceData: { currency: newProduct.currency, price: parseFloat( newProduct.price ) },
        sku: newProduct.sku,
        ribbon: newProduct.ribbon,
        brand: newProduct.brand,
      };
      if ( newProduct.productType === 'physical' )
      {
        productData.weight = parseFloat( newProduct.weight ) || 0;
      }
      const result = await api.createWixProduct( productData );
      setCreateResult( { success: true, ...result } );
      setNewProduct( { name: '', productType: 'digital', description: '', price: '', currency: 'INR', sku: '', ribbon: 'BNB CLUB', brand: 'WECARE.DIGITAL', weight: '0' } );
    } catch ( e: any )
    {
      setCreateResult( { success: false, error: e.message } );
    }
    setCreating( false );
  };

  const handleBulkCreate = async () => {
    setCreating( true );
    setCreateResult( null );
    try
    {
      const products = JSON.parse( bulkJson );
      if ( !Array.isArray( products ) ) throw new Error( 'JSON must be an array of products' );
      const result = await api.bulkCreateWixProducts( products );
      setCreateResult( { success: true, bulk: true, ...result } );
    } catch ( e: any )
    {
      setCreateResult( { success: false, error: e.message } );
    }
    setCreating( false );
  };

  const handleLoadSample = ( sample: any ) => {
    if ( manageMode === 'single' )
    {
      setNewProduct( {
        name: sample.name || '',
        productType: sample.productType || 'digital',
        description: sample.description || '',
        price: String( sample.priceData?.price || sample.price || '' ),
        currency: sample.priceData?.currency || 'INR',
        sku: sample.sku || '',
        ribbon: sample.ribbon || 'BNB CLUB',
        brand: sample.brand || 'WECARE.DIGITAL',
        weight: String( sample.weight || 0 ),
      } );
    } else
    {
      setBulkJson( JSON.stringify( [ sample ], null, 2 ) );
    }
  };

  const handleLoadAllSamples = () => {
    setBulkJson( JSON.stringify( sampleProducts, null, 2 ) );
    setManageMode( 'bulk' );
  };

  const handleOrderClick = async ( order: api.WixOrder ) => {
    try
    {
      const full = await api.getWixOrder( order._id );
      setSelectedOrder( full || order );
    } catch
    {
      setSelectedOrder( order );
    }
  };

  // ---- Product columns ----
  const productColumns = [
    {
      key: 'image', header: '', width: '50px',
      render: ( p: api.WixProduct ) => (
        <div style={ { width: 40, height: 40, borderRadius: 8, overflow: 'hidden', background: '#f3f4f6' } }>
          { p.mainMedia?.url ? (
            <img src={ p.mainMedia.url } alt={ p.name } style={ { width: '100%', height: '100%', objectFit: 'cover' } } />
          ) : (
            <div style={ { width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 12 } }>—</div>
          ) }
        </div>
      ),
    },
    {
      key: 'name', header: 'Product', render: ( p: api.WixProduct ) => (
        <div>
          <div style={ { fontWeight: 500 } }>{ p.name }</div>
          { p.sku && <div style={ { fontSize: 12, color: '#6b7280' } }>SKU: { p.sku }</div> }
        </div>
      )
    },
    {
      key: 'price', header: 'Price', render: ( p: api.WixProduct ) => (
        <span>{ p.formattedPrice || `${p.currency || '₹'}${p.price || 0}` }</span>
      )
    },
    {
      key: 'collections', header: 'Collections', render: ( p: api.WixProduct ) => (
        <div style={ { display: 'flex', gap: 4, flexWrap: 'wrap' } }>
          { ( p.collections || [] ).map( c => (
            <span key={ c._id } style={ { background: '#f9fafb', color: '#1a3a2a', padding: '2px 8px', borderRadius: 12, fontSize: 11 } }>{ c.name }</span>
          ) ) }
        </div>
      )
    },
    {
      key: 'stock', header: 'Stock', render: ( p: api.WixProduct ) => (
        <span style={ { color: p.inStock ? '#1a3a2a' : '#1a3a2a', fontWeight: 500, fontSize: 13 } }>
          { p.inStock ? ( p.quantityInStock !== undefined ? `${p.quantityInStock} in stock` : 'In Stock' ) : 'Out of Stock' }
        </span>
      )
    },
    {
      key: 'type', header: 'Type', render: ( p: api.WixProduct ) => (
        <span style={ { textTransform: 'capitalize', fontSize: 13 } }>{ p.productType || 'physical' }</span>
      )
    },
    {
      key: 'actions', header: '', width: '80px', render: ( p: api.WixProduct ) => (
        <button onClick={ () => handleProductClick( p ) } style={ { background: 'none', border: '1px solid #d1d5db', borderRadius: 8, padding: '4px 12px', cursor: 'pointer', fontSize: 12 } }>View</button>
      )
    },
  ];

  // ---- Order columns ----
  const orderColumns = [
    {
      key: 'number', header: 'Order #', width: '100px', render: ( o: api.WixOrder ) => (
        <div>
          <div style={ { fontWeight: 600 } }>{ o.customOrderNumber || o._summary?.customOrderNumber || o.customField?.value || o._summary?.externalOrderId || `#${o.number || '—'}` }</div>
        </div>
      )
    },
    {
      key: 'buyer', header: 'Buyer', render: ( o: api.WixOrder ) => {
        const email = ( o as any ).buyerEmail || o.buyerInfo?.email || o._summary?.buyerEmail || '';
        const name = ( o as any ).buyerName || o._summary?.billingName || '';
        return (
          <div>
            { name && <div style={ { fontWeight: 500, fontSize: 13 } }>{ name }</div> }
            <div style={ { fontSize: 12, color: '#6b7280' } }>{ email }</div>
          </div>
        );
      }
    },
    {
      key: 'items', header: 'Items', width: '60px', render: ( o: api.WixOrder ) => (
        <span>{ ( o as any ).lineItemCount || o.lineItems?.length || o._summary?.lineItemCount || 0 }</span>
      )
    },
    {
      key: 'total', header: 'Total', render: ( o: api.WixOrder ) => {
        const total = o.totals?.total || o._summary?.totalAmount || '0';
        const currency = o.currency || o._summary?.currency || 'INR';
        return <span style={ { fontWeight: 600 } }>{ currency === 'INR' ? '₹' : currency + ' ' }{ total }</span>;
      }
    },
    {
      key: 'payment', header: 'Payment', render: ( o: api.WixOrder ) => {
        const status = o.paymentStatus || o._summary?.paymentStatus || '';
        const color = status === 'PAID' ? '#1a3a2a' : status === 'NOT_PAID' ? '#1a3a2a' : '#1a3a2a';
        return <span style={ { color, fontWeight: 500, fontSize: 12, textTransform: 'uppercase' } }>{ status.replace( /_/g, ' ' ) }</span>;
      }
    },
    {
      key: 'fulfillment', header: 'Fulfillment', render: ( o: api.WixOrder ) => {
        const status = o.fulfillmentStatus || o._summary?.fulfillmentStatus || '';
        const color = status === 'FULFILLED' ? '#1a3a2a' : status === 'NOT_FULFILLED' ? '#6b7280' : '#1a3a2a';
        return <span style={ { color, fontWeight: 500, fontSize: 12, textTransform: 'uppercase' } }>{ status.replace( /_/g, ' ' ) || '—' }</span>;
      }
    },
    {
      key: 'date', header: 'Date', render: ( o: api.WixOrder ) => {
        const d = o.dateCreated || ( o as any ).createdDate || o._summary?.createdDate || '';
        return <span style={ { fontSize: 12, color: '#6b7280' } }>{ d ? new Date( d ).toLocaleDateString( 'en-IN', { day: '2-digit', month: 'short', year: 'numeric' } ) : '—' }</span>;
      }
    },
    {
      key: 'actions', header: '', width: '80px', render: ( o: api.WixOrder ) => (
        <button onClick={ () => handleOrderClick( o ) } style={ { background: 'none', border: '1px solid #d1d5db', borderRadius: 8, padding: '4px 12px', cursor: 'pointer', fontSize: 12 } }>View</button>
      )
    },
  ];

  // ---- Render ----
  return (
    <Layout user={ user } onSignOut={ signOut }>
      <SEO title="Store" description="Wix Store — Products, Orders, Collections" />
      <div className="store-page">
        <PageHeader
          title="Store"
          subtitle={ `Wix Store Integration — ${productCount} products, ${orderCount} orders` }
          icon="store"
          actions={
            <div style={ { display: 'flex', gap: 8 } }>
              <button onClick={ () => handleSync( 'products' ) } disabled={ syncing } style={ { display: 'flex', alignItems: 'center', gap: 6 } }>
                { syncing ? <Spinner size="sm" /> : null } Sync Products
              </button>
              <button onClick={ () => handleSync( 'orders' ) } disabled={ syncing } style={ { display: 'flex', alignItems: 'center', gap: 6 } }>
                { syncing ? <Spinner size="sm" /> : null } Sync Orders
              </button>
            </div>
          }
        />

        <Tabs items={ TABS } activeTab={ activeTab } onChange={ ( id ) => setActiveTab( id as TabType ) } />

        <div style={ { marginTop: 16 } }>
          {/* ---- PRODUCTS TAB ---- */ }
          { activeTab === 'products' && (
            <div>
              <div style={ { display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' } }>
                <input
                  type="text"
                  placeholder="Search products..."
                  value={ productSearch }
                  onChange={ e => setProductSearch( e.target.value ) }
                  onKeyDown={ e => e.key === 'Enter' && fetchProducts() }
                  style={ { flex: 1, padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 12, fontSize: 14, outline: 'none' } }
                />
                <button onClick={ fetchProducts }>Search</button>
                { selectedCollectionId && (
                  <button
                    onClick={ () => { setSelectedCollectionId( '' ); } }
                    className="btn btn-sm btn-secondary"
                  >
                    Clear filter
                  </button>
                ) }
              </div>
              { loading ? (
                <div style={ { textAlign: 'center', padding: 60 } }><Spinner size="lg" /></div>
              ) : products.length === 0 ? (
                <EmptyState icon="search" title="No Products Found" description="Connect your Wix Store and sync products to see them here." />
              ) : (
                <Table columns={ productColumns } data={ products } keyField="_id" />
              ) }
            </div>
          ) }

          {/* ---- ORDERS TAB ---- */ }
          { activeTab === 'orders' && (
            <div>
              <div style={ { display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' } }>
                <input
                  type="text"
                  placeholder="Search by WD order number or email..."
                  value={ orderSearch }
                  onChange={ e => setOrderSearch( e.target.value ) }
                  onKeyDown={ e => e.key === 'Enter' && fetchOrders() }
                  style={ { flex: 1, minWidth: 200, padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 12, fontSize: 14, outline: 'none' } }
                />
                <select
                  value={ orderStatusFilter }
                  onChange={ e => setOrderStatusFilter( e.target.value ) }
                  style={ { padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 12, fontSize: 14, background: '#fff' } }
                >
                  <option value="">All Statuses</option>
                  <option value="PAID">Paid</option>
                  <option value="NOT_PAID">Not Paid</option>
                  <option value="PARTIALLY_PAID">Partially Paid</option>
                  <option value="PARTIALLY_REFUNDED">Partially Refunded</option>
                  <option value="FULLY_REFUNDED">Fully Refunded</option>
                </select>
                <button onClick={ fetchOrders }>Search</button>
              </div>
              { loading ? (
                <div style={ { textAlign: 'center', padding: 60 } }><Spinner size="lg" /></div>
              ) : orders.length === 0 ? (
                <EmptyState icon="order" title="No Orders Found" description="Orders from your Wix Store will appear here." />
              ) : (
                <Table columns={ orderColumns } data={ orders } keyField="_id" />
              ) }
            </div>
          ) }

          {/* ---- COLLECTIONS TAB ---- */ }
          { activeTab === 'collections' && (
            <div>
              { loading ? (
                <div style={ { textAlign: 'center', padding: 60 } }><Spinner size="lg" /></div>
              ) : collections.length === 0 ? (
                <EmptyState icon="default" title="No Collections" description="Create collections in your Wix Store to organize products." />
              ) : (
                <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 } }>
                  { collections.map( c => (
                    <div key={ c._id } style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, cursor: 'pointer' } }
                      onClick={ () => { setProductSearch( '' ); setSelectedCollectionId( c._id ); setActiveTab( 'products' ); } }>
                      { c.mainMedia?.url && (
                        <img src={ c.mainMedia.url } alt={ c.name } style={ { width: '100%', height: 140, objectFit: 'cover', borderRadius: 8, marginBottom: 12 } } />
                      ) }
                      <h4 style={ { margin: 0, fontSize: 16, fontWeight: 600 } }>{ c.name }</h4>
                      { c.description && <p style={ { margin: '4px 0 0', fontSize: 13, color: '#6b7280' } }>{ c.description }</p> }
                    </div>
                  ) ) }
                </div>
              ) }
            </div>
          ) }

          {/* ---- PRODUCT MANAGER TAB ---- */ }
          { activeTab === 'manage' && (
            <div style={ { maxWidth: 900 } }>
              {/* Mode Toggle */ }
              <div style={ { display: 'flex', gap: 8, marginBottom: 16 } }>
                <button
                  onClick={ () => setManageMode( 'single' ) }
                  style={ { padding: '8px 20px', borderRadius: 8, border: manageMode === 'single' ? '2px solid #1a3a2a' : '1px solid #d1d5db', background: manageMode === 'single' ? '#f9fafb' : '#fff', cursor: 'pointer', fontWeight: manageMode === 'single' ? 600 : 400, fontSize: 13 } }
                >
                  Single Product
                </button>
                <button
                  onClick={ () => setManageMode( 'bulk' ) }
                  style={ { padding: '8px 20px', borderRadius: 8, border: manageMode === 'bulk' ? '2px solid #1a3a2a' : '1px solid #d1d5db', background: manageMode === 'bulk' ? '#f9fafb' : '#fff', cursor: 'pointer', fontWeight: manageMode === 'bulk' ? 600 : 400, fontSize: 13 } }
                >
                  Bulk Create (JSON)
                </button>
              </div>

              {/* Sample Products */ }
              { sampleProducts.length > 0 && (
                <div style={ { background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, marginBottom: 16 } }>
                  <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 } }>
                    <span style={ { fontWeight: 600, fontSize: 14 } }>BNB CLUB Templates</span>
                    <button onClick={ handleLoadAllSamples } style={ { fontSize: 12, padding: '4px 12px', border: '1px solid #86efac', borderRadius: 6, background: '#fff', cursor: 'pointer', color: '#1a3a2a' } }>
                      Load All → Bulk
                    </button>
                  </div>
                  <div style={ { display: 'flex', gap: 8, flexWrap: 'wrap' } }>
                    { sampleProducts.map( ( s: any, i: number ) => (
                      <button key={ i } onClick={ () => handleLoadSample( s ) }
                        style={ { padding: '6px 14px', borderRadius: 8, border: '1px solid #d1d5db', background: '#fff', cursor: 'pointer', fontSize: 12, textAlign: 'left', maxWidth: 260 } }>
                        <div style={ { fontWeight: 500 } }>{ s.name }</div>
                        <div style={ { color: '#6b7280', fontSize: 11 } }>₹{ s.priceData?.price || s.price } · { s.sku }</div>
                      </button>
                    ) ) }
                  </div>
                </div>
              ) }

              {/* Single Product Form */ }
              { manageMode === 'single' && (
                <div style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 } }>
                  <h3 style={ { margin: '0 0 16px', fontSize: 16, fontWeight: 600 } }>Create Product</h3>
                  <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 } }>
                    <div style={ { gridColumn: '1 / -1' } }>
                      <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Product Name *</label>
                      <input type="text" value={ newProduct.name } onChange={ e => setNewProduct( { ...newProduct, name: e.target.value } ) } placeholder="Visa Assistance — Tourist Visa"
                        style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 14, outline: 'none', boxSizing: 'border-box' } } />
                    </div>
                    <div>
                      <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Price *</label>
                      <input type="number" value={ newProduct.price } onChange={ e => setNewProduct( { ...newProduct, price: e.target.value } ) } placeholder="2999"
                        style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 14, outline: 'none', boxSizing: 'border-box' } } />
                    </div>
                    <div>
                      <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Currency</label>
                      <select value={ newProduct.currency } onChange={ e => setNewProduct( { ...newProduct, currency: e.target.value } ) }
                        style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 14, background: '#fff', boxSizing: 'border-box' } }>
                        <option value="INR">INR (₹)</option>
                        <option value="USD">USD ($)</option>
                        <option value="EUR">EUR (€)</option>
                        <option value="GBP">GBP (£)</option>
                      </select>
                    </div>
                    <div>
                      <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>SKU</label>
                      <input type="text" value={ newProduct.sku } onChange={ e => setNewProduct( { ...newProduct, sku: e.target.value } ) } placeholder="BNB-VISA-SINGLE-001"
                        style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 14, outline: 'none', boxSizing: 'border-box' } } />
                    </div>
                    <div>
                      <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Type</label>
                      <select value={ newProduct.productType } onChange={ e => setNewProduct( { ...newProduct, productType: e.target.value as 'digital' | 'physical' } ) }
                        style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 14, background: '#fff', boxSizing: 'border-box' } }>
                        <option value="digital">Digital</option>
                        <option value="physical">Physical</option>
                      </select>
                    </div>
                    <div>
                      <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Ribbon</label>
                      <input type="text" value={ newProduct.ribbon } onChange={ e => setNewProduct( { ...newProduct, ribbon: e.target.value } ) } placeholder="BNB CLUB"
                        style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 14, outline: 'none', boxSizing: 'border-box' } } />
                    </div>
                    <div>
                      <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Brand</label>
                      <input type="text" value={ newProduct.brand } onChange={ e => setNewProduct( { ...newProduct, brand: e.target.value } ) } placeholder="WECARE.DIGITAL"
                        style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 14, outline: 'none', boxSizing: 'border-box' } } />
                    </div>
                    { newProduct.productType === 'physical' && (
                      <div>
                        <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Weight (kg)</label>
                        <input type="number" value={ newProduct.weight } onChange={ e => setNewProduct( { ...newProduct, weight: e.target.value } ) } placeholder="0"
                          style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 14, outline: 'none', boxSizing: 'border-box' } } />
                      </div>
                    ) }
                    <div style={ { gridColumn: '1 / -1' } }>
                      <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Description (HTML)</label>
                      <textarea value={ newProduct.description } onChange={ e => setNewProduct( { ...newProduct, description: e.target.value } ) } rows={ 5 } placeholder="<p>Product description...</p>"
                        style={ { width: '100%', padding: '10px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 13, outline: 'none', fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box' } } />
                    </div>
                  </div>
                  <div style={ { marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' } }>
                    <button onClick={ handleCreateProduct } disabled={ creating || !newProduct.name || !newProduct.price }
                      style={ { padding: '10px 24px', background: '#d1f470', color: '#1a3a2a', border: 'none', borderRadius: 10, cursor: 'pointer', fontWeight: 600, fontSize: 14, opacity: creating || !newProduct.name || !newProduct.price ? 0.5 : 1 } }>
                      { creating ? 'Creating...' : 'Create Product' }
                    </button>
                  </div>
                </div>
              ) }

              {/* Bulk Create */ }
              { manageMode === 'bulk' && (
                <div style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 } }>
                  <h3 style={ { margin: '0 0 16px', fontSize: 16, fontWeight: 600 } }>Bulk Create Products</h3>
                  <label style={ { display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4, color: '#374151' } }>Products JSON Array</label>
                  <textarea value={ bulkJson } onChange={ e => setBulkJson( e.target.value ) } rows={ 14 } placeholder='[{"name": "Product 1", "productType": "digital", "priceData": {"currency": "INR", "price": 999}, "sku": "SKU-001"}]'
                    style={ { width: '100%', padding: '12px 14px', border: '1.5px solid #d1d5db', borderRadius: 10, fontSize: 12, outline: 'none', fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box' } } />
                  <div style={ { marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' } }>
                    <button onClick={ handleBulkCreate } disabled={ creating || !bulkJson.trim() }
                      style={ { padding: '10px 24px', background: '#d1f470', color: '#1a3a2a', border: 'none', borderRadius: 10, cursor: 'pointer', fontWeight: 600, fontSize: 14, opacity: creating || !bulkJson.trim() ? 0.5 : 1 } }>
                      { creating ? 'Creating...' : 'Bulk Create' }
                    </button>
                  </div>
                </div>
              ) }

              {/* Result */ }
              { createResult && (
                <div style={ { marginTop: 16, background: createResult.success ? '#f9fafb' : '#f3f4f6', border: `1px solid ${createResult.success ? '#e5e7eb' : '#e5e7eb'}`, borderRadius: 12, padding: 16 } }>
                  <div style={ { fontWeight: 600, fontSize: 14, color: createResult.success ? '#1a3a2a' : '#6b7280', marginBottom: 8 } }>
                    { createResult.success ? ( createResult.bulk ? `Bulk: ${createResult.succeeded}/${createResult.total} created` : 'Product Created' ) : 'Error' }
                  </div>
                  <pre style={ { fontSize: 12, margin: 0, whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto', color: '#374151' } }>
                    { JSON.stringify( createResult, null, 2 ) }
                  </pre>
                </div>
              ) }
            </div>
          ) }

          {/* ---- STORE ADMIN TAB ---- */ }
          { activeTab === 'admin' && (
            <div style={ { maxWidth: 900 } }>
              {/* Site Overview */ }
              <div style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 16 } }>
                <div style={ { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } }>
                  <h3 style={ { margin: 0, fontSize: 16, fontWeight: 600 } }>Wix Site</h3>
                  <a href="https://manage.wix.com/dashboard/c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5" target="_blank" rel="noopener noreferrer"
                    style={ { fontSize: 12, color: '#1a3a2a', textDecoration: 'none', padding: '4px 12px', border: '1px solid #f3f4f6', borderRadius: 8 } }>
                    Open Wix Dashboard →
                  </a>
                </div>
                <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 } }>
                  <div style={ adminCard }><span style={ adminLabel }>Site Name</span><span style={ adminVal }>WECARE.DIGITAL</span></div>
                  <div style={ adminCard }><span style={ adminLabel }>Site ID</span><span style={ { ...adminVal, fontSize: 11, fontFamily: 'monospace' } }>c17b0e20-d96d</span></div>
                  <div style={ adminCard }><span style={ adminLabel }>URL</span><a href="https://www.wecare.digital" target="_blank" rel="noopener noreferrer" style={ { ...adminVal, color: '#1a3a2a', textDecoration: 'none' } }>wecare.digital</a></div>
                  <div style={ adminCard }><span style={ adminLabel }>Status</span><span style={ { ...adminVal, color: '#1a3a2a' } }>Published</span></div>
                  <div style={ adminCard }><span style={ adminLabel }>Currency</span><span style={ adminVal }>INR (₹)</span></div>
                  <div style={ adminCard }><span style={ adminLabel }>Conv. Fee</span><span style={ adminVal }>2% + 18% GST</span></div>
                </div>
              </div>

              {/* Velo Code Files */ }
              <div style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 16 } }>
                <div style={ { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } }>
                  <h3 style={ { margin: 0, fontSize: 16, fontWeight: 600 } }>Velo Code Files</h3>
                  <a href="https://editor.wix.com/html/editor/web/renderer/edit/c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5" target="_blank" rel="noopener noreferrer"
                    style={ { fontSize: 12, color: '#1a3a2a', textDecoration: 'none', padding: '4px 12px', border: '1px solid #f3f4f6', borderRadius: 8 } }>
                    Open in Wix Editor →
                  </a>
                </div>

                {/* Backend Files */ }
                <div style={ { marginBottom: 16 } }>
                  <div style={ { fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 } }>Backend</div>
                  <div style={ { display: 'flex', flexDirection: 'column', gap: 6 } }>
                    { [
                      { name: 'orderId.web.js', desc: 'Custom order ID (WD prefix)', type: 'web-module', status: 'active' },
                      { name: 'convenience-fee.js', desc: 'Checkout convenience fee (2.2% + 18% GST)', type: 'backend', status: 'active' },
                      { name: 'pinger.js', desc: 'SEO + Store API health checks', type: 'backend', status: 'active' },
                      { name: 'sku-batch.web.js', desc: 'Batch SKU ops (dryRun, prefix)', type: 'web-module', status: 'active' },
                      { name: 'events.js', desc: 'Auto SKU on product create', type: 'events', status: 'active' },
                      { name: 'http-functions.js', desc: 'SEO + AI + Store API (merged)', type: 'http', status: 'active' },
                      { name: 'jobs.config', desc: 'Scheduled jobs configuration', type: 'config', status: 'active' },
                    ].map( f => (
                      <div key={ f.name } style={ { display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', background: '#f9fafb', borderRadius: 8 } }>
                        <span style={ { fontSize: 16, width: 24, textAlign: 'center' } }>
                          { f.type === 'web-module' ? 'Plug' : f.type === 'events' ? 'Evt' : f.type === 'http' ? 'API' : f.type === 'config' ? 'Cfg' : 'File' }
                        </span>
                        <div style={ { flex: 1 } }>
                          <div style={ { fontWeight: 500, fontSize: 13, fontFamily: 'monospace' } }>{ f.name }</div>
                          <div style={ { fontSize: 11, color: '#6b7280' } }>{ f.desc }</div>
                        </div>
                        <span style={ {
                          fontSize: 10, padding: '2px 8px', borderRadius: 10, fontWeight: 500,
                          background: f.status === 'active' ? '#f3f4f6' : '#f9fafb',
                          color: f.status === 'active' ? '#1a3a2a' : '#1a3a2a',
                        } }>
                          { f.status === 'active' ? 'Active' : 'Pending Merge' }
                        </span>
                      </div>
                    ) ) }
                  </div>
                </div>

                {/* Public Files */ }
                <div style={ { marginBottom: 16 } }>
                  <div style={ { fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 } }>Public</div>
                  <div style={ { display: 'flex', flexDirection: 'column', gap: 6 } }>
                    { [
                      { name: 'global-apply.js', desc: 'Global site-level code (runs on every page)' },
                      { name: 'ops-lite.js', desc: 'Operations / utility functions' },
                      { name: 'seo-bridge.js', desc: 'SEO meta tags & structured data' },
                      { name: 'site-hygiene.js', desc: 'Site maintenance & cleanup' },
                    ].map( f => (
                      <div key={ f.name } style={ { display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', background: '#f9fafb', borderRadius: 8 } }>
                        <span style={ { fontSize: 16, width: 24, textAlign: 'center', color: '#1a3a2a' } }>File</span>
                        <div style={ { flex: 1 } }>
                          <div style={ { fontWeight: 500, fontSize: 13, fontFamily: 'monospace' } }>{ f.name }</div>
                          <div style={ { fontSize: 11, color: '#6b7280' } }>{ f.desc }</div>
                        </div>
                        <span style={ { fontSize: 10, padding: '2px 8px', borderRadius: 10, fontWeight: 500, background: '#f3f4f6', color: '#1a3a2a' } }>Active</span>
                      </div>
                    ) ) }
                  </div>
                </div>

                {/* Service Plugins */ }
                <div>
                  <div style={ { fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 } }>Service Plugins</div>
                  <div style={ { display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', background: '#f9fafb', borderRadius: 8 } }>
                    <span style={ { fontSize: 16, width: 24, textAlign: 'center', color: '#1a3a2a' } }>Ext</span>
                    <div style={ { flex: 1 } }>
                      <div style={ { fontWeight: 500, fontSize: 13, fontFamily: 'monospace' } }>automations-velo-action-provider</div>
                      <div style={ { fontSize: 11, color: '#6b7280' } }>Custom automation actions for Wix Automations</div>
                    </div>
                    <span style={ { fontSize: 10, padding: '2px 8px', borderRadius: 10, fontWeight: 500, background: '#f3f4f6', color: '#1a3a2a' } }>Active</span>
                  </div>
                </div>
              </div>

              {/* Quick Actions */ }
              <div style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 16 } }>
                <h3 style={ { margin: '0 0 12px', fontSize: 16, fontWeight: 600 } }>Quick Actions</h3>
                <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 } }>
                  <a href="https://manage.wix.com/dashboard/c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5/store/products" target="_blank" rel="noopener noreferrer" style={ actionBtn }>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></svg>
                    <div><div style={ { fontWeight: 500, fontSize: 13 } }>Manage Products</div><div style={ { fontSize: 11, color: '#6b7280' } }>Wix Dashboard</div></div>
                  </a>
                  <a href="https://manage.wix.com/dashboard/c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5/store/orders" target="_blank" rel="noopener noreferrer" style={ actionBtn }>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>
                    <div><div style={ { fontWeight: 500, fontSize: 13 } }>Manage Orders</div><div style={ { fontSize: 11, color: '#6b7280' } }>Wix Dashboard</div></div>
                  </a>
                  <a href="https://manage.wix.com/dashboard/c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5/store/inventory" target="_blank" rel="noopener noreferrer" style={ actionBtn }>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>
                    <div><div style={ { fontWeight: 500, fontSize: 13 } }>Inventory</div><div style={ { fontSize: 11, color: '#6b7280' } }>Wix Dashboard</div></div>
                  </a>
                  <a href="https://manage.wix.com/dashboard/c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5/store/coupons" target="_blank" rel="noopener noreferrer" style={ actionBtn }>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" /><line x1="7" y1="7" x2="7.01" y2="7" /></svg>
                    <div><div style={ { fontWeight: 500, fontSize: 13 } }>Coupons</div><div style={ { fontSize: 11, color: '#6b7280' } }>Wix Dashboard</div></div>
                  </a>
                  <a href="https://manage.wix.com/dashboard/c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5/analytics" target="_blank" rel="noopener noreferrer" style={ actionBtn }>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="20" x2="12" y2="10" /><polyline points="18 20 12 10 6 20" /><polyline points="4 14 12 6 20 14" /></svg>
                    <div><div style={ { fontWeight: 500, fontSize: 13 } }>Analytics</div><div style={ { fontSize: 11, color: '#6b7280' } }>Wix Dashboard</div></div>
                  </a>
                  <a href="https://manage.wix.com/dashboard/c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5/developer-tools/secrets-manager" target="_blank" rel="noopener noreferrer" style={ actionBtn }>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" /></svg>
                    <div><div style={ { fontWeight: 500, fontSize: 13 } }>Secrets Manager</div><div style={ { fontSize: 11, color: '#6b7280' } }>API Keys & Secrets</div></div>
                  </a>
                </div>
              </div>

              {/* Git Integration Info */ }
              <div style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 } }>
                <h3 style={ { margin: '0 0 8px', fontSize: 16, fontWeight: 600 } }>Git Integration</h3>
                <p style={ { fontSize: 13, color: '#6b7280', margin: '0 0 12px' } }>
                  Velo code is managed in <code>store/src/</code> — sync with Wix via GitHub integration.
                </p>
                <div style={ { fontSize: 13, background: '#f9fafb', padding: 12, borderRadius: 8, fontFamily: 'monospace', lineHeight: 1.8 } }>
                  <span style={ { color: '#6b7280' } }># Pull code from Wix</span><br />
                  cd wix-store<br />
                  wix login<br />
                  wix dev<br /><br />
                  <span style={ { color: '#6b7280' } }># Push changes to Wix</span><br />
                  git add -A<br />
                  git commit -m "Update Velo code"<br />
                  git push
                </div>
              </div>
            </div>
          ) }

          {/* ---- SETTINGS TAB ---- */ }
          { activeTab === 'settings' && (
            <div style={ { maxWidth: 700 } }>
              <div style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 16 } }>
                <h3 style={ { margin: '0 0 12px', fontSize: 16, fontWeight: 600 } }>Connected Wix Sites</h3>
                { loading ? (
                  <Spinner size="md" />
                ) : sites.length === 0 ? (
                  <p style={ { color: '#6b7280', fontSize: 14 } }>No sites found. Check your WIX_API_KEY and WIX_ACCOUNT_ID configuration.</p>
                ) : (
                  <div style={ { display: 'flex', flexDirection: 'column', gap: 12 } }>
                    { sites.map( ( s: any ) => (
                      <div key={ s.id } style={ { display: 'flex', alignItems: 'center', gap: 12, padding: 12, background: '#f9fafb', borderRadius: 8 } }>
                        { s.thumbnail && <img src={ s.thumbnail } alt={ s.displayName } style={ { width: 48, height: 36, borderRadius: 6, objectFit: 'cover' } } /> }
                        <div style={ { flex: 1 } }>
                          <div style={ { fontWeight: 500 } }>{ s.displayName }</div>
                          <div style={ { fontSize: 12, color: '#6b7280' } }>ID: { s.id }</div>
                        </div>
                        <span style={ { fontSize: 11, padding: '2px 8px', borderRadius: 12, background: s.published ? '#f3f4f6' : '#f9fafb', color: s.published ? '#1a3a2a' : '#1a3a2a' } }>
                          { s.published ? 'Published' : 'Draft' }
                        </span>
                        { s.viewUrl && (
                          <a href={ s.viewUrl } target="_blank" rel="noopener noreferrer" style={ { fontSize: 12, color: '#1a3a2a' } }>Visit →</a>
                        ) }
                      </div>
                    ) ) }
                  </div>
                ) }
              </div>
              <div style={ { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 } }>
                <h3 style={ { margin: '0 0 8px', fontSize: 16, fontWeight: 600 } }>Integration Mode</h3>
                <p style={ { fontSize: 13, color: '#6b7280', margin: '0 0 12px' } }>
                  Configure in <code>amplify/functions/ecommerce/wix-store/resource.ts</code>
                </p>
                <div style={ { fontSize: 13, background: '#f9fafb', padding: 12, borderRadius: 8, fontFamily: 'monospace' } }>
                  WIX_MODE = "api" | "velo"<br />
                  WIX_API_KEY = IST.eyJ...<br />
                  WIX_SITE_ID = (from sites list above)<br />
                  WIX_VELO_BASE_URL = https://www.yoursite.com
                </div>
              </div>
            </div>
          ) }
        </div>

        {/* ---- PRODUCT DETAIL MODAL ---- */ }
        <Modal isOpen={ !!selectedProduct } onClose={ () => setSelectedProduct( null ) } title={ selectedProduct?.name || 'Product Detail' } size="lg">
          { selectedProduct && (
            <div style={ { display: 'flex', flexDirection: 'column', gap: 16 } }>
              <div style={ { display: 'flex', gap: 16 } }>
                { selectedProduct.mainMedia?.url && (
                  <img src={ selectedProduct.mainMedia.url } alt={ selectedProduct.name } style={ { width: 160, height: 160, objectFit: 'cover', borderRadius: 12 } } />
                ) }
                <div style={ { flex: 1 } }>
                  <h3 style={ { margin: 0 } }>{ selectedProduct.name }</h3>
                  <p style={ { color: '#6b7280', fontSize: 14, margin: '4px 0' } }>{ selectedProduct.description }</p>
                  <div style={ { display: 'flex', gap: 16, marginTop: 8 } }>
                    <div><span style={ { fontSize: 12, color: '#6b7280' } }>Price</span><br /><span style={ { fontWeight: 600, fontSize: 18 } }>{ selectedProduct.formattedPrice || `₹${selectedProduct.price}` }</span></div>
                    <div><span style={ { fontSize: 12, color: '#6b7280' } }>SKU</span><br /><span style={ { fontWeight: 500 } }>{ selectedProduct.sku || '—' }</span></div>
                    <div><span style={ { fontSize: 12, color: '#6b7280' } }>Stock</span><br /><span style={ { fontWeight: 500, color: selectedProduct.inStock ? '#1a3a2a' : '#1a3a2a' } }>{ selectedProduct.inStock ? `${selectedProduct.quantityInStock ?? 'Yes'}` : 'Out' }</span></div>
                    <div><span style={ { fontSize: 12, color: '#6b7280' } }>Type</span><br /><span style={ { fontWeight: 500, textTransform: 'capitalize' } }>{ selectedProduct.productType }</span></div>
                  </div>
                </div>
              </div>
              { selectedProduct.collections?.length > 0 && (
                <div>
                  <span style={ { fontSize: 12, color: '#6b7280' } }>Collections</span>
                  <div style={ { display: 'flex', gap: 6, marginTop: 4 } }>
                    { selectedProduct.collections.map( c => (
                      <span key={ c._id } style={ { background: '#f9fafb', color: '#1a3a2a', padding: '3px 10px', borderRadius: 12, fontSize: 12 } }>{ c.name }</span>
                    ) ) }
                  </div>
                </div>
              ) }
              { selectedProduct.productOptions?.length > 0 && (
                <div>
                  <span style={ { fontSize: 12, color: '#6b7280' } }>Options</span>
                  <div style={ { marginTop: 4 } }>
                    { selectedProduct.productOptions.map( ( opt: any, i: number ) => (
                      <div key={ i } style={ { fontSize: 13 } }>{ opt.name }: { ( opt.choices || [] ).map( ( c: any ) => c.description || c.value ).join( ', ' ) }</div>
                    ) ) }
                  </div>
                </div>
              ) }
              { selectedProduct.variants?.length > 1 && (
                <div>
                  <span style={ { fontSize: 12, color: '#6b7280' } }>Variants ({ selectedProduct.variants.length })</span>
                  <div style={ { marginTop: 4, maxHeight: 200, overflowY: 'auto' } }>
                    { selectedProduct.variants.map( ( v: any, i: number ) => (
                      <div key={ i } style={ { display: 'flex', gap: 12, padding: '6px 0', borderBottom: '1px solid #f3f4f6', fontSize: 13 } }>
                        <span style={ { flex: 1 } }>{ Object.values( v.choices || {} ).join( ' / ' ) || `Variant ${i + 1}` }</span>
                        <span style={ { fontWeight: 500 } }>{ v.variant?.priceData?.formatted?.price || '—' }</span>
                        <span style={ { color: '#6b7280' } }>SKU: { v.variant?.sku || '—' }</span>
                      </div>
                    ) ) }
                  </div>
                </div>
              ) }
            </div>
          ) }
        </Modal>

        {/* ---- ORDER DETAIL MODAL ---- */ }
        <Modal isOpen={ !!selectedOrder } onClose={ () => setSelectedOrder( null ) } title={ `Order ${selectedOrder?.customOrderNumber || selectedOrder?._summary?.customOrderNumber || selectedOrder?.customField?.value || selectedOrder?._summary?.externalOrderId || '#' + ( selectedOrder?.number || '—' )}` } size="lg">
          { selectedOrder && ( () => {
            const s = selectedOrder._summary || {};
            const buyerEmail = ( selectedOrder as any ).buyerEmail || s.buyerEmail || selectedOrder.buyerInfo?.email || '';
            const buyerName = ( selectedOrder as any ).buyerName || s.billingName || '';
            const buyerPhone = ( selectedOrder as any ).buyerPhone || s.billingPhone || '';
            const total = selectedOrder.totals?.total || s.totalAmount || '0';
            const currency = selectedOrder.currency || s.currency || 'INR';
            const customNum = selectedOrder.customOrderNumber || s.customOrderNumber || selectedOrder.customField?.value || s.externalOrderId || '';
            const items = ( selectedOrder as any ).lineItemsSummary || s.lineItems || selectedOrder.lineItems || [];

            return (
              <div style={ { display: 'flex', flexDirection: 'column', gap: 16 } }>
                {/* Order summary */ }
                <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 } }>
                  <div style={ statBox }><span style={ statLabel }>Order ID</span><span style={ statValue }>{ customNum || `#${selectedOrder.number || s.orderNumber || '—'}` }</span></div>
                  <div style={ statBox }><span style={ statLabel }>Total</span><span style={ statValue }>{ currency === 'INR' ? '₹' : currency + ' ' }{ total }</span></div>
                  <div style={ statBox }><span style={ statLabel }>Payment</span><span style={ { ...statValue, color: ( selectedOrder.paymentStatus || s.paymentStatus ) === 'PAID' ? '#1a3a2a' : '#1a3a2a' } }>{ ( selectedOrder.paymentStatus || s.paymentStatus || '' ).replace( /_/g, ' ' ) }</span></div>
                  <div style={ statBox }><span style={ statLabel }>Fulfillment</span><span style={ statValue }>{ ( selectedOrder.fulfillmentStatus || s.fulfillmentStatus || '—' ).replace( /_/g, ' ' ) }</span></div>
                  <div style={ statBox }><span style={ statLabel }>Date</span><span style={ statValue }>{ new Date( selectedOrder.dateCreated || ( selectedOrder as any ).createdDate || s.createdDate || '' ).toLocaleDateString( 'en-IN' ) }</span></div>
                </div>

                {/* Buyer info */ }
                <div style={ { background: '#f9fafb', borderRadius: 8, padding: 12 } }>
                  <span style={ { fontSize: 12, color: '#6b7280', fontWeight: 600 } }>Buyer</span>
                  <div style={ { marginTop: 4, fontSize: 14 } }>
                    { buyerName && <div>{ buyerName }</div> }
                    { buyerEmail && <div style={ { color: '#6b7280' } }>{ buyerEmail }</div> }
                    { buyerPhone && <div style={ { color: '#6b7280' } }>{ buyerPhone }</div> }
                  </div>
                  { selectedOrder.buyerNote && <div style={ { marginTop: 8, fontSize: 13, fontStyle: 'italic', color: '#6b7280' } }>Note: { selectedOrder.buyerNote }</div> }
                </div>

                {/* Line items */ }
                <div>
                  <span style={ { fontSize: 12, color: '#6b7280', fontWeight: 600 } }>Line Items ({ items.length })</span>
                  <div style={ { marginTop: 8 } }>
                    { items.map( ( item: any, i: number ) => (
                      <div key={ i } style={ { display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid #f3f4f6' } }>
                        { ( item.image?.url || item.mediaItem?.url ) && (
                          <img src={ item.image?.url || item.mediaItem?.url } alt={ item.name } style={ { width: 36, height: 36, borderRadius: 6, objectFit: 'cover' } } />
                        ) }
                        <div style={ { flex: 1 } }>
                          <div style={ { fontWeight: 500, fontSize: 14 } }>{ item.name || item.productName }</div>
                          { item.sku && <div style={ { fontSize: 11, color: '#6b7280' } }>SKU: { item.sku }</div> }
                        </div>
                        <span style={ { fontSize: 13, color: '#6b7280' } }>×{ item.quantity }</span>
                        <span style={ { fontWeight: 500, fontSize: 14 } }>{ currency === 'INR' ? '₹' : '' }{ item.price || item.totalPrice || '0' }</span>
                      </div>
                    ) ) }
                  </div>
                </div>

                {/* Transactions & Fulfillments */ }
                { selectedOrder._transactions && (
                  <div>
                    <span style={ { fontSize: 12, color: '#6b7280', fontWeight: 600 } }>Transactions</span>
                    <pre style={ { background: '#f9fafb', padding: 12, borderRadius: 8, fontSize: 12, overflow: 'auto', maxHeight: 150 } }>
                      { JSON.stringify( selectedOrder._transactions, null, 2 ) }
                    </pre>
                  </div>
                ) }
                { selectedOrder._fulfillments && Array.isArray( selectedOrder._fulfillments ) && selectedOrder._fulfillments.length > 0 && (
                  <div>
                    <span style={ { fontSize: 12, color: '#6b7280', fontWeight: 600 } }>Fulfillments</span>
                    <pre style={ { background: '#f9fafb', padding: 12, borderRadius: 8, fontSize: 12, overflow: 'auto', maxHeight: 150 } }>
                      { JSON.stringify( selectedOrder._fulfillments, null, 2 ) }
                    </pre>
                  </div>
                ) }
              </div>
            );
          } )() }
        </Modal>
      </div>
    </Layout>
  );
};

const statBox: React.CSSProperties = { background: '#f9fafb', borderRadius: 8, padding: '10px 12px' };
const statLabel: React.CSSProperties = { fontSize: 11, color: '#6b7280', display: 'block' };
const statValue: React.CSSProperties = { fontSize: 15, fontWeight: 600, display: 'block', marginTop: 2 };
const adminCard: React.CSSProperties = { background: '#f9fafb', borderRadius: 8, padding: '10px 12px' };
const adminLabel: React.CSSProperties = { fontSize: 11, color: '#6b7280', display: 'block' };
const adminVal: React.CSSProperties = { fontSize: 14, fontWeight: 600, display: 'block', marginTop: 2 };
const actionBtn: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', background: '#f9fafb', borderRadius: 10, textDecoration: 'none', color: 'inherit', border: '1px solid #e5e7eb', transition: 'background 0.15s' };

export default StorePage;
