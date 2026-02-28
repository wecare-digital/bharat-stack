@echo off
echo === Testing inbound-whatsapp ===
aws lambda invoke --function-name wecare-inbound-whatsapp --payload "{}" --region us-east-1 scripts\_test_inbound.json --output json --query "StatusCode"
type scripts\_test_inbound.json
echo.
echo === Testing invoice-engine ===
aws lambda invoke --function-name wecare-invoice-engine --payload "{}" --region us-east-1 scripts\_test_invoice.json --output json --query "StatusCode"
type scripts\_test_invoice.json
echo.
echo === Testing whatsapp-business-api ===
aws lambda invoke --function-name wecare-whatsapp-business-api --payload "{}" --region us-east-1 scripts\_test_wba.json --output json --query "StatusCode"
type scripts\_test_wba.json
echo.
echo === Testing razorpay-webhook ===
aws lambda invoke --function-name wecare-razorpay-webhook --payload "{}" --region us-east-1 scripts\_test_rzp.json --output json --query "StatusCode"
type scripts\_test_rzp.json
echo.
