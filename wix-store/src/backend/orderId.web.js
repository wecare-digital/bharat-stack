// backend/orderId.js
import wixData from 'wix-data';
import { Permissions, webMethod } from 'wix-web-module';

const COLLECTION = 'OrderIDs';
const DATA_OPTIONS = { suppressAuth: true, suppressHooks: true };
const IST_OFFSET_MINUTES = 330; // UTC+5:30
const ID_PREFIX = 'WDSR';

// ---------- helpers ----------

function safeText(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}

function mergeOrderFields(existingItem, fields) {
  let changed = false;
  const updated = { ...existingItem };

  Object.keys(fields).forEach((key) => {
    const incoming = fields[key];
    if (incoming === undefined || incoming === null) return;

    if (
      updated[key] === undefined ||
      updated[key] === null ||
      updated[key] === ''
    ) {
      updated[key] = incoming;
      changed = true;
    }
  });

  return { changed, updated };
}

// convert any date input to ISO text for storage
function toIsoString(dateInput) {
  if (!dateInput) return null;
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return null;
  return d.toISOString();
}

// IST conversion
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

// ORDER ID : DD-MM-YYYY - HH:MM:SS - IST - XXXXXXXXXX
function createOrderId(orderDateIso) {
  const { dateStr, timeStr } = formatIstDateTimeParts(orderDateIso);

  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no 0/O/1/I
  const length = 10;
  let randomPart = '';

  for (let i = 0; i < length; i++) {
    const idx = Math.floor(Math.random() * chars.length);
    randomPart += chars.charAt(idx);
  }

  return `${ID_PREFIX} : ${dateStr} - ${timeStr} - IST - ${randomPart}`;
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

// ---------- WEB METHODS ----------

// 1) Create or fetch ORDER ID for order (called from Thank You page)
export const createOrGetOrderId = webMethod(
  Permissions.Anyone,
  async (payload) => {
    const {
      wixOrderId,
      memberId,
      orderNumber,
      buyerEmail,
      buyerPhone,
      totalAmount,      // TEXT like "1,234.00 INR"
      currency,         // e.g. "INR"
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
      baseFields.totalAmount = cleanTotalAmount; // TEXT in CMS
    }

    // 1) If record already exists for this Wix order, update missing fields
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

    // 2) Create new ORDER ID
    const orderId = await generateUniqueOrderId(orderDateIso);
    const itemToInsert = { ...baseFields, orderId };

    await wixData.insert(COLLECTION, itemToInsert, DATA_OPTIONS);
    return orderId;
  }
);

// 2) Paged list of orders for a member
export const getMemberOrdersPaged = webMethod(
  Permissions.Anyone,
  async (payload) => {
    const {
      memberId,
      page = 0,
      pageSize = 20
    } = payload || {};

    const cleanMemberId = safeText(memberId);
    if (!cleanMemberId) {
      return {
        items: [],
        page: 0,
        pageSize,
        totalCount: 0,
        hasMore: false
      };
    }

    const safePage = Math.max(0, Number(page) || 0);
    let safePageSize = Number(pageSize) || 20;
    if (safePageSize < 1) safePageSize = 1;
    if (safePageSize > 50) safePageSize = 50; // cap

    const query = wixData.query(COLLECTION)
      .eq('memberId', cleanMemberId)
      .descending('orderDate')        // newest first
      .skip(safePage * safePageSize)  // paging
      .limit(safePageSize);

    const result = await query.find(DATA_OPTIONS);

    const totalCount = result.totalCount;
    const hasMore = (safePage + 1) * safePageSize < totalCount;

    return {
      items: result.items,
      page: safePage,
      pageSize: safePageSize,
      totalCount,
      hasMore
    };
  }
);