@echo off
aws dynamodb get-item --table-name base-wecare-digital-InvoicesTable --key "{\"invoiceId\":{\"S\":\"079d37da-8f93-4ab6-aa7e-716870ad3e06\"}}" --projection-expression "invoiceId, #st, paymentStatus, referenceId" --expression-attribute-names "{\"#st\":\"status\"}" --region us-east-1 --output json
echo ---
aws dynamodb get-item --table-name base-wecare-digital-InvoicesTable --key "{\"invoiceId\":{\"S\":\"ec35ed5a-2200-4375-8dac-efa95325b80a\"}}" --projection-expression "invoiceId, #st, paymentStatus, referenceId" --expression-attribute-names "{\"#st\":\"status\"}" --region us-east-1 --output json
