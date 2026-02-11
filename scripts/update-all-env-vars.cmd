@echo off
echo [1/13] wecare-scheduled-messages
aws lambda update-function-configuration --function-name wecare-scheduled-messages --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,SCHEDULED_TABLE=base-wecare-digital-ScheduledMessagesTable,CONTACTS_TABLE=base-wecare-digital-ContactsTable,OUTBOUND_LAMBDA=wecare-outbound-whatsapp,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-scheduled-messages

echo [2/13] wecare-bulk-job-create
aws lambda update-function-configuration --function-name wecare-bulk-job-create --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,BULK_JOBS_TABLE=base-wecare-digital-BulkJobsTable,BULK_RECIPIENTS_TABLE=base-wecare-digital-BulkRecipientsTable,BULK_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/775261844268/base-wecare-digital-bulk-queue,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-bulk-job-create

echo [3/13] wecare-bulk-job-control
aws lambda update-function-configuration --function-name wecare-bulk-job-control --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,BULK_JOBS_TABLE=base-wecare-digital-BulkJobsTable,BULK_RECIPIENTS_TABLE=base-wecare-digital-BulkRecipientsTable,BULK_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/775261844268/base-wecare-digital-bulk-queue,REPORT_BUCKET=app.wecare.digital,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-bulk-job-control

echo [4/13] wecare-bulk-worker
aws lambda update-function-configuration --function-name wecare-bulk-worker --environment "Variables={CONTACTS_TABLE=base-wecare-digital-ContactsTable,SEND_MODE=LIVE,BULK_JOBS_TABLE=base-wecare-digital-BulkJobsTable,BULK_RECIPIENTS_TABLE=base-wecare-digital-BulkRecipientsTable,DEFAULT_PHONE_NUMBER_ID=phone-number-id-5e020cecd221429996f6ae721cc42206,OUTBOUND_TABLE=base-wecare-digital-WhatsAppOutboundTable,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-bulk-worker

echo [5/13] wecare-inbound-whatsapp
aws lambda update-function-configuration --function-name wecare-inbound-whatsapp --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,MESSAGES_TABLE=base-wecare-digital-WhatsAppInboundTable,MEDIA_FILES_TABLE=base-wecare-digital-MediaFilesTable,SYSTEM_CONFIG_TABLE=base-wecare-digital-SystemConfigTable,AI_INTERACTIONS_TABLE=base-wecare-digital-AIInteractionsTable,MEDIA_BUCKET=app.wecare.digital,SEND_MODE=LIVE,AI_QUERY_KB_FUNCTION=wecare-ai-query-kb,AI_GENERATE_RESPONSE_FUNCTION=wecare-ai-generate-response,OUTBOUND_WHATSAPP_FUNCTION=wecare-outbound-whatsapp,WHATSAPP_PHONE_NUMBER_ID_1=phone-number-id-5e020cecd221429996f6ae721cc42206,WHATSAPP_PHONE_NUMBER_ID_2=phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-inbound-whatsapp

echo [6/13] wecare-outbound-whatsapp
aws lambda update-function-configuration --function-name wecare-outbound-whatsapp --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,MESSAGES_TABLE=base-wecare-digital-WhatsAppOutboundTable,MEDIA_FILES_TABLE=base-wecare-digital-MediaFilesTable,RATE_LIMIT_TABLE=base-wecare-digital-RateLimitTable,MEDIA_BUCKET=app.wecare.digital,SEND_MODE=LIVE,WHATSAPP_PHONE_NUMBER_ID_1=phone-number-id-5e020cecd221429996f6ae721cc42206,WHATSAPP_PHONE_NUMBER_ID_2=phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-outbound-whatsapp

echo [7/13] wecare-whatsapp-calling
aws lambda update-function-configuration --function-name wecare-whatsapp-calling --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CALL_LOG_TABLE=base-wecare-digital-WhatsAppCallingTable,META_TOKEN_SECRET=wecare/meta-system-user-token,SYSTEM_CONFIG_TABLE=base-wecare-digital-SystemConfigTable,MEDIA_BUCKET=app.wecare.digital,WHATSAPP_PHONE_NUMBER_ID_1=phone-number-id-5e020cecd221429996f6ae721cc42206,WHATSAPP_PHONE_NUMBER_ID_2=phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-whatsapp-calling

echo [8/13] wecare-whatsapp-business-api
aws lambda update-function-configuration --function-name wecare-whatsapp-business-api --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,META_TOKEN_SECRET=wecare/meta-system-user-token,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-whatsapp-business-api

echo [9/13] wecare-sms-in-airtel
aws lambda update-function-configuration --function-name wecare-sms-in-airtel --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,AIRTEL_SMS_TABLE=base-wecare-digital-AirtelSMSTable,DLT_TEMPLATES_TABLE=base-wecare-digital-DLTTemplates,CONTACTS_TABLE=base-wecare-digital-ContactsTable,AIRTEL_SMS_SECRET_NAME=wecare/airtel/sms,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-sms-in-airtel

echo [10/13] wecare-voice-in-c2c
aws lambda update-function-configuration --function-name wecare-voice-in-c2c --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,AIRTEL_C2C_TABLE=base-wecare-digital-AirtelC2CTable,AIRTEL_C2C_SECRET_NAME=wecare/airtel/c2c,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-voice-in-c2c

echo [11/13] wecare-voice-in-obd
aws lambda update-function-configuration --function-name wecare-voice-in-obd --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,OBD_CAMPAIGNS_TABLE=base-wecare-digital-OBDCampaigns,AIRTEL_OBD_SECRET_NAME=wecare/airtel/obd,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-voice-in-obd

echo [12/13] wecare-ai-generate-response
aws lambda update-function-configuration --function-name wecare-ai-generate-response --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,INTERNAL_AGENT_ID=QIEEHEBTZO,INTERNAL_AGENT_ALIAS=ASCBD7YPUT,INTERNAL_KB_ID=D0JU8Q7IQS,EXTERNAL_AGENT_ID=Z4YAK0ZLBO,EXTERNAL_AGENT_ALIAS=WANPKHQGIB,EXTERNAL_KB_ID=LYMQLKZNY7,SEND_MODE=LIVE,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-ai-generate-response

echo [13/13] wecare-agent-action-group
aws lambda update-function-configuration --function-name wecare-agent-action-group --environment "Variables={S3_BUCKET=app.wecare.digital,AWS_ACCOUNT_ID=775261844268,REGION=us-east-1,CONTACTS_TABLE=base-wecare-digital-ContactsTable,MESSAGES_INBOUND_TABLE=base-wecare-digital-WhatsAppInboundTable,MESSAGES_OUTBOUND_TABLE=base-wecare-digital-WhatsAppOutboundTable,OUTBOUND_WHATSAPP_FUNCTION=wecare-outbound-whatsapp,OUTBOUND_SMS_FUNCTION=wecare-outbound-sms,OUTBOUND_EMAIL_FUNCTION=wecare-outbound-email,LOG_LEVEL=INFO}" --region us-east-1 --no-cli-pager --query FunctionName --output text
if %ERRORLEVEL% NEQ 0 echo FAIL: wecare-agent-action-group

echo === ALL ENV VARS UPDATED ===
