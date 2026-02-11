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
        Resource: 'arn:aws:logs:us-east-1:775261844268:log-group:/base-wecare-digital/*',
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
          'arn:aws:dynamodb:us-east-1:775261844268:table/base-wecare-digital-*',
          // Legacy table patterns (for backwards compatibility)
          'arn:aws:dynamodb:us-east-1:775261844268:table/Contact-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/Message-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/BulkJob-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/BulkRecipient-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/User-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/MediaFile-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/DLQMessage-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/AuditLog-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/AIInteraction-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/RateLimitTracker-*',
          'arn:aws:dynamodb:us-east-1:775261844268:table/SystemConfig-*',
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
          'arn:aws:social-messaging:us-east-1:775261844268:phone-number-id/5e020cecd221429996f6ae721cc42206',
          // Phone Number 2: Manish Agarwal (+91 99033 00044)
          'arn:aws:social-messaging:us-east-1:775261844268:phone-number-id/abdd81f7bec24ec085a25ab9df6a6f7c',
          // WABA 1: WECARE.DIGITAL (Meta ID: 1912405516040025)
          'arn:aws:social-messaging:us-east-1:775261844268:waba/e47d916f3c7a47e1a34a19653893dd4b',
          // WABA 2: Manish Agarwal (Meta ID: 1633959101297902)
          'arn:aws:social-messaging:us-east-1:775261844268:waba/dbe343f210204752b74c80a0a59631a6',
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
        Resource: 'arn:aws:sms-voice:us-east-1:775261844268:*',
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
        Resource: 'arn:aws:ses:us-east-1:775261844268:identity/one@wecare.digital',
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
          'arn:aws:sqs:us-east-1:775261844268:base-wecare-digital-inbound-dlq',
          'arn:aws:sqs:us-east-1:775261844268:base-wecare-digital-bulk-queue',
          'arn:aws:sqs:us-east-1:775261844268:base-wecare-digital-bulk-dlq',
          'arn:aws:sqs:us-east-1:775261844268:base-wecare-digital-outbound-dlq',
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
        Resource: 'arn:aws:sns:us-east-1:775261844268:base-wecare-digital',
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
          'arn:aws:bedrock:us-east-1:775261844268:knowledge-base/*',
          'arn:aws:bedrock:us-east-1:775261844268:agent/*',
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
        Resource: 'arn:aws:cognito-idp:us-east-1:775261844268:userpool/us-east-1_CC9u1fYh6',
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
          'arn:aws:secretsmanager:us-east-1:775261844268:secret:wecare/airtel/*',
        ],
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
  'wecare-sms-in-airtel': ['common', 'secrets'],
  'sms-aws': ['common', 'sms'],
  'voice-aws': ['common', 'sms'],
  'wecare-voice-in-c2c': ['common', 'secrets'],
  'wecare-voice-in-obd': ['common', 'secrets'],
  'wecare-voice-cdr-webhook': ['common'],
};
