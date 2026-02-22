/**
 * SEO Bridge — WECARE.DIGITAL
 *
 * Manages dynamic SEO meta tags and structured data (JSON-LD)
 * for product pages, collection pages, and the store homepage.
 *
 * Usage in page code:
 *   import { applyProductSEO, applyCollectionSEO } from 'public/seo-bridge.js';
 *   $w.onReady(() => applyProductSEO(product));
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-seo-frontend
 */

import wixSeoFrontend from 'wix-seo-frontend';

const SITE_NAME = 'WECARE.DIGITAL';
const SITE_URL = 'https://www.wecare.digital';

/**
 * Apply SEO tags for a product detail page.
 * @param {object} product - Wix Stores product object
 */
export async function applyProductSEO(product) {
  if (!product) return;

  const title = `${product.name} | ${SITE_NAME}`;
  const description = (product.description || '')
    .replace(/<[^>]*>/g, '')
    .slice(0, 160);
  const image = product.mainMedia?.image?.url || product.mainMedia?.url || '';
  const price = product.price?.formatted?.actualPrice || product.formattedPrice || '';
  const currency = product.price?.currency || 'INR';
  const url = `${SITE_URL}/store/product/${product.slug || product._id}`;

  // Set meta tags
  await wixSeoFrontend.setTitle(title);
  await wixSeoFrontend.setMetaTags([
    { property: 'og:title', content: title },
    { property: 'og:description', content: description },
    { property: 'og:image', content: image },
    { property: 'og:url', content: url },
    { property: 'og:type', content: 'product' },
    { name: 'description', content: description },
    { name: 'twitter:card', content: 'summary_large_image' },
    { name: 'twitter:title', content: title },
    { name: 'twitter:description', content: description },
    { name: 'twitter:image', content: image },
  ]);

  // Structured data — Product schema
  await wixSeoFrontend.setStructuredData([
    {
      '@context': 'https://schema.org',
      '@type': 'Product',
      name: product.name,
      description,
      image: image ? [image] : [],
      sku: product.sku || '',
      brand: {
        '@type': 'Brand',
        name: product.brand || SITE_NAME,
      },
      offers: {
        '@type': 'Offer',
        url,
        priceCurrency: currency,
        price: product.price?.amount || product.price || '0',
        availability: product.inStock
          ? 'https://schema.org/InStock'
          : 'https://schema.org/OutOfStock',
        seller: {
          '@type': 'Organization',
          name: SITE_NAME,
        },
      },
    },
  ]);
}

/**
 * Apply SEO tags for a collection page.
 * @param {object} collection - Wix Stores collection object
 * @param {number} productCount - Number of products in collection
 */
export async function applyCollectionSEO(collection, productCount = 0) {
  if (!collection) return;

  const title = `${collection.name} | ${SITE_NAME} Store`;
  const description = (collection.description || `Browse ${collection.name} collection`)
    .replace(/<[^>]*>/g, '')
    .slice(0, 160);
  const image = collection.mainMedia?.image?.url || collection.mainMedia?.url || '';
  const url = `${SITE_URL}/store/collection/${collection.slug || collection._id}`;

  await wixSeoFrontend.setTitle(title);
  await wixSeoFrontend.setMetaTags([
    { property: 'og:title', content: title },
    { property: 'og:description', content: description },
    { property: 'og:image', content: image },
    { property: 'og:url', content: url },
    { property: 'og:type', content: 'website' },
    { name: 'description', content: description },
  ]);

  // Structured data — CollectionPage
  await wixSeoFrontend.setStructuredData([
    {
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: collection.name,
      description,
      url,
      numberOfItems: productCount,
      isPartOf: {
        '@type': 'WebSite',
        name: SITE_NAME,
        url: SITE_URL,
      },
    },
  ]);
}

/**
 * Apply SEO tags for the store homepage.
 */
export async function applyStoreSEO() {
  const title = `Store | ${SITE_NAME}`;
  const description = 'Shop the latest products at WECARE.DIGITAL — quality products with fast delivery across India.';

  await wixSeoFrontend.setTitle(title);
  await wixSeoFrontend.setMetaTags([
    { property: 'og:title', content: title },
    { property: 'og:description', content: description },
    { property: 'og:url', content: `${SITE_URL}/store` },
    { property: 'og:type', content: 'website' },
    { name: 'description', content: description },
  ]);

  await wixSeoFrontend.setStructuredData([
    {
      '@context': 'https://schema.org',
      '@type': 'Store',
      name: SITE_NAME,
      url: `${SITE_URL}/store`,
      description,
      currenciesAccepted: 'INR',
    },
  ]);
}
