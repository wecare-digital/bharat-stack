import { defineFunction } from '@aws-amplify/backend';

export const faqHandler = defineFunction({
  name: 'wecare-faq-handler',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 30,
  memoryMB: 256,
});
