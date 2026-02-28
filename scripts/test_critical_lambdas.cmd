@echo off
echo === contacts ===
aws lambda invoke --function-name wecare-contacts --payload "{}" --region us-east-1 scripts\_t1.json --output json --query "StatusCode"
type scripts\_t1.json
echo.
echo === messages-read ===
aws lambda invoke --function-name wecare-messages-read --payload "{}" --region us-east-1 scripts\_t2.json --output json --query "StatusCode"
type scripts\_t2.json
echo.
echo === scheduled-messages ===
aws lambda invoke --function-name wecare-scheduled-messages --payload "{}" --region us-east-1 scripts\_t3.json --output json --query "StatusCode"
type scripts\_t3.json
echo.
echo === ai-generate-response ===
aws lambda invoke --function-name wecare-ai-generate-response --payload "{}" --region us-east-1 scripts\_t4.json --output json --query "StatusCode"
type scripts\_t4.json
echo.
echo === voice-aws ===
aws lambda invoke --function-name wecare-voice-aws --payload "{}" --region us-east-1 scripts\_t5.json --output json --query "StatusCode"
type scripts\_t5.json
echo.
echo === sms-aws ===
aws lambda invoke --function-name wecare-sms-aws --payload "{}" --region us-east-1 scripts\_t6.json --output json --query "StatusCode"
type scripts\_t6.json
echo.
