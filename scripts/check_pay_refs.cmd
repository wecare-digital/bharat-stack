@echo off
aws dynamodb get-item --table-name base-wecare-digital-PaymentsTable --key "{\"id\":{\"S\":\"pay_SKl9E75njV8B8A\"}}" --projection-expression "paymentId, referenceId, notes, description" --region us-east-1 --output json
echo ---
aws dynamodb get-item --table-name base-wecare-digital-PaymentsTable --key "{\"id\":{\"S\":\"pay_SKlA3k7h9ooQZ1\"}}" --projection-expression "paymentId, referenceId, notes, description" --region us-east-1 --output json
