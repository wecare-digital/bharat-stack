/**
 * Store Page — WECARE.DIGITAL
 *
 * Velo page code for the main store/shop page.
 * Applies SEO tags and initializes store-level functionality.
 *
 * Wix Editor: Pages > Store
 */

import { applyStoreSEO } from 'public/seo-bridge.js';
import { fixBrokenImages, cleanConsole } from 'public/site-hygiene.js';
import { formatPrice } from 'public/ops-lite.js';

$w.onReady(async function () {
  cleanConsole();
  await applyStoreSEO();

  // Initialize product repeater if present
  setupProductRepeater();
  setupCollectionStrip();
  setupSearch();
});

// ---------------------------------------------------------------------------
// Product Grid / Repeater
// ---------------------------------------------------------------------------

function setupProductRepeater() {
  try {
    const repeater = $w('#productRepeater');
    if (!repeater) return;

    repeater.onItemReady(($item, itemData) => {
      const img = $item('#productImage');
      const name = $item('#productName');
      const price = $item('#productPrice');
      const badge = $item('#productBadge');

      if (img) img.src = itemData.mainMedia?.image?.url || itemData.mainMedia?.url || '';
      if (name) name.text = itemData.name || '';
      if (price) price.text = formatPrice(itemData.price?.amount || itemData.price || 0);

      // Show ribbon/badge if present
      if (badge) {
        if (itemData.ribbon) {
          badge.text = itemData.ribbon;
          badge.show();
        } else {
          badge.hide();
        }
      }
    });

    // Fix broken images after data loads
    setTimeout(() => fixBrokenImages('#productRepeater', '#productImage'), 1000);
  } catch { /* repeater may not exist on this page layout */ }
}

// ---------------------------------------------------------------------------
// Collection Strip (horizontal scroll of collections)
// ---------------------------------------------------------------------------

function setupCollectionStrip() {
  try {
    const collRepeater = $w('#collectionRepeater');
    if (!collRepeater) return;

    collRepeater.onItemReady(($item, itemData) => {
      const img = $item('#collectionImage');
      const name = $item('#collectionName');

      if (img) img.src = itemData.mainMedia?.image?.url || itemData.mainMedia?.url || '';
      if (name) name.text = itemData.name || '';
    });
  } catch { /* collection strip may not exist */ }
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

function setupSearch() {
  try {
    const searchInput = $w('#storeSearch');
    if (!searchInput) return;

    let debounceTimer;
    searchInput.onInput((event) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const query = event.target.value?.trim();
        if (query && query.length >= 2) {
          // Wix Stores dataset filter
          const dataset = $w('#productsDataset');
          if (dataset) {
            dataset.setFilter(
              $w.filter().contains('name', query)
            );
          }
        } else {
          const dataset = $w('#productsDataset');
          if (dataset) dataset.setFilter($w.filter());
        }
      }, 400);
    });
  } catch { /* search input may not exist */ }
}
