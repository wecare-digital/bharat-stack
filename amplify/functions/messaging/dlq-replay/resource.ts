import { defineFunction } from '@aws-amplify/backend';

export const dlqReplay = defineFunction({
  name: 'wecare-dlq-replay',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    DLQ_URL: 'https://sqs.us-east-1.amazonaws.com/775261844268/base-wecare-digital-inbound-dlq',
    SNS_TOPIC_ARN: 'arn:aws:sns:us-east-1:775261844268:base-wecare-digital',
    MAX_MESSAGES: '10',
  },
});
