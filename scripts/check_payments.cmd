@echo off
aws dynamodb scan --table-name stack-wecare-digital-PaymentsTable --filter-expression "contains(contact, :phone)" --expression-attribute-values "{\":phone\":{\"S\":\"8100640044\"}}" --projection-expression "paymentId, contact, referenceId, amountInRupees, #st, createdAt" --expression-attribute-names "{\"#st\":\"status\"}" --region us-east-1 --output json
