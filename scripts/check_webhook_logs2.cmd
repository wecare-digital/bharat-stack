@echo off
aws dynamodb scan --table-name stack-wecare-digital-RazorpayWebhookLogTable --filter-expression "contains(contact, :phone)" --expression-attribute-values "{\":phone\":{\"S\":\"8100640044\"}}" --projection-expression "id, contact, referenceId, amount, createdAt" --region us-east-1 --output json
