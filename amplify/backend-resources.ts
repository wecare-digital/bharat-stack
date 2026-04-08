/**
 * Additional AWS Resources Configuration
 * 
 * This file defines AWS resources that are not directly supported by Amplify Gen 2
 * but need to be created as part of the backend infrastructure.
 */

import { Stack } from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatch_actions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Duration } from 'aws-cdk-lib';

const AWS_ACCOUNT_ID = process.env.AWS_ACCOUNT_ID || '';
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';

export function addBackendResources(stack: Stack) {
  // SQS Queues
  const inboundDlq = new sqs.Queue(stack, 'InboundDLQ', {
    queueName: 'stack-wecare-digital-inbound-dlq',
    visibilityTimeout: Duration.seconds(300),
    retentionPeriod: Duration.days(7),
  });

  const bulkDlq = new sqs.Queue(stack, 'BulkDLQ', {
    queueName: 'stack-wecare-digital-bulk-dlq',
    visibilityTimeout: Duration.seconds(300),
    retentionPeriod: Duration.days(7),
  });

  const bulkQueue = new sqs.Queue(stack, 'BulkQueue', {
    queueName: 'stack-wecare-digital-bulk-queue',
    visibilityTimeout: Duration.seconds(300),
    retentionPeriod: Duration.days(1),
    deadLetterQueue: {
      queue: bulkDlq,
      maxReceiveCount: 3,
    },
  });

  const outboundDlq = new sqs.Queue(stack, 'OutboundDLQ', {
    queueName: 'stack-wecare-digital-outbound-dlq',
    visibilityTimeout: Duration.seconds(300),
    retentionPeriod: Duration.days(7),
  });

  // SNS Topic (if not already exists)
  const alarmTopic = sns.Topic.fromTopicArn(
    stack,
    'AlarmTopic',
    `arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:stack-wecare-digital`
  );

  // CloudWatch Alarms
  const lambdaErrorAlarm = new cloudwatch.Alarm(stack, 'LambdaErrorRateAlarm', {
    alarmName: 'wecare-lambda-error-rate',
    alarmDescription: 'Lambda error rate exceeds 1%',
    metric: new cloudwatch.Metric({
      namespace: 'AWS/Lambda',
      metricName: 'Errors',
      statistic: 'Average',
      period: Duration.minutes(5),
    }),
    threshold: 0.01,
    evaluationPeriods: 2,
    comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
    treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
  });
  lambdaErrorAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alarmTopic));

  const dlqDepthAlarm = new cloudwatch.Alarm(stack, 'DLQDepthAlarm', {
    alarmName: 'wecare-dlq-depth',
    alarmDescription: 'DLQ depth exceeds 10 messages',
    metric: inboundDlq.metricApproximateNumberOfMessagesVisible({
      period: Duration.minutes(5),
    }),
    threshold: 10,
    evaluationPeriods: 1,
    comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
    treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
  });
  dlqDepthAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alarmTopic));

  // CloudWatch Dashboard
  new cloudwatch.Dashboard(stack, 'WECAREDashboard', {
    dashboardName: 'WECARE-DIGITAL-Dashboard',
    widgets: [
      [
        new cloudwatch.GraphWidget({
          title: 'Message Delivery by Channel',
          left: [
            new cloudwatch.Metric({
              namespace: 'WECARE.DIGITAL',
              metricName: 'MessagesSuccess',
              dimensionsMap: { Channel: 'WHATSAPP' },
            }),
            new cloudwatch.Metric({
              namespace: 'WECARE.DIGITAL',
              metricName: 'MessagesSuccess',
              dimensionsMap: { Channel: 'SMS' },
            }),
            new cloudwatch.Metric({
              namespace: 'WECARE.DIGITAL',
              metricName: 'MessagesSuccess',
              dimensionsMap: { Channel: 'EMAIL' },
            }),
          ],
        }),
      ],
      [
        new cloudwatch.GraphWidget({
          title: 'DLQ Depth',
          left: [
            inboundDlq.metricApproximateNumberOfMessagesVisible(),
            bulkDlq.metricApproximateNumberOfMessagesVisible(),
            outboundDlq.metricApproximateNumberOfMessagesVisible(),
          ],
        }),
      ],
    ],
  });

  // ─── CloudWatch Log Retention Policies ───────────────────────────────
  // Set 90-day retention on all Lambda log groups to control costs
  const LAMBDA_FUNCTIONS = [
    'wecare-inbound-whatsapp', 'wecare-outbound-whatsapp', 'wecare-whatsapp-calling',
    'wecare-whatsapp-business-api', 'wecare-whatsapp-voice', 'wecare-whatsapp-template-management',
    'wecare-scheduled-messages', 'wecare-bulk-job-create', 'wecare-bulk-worker',
    'wecare-ai-query-kb', 'wecare-ai-generate-response', 'wecare-razorpay-webhook',
    'wecare-dlq-replay', 'wecare-contacts', 'wecare-meta-analytics',
    'wecare-catalog-management', 'wecare-ad-attribution',
    'wecare-outbound-sms', 'wecare-outbound-email', 'wecare-outbound-voice',
    'wecare-sms-aws', 'wecare-voice-aws', 'wecare-sms-in-airtel',
    'wecare-voice-in-c2c', 'wecare-voice-in-obd', 'wecare-voice-in-cdr',
    'wecare-voice-cdr-read', 'wecare-billing', 'wecare-system-cleanup',
    'wecare-bulk-job-control', 'wecare-payu-webhook', 'wecare-payments-read',
    'wecare-invoice-engine', 'wecare-wix-store', 'wecare-product-image-gen',
    'wecare-auth-middleware', 'wecare-faq-handler', 'wecare-messages-read',
    'wecare-messages-delete', 'wecare-ai-config-management', 'wecare-waba-management',
    'wecare-push-notifications', 'wecare-media-cleanup', 'wecare-template-analytics',
    'wecare-whatsapp-templates', 'wecare-agent-action-group',
  ];

  for (const fnName of LAMBDA_FUNCTIONS) {
    new logs.LogGroup(stack, `LogRetention-${fnName}`, {
      logGroupName: `/aws/lambda/${fnName}`,
      retention: logs.RetentionDays.THREE_MONTHS,
    });
  }

  // ─── Per-Lambda Error Rate Alarms ──────────────────────────────────
  const CRITICAL_LAMBDAS = [
    'wecare-inbound-whatsapp', 'wecare-outbound-whatsapp', 'wecare-whatsapp-calling',
    'wecare-razorpay-webhook', 'wecare-bulk-worker', 'wecare-payu-webhook',
    'wecare-invoice-engine', 'wecare-scheduled-messages',
  ];

  const perLambdaAlarms: cloudwatch.Alarm[] = [];
  for (const fnName of CRITICAL_LAMBDAS) {
    const alarm = new cloudwatch.Alarm(stack, `ErrorAlarm-${fnName}`, {
      alarmName: `wecare-${fnName}-errors`,
      alarmDescription: `Error rate for ${fnName} exceeds threshold`,
      metric: new cloudwatch.Metric({
        namespace: 'AWS/Lambda',
        metricName: 'Errors',
        dimensionsMap: { FunctionName: fnName },
        statistic: 'Sum',
        period: Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    alarm.addAlarmAction(new cloudwatch_actions.SnsAction(alarmTopic));
    perLambdaAlarms.push(alarm);
  }

  // ─── WAF Web ACL for Webhook Endpoints ─────────────────────────────
  const webhookWaf = new wafv2.CfnWebACL(stack, 'WebhookWAF', {
    name: 'wecare-webhook-waf',
    scope: 'REGIONAL',
    defaultAction: { allow: {} },
    visibilityConfig: {
      cloudWatchMetricsEnabled: true,
      metricName: 'wecare-webhook-waf',
      sampledRequestsEnabled: true,
    },
    rules: [
      {
        name: 'RateLimit',
        priority: 1,
        action: { block: {} },
        visibilityConfig: {
          cloudWatchMetricsEnabled: true,
          metricName: 'wecare-waf-rate-limit',
          sampledRequestsEnabled: true,
        },
        statement: {
          rateBasedStatement: {
            limit: 2000,
            aggregateKeyType: 'IP',
          },
        },
      },
      {
        name: 'AWSManagedRulesCommonRuleSet',
        priority: 2,
        overrideAction: { none: {} },
        visibilityConfig: {
          cloudWatchMetricsEnabled: true,
          metricName: 'wecare-waf-common-rules',
          sampledRequestsEnabled: true,
        },
        statement: {
          managedRuleGroupStatement: {
            vendorName: 'AWS',
            name: 'AWSManagedRulesCommonRuleSet',
          },
        },
      },
    ],
  });

  return {
    queues: {
      inboundDlq,
      bulkQueue,
      bulkDlq,
      outboundDlq,
    },
    alarms: {
      lambdaErrorAlarm,
      dlqDepthAlarm,
      perLambdaAlarms,
    },
    waf: webhookWaf,
  };
}
