@echo off
echo === wecare-contacts-create ===
aws lambda get-function-configuration --function-name wecare-contacts-create --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-contacts-read ===
aws lambda get-function-configuration --function-name wecare-contacts-read --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-messages-read ===
aws lambda get-function-configuration --function-name wecare-messages-read --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-dlq-replay ===
aws lambda get-function-configuration --function-name wecare-dlq-replay --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-template-analytics ===
aws lambda get-function-configuration --function-name wecare-template-analytics --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-ai-config-management ===
aws lambda get-function-configuration --function-name wecare-ai-config-management --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-ai-query-kb ===
aws lambda get-function-configuration --function-name wecare-ai-query-kb --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === wecare-waba-management ===
aws lambda get-function-configuration --function-name wecare-waba-management --query Environment.Variables --output json --region us-east-1 --no-cli-pager
echo === DONE ===
