/**
 * URL Shortener AWS Resources - WECARE.DIGITAL
 * Domain: r.wecare.digital
 *
 * Creates:
 * 1. DynamoDB: ShortLinksTable (shortCode PK)
 * 2. DynamoDB: LinkClicksTable (shortCode PK, clickedAt SK)
 * 3. ACM Certificate for r.wecare.digital
 * 4. API Gateway HTTP API with custom domain r.wecare.digital
 * 5. Route53 CNAME record: r.wecare.digital -> API Gateway
 * 6. Lambda integration for url-shortener
 * 7. IAM Policy for Lambda
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
const SHORT_DOMAIN = 'r.wecare.digital';
const ROOT_DOMAIN = 'wecare.digital';

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
      SHORT_DOMAIN: SHORT_DOMAIN,
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
      allowOrigins: ['*'],
      allowMethods: [
        apigatewayv2.CorsHttpMethod.GET,
        apigatewayv2.CorsHttpMethod.POST,
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

  // ═══════════════════════════════════════════
  // 6. Route53 CNAME: r.wecare.digital -> API Gateway
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