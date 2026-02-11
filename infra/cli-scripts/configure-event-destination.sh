#!/bin/bash
# Configure WABA event destinations to SNS topic
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="775261844268"
SNS_TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:base-wecare-digital"
WABA_1="waba-e47d916f3c7a47e1a34a19653893dd4b"
WABA_2="waba-dbe343f210204752b74c80a0a59631a6"

for WABA in "${WABA_1}" "${WABA_2}"; do
  echo "Configuring event destination for ${WABA}..."
  aws social-messaging put-whatsapp-business-account-event-destinations \
    --id "${WABA}" \
    --event-destinations "[{\"eventDestinationArn\":\"${SNS_TOPIC_ARN}\"}]" \
    --region "${REGION}"
  echo "  → ${WABA} → ${SNS_TOPIC_ARN}"
done

echo "Verifying..."
for WABA in "${WABA_1}" "${WABA_2}"; do
  aws social-messaging get-linked-whatsapp-business-account \
    --id "${WABA}" --query 'account.eventDestinations' --region "${REGION}"
done
