@echo off
echo === wecare-bulk-job-create === >> envs-output.txt
aws lambda get-function-configuration --function-name wecare-bulk-job-create --query Environment.Variables --output json --region us-east-1 --no-cli-pager >> envs-output.txt 2>&1
echo === wecare-bulk-job-control === >> envs-output.txt
aws lambda get-function-configuration --function-name wecare-bulk-job-control --query Environment.Variables --output json --region us-east-1 --no-cli-pager >> envs-output.txt 2>&1
echo === wecare-bulk-worker === >> envs-output.txt
aws lambda get-function-configuration --function-name wecare-bulk-worker --query Environment.Variables --output json --region us-east-1 --no-cli-pager >> envs-output.txt 2>&1
echo === wecare-scheduled-messages === >> envs-output.txt
aws lambda get-function-configuration --function-name wecare-scheduled-messages --query Environment.Variables --output json --region us-east-1 --no-cli-pager >> envs-output.txt 2>&1
echo === wecare-inbound-whatsapp === >> envs-output.txt
aws lambda get-function-configuration --function-name wecare-inbound-whatsapp --query Environment.Variables --output json --region us-east-1 --no-cli-pager >> envs-output.txt 2>&1
echo === wecare-outbound-whatsapp === >> envs-output.txt
aws lambda get-function-configuration --function-name wecare-outbound-whatsapp --query Environment.Variables --output json --region us-east-1 --no-cli-pager >> envs-output.txt 2>&1
echo === wecare-auth-middleware === >> envs-output.txt
aws lambda get-function-configuration --function-name wecare-auth-middleware --query Environment.Variables --output json --region us-east-1 --no-cli-pager >> envs-output.txt 2>&1
echo === DONE === >> envs-output.txt
