/**
 * Collection Page — WECARE.DIGITAL
 *
 * Velo page code for store collection pages.
 * Applies collection-level SEO and handles product filtering.
 *
 * Wix Editor: Pages > Store Collection (dynamic page)
 * URL pattern: /store/collection/{slug}
 */

import { applyCollectionSEO } from 'public/seo-bridge.js';
import { fixBrokenImages, cleanConsole } from 'public/site-hygiene.js';
import { formatPrice } from 'public/ops-lite.js';

$w.onReady(async function () {
  cleanConsole();

  const dataset = $w('#collectionDataset');
  if (!dataset) return;

  dataset.onReady(async () => {
    const collection = dataset.getCurrentItem();
    if (!collection) return;

    // Get product count for this collection
    let productCount = 0;
    try {
      const productsDataset = $w('#collectionProductsDataset');
      if (productsDataset) {
        productCount = productsDataset.getTotalCount();
      }
    } catch { /* dataset may not exist */ }

    // Apply SEO
    await applyCollectionSEO(collection, productCount);

    // Setup product grid
    setupCollectionProducts();

    // Update header
    updateCollectionHeader(collection, productCount);
  });
});

// ---------------------------------------------------------------------------
// Collection Header
// ---------------------------------------------------------------------------

function updateCollectionHeader(collection, productCount) {
  try {
    const title = $w('#collectionTitle');
    if (title) title.text = collection.name || '';

    const desc = $w('#collectionDescription');
    if (desc) {
      const text = (collection.description || '').replace(/<[^>]*>/g, '');
      if (text) {
        desc.text = text;
        desc.show();
      } else {
        desc.hide();
      }
    }

    const count = $w('#productCount');
    if (count) count.text = `${productCount} product${productCount !== 1 ? 's' : ''}`;
  } catch { /* elements may not exist */ }
}

// ---------------------------------------------------------------------------
// Product Grid
// ---------------------------------------------------------------------------

function setupCollectionProducts() {
  try {
    const repeater = $w('#collectionProductRepeater');
    if (!repeater) return;

    repeater.onItemReady(($item, itemData) => {
      const img = $item('#productImage');
      const name = $item('#productName');
      const price = $item('#productPrice');
      const badge = $item('#productBadge');

      if (img) img.src = itemData.mainMedia?.image?.url || itemData.mainMedia?.url || '';
      if (name) name.text = itemData.name || '';
      if (price) price.text = formatPrice(itemData.price?.amount || itemData.price || 0);

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
    setTimeout(() => fixBrokenImages('#collectionProductRepeater', '#productImage'), 1000);
  } catch { /* repeater may not exist */ }
}
