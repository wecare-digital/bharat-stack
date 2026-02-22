/**
 * Product Detail Page — WECARE.DIGITAL
 *
 * Velo page code for individual product pages.
 * Applies product-level SEO (meta tags + JSON-LD structured data),
 * handles variant selection, and tracks product views.
 *
 * Wix Editor: Pages > Store Product (dynamic page)
 * URL pattern: /store/product/{slug}
 */

import wixWindow from 'wix-window';
import wixLocation from 'wix-location';
import { applyProductSEO } from 'public/seo-bridge.js';
import { formatPrice, formatDate } from 'public/ops-lite.js';
import { cleanConsole } from 'public/site-hygiene.js';

$w.onReady(async function () {
  cleanConsole();

  // Wait for the product dataset to be ready
  const dataset = $w('#productDataset');
  if (!dataset) return;

  dataset.onReady(async () => {
    const product = dataset.getCurrentItem();
    if (!product) return;

    // Apply SEO
    await applyProductSEO(product);

    // Populate custom fields
    populateProductDetails(product);

    // Track product view
    trackProductView(product);
  });
});

// ---------------------------------------------------------------------------
// Product Details
// ---------------------------------------------------------------------------

function populateProductDetails(product) {
  try {
    // SKU display
    const skuEl = $w('#productSku');
    if (skuEl) {
      skuEl.text = product.sku ? `SKU: ${product.sku}` : '';
      if (!product.sku) skuEl.hide();
    }

    // Stock status
    const stockEl = $w('#stockStatus');
    if (stockEl) {
      if (product.inStock) {
        stockEl.text = product.quantityInStock
          ? `In Stock (${product.quantityInStock} available)`
          : 'In Stock';
        stockEl.style.color = '#059669';
      } else {
        stockEl.text = 'Out of Stock';
        stockEl.style.color = '#dc2626';
      }
    }

    // Brand
    const brandEl = $w('#productBrand');
    if (brandEl) {
      if (product.brand) {
        brandEl.text = product.brand;
        brandEl.show();
      } else {
        brandEl.hide();
      }
    }

    // Last updated
    const updatedEl = $w('#lastUpdated');
    if (updatedEl && product.lastUpdated) {
      updatedEl.text = `Updated: ${formatDate(product.lastUpdated)}`;
    }
  } catch { /* elements may not exist in all layouts */ }
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

function trackProductView(product) {
  try {
    wixWindow.trackEvent('ViewContent', {
      origin: 'Stores',
      id: product._id,
      name: product.name,
      category: product.productType || 'physical',
      price: product.price?.amount || product.price || 0,
      currency: product.price?.currency || 'INR',
      sku: product.sku || '',
      inStock: product.inStock,
    });
  } catch { /* tracking may fail silently */ }
}
