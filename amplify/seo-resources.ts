import { RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

export const SEO_TOOLS_TABLE_NAME = 'stack-wecare-digital-SeoToolsTable';

/** Durable, single-table state for Admin SEO audits and Bedrock logs. */
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

    return table;
}