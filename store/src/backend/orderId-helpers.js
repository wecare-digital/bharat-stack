/**
 * Order ID Helpers — WECARE.DIGITAL
 *
 * Pure backend module (NOT a web module). Can be safely imported
 * from events.js, data.js, routers.js, and other backend files.
 *
 * The .web.js file delegates to these functions for frontend calls.
 *
 * Format: WD-ORD-{UUID8}-{DD-MM-YYYY}-{HH:MM:SS}-IST
 *   e.g. WD-ORD-A3F7B2C1-22-02-2026-17:43:01-IST
 */

import wixData from 'wix-data';

const ID_PREFIX = 'WD-ORD';
const COLLECTION = 'OrderIDs';
const COLLECTION_CUSTOM = 'OrderCustomIds';
const DATA_OPTIONS = { suppressAuth: true, suppressHooks: true };
const IST_OFFSET_MINUTES = 330; // UTC+5:30

// ---------- helpers ----------

export function safeText(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}

export function mergeOrderFields(existingItem, fields) {
  let changed = false;
  const updated = { ...existingItem };
  Object.keys(fields).forEach((key) => {
    const incoming = fields[key];
    if (incoming === undefined || incoming === null) return;
    if (updated[key] === undefined || updated[key] === null || updated[key] === '') {
      updated[key] = incoming;
      changed = true;
    }
  });
  return { changed, updated };
}

export function toIsoString(dateInput) {
  if (!dateInput) return null;
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return null;
  return d.toISOString();
}

function getIstParts(date) {
  const base = date instanceof Date ? date : new Date();
  const istMs = base.getTime() + IST_OFFSET_MINUTES * 60 * 1000;
  const ist = new Date(istMs);
  const dd = String(ist.getUTCDate()).padStart(2, '0');
  const mm = String(ist.getUTCMonth() + 1).padStart(2, '0');
  const yyyy = ist.getUTCFullYear();
  const hh = String(ist.getUTCHours()).padStart(2, '0');
  const mi = String(ist.getUTCMinutes()).padStart(2, '0');
  const ss = String(ist.getUTCSeconds()).padStart(2, '0');
  return { dd, mm, yyyy, hh, mi, ss };
}

function formatIstDateTimeParts(isoString) {
  const d = isoString ? new Date(isoString) : new Date();
  const { dd, mm, yyyy, hh, mi, ss } = getIstParts(d);
  return {
    dateStr: `${dd}-${mm}-${yyyy}`,
    timeStr: `${hh}:${mi}:${ss}`
  };
}

/**
 * Generate WD-ORD-{UUID8}-{DD-MM-YYYY}-{HH:MM:SS}-IST
 */
function createOrderId(orderDateIso) {
  const { dateStr, timeStr } = formatIstDateTimeParts(orderDateIso);
  const uid = Array.from({ length: 8 }, () =>
    Math.floor(Math.random() * 16).toString(16)
  ).join('').toUpperCase();
  return `${ID_PREFIX}-${uid}-${dateStr}-${timeStr}-IST`;
}

async function generateUniqueOrderId(orderDateIso) {
  let attempts = 0;
  while (attempts < 20) {
    attempts++;
    const id = createOrderId(orderDateIso);
    const existing = await wixData.query(COLLECTION)
      .eq('orderId', id)
      .limit(1)
      .find(DATA_OPTIONS);
    if (existing.totalCount === 0) {
      return id;
    }
  }
  throw new Error('Failed to generate unique ORDER ID after 20 attempts');
}

// ---------- main functions ----------

/**
 * Create or fetch ORDER ID for an order.
 * This is the raw function — no webMethod wrapper.
 * Safe to call from events.js and other backend files.
 */
export async function createOrGetOrderId(payload) {
  const {
    wixOrderId,
    memberId,
    orderNumber,
    buyerEmail,
    buyerPhone,
    totalAmount,
    currency,
    productsSummary,
    orderDate
  } = payload || {};

  const cleanWixOrderId = safeText(wixOrderId);
  if (!cleanWixOrderId) {
    throw new Error('wixOrderId is required');
  }

  const orderDateIso = toIsoString(orderDate) || new Date().toISOString();

  const baseFields = {
    wixOrderId: cleanWixOrderId,
    memberId: safeText(memberId),
    orderNumber: safeText(orderNumber),
    buyerEmail: safeText(buyerEmail),
    buyerPhone: safeText(buyerPhone),
    currency: safeText(currency),
    productsSummary: safeText(productsSummary),
    orderDate: orderDateIso
  };

  const cleanTotalAmount = safeText(totalAmount);
  if (cleanTotalAmount) {
    baseFields.totalAmount = cleanTotalAmount;
  }

  // Check if record already exists for this Wix order
  const existingRes = await wixData.query(COLLECTION)
    .eq('wixOrderId', cleanWixOrderId)
    .limit(1)
    .find(DATA_OPTIONS);

  if (existingRes.totalCount > 0) {
    const existing = existingRes.items[0];
    const { changed, updated } = mergeOrderFields(existing, baseFields);
    if (changed) {
      await wixData.update(COLLECTION, updated, DATA_OPTIONS);
    }
    return existing.orderId;
  }

  // Create new ORDER ID
  const orderId = await generateUniqueOrderId(orderDateIso);
  const itemToInsert = { ...baseFields, orderId };

  await wixData.insert(COLLECTION, itemToInsert, DATA_OPTIONS);

  // Also write to OrderCustomIds for Lambda/dashboard compatibility
  try {
    await wixData.insert(COLLECTION_CUSTOM, {
      orderId: cleanWixOrderId,
      customOrderNumber: orderId,
      memberId: safeText(memberId) || '',
      buyerEmail: safeText(buyerEmail) || '',
    }, DATA_OPTIONS);
  } catch (e) {
    console.warn('[orderId] Failed to write to OrderCustomIds:', e?.message);
  }

  return orderId;
}

/**
 * Paged list of orders for a member.
 */
export async function getMemberOrdersPaged(payload) {
  const {
    memberId,
    page = 0,
    pageSize = 20
  } = payload || {};

  const cleanMemberId = safeText(memberId);
  if (!cleanMemberId) {
    return { items: [], page: 0, pageSize, totalCount: 0, hasMore: false };
  }

  const safePage = Math.max(0, Number(page) || 0);
  let safePageSize = Number(pageSize) || 20;
  if (safePageSize < 1) safePageSize = 1;
  if (safePageSize > 50) safePageSize = 50;

  const query = wixData.query(COLLECTION)
    .eq('memberId', cleanMemberId)
    .descending('orderDate')
    .skip(safePage * safePageSize)
    .limit(safePageSize);

  const result = await query.find(DATA_OPTIONS);
  const totalCount = result.totalCount;
  const hasMore = (safePage + 1) * safePageSize < totalCount;

  return { items: result.items, page: safePage, pageSize: safePageSize, totalCount, hasMore };
}
