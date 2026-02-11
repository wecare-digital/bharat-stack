@echo off
echo [1/10] wecare-contacts-create (default Contact -> needs CONTACTS_TABLE)
aws lambda update-function-configuration --function-name wecare-contacts-create --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [2/10] wecare-contacts-read
aws lambda update-function-configuration --function-name wecare-contacts-read --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [3/10] wecare-contacts-update
aws lambda update-function-configuration --function-name wecare-contacts-update --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [4/10] wecare-contacts-delete
aws lambda update-function-configuration --function-name wecare-contacts-delete --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [5/10] wecare-contacts-search
aws lambda update-function-configuration --function-name wecare-contacts-search --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [6/10] wecare-dlq-replay (default DLQMessages -> needs correct table)
aws lambda update-function-configuration --function-name wecare-dlq-replay --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,DLQ_MESSAGES_TABLE=base-wecare-digital-DLQMessagesTable,INBOUND_DLQ_URL=https://sqs.us-east-1.amazonaws.com/775261844268/base-wecare-digital-inbound-dlq,BULK_DLQ_URL=https://sqs.us-east-1.amazonaws.com/775261844268/base-wecare-digital-bulk-dlq,INBOUND_HANDLER_FUNCTION=wecare-inbound-whatsapp,BULK_WORKER_FUNCTION=wecare-bulk-worker,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [7/10] wecare-outbound-sms
aws lambda update-function-configuration --function-name wecare-outbound-sms --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,MESSAGES_TABLE=base-wecare-digital-WhatsAppOutboundTable,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [8/10] wecare-outbound-email
aws lambda update-function-configuration --function-name wecare-outbound-email --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,MESSAGES_TABLE=base-wecare-digital-WhatsAppOutboundTable,FROM_EMAIL=noreply@wecare.digital,REPLY_TO_EMAIL=support@wecare.digital,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [9/10] wecare-ai-query-kb
aws lambda update-function-configuration --function-name wecare-ai-query-kb --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,INTERNAL_KB_ID=D0JU8Q7IQS,EXTERNAL_KB_ID=LYMQLKZNY7,SEND_MODE=LIVE,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo [10/10] wecare-ai-config-management
aws lambda update-function-configuration --function-name wecare-ai-config-management --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,SYSTEM_CONFIG_TABLE=base-wecare-digital-SystemConfigTable,AI_INTERACTIONS_TABLE=base-wecare-digital-AIInteractionsTable,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
echo === ALL REMAINING ENV VARS UPDATED ===
