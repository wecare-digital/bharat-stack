// my-orders page code

import { getMemberOrdersPaged } from 'backend/orderId';
import { currentMember } from 'wix-members-frontend';

const IST_OFFSET_MINUTES = 330;
const PAGE_SIZE = 20;

let currentPage = 0;
let hasMore = false;
let allOrders = [];
let currentMemberId = null;

function formatIstDateTime(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return '';
  const istMs = d.getTime() + IST_OFFSET_MINUTES * 60 * 1000;
  const ist = new Date(istMs);

  const dd = String(ist.getUTCDate()).padStart(2, '0');
  const mm = String(ist.getUTCMonth() + 1).padStart(2, '0');
  const yyyy = ist.getUTCFullYear();
  const hh = String(ist.getUTCHours()).padStart(2, '0');
  const mi = String(ist.getUTCMinutes()).padStart(2, '0');
  const ss = String(ist.getUTCSeconds()).padStart(2, '0');

  return `${dd}-${mm}-${yyyy} ${hh}:${mi}:${ss} IST`;
}

function mapOrdersToRepeaterData(orders) {
  return orders.map((o, index) => {
    const iso = o.orderDate || o._createdDate;
    return {
      _id: o._id,
      slNo: index + 1,
      orderId: o.orderId,
      date: formatIstDateTime(iso),
      products: o.productsSummary || '',
      amount: o.totalAmount || '' // TEXT from CMS
    };
  });
}

function bindOrdersToRepeater() {
  if (!allOrders || allOrders.length === 0) {
    $w('#ordersRepeater').data = [];
    $w('#ordersRepeater').hide();
    return;
  }

  const repeaterData = mapOrdersToRepeaterData(allOrders);

  $w('#ordersRepeater').data = repeaterData;
  $w('#ordersRepeater').onItemReady(($item, itemData) => {
    $item('#slNoText').text = String(itemData.slNo);
    $item('#shopIdText').text = itemData.orderId || '';
    $item('#dateText').text = itemData.date || '';
    $item('#productText').text = itemData.products || '';
    $item('#amountText').text = itemData.amount || '';
  });

  $w('#ordersRepeater').show();
}

async function loadPage(pageIndex) {
  if (!currentMemberId) return;

  $w('#loadMoreButton').disable();
  $w('#emptyStateText').text = pageIndex === 0
    ? 'Loading your orders...'
    : 'Loading more orders...';
  $w('#emptyStateText').show();

  try {
    const res = await getMemberOrdersPaged({
      memberId: currentMemberId,
      page: pageIndex,
      pageSize: PAGE_SIZE
    });

    if (pageIndex === 0) {
      allOrders = res.items || [];
    } else {
      allOrders = allOrders.concat(res.items || []);
    }

    hasMore = !!res.hasMore;
    currentPage = res.page;

    if (!allOrders || allOrders.length === 0) {
      $w('#ordersRepeater').hide();
      $w('#emptyStateText').text =
        "You haven't placed any orders yet. Once you place an order, it will appear here.";
      $w('#loadMoreButton').hide();
      return;
    }

    bindOrdersToRepeater();
    $w('#emptyStateText').hide();

    if (hasMore) {
      $w('#loadMoreButton').show();
      $w('#loadMoreButton').enable();
    } else {
      $w('#loadMoreButton').hide();
    }
  } catch (err) {
    console.error('Error loading orders:', err);
    $w('#ordersRepeater').hide();
    $w('#emptyStateText').text =
      'We could not load your orders right now. Please refresh the page.';
    $w('#loadMoreButton').hide();
  }
}

$w.onReady(async function () {
  $w('#ordersContainer').expand();
  $w('#ordersRepeater').hide();
  $w('#loadMoreButton').hide();
  $w('#emptyStateText').text = 'Loading your orders...';
  $w('#emptyStateText').show();

  // get logged-in member
  try {
    const member = await currentMember.getMember();
    currentMemberId = member?._id || null;
  } catch (err) {
    console.error('currentMember error:', err);
  }

  if (!currentMemberId) {
    $w('#emptyStateText').text = 'Please log in to view your orders.';
    return;
  }

  // first page
  await loadPage(0);

  // Load older orders button
  $w('#loadMoreButton').onClick(async () => {
    if (!hasMore) {
      $w('#loadMoreButton').hide();
      return;
    }
    await loadPage(currentPage + 1);
  });
});
