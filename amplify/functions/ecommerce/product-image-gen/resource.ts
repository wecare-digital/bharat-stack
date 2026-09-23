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
  timeout: 60,
  memorySize: 512,
  environment: {
    LOG_LEVEL: 'INFO',
    WIX_SITE_ID: 'fcd82f0c-9572-49c7-acfb-88fb05042ece',
    WIX_ACCOUNT_ID: '15f02319-40ff-4288-b8e6-69c791adae5e',
    WIX_CREDENTIALS_DISABLED: 'true',
  },
};
