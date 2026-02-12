#!/bin/bash
# infra/cli-scripts/create-iam-role.sh
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-775261844268}"
ROLE_NAME="wecare-digital-lambda-role"

# Create Lambda execution role
aws iam create-role \
  --role-name "${ROLE_NAME}" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "Role already exists"

# Attach basic Lambda execution
aws iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

# Create inline policy for EUM Social + DynamoDB + S3 + SQS + Secrets
aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name "wecare-digital-lambda-policy" \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "SocialMessagingFull",
        "Effect": "Allow",
        "Action": [
          "social-messaging:SendWhatsAppMessage",
          "social-messaging:GetWhatsAppMessageMedia",
          "social-messaging:PostWhatsAppMessageMedia",
          "social-messaging:DeleteWhatsAppMessageMedia",
          "social-messaging:GetLinkedWhatsAppBusinessAccount",
          "social-messaging:GetLinkedWhatsAppBusinessAccountPhoneNumber",
          "social-messaging:ListLinkedWhatsAppBusinessAccounts",
          "social-messaging:PutWhatsAppBusinessAccountEventDestinations",
          "social-messaging:AssociateWhatsAppBusinessAccount",
          "social-messaging:DisassociateWhatsAppBusinessAccount",
          "social-messaging:TagResource",
          "social-messaging:UntagResource",
          "social-messaging:ListTagsForResource",
          "social-messaging:CreateMessageTemplate",
          "social-messaging:GetMessageTemplate",
          "social-messaging:ListMessageTemplates",
          "social-messaging:DeleteMessageTemplate",
          "social-messaging:UpdateMessageTemplate",
          "social-messaging:SubmitMessageTemplateForReview",
          "social-messaging:GetMessageTemplatePreview",
          "social-messaging:GetWhatsAppBusinessAccountEventDestinations"
        ],
        "Resource": "*"
      },
      {
        "Sid": "DynamoDBAccess",
        "Effect": "Allow",
        "Action": [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ],
        "Resource": [
          "arn:aws:dynamodb:us-east-1:'"${ACCOUNT_ID}"':table/base-wecare-digital-*",
          "arn:aws:dynamodb:us-east-1:'"${ACCOUNT_ID}"':table/base-wecare-digital-*/index/*"
        ]
      },
      {
        "Sid": "S3MediaAccess",
        "Effect": "Allow",
        "Action": [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        "Resource": [
          "arn:aws:s3:::app.wecare.digital",
          "arn:aws:s3:::app.wecare.digital/whatsapp-media/*"
        ]
      },
      {
        "Sid": "SQSAccess",
        "Effect": "Allow",
        "Action": [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        "Resource": "arn:aws:sqs:us-east-1:'"${ACCOUNT_ID}"':base-wecare-digital-*"
      },
      {
        "Sid": "SNSPublish",
        "Effect": "Allow",
        "Action": ["sns:Publish"],
        "Resource": "arn:aws:sns:us-east-1:'"${ACCOUNT_ID}"':base-wecare-digital"
      },
      {
        "Sid": "SecretsManagerRead",
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue"],
        "Resource": "arn:aws:secretsmanager:us-east-1:'"${ACCOUNT_ID}"':secret:wecare/*"
      },
      {
        "Sid": "CloudWatchMetrics",
        "Effect": "Allow",
        "Action": ["cloudwatch:PutMetricData"],
        "Resource": "*",
        "Condition": {
          "StringEquals": {"cloudwatch:namespace": "WECARE.DIGITAL"}
        }
      },
      {
        "Sid": "LambdaInvoke",
        "Effect": "Allow",
        "Action": ["lambda:InvokeFunction"],
        "Resource": "arn:aws:lambda:us-east-1:'"${ACCOUNT_ID}"':function:wecare-*"
      }
    ]
  }'

echo "IAM role ${ROLE_NAME} created with least-privilege policy"
