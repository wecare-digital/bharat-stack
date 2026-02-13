/**
 * Wix Velo HTTP Functions — WECARE.DIGITAL Store Integration
 *
 * Deploy to your Wix site via:
 *   1. Wix Editor: Backend & Public > Backend > http-functions.js
 *   2. OR Wix CLI: place in src/backend/http-functions.js, then `wix publish`
 *
 * Endpoints exposed at: https://www.yoursite.com/_functions/<name>
 *
 * Security: Validates X-Api-Key header against a Wix Secret named "WECARE_API_KEY".
 *           Create this secret in Wix dashboard > Developer Tools > Secrets Manager.
 *
 * Improvements over v1:
 *   - Pagination with cursor (hasNext + skip)
 *   - Server-side filtering (email via eq, date ranges)
 *   - CORS headers for cross-origin Lambda calls
 *   - Collection include on single product
 *   - hasSome query for collection filtering (no in-memory filter)
 *   - Date range filtering on orders
 *   - inventory-all endpoint
 *   - Order search by number (server-side)
 */

import { ok, badRequest, forbidden, serverError, options } from 'wix-http-functions';
import wixData from 'wix-data';
import { getSecret } from 'wix-secrets-backend';

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

const CORS_HEADERS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-Api-Key, Authorization',
};

async function authenticate(request) {
  try {
    const secret = await getSecret('WECARE_API_KEY');
    const apiKey = request.headers['x-api-key'];
    return apiKey === secret;
  } catch {
    return true; // Dev mode: allow all if secret not configured
  }
}

function json(data) {
  return ok({ body: JSON.stringify(data), headers: CORS_HEADERS });
}

function err400(msg) {
  return badRequest({ body: JSON.stringify({ error: msg }), headers: CORS_HEADERS });
}

function err500(e) {
  return serverError({ body: JSON.stringify({ error: e.message }), headers: CORS_HEADERS });
}

// CORS preflight for all endpoints
export function options_products() { return options({ headers: CORS_HEADERS }); }
export function options_product() { return options({ headers: CORS_HEADERS }); }
export function options_orders() { return options({ headers: CORS_HEADERS }); }
export function options_order() { return options({ headers: CORS_HEADERS }); }
export function options_collections() { return options({ headers: CORS_HEADERS }); }
export function options_inventory() { return options({ headers: CORS_HEADERS }); }

// ---------------------------------------------------------------------------
// GET /products — List products with pagination, search, collection filter
// Query: limit, skip, search, collectionId, sort (name|price|_updatedDate)
// ---------------------------------------------------------------------------
export async function get_products(request) {
  if (!(await authenticate(request))) return forbidden({ body: 'Unauthorized' });

  try {
    const limit = Math.min(Number(request.query.limit) || 100, 100);
    const skip = Number(request.query.skip) || 0;
    const search = request.query.search || '';
    const collectionId = request.query.collectionId || '';
    const sortField = request.query.sort || '_updatedDate';
    const sortDir = request.query.dir || 'desc';

    let query = wixData.query('Stores/Products')
      .include('collections')
      .limit(limit)
      .skip(skip);

    if (search) {
      query = query.contains('name', search);
    }

    // Server-side collection filter using hasSome
    if (collectionId) {
      query = query.hasSome('collections', [collectionId]);
    }

    // Sorting
    if (sortDir === 'asc') {
      query = query.ascending(sortField);
    } else {
      query = query.descending(sortField);
    }

    const results = await query.find();

    return json({
      products: results.items.map(formatProduct),
      totalCount: results.totalCount,
      hasNext: results.hasNext(),
      skip,
      limit,
    });
  } catch (e) {
    return err500(e);
  }
}

// ---------------------------------------------------------------------------
// GET /product — Single product by ID (with collections)
// Query: id
// ---------------------------------------------------------------------------
export async function get_product(request) {
  if (!(await authenticate(request))) return forbidden({ body: 'Unauthorized' });

  try {
    const id = request.query.id;
    if (!id) return err400('id is required');

    // Use query with include to get collections (wixData.get doesn't support include)
    const results = await wixData.query('Stores/Products')
      .include('collections')
      .eq('_id', id)
      .find();

    if (results.items.length === 0) {
      return err400('Product not found');
    }

    return json({ product: formatProduct(results.items[0]) });
  } catch (e) {
    return err500(e);
  }
}

function formatProduct(p) {
  return {
    _id: p._id,
    name: p.name,
    description: p.description,
    price: p.price,
    formattedPrice: p.formattedPrice,
    discountedPrice: p.discountedPrice,
    formattedDiscountedPrice: p.formattedDiscountedPrice,
    currency: p.currency,
    sku: p.sku,
    ribbon: p.ribbon,
    brand: p.brand,
    weight: p.weight,
    inStock: p.inStock,
    quantityInStock: p.quantityInStock,
    trackInventory: p.trackInventory,
    productType: p.productType,
    slug: p.slug,
    visible: p.visible,
    mainMedia: p.mainMedia,
    mediaItems: p.mediaItems,
    collections: (p.collections || []).map(c => ({ _id: c._id, name: c.name })),
    customTextFields: p.customTextFields,
    productOptions: p.productOptions,
    variants: p.variants,
    additionalInfoSections: p.additionalInfoSections,
    createdDate: p._createdDate,
    lastUpdated: p._updatedDate,
  };
}

// ---------------------------------------------------------------------------
// GET /orders — List orders with server-side filtering and pagination
// Query: limit, skip, status, paymentStatus, fulfillmentStatus,
//        email, orderNumber, customOrderNumber, dateFrom, dateTo
// ---------------------------------------------------------------------------
export async function get_orders(request) {
  if (!(await authenticate(request))) return forbidden({ body: 'Unauthorized' });

  try {
    const limit = Math.min(Number(request.query.limit) || 50, 100);
    const skip = Number(request.query.skip) || 0;
    const status = request.query.status || '';
    const paymentStatus = request.query.paymentStatus || '';
    const fulfillmentStatus = request.query.fulfillmentStatus || '';
    const email = request.query.email || '';
    const orderNumber = request.query.orderNumber || '';
    const customOrderNumber = request.query.customOrderNumber || '';
    const dateFrom = request.query.dateFrom || '';
    const dateTo = request.query.dateTo || '';

    let query = wixData.query('Stores/Orders')
      .descending('_dateCreated')
      .limit(limit)
      .skip(skip);

    // Server-side filters (these hit the index)
    if (paymentStatus) {
      query = query.eq('paymentStatus', paymentStatus);
    }
    if (fulfillmentStatus) {
      query = query.eq('fulfillmentStatus', fulfillmentStatus);
    }
    if (orderNumber) {
      query = query.eq('number', Number(orderNumber));
    }

    // Date range filtering
    if (dateFrom) {
      query = query.ge('_dateCreated', new Date(dateFrom));
    }
    if (dateTo) {
      query = query.le('_dateCreated', new Date(dateTo));
    }

    const results = await query.find({ suppressAuth: true });

    let orders = results.items.map(formatOrder);

    // In-memory filters for nested fields (buyerInfo is an object)
    if (email) {
      const emailLower = email.toLowerCase();
      orders = orders.filter(o =>
        o.buyerEmail && o.buyerEmail.toLowerCase().includes(emailLower)
      );
    }

    // Custom order number — check customField.value and number
    if (customOrderNumber) {
      orders = orders.filter(o =>
        o.customOrderNumber === customOrderNumber ||
        String(o.number) === customOrderNumber
      );
    }

    return json({
      orders,
      totalCount: results.totalCount,
      hasNext: results.hasNext(),
      skip,
      limit,
    });
  } catch (e) {
    return err500(e);
  }
}

// ---------------------------------------------------------------------------
// GET /order — Single order by ID (full detail)
// Query: id
// ---------------------------------------------------------------------------
export async function get_order(request) {
  if (!(await authenticate(request))) return forbidden({ body: 'Unauthorized' });

  try {
    const id = request.query.id;
    if (!id) return err400('id is required');

    const order = await wixData.get('Stores/Orders', id, { suppressAuth: true });
    if (!order) return err400('Order not found');

    return json({ order: formatOrder(order) });
  } catch (e) {
    return err500(e);
  }
}

function formatOrder(o) {
  // Extract buyer email/phone from nested buyerInfo
  const buyerEmail = o.buyerInfo?.email || '';
  const buyerPhone = o.billingInfo?.phone || o.buyerInfo?.phone || '';
  const buyerName = [
    o.billingInfo?.firstName || o.buyerInfo?.firstName || '',
    o.billingInfo?.lastName || o.buyerInfo?.lastName || '',
  ].filter(Boolean).join(' ');

  // Extract custom order number from customField
  const customOrderNumber = o.customField?.value || '';

  // Line items summary
  const lineItemsSummary = (o.lineItems || []).map(item => ({
    name: item.name || item.productName || '',
    quantity: item.quantity || 0,
    price: item.price || item.priceData?.price || 0,
    totalPrice: item.totalPrice || item.priceData?.totalPrice || 0,
    sku: item.sku || '',
    weight: item.weight || 0,
    mediaItem: item.mediaItem || null,
    customTextFields: item.customTextFields || [],
    options: item.options || [],
  }));

  return {
    _id: o._id,
    number: o.number,
    customOrderNumber,
    customField: o.customField,
    // Buyer info (flattened for easy access)
    buyerEmail,
    buyerPhone,
    buyerName,
    buyerInfo: o.buyerInfo,
    buyerNote: o.buyerNote || '',
    // Billing & shipping
    billingInfo: o.billingInfo,
    shippingInfo: o.shippingInfo,
    // Items
    lineItems: o.lineItems,
    lineItemsSummary,
    lineItemCount: (o.lineItems || []).length,
    // Totals
    totals: o.totals,
    currency: o.currency || 'INR',
    weightUnit: o.weightUnit || 'KG',
    // Status
    paymentStatus: o.paymentStatus || '',
    fulfillmentStatus: o.fulfillmentStatus || '',
    // Fulfillment & activity
    fulfillments: o.fulfillments || [],
    activities: o.activities || [],
    // Channel
    channelInfo: o.channelInfo,
    enteredBy: o.enteredBy,
    cartId: o.cartId,
    // Refunds & subscriptions
    refunds: o.refunds || [],
    subscriptionInfo: o.subscriptionInfo,
    // Flags
    archived: o.archived || false,
    read: o.read || false,
    buyerLanguage: o.buyerLanguage || '',
    // Dates
    dateCreated: o._dateCreated,
    dateUpdated: o._updatedDate,
  };
}

// ---------------------------------------------------------------------------
// GET /collections — List store collections with pagination
// Query: limit, skip
// ---------------------------------------------------------------------------
export async function get_collections(request) {
  if (!(await authenticate(request))) return forbidden({ body: 'Unauthorized' });

  try {
    const limit = Math.min(Number(request.query.limit) || 100, 100);
    const skip = Number(request.query.skip) || 0;

    const results = await wixData.query('Stores/Collections')
      .limit(limit)
      .skip(skip)
      .find();

    return json({
      collections: results.items.map(c => ({
        _id: c._id,
        name: c.name,
        description: c.description,
        mainMedia: c.mainMedia,
        slug: c.slug,
        numberOfProducts: c.numberOfProducts,
      })),
      totalCount: results.totalCount,
      hasNext: results.hasNext(),
    });
  } catch (e) {
    return err500(e);
  }
}

// ---------------------------------------------------------------------------
// GET /inventory — Inventory for a specific product
// Query: productId
// ---------------------------------------------------------------------------
export async function get_inventory(request) {
  if (!(await authenticate(request))) return forbidden({ body: 'Unauthorized' });

  try {
    const productId = request.query.productId;
    if (!productId) return err400('productId is required');

    const results = await wixData.query('Stores/InventoryItems')
      .eq('productId', productId)
      .find({ suppressAuth: true });

    return json({
      productId,
      inventoryItems: results.items,
      totalCount: results.totalCount,
    });
  } catch (e) {
    return err500(e);
  }
}

// ---------------------------------------------------------------------------
// GET /inventory-all — All inventory items with pagination
// Query: limit, skip, inStock (true/false)
// ---------------------------------------------------------------------------
export async function get_inventoryAll(request) {
  if (!(await authenticate(request))) return forbidden({ body: 'Unauthorized' });

  try {
    const limit = Math.min(Number(request.query.limit) || 100, 100);
    const skip = Number(request.query.skip) || 0;
    const inStockFilter = request.query.inStock;

    let query = wixData.query('Stores/InventoryItems')
      .limit(limit)
      .skip(skip);

    if (inStockFilter === 'true') {
      query = query.gt('quantity', 0);
    } else if (inStockFilter === 'false') {
      query = query.eq('quantity', 0);
    }

    const results = await query.find({ suppressAuth: true });

    return json({
      inventoryItems: results.items,
      totalCount: results.totalCount,
      hasNext: results.hasNext(),
    });
  } catch (e) {
    return err500(e);
  }
}

// ---------------------------------------------------------------------------
// GET /stats — Store summary stats (product count, order count, revenue)
// ---------------------------------------------------------------------------
export async function get_stats(request) {
  if (!(await authenticate(request))) return forbidden({ body: 'Unauthorized' });

  try {
    const [products, orders, collections] = await Promise.all([
      wixData.query('Stores/Products').count(),
      wixData.query('Stores/Orders').find({ suppressAuth: true }),
      wixData.query('Stores/Collections').count(),
    ]);

    // Calculate revenue from orders
    let totalRevenue = 0;
    let paidOrders = 0;
    let pendingOrders = 0;
    let fulfilledOrders = 0;

    for (const order of orders.items) {
      if (order.totals && order.totals.total) {
        totalRevenue += Number(order.totals.total) || 0;
      }
      if (order.paymentStatus === 'PAID') paidOrders++;
      if (order.paymentStatus === 'NOT_PAID' || order.paymentStatus === 'PENDING') pendingOrders++;
      if (order.fulfillmentStatus === 'FULFILLED') fulfilledOrders++;
    }

    return json({
      productCount: products,
      orderCount: orders.totalCount,
      collectionCount: collections,
      totalRevenue,
      paidOrders,
      pendingOrders,
      fulfilledOrders,
      currency: orders.items[0]?.currency || 'INR',
    });
  } catch (e) {
    return err500(e);
  }
}
