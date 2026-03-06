@echo off
aws dynamodb scan --table-name stack-wecare-digital-InvoicesTable --filter-expression "contains(customerPhone, :phone)" --expression-attribute-values "{\":phone\":{\"S\":\"8100640044\"}}" --region us-east-1 --output json
