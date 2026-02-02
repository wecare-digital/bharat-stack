/**
 * IAM Policies for Lambda Functions
 * 
 * Defines the permissions required for each Lambda function to access AWS services.
 */

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
        Resource: 'arn:aws:logs:us-east-1:809904170947:log-group:/base-wecare-digital/*',
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
          // Actual tables used by the system (base-wecare-digital-* prefix)
          'arn:aws:dynamodb:us-east-1:809904170947:table/base-wecare-digital-*',
          // Legacy table patterns (for backwards compatibility)
          'arn:aws:dynamodb:us-east-1:809904170947:table/Contact-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/Message-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/BulkJob-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/BulkRecipient-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/User-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/MediaFile-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/DLQMessage-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/AuditLog-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/AIInteraction-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/RateLimitTracker-*',
          'arn:aws:dynamodb:us-east-1:809904170947:table/SystemConfig-*',
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
          'arn:aws:social-messaging:us-east-1:809904170947:phone-number-id/phone-number-id-baa217c3f11b4ffd956f6f3afb44ce54',
          // Phone Number 2: Manish Agarwal (+91 99033 00044)
          'arn:aws:social-messaging:us-east-1:809904170947:phone-number-id/phone-number-id-1447bc72d1b040f4bf2341c9e04b2e06',
          // WABA 1: WECARE.DIGITAL
          'arn:aws:social-messaging:us-east-1:809904170947:waba/waba-0aae9cf04cf24c66960f291c793359b4',
          // WABA 2: Manish Agarwal
          'arn:aws:social-messaging:us-east-1:809904170947:waba/waba-9bbe054d8404487397c38a9d197bc44a',
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
          'arn:aws:s3:::auth.wecare.digital',
          'arn:aws:s3:::auth.wecare.digital/*',
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
        ],
        Resource: 'arn:aws:sms-voice:us-east-1:809904170947:pool/pool-6fbf5a5f390d4eeeaa7dbae39d78933e',
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
        Resource: 'arn:aws:ses:us-east-1:809904170947:identity/one@wecare.digital',
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
          'arn:aws:sqs:us-east-1:809904170947:base-wecare-digital-inbound-dlq',
          'arn:aws:sqs:us-east-1:809904170947:base-wecare-digital-bulk-queue',
          'arn:aws:sqs:us-east-1:809904170947:base-wecare-digital-bulk-dlq',
          'arn:aws:sqs:us-east-1:809904170947:base-wecare-digital-outbound-dlq',
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
        Resource: 'arn:aws:sns:us-east-1:809904170947:base-wecare-digital',
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
          'arn:aws:bedrock:us-east-1:809904170947:knowledge-base/*',
          'arn:aws:bedrock:us-east-1:809904170947:agent/*',
          'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0',
        ],
      },
      {
        Effect: 'Allow',
        Action: [
          's3:GetObject',
          's3:PutObject',
        ],
        Resource: 'arn:aws:s3:::auth.wecare.digital/*',
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
        Resource: 'arn:aws:cognito-idp:us-east-1:809904170947:userpool/us-east-1_CC9u1fYh6',
      },
    ],
  },
};

/**
 * Function-specific policy mappings
 * 
 * Maps each Lambda function to the policies it requires.
 */
export const FUNCTION_POLICIES = {
  'auth-middleware': ['common', 'cognito'],
  'contacts-create': ['common'],
  'contacts-read': ['common'],
  'contacts-update': ['common'],
  'contacts-delete': ['common'],
  'contacts-search': ['common'],
  'inbound-whatsapp-handler': ['common', 'whatsapp', 'sqs', 'sns'],
  'outbound-whatsapp': ['common', 'whatsapp', 'sqs'],
  'outbound-sms': ['common', 'sms', 'sqs'],
  'outbound-email': ['common', 'email', 'sqs'],
  'bulk-job-create': ['common', 'sqs'],
  'bulk-worker': ['common', 'sqs', 'whatsapp', 'sms', 'email'],
  'bulk-job-control': ['common', 'sqs'],
  'dlq-replay': ['common', 'sqs', 'sns'],
  'ai-query-kb': ['common', 'bedrock'],
  'ai-generate-response': ['common', 'bedrock'],
  'billing': ['common', 'billing'],
};
