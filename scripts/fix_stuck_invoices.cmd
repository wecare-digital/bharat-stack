@echo off
REM Fix invoice 079d37da - status pending_payment but paymentStatus captured
aws dynamodb update-item --table-name stack-wecare-digital-InvoicesTable --key "{\"invoiceId\":{\"S\":\"079d37da-8f93-4ab6-aa7e-716870ad3e06\"}}" --update-expression "SET #st = :st" --expression-attribute-names "{\"#st\":\"status\"}" --expression-attribute-values "{\":st\":{\"S\":\"paid\"}}" --region us-east-1 --output json

REM Fix invoice ec35ed5a - status sent but paymentStatus captured
aws dynamodb update-item --table-name stack-wecare-digital-InvoicesTable --key "{\"invoiceId\":{\"S\":\"ec35ed5a-2200-4375-8dac-efa95325b80a\"}}" --update-expression "SET #st = :st" --expression-attribute-names "{\"#st\":\"status\"}" --expression-attribute-values "{\":st\":{\"S\":\"paid\"}}" --region us-east-1 --output json

echo Done fixing stuck invoices
