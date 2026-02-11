#!/bin/bash
# infra/cli-scripts/create-log-groups.sh
set -euo pipefail

REGION="us-east-1"
RETENTION_DAYS=30

for FUNC in wecare-inbound-whatsapp wecare-outbound-whatsapp wecare-waba-management wecare-dlq-replay; do
  aws logs create-log-group \
    --log-group-name "/aws/lambda/${FUNC}" \
    --region "${REGION}" 2>/dev/null || echo "Log group exists: ${FUNC}"

  aws logs put-retention-policy \
    --log-group-name "/aws/lambda/${FUNC}" \
    --retention-in-days "${RETENTION_DAYS}" \
    --region "${REGION}"
done

echo "Log groups created with ${RETENTION_DAYS}-day retention"
