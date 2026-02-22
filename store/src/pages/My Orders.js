/**
 * My Orders Page — WECARE.DIGITAL
 *
 * Velo page code for the member "My Orders" page.
 * Logged-in users can view their order history using WDSR custom order IDs.
 * Wix native order numbers are never shown.
 *
 * Features:
 *   - Auto-fetches orders for the logged-in member
 *   - Search by WDSR order number
 *   - Order detail expand
 *   - Works with Wix Forms (order lookup input)
 *
 * Required elements in Wix Editor:
 *   #ordersRepeater  — Repeater for order list
 *   #orderSearch     — Text input for WDSR search
 *   #searchButton    — Search button
 *   #noOrdersText    — Text shown when no orders found
 *   #loadingIndicator — Loading spinner
 *   #orderCount      — Text showing total order count
 *
 * Wix Editor: Pages > My Orders (Members Area)
 */

import wixWindow from 'wix-window';
import { currentMember } from 'wix-members-frontend';
import { getMyOrders, getMyOrderByNumber } from 'backend/member-orders.web.js';
import { formatPrice, formatDate } from 'public/ops-lite.js';
import { cleanConsole } from 'public/site-hygiene.js';

let _memberId = null;

$w.onReady(async function () {
  cleanConsole();

  // Get current logged-in member
  try {
    const member = await currentMember.getMember();
    _memberId = member?._id;
  } catch {
    // Not logged in — show login prompt
    showElement('#loginPrompt');
    hideElement('#ordersContainer');
    return;
  }

  if (!_memberId) {
    showElement('#loginPrompt');
    hideElement('#ordersContainer');
    return;
  }

  hideElement('#loginPrompt');
  showElement('#ordersContainer');

  // Load orders
  await loadOrders();

  // Setup search
  setupSearch();
});

// ---------------------------------------------------------------------------
// Load Orders
// ---------------------------------------------------------------------------

async function loadOrders() {
  showElement('#loadingIndicator');
  hideElement('#noOrdersText');

  try {
    const { orders, totalCount } = await getMyOrders(_memberId, { limit: 50 });

    const countEl = $w('#orderCount');
    if (countEl) countEl.text = `${totalCount} order${totalCount !== 1 ? 's' : ''}`;

    if (orders.length === 0) {
      showElement('#noOrdersText');
      hideElement('#ordersRepeater');
      hideElement('#loadingIndicator');
      return;
    }

    const repeater = $w('#ordersRepeater');
    if (repeater) {
      repeater.data = orders.map(o => ({ ...o, _id: o._id || o.customOrderNumber }));

      repeater.onItemReady(($item, itemData) => {
        // WDSR order number (primary — Wix native is never shown)
        const orderIdEl = $item('#orderDisplayId');
        if (orderIdEl) orderIdEl.text = itemData.customOrderNumber || itemData.orderDisplayId || '—';

        // Status
        const statusEl = $item('#orderStatus');
        if (statusEl) {
          const status = itemData.paymentStatus || itemData.status || '';
          statusEl.text = status.replace(/_/g, ' ');
          if (status === 'PAID') statusEl.style.color = '#059669';
          else if (status === 'NOT_PAID') statusEl.style.color = '#dc2626';
        }

        // Total
        const totalEl = $item('#orderTotal');
        if (totalEl) {
          const total = itemData.totals?.total || itemData.priceSummary?.total?.amount || '0';
          const currency = itemData.currency || 'INR';
          totalEl.text = formatPrice(parseFloat(total), currency);
        }

        // Date
        const dateEl = $item('#orderDate');
        if (dateEl) {
          dateEl.text = formatDate(itemData._dateCreated || itemData.dateCreated || itemData._createdDate);
        }

        // Items count
        const itemsEl = $item('#orderItemCount');
        if (itemsEl) {
          const count = itemData.lineItems?.length || 0;
          itemsEl.text = `${count} item${count !== 1 ? 's' : ''}`;
        }

        // Fulfillment
        const fulfillEl = $item('#fulfillmentStatus');
        if (fulfillEl) {
          const fs = itemData.fulfillmentStatus || 'NOT_FULFILLED';
          fulfillEl.text = fs.replace(/_/g, ' ');
        }
      });

      showElement('#ordersRepeater');
    }
  } catch (err) {
    console.error('Failed to load orders:', err);
    showElement('#noOrdersText');
  }

  hideElement('#loadingIndicator');
}

// ---------------------------------------------------------------------------
// Search by WDSR order number
// ---------------------------------------------------------------------------

function setupSearch() {
  const searchInput = $w('#orderSearch');
  const searchBtn = $w('#searchButton');

  if (searchBtn) {
    searchBtn.onClick(async () => {
      const query = searchInput?.value?.trim();
      if (!query) {
        await loadOrders(); // Reset to full list
        return;
      }
      await searchOrder(query);
    });
  }

  if (searchInput) {
    searchInput.onKeyPress(async (event) => {
      if (event.key === 'Enter') {
        const query = searchInput.value?.trim();
        if (!query) {
          await loadOrders();
          return;
        }
        await searchOrder(query);
      }
    });
  }
}

async function searchOrder(customOrderNumber) {
  showElement('#loadingIndicator');
  hideElement('#noOrdersText');

  try {
    const order = await getMyOrderByNumber(_memberId, customOrderNumber);

    if (!order) {
      showElement('#noOrdersText');
      hideElement('#ordersRepeater');
      const countEl = $w('#orderCount');
      if (countEl) countEl.text = '0 orders';
    } else {
      const repeater = $w('#ordersRepeater');
      if (repeater) {
        repeater.data = [{ ...order, _id: order._id || order.customOrderNumber }];
        showElement('#ordersRepeater');
      }
      const countEl = $w('#orderCount');
      if (countEl) countEl.text = '1 order';
    }
  } catch (err) {
    console.error('Search failed:', err);
    showElement('#noOrdersText');
  }

  hideElement('#loadingIndicator');
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function showElement(selector) {
  try { $w(selector)?.show(); } catch { /* element may not exist */ }
}

function hideElement(selector) {
  try { $w(selector)?.hide(); } catch { /* element may not exist */ }
}
