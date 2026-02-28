@echo off
aws dynamodb update-item --table-name base-wecare-digital-InvoicesTable --key "{\"invoiceId\":{\"S\":\"2193f47c-d687-44af-bd0e-20ca2a6446b9\"}}" --update-expression "SET #st = :st" --expression-attribute-names "{\"#st\":\"status\"}" --expression-attribute-values "{\":st\":{\"S\":\"paid\"}}" --region us-east-1 --output json
echo Fixed invoice 2193f47c status to paid
