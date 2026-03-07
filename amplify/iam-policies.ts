/**
 * IAM Policies for Lambda Functions
 * 
 * Defines the permissions required for each Lambda function to access AWS services.
 */

const AWS_ACCOUNT_ID = process.env.AWS_ACCOUNT_ID || '775261844268';
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';

export const IAM_POLICIES = {
  // Common permissions for all Lambda functions
  common: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'logs:CreateLogGroup',
          'logs:CreateLogStream',
          'logs:PutLogEvents',
        ],
        Resource: `arn:aws:logs:${AWS_REGION}:${AWS_ACCOUNT_ID}:log-group:/stack-wecare-digital/*`,
      },
      {
        Effect: 'Allow',
        Action: [
          'dynamodb:GetItem',
          'dynamodb:PutItem',
          'dynamodb:UpdateItem',
          'dynamodb:DeleteItem',
          'dynamodb:Query',
          'dynamodb:Scan',
        ],
        Resource: [
          `arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/stack-wecare-digital-*`,
        ],
      },
      {
        Effect: 'Allow',
        Action: [
          'cloudwatch:PutMetricData',
        ],
        Resource: '*',
        Condition: {
          StringEquals: {
            'cloudwatch:namespace': 'WECARE.DIGITAL',
          },
        },
      },
    ],
  },

  // WhatsApp-specific permissions
  whatsapp: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'social-messaging:SendWhatsAppMessage',
          'social-messaging:GetWhatsAppMessageMedia',
          'social-messaging:PostWhatsAppMessageMedia',
          'social-messaging:DeleteWhatsAppMessageMedia',
        ],
        Resource: [
          // Phone Number 1: WECARE.DIGITAL (+91 93309 94400)
          `arn:aws:social-messaging:${AWS_REGION}:${AWS_ACCOUNT_ID}:phone-number-id/5e020cecd221429996f6ae721cc42206`,
          // Phone Number 2: Manish Agarwal (+91 99033 00044)
          `arn:aws:social-messaging:${AWS_REGION}:${AWS_ACCOUNT_ID}:phone-number-id/abdd81f7bec24ec085a25ab9df6a6f7c`,
          // WABA 1: WECARE.DIGITAL (Meta ID: 1912405516040025)
          `arn:aws:social-messaging:${AWS_REGION}:${AWS_ACCOUNT_ID}:waba/e47d916f3c7a47e1a34a19653893dd4b`,
          // WABA 2: Manish Agarwal (Meta ID: 1633959101297902)
          `arn:aws:social-messaging:${AWS_REGION}:${AWS_ACCOUNT_ID}:waba/dbe343f210204752b74c80a0a59631a6`,
        ],
      },
      {
        Effect: 'Allow',
        Action: [
          's3:GetObject',
          's3:PutObject',
          's3:DeleteObject',
          's3:ListBucket',
        ],
        Resource: [
          'arn:aws:s3:::app.wecare.digital',
          'arn:aws:s3:::app.wecare.digital/*',
        ],
      },
    ],
  },

  // SMS-specific permissions
  sms: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'sms-voice:SendTextMessage',
          'sms-voice:SendVoiceMessage',
        ],
        Resource: `arn:aws:sms-voice:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`,
      },
    ],
  },

  // Email-specific permissions
  email: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'ses:SendEmail',
          'ses:SendRawEmail',
        ],
        Resource: `arn:aws:ses:${AWS_REGION}:${AWS_ACCOUNT_ID}:identity/one@wecare.digital`,
      },
    ],
  },

  // SQS permissions
  sqs: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'sqs:SendMessage',
          'sqs:ReceiveMessage',
          'sqs:DeleteMessage',
          'sqs:GetQueueAttributes',
        ],
        Resource: [
          `arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:stack-wecare-digital-inbound-dlq`,
          `arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:stack-wecare-digital-bulk-queue`,
          `arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:stack-wecare-digital-bulk-dlq`,
          `arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:stack-wecare-digital-outbound-dlq`,
        ],
      },
    ],
  },

  // SNS permissions
  sns: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'sns:Publish',
        ],
        Resource: `arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:stack-wecare-digital`,
      },
    ],
  },

  // Bedrock AI permissions
  bedrock: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'bedrock:InvokeModel',
          'bedrock:InvokeAgent',
          'bedrock:Retrieve',
        ],
        Resource: [
          `arn:aws:bedrock:${AWS_REGION}:${AWS_ACCOUNT_ID}:knowledge-base/*`,
          `arn:aws:bedrock:${AWS_REGION}:${AWS_ACCOUNT_ID}:agent/*`,
          'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0',
        ],
      },
      {
        Effect: 'Allow',
        Action: [
          's3:GetObject',
          's3:PutObject',
        ],
        Resource: 'arn:aws:s3:::app.wecare.digital/*',
      },
    ],
  },

  // Cost Explorer permissions (for billing)
  billing: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'ce:GetCostAndUsage',
          'ce:GetCostForecast',
          'ce:GetDimensionValues',
          'ce:GetTags',
        ],
        Resource: '*',
      },
      {
        Effect: 'Allow',
        Action: [
          'health:DescribeEvents',
          'health:DescribeEventDetails',
          'health:DescribeAffectedEntities',
        ],
        Resource: '*',
      },
      {
        Effect: 'Allow',
        Action: [
          'support:DescribeTrustedAdvisorChecks',
          'support:DescribeTrustedAdvisorCheckSummaries',
          'support:DescribeTrustedAdvisorCheckResult',
          'support:RefreshTrustedAdvisorCheck',
        ],
        Resource: '*',
      },
    ],
  },

  // Cognito permissions
  cognito: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'cognito-idp:AdminGetUser',
          'cognito-idp:AdminListGroupsForUser',
          'cognito-idp:GetUser',
        ],
        Resource: `arn:aws:cognito-idp:${AWS_REGION}:${AWS_ACCOUNT_ID}:userpool/us-east-1_cSx0RHCIR`,
      },
    ],
  },

  // Secrets Manager permissions (for Airtel API credentials)
  secrets: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'secretsmanager:GetSecretValue',
        ],
        Resource: [
          `arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:wecare/*`,
        ],
      },
    ],
  },

  // S3 permissions (for non-WhatsApp S3 access — voice recordings, OBD uploads, etc.)
  s3: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          's3:GetObject',
          's3:PutObject',
          's3:DeleteObject',
          's3:ListBucket',
        ],
        Resource: [
          'arn:aws:s3:::app.wecare.digital',
          'arn:aws:s3:::app.wecare.digital/*',
        ],
      },
    ],
  },

  // Amazon Polly permissions (for TTS)
  polly: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'polly:SynthesizeSpeech',
          'polly:DescribeVoices',
        ],
        Resource: '*',
      },
    ],
  },

  // Lambda invoke permissions (for scheduled-messages invoking outbound lambdas)
  lambdaInvoke: {
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Action: [
          'lambda:InvokeFunction',
        ],
        Resource: `arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:wecare-*`,
      },
    ],
  },
};

/**
 * Function-specific policy mappings
 * 
 * Maps each Lambda function to the policies it requires.
 * Naming: use full Lambda function name (wecare-* prefix) for deployed functions,
 * short names for Amplify-managed functions.
 */
export const FUNCTION_POLICIES: Record<string, string[]> = {
  // === Core ===
  'wecare-auth-middleware': ['common', 'cognito'],
  'wecare-contacts': ['common'],  // Unified contacts handler
  'wecare-messages-read': ['common'],
  'wecare-messages-delete': ['common'],

  // === WhatsApp ===
  'wecare-inbound-whatsapp': ['common', 'whatsapp', 'sqs', 'sns', 'lambdaInvoke'],
  'wecare-outbound-whatsapp': ['common', 'whatsapp', 'sqs'],
  'wecare-whatsapp-calling': ['common', 'whatsapp', 'secrets'],
  'wecare-whatsapp-voice': ['common', 'whatsapp', 'polly'],
  'wecare-whatsapp-template-management': ['common', 'whatsapp', 'secrets'],
  'wecare-whatsapp-templates': ['common', 'whatsapp', 'secrets'], // alias
  'wecare-whatsapp-business-api': ['common', 'secrets'],
  'wecare-waba-management': ['common', 'whatsapp'],
  'wecare-media-cleanup': ['common', 'whatsapp'],
  'wecare-template-analytics': ['common'],

  // === SMS ===
  'wecare-outbound-sms': ['common', 'sms', 'sqs'],
  'wecare-outbound-email': ['common', 'email', 'sqs'],
  'wecare-sms-aws': ['common', 'sms'],
  'wecare-sms-in-airtel': ['common', 'secrets'],

  // === Voice (AWS Pinpoint) ===
  'wecare-voice-aws': ['common', 'sms'],

  // === Voice (Airtel IQ — voice-in) ===
  'wecare-voice-in-c2c': ['common', 'secrets', 's3'],
  'wecare-voice-in-obd': ['common', 'secrets', 's3'],
  'wecare-voice-in-cdr': ['common', 's3'],              // CDR webhook (alias route)
  'wecare-voice-cdr-webhook': ['common', 's3'],          // CDR webhook (primary route)
  'wecare-voice-cdr-read': ['common'],
  'wecare-voice-calls-read': ['common'],                  // alias of voice-cdr-read
  'wecare-outbound-voice': ['common', 'secrets'],
  'wecare-voice-calls': ['common', 'secrets'],            // alias of outbound-voice

  // === Scheduled & Bulk ===
  'wecare-scheduled-messages': ['common', 'lambdaInvoke'],
  'wecare-bulk-job-create': ['common', 'sqs'],
  'wecare-bulk-worker': ['common', 'sqs', 'whatsapp', 'sms', 'email'],
  'wecare-bulk-job-control': ['common', 'sqs', 's3'],

  // === AI ===
  'wecare-ai-query-kb': ['common', 'bedrock'],
  'wecare-ai-generate-response': ['common', 'bedrock'],
  'wecare-ai-config-management': ['common'],
  'wecare-agent-action-group': ['common', 'bedrock', 'lambdaInvoke'],

  // === Operations ===
  'wecare-dlq-replay': ['common', 'sqs', 'sns'],
  'wecare-billing': ['common', 'billing'],

  // === Payments ===
  'wecare-razorpay-webhook': ['common', 'lambdaInvoke'],
  'wecare-payu-webhook': ['common'],
  'wecare-payments-read': ['common'],
  'wecare-invoice-engine': ['common', 'whatsapp', 'lambdaInvoke'],

  // === Ecommerce ===
  'wecare-wix-store': ['common'],
  'wecare-product-image-gen': ['common', 's3'],

  // === Operations (additional) ===
  'wecare-system-cleanup': ['common', 'sqs', 's3'],

  // === Core (additional) ===
  'wecare-faq-handler': ['common'],
};
