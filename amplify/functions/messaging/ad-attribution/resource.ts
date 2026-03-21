/**
 * Ad Attribution Lambda — deployed separately (not managed by Amplify Gen 2)
 * Function Name: wecare-ad-attribution
 * Runtime: Python 3.12
 * Handler: handler.handler
 * Timeout: 30s
 * Memory: 128MB
 * 
 * Environment Variables:
 *   AD_ATTRIBUTION_TABLE: stack-wecare-digital-AdClickAttributionTable
 * 
 * IAM Permissions:
 *   - dynamodb:PutItem, GetItem, Query, Scan (AdClickAttribution table)
 * 
 * API Gateway Route: /ad-attribution, /ad-attribution/stats
 */
export {};
