/**
 * Push Notification AWS Resources - WECARE.DIGITAL
 *
 * Creates the required AWS infrastructure for mobile push notifications:
 *
 * 1. DynamoDB Table: PushTokensTable
 *    - Stores device token -> user ID -> SNS endpoint ARN mappings
 *    - PK: deviceToken, SK: userId
 *
 * 2. SNS Platform Applications (created manually in AWS Console):
 *    - stack-wecare-push-android (FCM / Firebase Cloud Messaging)
 *      Requires: Firebase Server Key from Firebase Console
 *    - stack-wecare-push-ios (APNs / Apple Push Notification service)
 *      Requires: APNs Auth Key (.p8) from Apple Developer Portal
 *
 * 3. IAM Policy for Lambda to access SNS + DynamoDB
 *
 * SETUP INSTRUCTIONS:
 *
 * A) Firebase (Android):
 *    1. Go to Firebase Console -> Project Settings -> Cloud Messaging
 *    2. Copy the Server Key (or use FCM v1 service account JSON)
 *    3. In AWS Console -> SNS -> Push Notifications -> Create Platform Application
 *       - Name: stack-wecare-push-android
 *       - Platform: FCM
 *       - API Key: paste Firebase Server Key
 *    4. Copy the Platform Application ARN
 *    5. Set env var: SNS_PLATFORM_APP_ARN_ANDROID=<arn>
 *
 * B) Apple (iOS):
 *    1. Go to Apple Developer -> Certificates, IDs & Profiles -> Keys
 *    2. Create a key with APNs enabled, download .p8 file
 *    3. In AWS Console -> SNS -> Push Notifications -> Create Platform Application
 *       - Name: stack-wecare-push-ios
 *       - Platform: Apple iOS/VoIP/macOS
 *       - Auth method: Token-based (.p8)
 *       - Signing key: upload .p8
 *       - Key ID, Team ID, Bundle ID: from Apple Developer
 *    4. Copy the Platform Application ARN
 *    5. Set env var: SNS_PLATFORM_APP_ARN_IOS=<arn>
 *
 * C) DynamoDB Table:
 *    Created automatically by this CDK stack, or manually:
 *    - Table name: PushTokensTable
 *    - Partition key: deviceToken (String)
 *    - Sort key: userId (String)
 *    - GSI: userId-index (PK: userId) for querying all devices of a user
 */

import { Stack } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import { RemovalPolicy } from 'aws-cdk-lib';

const AWS_ACCOUNT_ID = process.env.AWS_ACCOUNT_ID || '';
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';

export function addPushResources(stack: Stack) {
  // DynamoDB: PushTokensTable
  const pushTokensTable = new dynamodb.Table(stack, 'PushTokensTable', {
    tableName: 'PushTokensTable',
    partitionKey: { name: 'deviceToken', type: dynamodb.AttributeType.STRING },
    sortKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
    billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    removalPolicy: RemovalPolicy.RETAIN,
    pointInTimeRecovery: true,
  });

  // GSI: query all devices for a user
  pushTokensTable.addGlobalSecondaryIndex({
    indexName: 'userId-index',
    partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
    projectionType: dynamodb.ProjectionType.ALL,
  });

  // IAM Policy for push-notifications Lambda
  const pushLambdaPolicy = new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: [
      'sns:CreatePlatformEndpoint',
      'sns:DeleteEndpoint',
      'sns:Publish',
      'sns:GetEndpointAttributes',
      'sns:SetEndpointAttributes',
      'dynamodb:PutItem',
      'dynamodb:GetItem',
      'dynamodb:DeleteItem',
      'dynamodb:Scan',
      'dynamodb:Query',
    ],
    resources: [
      pushTokensTable.tableArn,
      `${pushTokensTable.tableArn}/index/*`,
      `arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:app/*`,
      `arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:endpoint/*`,
    ],
  });

  return {
    pushTokensTable,
    pushLambdaPolicy,
  };
}
