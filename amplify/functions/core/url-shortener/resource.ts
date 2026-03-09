/**
 * URL Shortener Lambda - WECARE.DIGITAL
 * Domain: r.wecare.digital
 *
 * Endpoints:
 * - POST   /links          — Create short link
 * - GET    /links          — List all links
 * - GET    /links/:code    — Get link details + analytics
 * - DELETE /links/:code    — Delete short link
 * - GET    /r/:code        — Redirect (served by CloudFront/API Gateway)
 *
 * AWS Resources:
 * - DynamoDB: ShortLinksTable (shortCode PK)
 * - DynamoDB: LinkClicksTable (shortCode PK, clickedAt SK)
 * - CloudFront: r.wecare.digital -> API Gateway
 * - ACM Certificate for r.wecare.digital
 * - Route53 CNAME: r.wecare.digital -> CloudFront
 */
import { defineFunction } from '@aws-amplify/backend';

export const urlShortener = defineFunction({
  name: 'url-shortener',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 10,
  memoryMB: 256,
  environment: {
    SHORT_LINKS_TABLE: process.env.SHORT_LINKS_TABLE || 'ShortLinksTable',
    LINK_CLICKS_TABLE: process.env.LINK_CLICKS_TABLE || 'LinkClicksTable',
    SHORT_DOMAIN: 'r.wecare.digital',
  },
});
