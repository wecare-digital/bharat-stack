@echo off
echo === wecare-bulk-job-create ===
aws lambda get-function-configuration --function-name wecare-bulk-job-create --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-bulk-job-control ===
aws lambda get-function-configuration --function-name wecare-bulk-job-control --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-bulk-worker ===
aws lambda get-function-configuration --function-name wecare-bulk-worker --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-scheduled-messages ===
aws lambda get-function-configuration --function-name wecare-scheduled-messages --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-inbound-whatsapp ===
aws lambda get-function-configuration --function-name wecare-inbound-whatsapp --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-outbound-whatsapp ===
aws lambda get-function-configuration --function-name wecare-outbound-whatsapp --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-whatsapp-calling ===
aws lambda get-function-configuration --function-name wecare-whatsapp-calling --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-whatsapp-business-api ===
aws lambda get-function-configuration --function-name wecare-whatsapp-business-api --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-auth-middleware ===
aws lambda get-function-configuration --function-name wecare-auth-middleware --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-outbound-voice ===
aws lambda get-function-configuration --function-name wecare-outbound-voice --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-sms-in-airtel ===
aws lambda get-function-configuration --function-name wecare-sms-in-airtel --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-voice-in-c2c ===
aws lambda get-function-configuration --function-name wecare-voice-in-c2c --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-voice-in-obd ===
aws lambda get-function-configuration --function-name wecare-voice-in-obd --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === DONE ===
