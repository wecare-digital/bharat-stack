/**
 * Product Image Generator Lambda
 *
 * Deployed as: wecare-product-image-gen
 * Runtime: Python 3.12
 * Timeout: 30s
 * Memory: 256MB
 *
 * API Gateway routes:
 *   GET  /store/preview-product-image?country=fr&visaType=tourist&price=₹2,999
 *   POST /store/generate-product-image
 *
 * Generates branded SVG product cards for the Wix Store.
 * Uploads to S3: app.wecare.digital/store/products/{category}/{country}-{visaType}.svg
 */
export const productImageGenFunction = {
  name: 'wecare-product-image-gen',
  runtime: 'python3.12',
  handler: 'handler.handler',
  timeout: 30,
  memorySize: 256,
  environment: {
    LOG_LEVEL: 'INFO',
    WIX_API_KEY: '${WIX_API_KEY}',
    WIX_SITE_ID: '${WIX_SITE_ID}',
  },
};
