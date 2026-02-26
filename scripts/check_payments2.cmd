@echo off
aws dynamodb scan --table-name base-wecare-digital-PaymentsTable --filter-expression "contains(contact, :phone)" --expression-attribute-values "{\":phone\":{\"S\":\"8100640044\"}}" --projection-expression "paymentId, referenceId, notes, description" --region us-east-1 --output json
