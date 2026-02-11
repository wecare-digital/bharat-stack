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
import { Duration } from 'aws-cdk-lib';

export function addBackendResources(stack: Stack) {
  // SQS Queues
  const inboundDlq = new sqs.Queue(stack, 'InboundDLQ', {
    queueName: 'base-wecare-digital-inbound-dlq',
    visibilityTimeout: Duration.seconds(300),
    retentionPeriod: Duration.days(7),
  });

  const bulkDlq = new sqs.Queue(stack, 'BulkDLQ', {
    queueName: 'base-wecare-digital-bulk-dlq',
    visibilityTimeout: Duration.seconds(300),
    retentionPeriod: Duration.days(7),
  });

  const bulkQueue = new sqs.Queue(stack, 'BulkQueue', {
    queueName: 'base-wecare-digital-bulk-queue',
    visibilityTimeout: Duration.seconds(300),
    retentionPeriod: Duration.days(1),
    deadLetterQueue: {
      queue: bulkDlq,
      maxReceiveCount: 3,
    },
  });

  const outboundDlq = new sqs.Queue(stack, 'OutboundDLQ', {
    queueName: 'base-wecare-digital-outbound-dlq',
    visibilityTimeout: Duration.seconds(300),
    retentionPeriod: Duration.days(7),
  });

  // SNS Topic (if not already exists)
  const alarmTopic = sns.Topic.fromTopicArn(
    stack,
    'AlarmTopic',
    'arn:aws:sns:us-east-1:775261844268:base-wecare-digital'
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
    },
  };
}
