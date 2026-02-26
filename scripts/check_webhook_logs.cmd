@echo off
REM Check RazorpayWebhookLogTable for payments related to 8100640044
aws dynamodb scan --table-name base-wecare-digital-RazorpayWebhookLogTable --filter-expression "contains(#ct, :phone)" --expression-attribute-names "{\"#ct\":\"contact\"}" --expression-attribute-values "{\":phone\":{\"S\":\"8100640044\"}}" --projection-expression "id, #ct, #st, referenceId, amount, createdAt" --region us-east-1 --output json
