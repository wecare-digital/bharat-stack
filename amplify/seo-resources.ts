import { Duration, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';

export const SEO_TOOLS_TABLE_NAME = 'stack-wecare-digital-SeoToolsTable';

/** Durable Admin SEO storage and a Docker-free Python Lambda asset. */
export function addSeoResources ( stack: Stack ) {
    const table = new dynamodb.Table( stack, 'SeoToolsTable', {
        tableName: SEO_TOOLS_TABLE_NAME,
        partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        pointInTimeRecovery: true,
        removalPolicy: RemovalPolicy.RETAIN,
    } );

    table.addGlobalSecondaryIndex( {
        indexName: 'recordType-createdAt-index',
        partitionKey: { name: 'recordType', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
        projectionType: dynamodb.ProjectionType.ALL,
    } );

    table.addGlobalSecondaryIndex( {
        indexName: 'slug-createdAt-index',
        partitionKey: { name: 'slug', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
        projectionType: dynamodb.ProjectionType.ALL,
    } );

    const seoFunction = new lambda.Function( stack, 'SeoToolsFunction', {
        functionName: 'wecare-seo-tools',
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: 'seo_tools_handler.handler',
        code: lambda.Code.fromAsset( 'amplify/functions' ),
        timeout: Duration.seconds( 120 ),
        memorySize: 512,
        environment: {
            LOG_LEVEL: 'INFO',
            SEO_TOOLS_TABLE: SEO_TOOLS_TABLE_NAME,
            WEBHOOK_DEDUP_TABLE: 'stack-wecare-digital-WebhookDedup',
            WIX_API_KEY_SECRET: 'wecare/wix/headless-api-key',
            WIX_SITE_ID: 'fcd82f0c-9572-49c7-acfb-88fb05042ece',
            WIX_ACCOUNT_ID: '15f02319-40ff-4288-b8e6-69c791adae5e',
            WIX_BLOG_AUTHOR_NAME: 'Anew by WECARE.DIGITAL',
            BEDROCK_MODEL_ID: process.env.BEDROCK_MODEL_ID || 'global.anthropic.claude-sonnet-4-6',
        },
    } );

    const wixSecret = secretsmanager.Secret.fromSecretNameV2(
        stack, 'WixHeadlessApiKeySecret', 'wecare/wix/headless-api-key'
    );
    wixSecret.grantRead( seoFunction );

    return { table, function: seoFunction };
}