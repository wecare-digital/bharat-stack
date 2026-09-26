/**
 * URL Shortener AWS Resources - WECARE.DIGITAL
 *
 * Canonical base for new links: wecare.digital/r  (since 2026-09-26)
 * Also honoured, permanently:   r.wecare.digital
 *
 * NOT DEPLOYED - verified 2026-09-26. There is no CloudFormation stack for this
 * file, and the `stack-wecare-short-links` HTTP API it declares below does not
 * exist: the account holds exactly one HTTP API, `zllr9lrg7j`
 * ("wecare-digital-api"). The live wiring is different from what this file
 * describes - the `r.wecare.digital` custom domain is mapped straight to
 * `zllr9lrg7j` stage `prod`, and the shortener's routes (`GET /r/{code}`,
 * `GET /{code}`, `/links*`) live on that same shared API against
 * `stack-wecare-url-shortener:live`.
 *
 * So treat this as a description of intent, not of production. Changing a value
 * here does NOT change the account; the live Lambda environment and the API
 * Gateway mapping have to be changed directly. Recorded because a reader who
 * assumes this file is authoritative will make a change here, see nothing happen,
 * and conclude the change did not work.
 *
 * Creates:
 * 1. DynamoDB: ShortLinksTable (shortCode PK)
 * 2. DynamoDB: LinkClicksTable (shortCode PK, clickedAt SK)
 * 3. ACM Certificate for r.wecare.digital
 * 4. API Gateway HTTP API with custom domain r.wecare.digital
 * 5. Route53 CNAME record: r.wecare.digital -> API Gateway
 * 6. Google Workspace domain verification TXT + CNAME records
 * 7. Lambda integration for url-shortener
 * 8. IAM Policy for Lambda
 *
 * API Gateway Routes:
 * - GET  /{code}        -> url-shortener Lambda (redirect)
 * - POST /links         -> url-shortener Lambda (create)
 * - GET  /links         -> url-shortener Lambda (list)
 * - GET  /links/{code}  -> url-shortener Lambda (get + analytics)
 * - DELETE /links/{code} -> url-shortener Lambda (delete)
 */

import { Stack, RemovalPolicy, Duration, CfnOutput } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53targets from 'aws-cdk-lib/aws-route53-targets';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigatewayv2Integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';

const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
const ROOT_DOMAIN = 'wecare.digital';

// The DNS name. Used for the ACM certificate subject and the API Gateway custom
// domain, both of which require a bare hostname. This stays as it is: short links
// already delivered to customers name this host, and they cannot be recalled.
const SHORT_DOMAIN = 'r.wecare.digital';

// The base that NEW short links are published under, canonical since 2026-09-26.
// Carries a path, so it is NOT interchangeable with SHORT_DOMAIN above — one
// constant previously served both purposes, which is exactly what makes moving the
// shortener onto a path look like it requires giving up the subdomain.
//
// Resolution is unaffected either way: the handler already accepts both `/r/{code}`
// and a bare `/{code}`, and Amplify proxies `/r/<*>` to the API. This value only
// decides what we MINT.
const SHORT_LINK_BASE = `${ROOT_DOMAIN}/r`;

export function addLinkResources(stack: Stack) {
  // ═══════════════════════════════════════════
  // 1. DynamoDB Tables
  // ═══════════════════════════════════════════

  const shortLinksTable = new dynamodb.Table(stack, 'ShortLinksTable', {
    tableName: 'ShortLinksTable',
    partitionKey: { name: 'shortCode', type: dynamodb.AttributeType.STRING },
    billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    removalPolicy: RemovalPolicy.RETAIN,
    pointInTimeRecovery: true,
  });

  const linkClicksTable = new dynamodb.Table(stack, 'LinkClicksTable', {
    tableName: 'LinkClicksTable',
    partitionKey: { name: 'shortCode', type: dynamodb.AttributeType.STRING },
    sortKey: { name: 'clickedAt', type: dynamodb.AttributeType.STRING },
    billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    removalPolicy: RemovalPolicy.RETAIN,
  });

  // ═══════════════════════════════════════════
  // 2. Route53 Hosted Zone (lookup existing)
  // ═══════════════════════════════════════════

  const hostedZone = route53.HostedZone.fromLookup(stack, 'WecareHostedZone', {
    domainName: ROOT_DOMAIN,
  });

  // ═══════════════════════════════════════════
  // 3. ACM Certificate for r.wecare.digital
  //    DNS validation via Route53 (auto-creates CNAME validation records)
  // ═══════════════════════════════════════════

  const certificate = new acm.Certificate(stack, 'ShortLinkCert', {
    domainName: SHORT_DOMAIN,
    certificateName: 'r-wecare-digital-cert',
    validation: acm.CertificateValidation.fromDns(hostedZone),
  });

  // ═══════════════════════════════════════════
  // 4. Lambda Function for URL Shortener
  // ═══════════════════════════════════════════

  const urlShortenerFn = new lambda.Function(stack, 'UrlShortenerFn', {
    functionName: 'stack-wecare-url-shortener',
    runtime: lambda.Runtime.PYTHON_3_12,
    handler: 'handler.handler',
    code: lambda.Code.fromAsset('amplify/functions/core/url-shortener'),
    timeout: Duration.seconds(10),
    memorySize: 256,
    environment: {
      SHORT_LINKS_TABLE: shortLinksTable.tableName,
      LINK_CLICKS_TABLE: linkClicksTable.tableName,
      // The public link base, not the DNS name — see the constants above.
      SHORT_LINK_BASE: SHORT_LINK_BASE,
    },
  });

  // Grant Lambda access to DynamoDB tables
  shortLinksTable.grantReadWriteData(urlShortenerFn);
  linkClicksTable.grantReadWriteData(urlShortenerFn);

  // ═══════════════════════════════════════════
  // 5. API Gateway HTTP API with Custom Domain
  // ═══════════════════════════════════════════

  // Custom domain name for API Gateway
  const domainName = new apigatewayv2.DomainName(stack, 'ShortLinkDomain', {
    domainName: SHORT_DOMAIN,
    certificate: certificate,
  });

  // HTTP API
  const httpApi = new apigatewayv2.HttpApi(stack, 'ShortLinkApi', {
    apiName: 'stack-wecare-short-links',
    description: 'URL Shortener API for r.wecare.digital',
    corsPreflight: {
      // stack.wecare.digital removed with that hostname's retirement; it only 301'd
      // to the apex, and a redirecting host is never a usable allowed origin.
      allowOrigins: [
        'https://wecare.digital',
        'https://www.wecare.digital',
      ],
      allowMethods: [
        apigatewayv2.CorsHttpMethod.GET,
        apigatewayv2.CorsHttpMethod.POST,
        apigatewayv2.CorsHttpMethod.PUT,
        apigatewayv2.CorsHttpMethod.DELETE,
        apigatewayv2.CorsHttpMethod.OPTIONS,
      ],
      allowHeaders: ['Content-Type', 'Authorization'],
    },
    defaultDomainMapping: {
      domainName: domainName,
    },
  });

  // Lambda integration
  const lambdaIntegration = new apigatewayv2Integrations.HttpLambdaIntegration(
    'ShortLinkLambdaIntegration',
    urlShortenerFn,
  );

  // API Routes
  // GET /{code} — redirect (catch-all for short codes)
  httpApi.addRoutes({
    path: '/{code}',
    methods: [apigatewayv2.HttpMethod.GET],
    integration: lambdaIntegration,
  });

  // POST /links — create short link
  httpApi.addRoutes({
    path: '/links',
    methods: [apigatewayv2.HttpMethod.POST],
    integration: lambdaIntegration,
  });

  // GET /links — list all links
  httpApi.addRoutes({
    path: '/links',
    methods: [apigatewayv2.HttpMethod.GET],
    integration: lambdaIntegration,
  });

  // GET /links/{code} — get link details
  httpApi.addRoutes({
    path: '/links/{code}',
    methods: [apigatewayv2.HttpMethod.GET],
    integration: lambdaIntegration,
  });

  // DELETE /links/{code} — delete link
  httpApi.addRoutes({
    path: '/links/{code}',
    methods: [apigatewayv2.HttpMethod.DELETE],
    integration: lambdaIntegration,
  });

  // PUT /links/{code} — update link
  httpApi.addRoutes({
    path: '/links/{code}',
    methods: [apigatewayv2.HttpMethod.PUT],
    integration: lambdaIntegration,
  });

  // ═══════════════════════════════════════════
  // 6. Route53 records
  // ═══════════════════════════════════════════

  new route53.ARecord(stack, 'ShortLinkAliasRecord', {
    zone: hostedZone,
    recordName: 'r',
    target: route53.RecordTarget.fromAlias(
      new route53targets.ApiGatewayv2DomainProperties(
        domainName.regionalDomainName,
        domainName.regionalHostedZoneId,
      ),
    ),
    comment: 'URL Shortener - r.wecare.digital -> API Gateway',
  });

  // Google Workspace domain verification (primary TXT method)
  new route53.TxtRecord(stack, 'GoogleWorkspaceVerificationTxt', {
    zone: hostedZone,
    recordName: ROOT_DOMAIN,
    values: [
      'google-site-verification=G74l7Vaf6_5214FKtpjHqCkaw4wQ6TEc2qMmVlRSg0k',
    ],
    ttl: Duration.minutes(5),
    comment: 'Google Workspace domain verification',
  });

  // Google Workspace domain verification (alternative CNAME method)
  new route53.CnameRecord(stack, 'GoogleWorkspaceVerificationCname', {
    zone: hostedZone,
    recordName: 'qu75cp2vx25y',
    domainName: 'gv-jipfxur7egi32x.dv.googlehosted.com',
    ttl: Duration.minutes(5),
    comment: 'Google Workspace alternative domain verification',
  });

  // ═══════════════════════════════════════════
  // 7. Outputs
  // ═══════════════════════════════════════════

  new CfnOutput(stack, 'ShortLinkDomainOutput', {
    value: `https://${SHORT_DOMAIN}`,
    description: 'URL Shortener domain',
  });

  new CfnOutput(stack, 'ShortLinkApiUrl', {
    value: httpApi.apiEndpoint,
    description: 'API Gateway endpoint (before custom domain)',
  });

  new CfnOutput(stack, 'ShortLinkCertArn', {
    value: certificate.certificateArn,
    description: 'ACM Certificate ARN for r.wecare.digital',
  });

  // IAM Policy (for external Lambda references if needed)
  const linkLambdaPolicy = new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: [
      'dynamodb:PutItem',
      'dynamodb:GetItem',
      'dynamodb:DeleteItem',
      'dynamodb:Scan',
      'dynamodb:Query',
      'dynamodb:UpdateItem',
    ],
    resources: [
      shortLinksTable.tableArn,
      linkClicksTable.tableArn,
      `${linkClicksTable.tableArn}/index/*`,
    ],
  });

  return {
    shortLinksTable,
    linkClicksTable,
    certificate,
    httpApi,
    domainName,
    urlShortenerFn,
    linkLambdaPolicy,
  };
}
