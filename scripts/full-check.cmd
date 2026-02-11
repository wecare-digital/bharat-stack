@echo off
echo ========================================
echo FULL INFRASTRUCTURE VERIFICATION CHECK
echo ========================================

echo.
echo --- 1. LAMBDA FUNCTIONS (count) ---
aws lambda list-functions --query "length(Functions[?starts_with(FunctionName,'wecare-')])" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 2. DYNAMODB TABLES (count) ---
aws dynamodb list-tables --query "length(TableNames[?starts_with(@,'base-wecare-digital-')])" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 3. API GATEWAY ROUTES (count) ---
aws apigatewayv2 get-routes --api-id zllr9lrg7j --query "length(Items)" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 4. SECRETS MANAGER (count) ---
aws secretsmanager list-secrets --query "length(SecretList[?starts_with(Name,'wecare/')])" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 5. SQS QUEUES ---
aws sqs list-queues --queue-name-prefix base-wecare-digital --query "length(QueueUrls)" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 6. AMPLIFY BUILD STATUS ---
aws amplify list-jobs --app-id d3nadrc9t6n3f8 --branch-name base --max-items 1 --query "jobSummaries[0].[jobId,status]" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 7. AMPLIFY DOMAIN STATUS ---
aws amplify get-domain-association --app-id d3nadrc9t6n3f8 --domain-name wecare.digital --query "domainAssociation.domainStatus" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 8. COGNITO USER POOL ---
aws cognito-idp describe-user-pool --user-pool-id us-east-1_cSx0RHCIR --query "UserPool.[Id,Name,Domain,EstimatedNumberOfUsers]" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 9. PINPOINT TOLL-FREE STATUS ---
aws pinpoint-sms-voice-v2 describe-phone-numbers --query "PhoneNumbers[?NumberType=='TOLL_FREE'].[PhoneNumber,Status]" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 10. BEDROCK AGENTS ---
aws bedrock-agent list-agents --query "agentSummaries[*].[agentId,agentName,agentStatus]" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 11. BEDROCK KNOWLEDGE BASES ---
aws bedrock-agent list-knowledge-bases --query "knowledgeBaseSummaries[*].[knowledgeBaseId,name,status]" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 12. CLOUDFRONT DISTRIBUTION ---
aws cloudfront get-distribution --id ERCXSFDL0VM8X --query "Distribution.[Id,Status,DomainName]" --output text --no-cli-pager

echo.
echo --- 13. SQS-LAMBDA TRIGGER ---
aws lambda list-event-source-mappings --function-name wecare-bulk-worker --query "EventSourceMappings[0].[EventSourceArn,State]" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 14. EVENTBRIDGE RULE ---
aws events describe-rule --name wecare-scheduled-messages-trigger --query "[Name,State,ScheduleExpression]" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 15. DYNAMODB GSI ---
aws dynamodb describe-table --table-name base-wecare-digital-ScheduledMessagesTable --query "Table.GlobalSecondaryIndexes[0].[IndexName,IndexStatus]" --output text --region us-east-1 --no-cli-pager

echo.
echo --- 16. STATIC ASSETS (CloudFront) ---
curl -s -o nul -w "logo.png: %%{http_code}\n" https://app.wecare.digital/stream/media/m/wecare-digital.png
curl -s -o nul -w "favicon.ico: %%{http_code}\n" https://app.wecare.digital/stream/media/m/wecare-digital.ico
curl -s -o nul -w "logo.svg: %%{http_code}\n" https://app.wecare.digital/stream/media/m/wecare-digital.svg
curl -s -o nul -w "widget.js: %%{http_code}\n" https://app.wecare.digital/stream/code/wecare-wa-widget.js

echo.
echo --- 17. API GATEWAY CUSTOM DOMAIN ---
curl -s -o nul -w "api.wecare.digital: %%{http_code}\n" https://api.wecare.digital/

echo.
echo ========================================
echo VERIFICATION COMPLETE
echo ========================================
