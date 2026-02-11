#!/bin/bash
# Create SNS standard topic with EUM Social publish policy
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="775261844268"
TOPIC_NAME="base-wecare-digital"
TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:${TOPIC_NAME}"

aws sns create-topic --name "${TOPIC_NAME}" --region "${REGION}" --output text --query 'TopicArn'

aws sns set-topic-attributes \
  --topic-arn "${TOPIC_ARN}" \
  --attribute-name Policy \
  --attribute-value '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "AllowEUMSocialPublish",
      "Effect": "Allow",
      "Principal": {"Service": "social-messaging.amazonaws.com"},
      "Action": "sns:Publish",
      "Resource": "'"${TOPIC_ARN}"'",
      "Condition": {"StringEquals": {"aws:SourceAccount": "'"${ACCOUNT_ID}"'"}}
    }]
  }' \
  --region "${REGION}"

echo "SNS topic ${TOPIC_ARN} ready with EUM Social publish policy"
