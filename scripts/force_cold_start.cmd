@echo off
REM Force cold start on all wecare- Lambda functions by updating description
REM This forces new execution environments that pick up the latest IAM policy

for %%F in (wecare-payments-read wecare-razorpay-webhook wecare-invoice-engine wecare-template-analytics wecare-contacts-search wecare-billing wecare-whatsapp-template-management wecare-scheduled-messages wecare-outbound-sms wecare-sms-aws) do (
    echo Updating %%F...
    aws lambda update-function-configuration --function-name %%F --description "IAM-refresh-20260306" --region us-east-1 --no-cli-pager --output text --query "FunctionName"
)

for %%F in (wecare-system-cleanup wecare-outbound-voice wecare-product-image-gen wecare-dlq-replay wecare-messages-read wecare-whatsapp-voice wecare-agent-action-group wecare-messages-delete wecare-payu-webhook wecare-contacts-read) do (
    echo Updating %%F...
    aws lambda update-function-configuration --function-name %%F --description "IAM-refresh-20260306" --region us-east-1 --no-cli-pager --output text --query "FunctionName"
)

for %%F in (wecare-faq-handler wecare-ai-config-management wecare-ai-query-kb wecare-whatsapp-business-api wecare-bulk-job-create wecare-voice-in-c2c wecare-contacts-delete wecare-contacts-update wecare-bulk-job-control wecare-bulk-worker) do (
    echo Updating %%F...
    aws lambda update-function-configuration --function-name %%F --description "IAM-refresh-20260306" --region us-east-1 --no-cli-pager --output text --query "FunctionName"
)

for %%F in (wecare-whatsapp-calling wecare-sms-in-airtel wecare-auth-middleware wecare-wix-store wecare-voice-aws wecare-voice-cdr-read) do (
    echo Updating %%F...
    aws lambda update-function-configuration --function-name %%F --description "IAM-refresh-20260306" --region us-east-1 --no-cli-pager --output text --query "FunctionName"
)

echo === All Lambda functions updated ===
