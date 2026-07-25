/**
 * Wix Velo HTTP Functions — WECARE.DIGITAL Store API
 *
 * Exposes store data via /_functions/* endpoints so the AWS Lambda
 * (handler.py in velo mode) can query products, orders, collections
 * and inventory through the published Wix site.
 *
 * Endpoints served (Velo maps get_<name> → GET /_functions/<name>):
 *   GET /_functions/products?limit=&search=&collectionId=
 *   GET /_functions/product?id=
 *   GET /_functions/orders?limit=&status=&email=&customOrderNumber=&memberId=
 *   GET /_functions/order?id=
 *   GET /_functions/member-orders?memberId=&limit=
 *   GET /_functions/collections?limit=
 *   GET /_functions/inventory?productId=
 *   GET /_functions/inventory-all?limit=
 *   GET /_functions/health
 *
 * IMPORTANT: Velo converts function names to kebab-case URLs.
 *   get_inventoryAll  → /_functions/inventory-all  ✓
 *   get_inventory_all → /_functions/inventory_all  ✗ (underscore, not hyphen)
 *
 * Auth: Optional X-Api-Key header checked against Secrets Manager.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-http-functions
 */

import { ok, notFound, forbidden, response as rawResponse } from 'wix-http-functions';
import wixData from 'wix-data';
import { getSecret } from 'wix-secrets-backend';

// ---------------------------------------------------------------------------
// Auth helper — caches secret for the lifetime of the backend instance
// ---------------------------------------------------------------------------

let _cachedSecret = undefined;

async function authenticate ( request )
{
  try
  {
    if ( _cachedSecret === undefined )
    {
      _cachedSecret = await getSecret( 'WECARE_API_KEY' ).catch( () => null );
    }
    if ( !_cachedSecret ) return true; // no secret configured = open
    const provided = request.headers[ 'x-api-key' ];
    return provided === _cachedSecret;
  } catch
  {
    return true;
  }
}

// ---------------------------------------------------------------------------
// CORS — reflect allowed origins instead of wildcard
// ---------------------------------------------------------------------------
const ALLOWED_ORIGINS = [
  'https://stack.wecare.digital',
  'https://wecare.digital',
  'https://app.wecare.digital',
];

function getAllowedOrigin ( request )
{
  const origin = request.headers?.origin || '';
  return ALLOWED_ORIGINS.includes( origin ) ? origin : ALLOWED_ORIGINS[ 0 ];
}

function jsonOk ( body, request )
{
  return ok( {
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': request ? getAllowedOrigin( request ) : ALLOWED_ORIGINS[ 0 ],
    },
    body: JSON.stringify( body ),
  } );
}

function jsonError ( body, statusCode = 500, request )
{
  return rawResponse( {
    status: statusCode,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': request ? getAllowedOrigin( request ) : ALLOWED_ORIGINS[ 0 ],
    },
    body: JSON.stringify( body ),
  } );
}

function jsonForbidden ( request )
{
  return forbidden( {
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': request ? getAllowedOrigin( request ) : ALLOWED_ORIGINS[ 0 ],
    },
    body: JSON.stringify( { error: 'Unauthorized' } ),
  } );
}

function jsonNotFound ( body, request )
{
  return notFound( {
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': request ? getAllowedOrigin( request ) : ALLOWED_ORIGINS[ 0 ],
    },
    body: JSON.stringify( body ),
  } );
}

// ---------------------------------------------------------------------------
// Shared: enrich orders with custom order number from OrderCustomIds
// ---------------------------------------------------------------------------

async function enrichOrderWithCustomId ( order )
{
  if ( !order?._id ) return order;
  try
  {
    const customId = await wixData.query( 'OrderCustomIds' )
      .eq( 'orderId', order._id )
      .limit( 1 )
      .find( { suppressAuth: true } );
    if ( customId.items.length > 0 )
    {
      order.customOrderNumber = customId.items[ 0 ].customOrderNumber;
    }
  } catch { /* OrderCustomIds collection may not exist yet */ }
  return order;
}

// ---------------------------------------------------------------------------
// GET /_functions/products
// ---------------------------------------------------------------------------

export async function get_products ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const { limit = '100', search = '', collectionId = '' } = request.query;
    const parsedLimit = Math.min( parseInt( limit, 10 ) || 100, 1000 );

    let query = wixData.query( 'Stores/Products' ).limit( parsedLimit );

    if ( search )
    {
      query = query.contains( 'name', search );
    }
    if ( collectionId )
    {
      query = query.hasSome( 'collections._id', [ collectionId ] );
    }

    const result = await query.find( { suppressAuth: true } );

    return jsonOk( {
      products: result.items,
      totalResults: result.totalCount,
    } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// GET /_functions/product?id=
// ---------------------------------------------------------------------------

export async function get_product ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const { id } = request.query;
    if ( !id ) return jsonNotFound( { error: 'Missing id parameter' } );

    const product = await wixData.get( 'Stores/Products', id, { suppressAuth: true } );
    if ( !product ) return jsonNotFound( { error: 'Product not found' } );

    // Fetch inventory for this product
    let inventory = null;
    try
    {
      const invResult = await wixData.query( 'Stores/InventoryItems' )
        .eq( 'productId', id )
        .find( { suppressAuth: true } );
      inventory = invResult.items;
    } catch { /* inventory collection may not exist */ }

    return jsonOk( {
      product: { ...product, _inventory: inventory },
    } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// GET /_functions/orders
// ---------------------------------------------------------------------------

export async function get_orders ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const { limit = '50', status = '', email = '', customOrderNumber = '', memberId = '' } = request.query;
    const parsedLimit = Math.min( parseInt( limit, 10 ) || 50, 500 );

    // If searching by custom order number, look up the real orderId first
    if ( customOrderNumber )
    {
      try
      {
        const mapping = await wixData.query( 'OrderCustomIds' )
          .eq( 'customOrderNumber', customOrderNumber )
          .limit( 1 )
          .find( { suppressAuth: true } );

        if ( mapping.items.length > 0 )
        {
          const order = await wixData.get( 'Stores/Orders', mapping.items[ 0 ].orderId, { suppressAuth: true } );
          if ( order )
          {
            order.customOrderNumber = customOrderNumber;
            // Strip Wix native order number — only WD is used
            delete order.number;
            return jsonOk( { orders: [ order ], totalResults: 1 } );
          }
        }
        return jsonOk( { orders: [], totalResults: 0 } );
      } catch
      {
        return jsonOk( { orders: [], totalResults: 0 } );
      }
    }

    // If searching by memberId, query through OrderCustomIds
    if ( memberId )
    {
      try
      {
        const mappings = await wixData.query( 'OrderCustomIds' )
          .eq( 'memberId', memberId )
          .descending( '_createdDate' )
          .limit( parsedLimit )
          .find( { suppressAuth: true } );

        const orders = [];
        for ( const m of mappings.items )
        {
          try
          {
            const order = await wixData.get( 'Stores/Orders', m.orderId, { suppressAuth: true } );
            if ( order )
            {
              order.customOrderNumber = m.customOrderNumber;
              delete order.number; // Strip Wix native
              orders.push( order );
            }
          } catch { /* skip missing orders */ }
        }
        return jsonOk( { orders, totalResults: mappings.totalCount } );
      } catch
      {
        return jsonOk( { orders: [], totalResults: 0 } );
      }
    }

    let query = wixData.query( 'Stores/Orders' )
      .limit( parsedLimit )
      .descending( '_dateCreated' );

    if ( status )
    {
      query = query.eq( 'paymentStatus', status );
    }
    if ( email )
    {
      query = query.eq( 'buyerEmail', email );
    }

    const result = await query.find( { suppressAuth: true } );

    // Enrich with custom order numbers (batch — limit concurrency)
    const batchSize = 10;
    const enriched = [];
    for ( let i = 0; i < result.items.length; i += batchSize )
    {
      const batch = result.items.slice( i, i + batchSize );
      const enrichedBatch = await Promise.all( batch.map( async ( order ) =>
      {
        await enrichOrderWithCustomId( order );
        delete order.number; // Strip Wix native
        return order;
      } ) );
      enriched.push( ...enrichedBatch );
    }

    return jsonOk( {
      orders: enriched,
      totalResults: result.totalCount,
    } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// GET /_functions/order?id=
// ---------------------------------------------------------------------------

export async function get_order ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const { id } = request.query;
    if ( !id ) return jsonNotFound( { error: 'Missing id parameter' } );

    const order = await wixData.get( 'Stores/Orders', id, { suppressAuth: true } );
    if ( !order ) return jsonNotFound( { error: 'Order not found' } );

    await enrichOrderWithCustomId( order );
    delete order.number; // Strip Wix native order number — only WD is used

    return jsonOk( { order } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// GET /_functions/collections
// ---------------------------------------------------------------------------

export async function get_collections ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const { limit = '100' } = request.query;
    const parsedLimit = Math.min( parseInt( limit, 10 ) || 100, 1000 );

    const result = await wixData.query( 'Stores/Collections' )
      .limit( parsedLimit )
      .find( { suppressAuth: true } );

    return jsonOk( {
      collections: result.items,
      totalResults: result.totalCount,
    } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// GET /_functions/inventory?productId=
// ---------------------------------------------------------------------------

export async function get_inventory ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const { productId } = request.query;
    if ( !productId ) return jsonNotFound( { error: 'Missing productId parameter' } );

    const result = await wixData.query( 'Stores/InventoryItems' )
      .eq( 'productId', productId )
      .find( { suppressAuth: true } );

    return jsonOk( {
      productId,
      inventoryItems: result.items,
    } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// GET /_functions/inventory-all
// Velo maps get_inventoryAll → /_functions/inventory-all (camelCase → kebab)
// ---------------------------------------------------------------------------

export async function get_inventoryAll ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const { limit = '100' } = request.query;
    const parsedLimit = Math.min( parseInt( limit, 10 ) || 100, 1000 );

    const result = await wixData.query( 'Stores/InventoryItems' )
      .limit( parsedLimit )
      .find( { suppressAuth: true } );

    return jsonOk( {
      inventoryItems: result.items,
      totalResults: result.totalCount,
    } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// GET /_functions/health
// ---------------------------------------------------------------------------

export async function get_health ( _request )
{
  // Health endpoint is open — no auth required
  let productCount = 0;
  try
  {
    productCount = await wixData.query( 'Stores/Products' ).count( { suppressAuth: true } );
  } catch { /* ignore */ }

  return jsonOk( {
    status: 'ok',
    service: 'wecare-digital-velo',
    productCount,
    timestamp: new Date().toISOString(),
  } );
}

// ---------------------------------------------------------------------------
// POST /_functions/create-product
// Body: { product: { name, description, priceData, sku, ... } }
// ---------------------------------------------------------------------------

export async function post_createProduct ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const body = await request.body.json();
    const productData = body.product;
    if ( !productData || !productData.name )
    {
      return jsonError( { error: 'Missing product.name' }, 400 );
    }

    const { createProduct } = await import( './product-manager.web' );
    const result = await createProduct( productData );

    if ( !result.success )
    {
      return jsonError( { error: result.error }, 400 );
    }

    return jsonOk( { product: result.product, created: true } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// POST /_functions/bulk-create-products
// Body: { products: [ { name, description, priceData, sku, ... }, ... ] }
// ---------------------------------------------------------------------------

export async function post_bulkCreateProducts ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const body = await request.body.json();
    const productsArray = body.products;
    if ( !Array.isArray( productsArray ) || productsArray.length === 0 )
    {
      return jsonError( { error: 'Missing or empty products array' }, 400 );
    }

    const { bulkCreateProducts } = await import( './product-manager.web' );
    const result = await bulkCreateProducts( productsArray );

    return jsonOk( result );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// POST /_functions/update-product
// Body: { productId: "...", updates: { name, description, ... } }
// ---------------------------------------------------------------------------

export async function post_updateProduct ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const body = await request.body.json();
    if ( !body.productId )
    {
      return jsonError( { error: 'Missing productId' }, 400 );
    }

    const { updateProduct } = await import( './product-manager.web' );
    const result = await updateProduct( body.productId, body.updates || {} );

    if ( !result.success )
    {
      return jsonError( { error: result.error }, 400 );
    }

    return jsonOk( { product: result.product, updated: true } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// POST /_functions/delete-product
// Body: { productId: "..." }
// ---------------------------------------------------------------------------

export async function post_deleteProduct ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const body = await request.body.json();
    if ( !body.productId )
    {
      return jsonError( { error: 'Missing productId' }, 400 );
    }

    const { deleteProduct } = await import( './product-manager.web' );
    const result = await deleteProduct( body.productId );

    if ( !result.success )
    {
      return jsonError( { error: result.error }, 400 );
    }

    return jsonOk( { deleted: true } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// GET /_functions/sample-products
// Returns BNB CLUB sample product templates
// ---------------------------------------------------------------------------

export async function get_sampleProducts ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const { getSampleProducts } = await import( './product-manager.web' );
    const samples = await getSampleProducts();
    return jsonOk( samples );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// POST /_functions/reprefix-skus
// Body: { oldPrefix: "OLDPREFIX", newPrefix: "WD", dryRun: true }
// Re-prefixes all product SKUs from oldPrefix to newPrefix.
// Use dryRun: true first to preview, then dryRun: false to commit.
// ---------------------------------------------------------------------------

export async function post_reprefixSkus ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const body = await request.body.json();
    const { reprefixSKUs } = await import( './sku-batch.web' );
    const result = await reprefixSKUs( {
      oldPrefix: body.oldPrefix || '',
      newPrefix: body.newPrefix || 'WD',
      dryRun: body.dryRun !== false,
    } );
    return jsonOk( result );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// POST /_functions/assign-skus
// Body: { prefix: "WD", dryRun: true }
// Assigns WD-prefixed SKUs to all products missing one.
// ---------------------------------------------------------------------------

export async function post_assignSkus ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const body = await request.body.json();
    const { assignMissingSKUs } = await import( './sku-batch.web' );
    const result = await assignMissingSKUs( {
      prefix: body.prefix || 'WD',
      dryRun: body.dryRun !== false,
    } );
    return jsonOk( result );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// POST /_functions/backfill-order-custom-fields
// Reads OrderCustomIds collection and sets customField on each Wix order
// so the WD-ORD number appears in Wix native order views (Owner App, emails).
// ---------------------------------------------------------------------------

export async function post_backfillOrderCustomFields ( request )
{
  if ( !( await authenticate( request ) ) ) return jsonForbidden();

  try
  {
    const allMappings = await wixData.query( 'OrderCustomIds' )
      .limit( 100 )
      .find( { suppressAuth: true } );

    let updated = 0;
    let skipped = 0;
    let errors = [];

    for ( const mapping of allMappings.items )
    {
      const { orderId, customOrderNumber } = mapping;
      if ( !orderId || !customOrderNumber ) { skipped++; continue; }

      try
      {
        const order = await wixData.get( 'Stores/Orders', orderId, { suppressAuth: true } );
        if ( !order ) { skipped++; continue; }

        // Skip if customField already has the correct WD number
        if ( order.customField?.value === customOrderNumber ) { skipped++; continue; }

        await wixData.update( 'Stores/Orders', {
          ...order,
          customField: {
            title: 'Order ID',
            value: customOrderNumber,
          },
        }, { suppressAuth: true } );
        updated++;
      } catch ( err )
      {
        errors.push( { orderId, error: err.message } );
      }
    }

    return jsonOk( { updated, skipped, errors: errors.slice( 0, 10 ), total: allMappings.items.length } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}


// ---------------------------------------------------------------------------
// POST /_functions/flow-orders
// WhatsApp Flow data endpoint — returns WD-ORD IDs for a phone/email.
// Flow sends: { phone: "+91...", email: "..." }
// Returns: { orders: [{ id: "WD-ORD - ...", label: "WD-ORD - ..." }] }
// ---------------------------------------------------------------------------

export async function post_flowOrders ( request )
{
  // Auth via shared secret header
  try
  {
    if ( _cachedSecret === undefined )
    {
      _cachedSecret = await getSecret( 'WECARE_API_KEY' ).catch( () => null );
    }
    if ( _cachedSecret )
    {
      const provided = request.headers[ 'x-api-key' ] || request.headers[ 'x-flow-secret' ];
      if ( provided !== _cachedSecret ) return jsonForbidden();
    }
  } catch { }

  try
  {
    const body = await request.body.json();
    const phone = ( body.phone || '' ).trim();
    const email = ( body.email || '' ).trim();

    if ( !phone && !email )
    {
      return jsonError( { error: 'phone or email required' }, 400 );
    }

    // Query OrderCustomIds by email first, then by phone via Stores/Orders
    let orders = [];

    if ( email )
    {
      const res = await wixData.query( 'OrderCustomIds' )
        .eq( 'buyerEmail', email )
        .descending( '_createdDate' )
        .limit( 50 )
        .find( { suppressAuth: true } );
      orders = res.items.map( item => ( {
        id: item.customOrderNumber,
        label: item.customOrderNumber,
      } ) );
    }

    // Fallback: search by phone in Stores/Orders, then map to custom IDs
    if ( orders.length === 0 && phone )
    {
      const ordersRes = await wixData.query( 'Stores/Orders' )
        .eq( 'buyerInfo.phone', phone )
        .descending( '_dateCreated' )
        .limit( 50 )
        .find( { suppressAuth: true } );

      for ( const order of ordersRes.items )
      {
        const wdId = order.customField?.value;
        if ( wdId && wdId.startsWith( 'WD-ORD' ) )
        {
          orders.push( { id: wdId, label: wdId } );
        }
      }
    }

    return jsonOk( { orders } );
  } catch ( err )
  {
    return jsonError( { error: err.message } );
  }
}

// ---------------------------------------------------------------------------
// Order notification Admin bridge. Unlike legacy read endpoints, these fail
// closed when the shared secret is missing or Secrets Manager is unavailable.
// ---------------------------------------------------------------------------
async function authenticateRequired ( request )
{
  try
  {
    if ( _cachedSecret === undefined )
    {
      _cachedSecret = await getSecret( 'WECARE_API_KEY' ).catch( () => null );
    }
    if ( !_cachedSecret ) return false;
    return request.headers?.[ 'x-api-key' ] === _cachedSecret;
  } catch
  {
    return false;
  }
}

export async function get_orderNotifications ( request )
{
  if ( !( await authenticateRequired( request ) ) ) return jsonForbidden( request );
  try
  {
    const limit = Math.min( Math.max( Number( request.query?.limit || 200 ), 1 ), 500 );
    const orderId = String( request.query?.orderId || '' ).trim();
    const status = String( request.query?.status || '' ).toLowerCase();
    let query = wixData.query( 'OrderNotifications' ).descending( '_updatedDate' ).limit( limit );
    if ( orderId ) query = query.eq( 'orderId', orderId );
    const result = await query.find( { suppressAuth: true } );
    let notifications = result.items;
    if ( status && status !== 'all' )
    {
      notifications = notifications.filter( item =>
        [ item.whatsappStatus, item.smsStatus, item.rcsStatus ]
          .some( value => String( value || '' ).toLowerCase() === status ) );
    }
    return jsonOk( { notifications, count: notifications.length }, request );
  } catch ( error )
  {
    return jsonError( { error: error.message }, 500, request );
  }
}

export async function post_orderNotificationStatus ( request )
{
  if ( !( await authenticateRequired( request ) ) ) return jsonForbidden( request );
  try
  {
    const body = await request.body.json();
    const orderId = String( body.orderId || '' ).trim();
    const channel = String( body.channel || '' ).toLowerCase();
    if ( !orderId || ![ 'whatsapp', 'sms' ].includes( channel ) )
    {
      return jsonError( { error: 'orderId and a supported channel are required' }, 400, request );
    }
    const result = await wixData.query( 'OrderNotifications' )
      .eq( 'orderId', orderId ).limit( 1 ).find( { suppressAuth: true } );
    if ( !result.items.length ) return jsonNotFound( { error: 'Order notification not found' }, request );
    const item = result.items[ 0 ];
    const attemptsField = `${ channel }RetryAttempts`;
    const statusField = `${ channel }Status`;
    const messageIdField = `${ channel }MessageId`;
    const errorField = `${ channel }Error`;
    const updated = {
      ...item,
      [ attemptsField ]: Number( item[ attemptsField ] || 0 ) + 1,
      [ statusField ]: String( body.status || 'failed' ),
      [ messageIdField ]: String( body.providerMessageId || '' ),
      [ errorField ]: String( body.error || '' ),
      lastRetryActor: String( body.actor || '' ),
      lastRetryAt: body.attemptedAt ? new Date( body.attemptedAt ) : new Date(),
      updatedAt: new Date(),
    };
    await wixData.update( 'OrderNotifications', updated, { suppressAuth: true } );
    return jsonOk( { ok: true, orderId, channel, attempts: updated[ attemptsField ] }, request );
  } catch ( error )
  {
    return jsonError( { error: error.message }, 500, request );
  }
}
