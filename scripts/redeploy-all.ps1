# Redeploy all 42 Lambda functions from source code
$mappings = @{
    "wecare-contacts-read" = "amplify/functions/core/contacts-read/handler.py"
    "wecare-contacts-create" = "amplify/functions/core/contacts-create/handler.py"
    "wecare-contacts-update" = "amplify/functions/core/contacts-update/handler.py"
    "wecare-contacts-delete" = "amplify/functions/core/contacts-delete/handler.py"
    "wecare-contacts-search" = "amplify/functions/core/contacts-search/handler.py"
    "wecare-messages-read" = "amplify/functions/core/messages-read/handler.py"
    "wecare-messages-delete" = "amplify/functions/core/messages-delete/handler.py"
    "wecare-auth-middleware" = "amplify/functions/core/auth-middleware/handler.py"
    "wecare-outbound-whatsapp" = "amplify/functions/messaging/outbound-whatsapp/handler.py"
    "wecare-outbound-sms" = "amplify/functions/messaging/outbound-sms/handler.py"
    "wecare-outbound-email" = "amplify/functions/messaging/outbound-email/handler.py"
    "wecare-outbound-voice" = "amplify/functions/messaging/outbound-voice/handler.py"
    "wecare-inbound-whatsapp" = "amplify/functions/messaging/inbound-whatsapp-handler/handler.py"
    "wecare-scheduled-messages" = "amplify/functions/messaging/scheduled-messages/handler.py"
    "wecare-template-analytics" = "amplify/functions/messaging/template-analytics/handler.py"
    "wecare-waba-management" = "amplify/functions/messaging/waba-management/handler.py"
    "wecare-whatsapp-calling" = "amplify/functions/messaging/whatsapp-calling/handler.py"
    "wecare-whatsapp-voice" = "amplify/functions/messaging/whatsapp-voice/handler.py"
    "wecare-whatsapp-templates" = "amplify/functions/messaging/whatsapp-template-management/handler.py"
    "wecare-whatsapp-template-management" = "amplify/functions/messaging/whatsapp-template-management/handler.py"
    "wecare-whatsapp-business-api" = "amplify/functions/messaging/whatsapp-business-api/handler.py"
    "wecare-sms-aws" = "amplify/functions/messaging/sms-aws/handler.py"
    "wecare-voice-aws" = "amplify/functions/messaging/voice-aws/handler.py"
    "wecare-voice-cdr-read" = "amplify/functions/messaging/voice-cdr-read/handler.py"
    "wecare-sms-in-airtel" = "amplify/functions/messaging/sms-in/airtel/handler.py"
    "wecare-voice-in-c2c" = "amplify/functions/messaging/voice-in/c2c/handler.py"
    "wecare-voice-in-cdr" = "amplify/functions/messaging/voice-in/cdr/handler.py"
    "wecare-voice-in-obd" = "amplify/functions/messaging/voice-in/obd/handler.py"
    "wecare-bulk-job-create" = "amplify/functions/operations/bulk-job-create/handler.py"
    "wecare-bulk-job-control" = "amplify/functions/operations/bulk-job-control/handler.py"
    "wecare-bulk-worker" = "amplify/functions/operations/bulk-worker/handler.py"
    "wecare-dlq-replay" = "amplify/functions/operations/dlq-replay/handler.py"
    "wecare-billing" = "amplify/functions/operations/billing/handler.py"
    "wecare-ai-config-management" = "amplify/functions/ai/ai-config-management/handler.py"
    "wecare-ai-generate-response" = "amplify/functions/ai/ai-generate-response/handler.py"
    "wecare-ai-query-kb" = "amplify/functions/ai/ai-query-kb/handler.py"
    "wecare-agent-action-group" = "amplify/functions/ai/agent-action-group/handler.py"
    "wecare-razorpay-webhook" = "amplify/functions/payments/razorpay-webhook/handler.py"
    "wecare-payments-read" = "amplify/functions/payments/payments-read/handler.py"
}

$count = 0
$total = $mappings.Count
foreach ($entry in $mappings.GetEnumerator()) {
    $count++
    $fn = $entry.Key
    $src = $entry.Value
    Write-Host "[$count/$total] Deploying $fn"
    Copy-Item $src "scripts/handler.py" -Force
    Compress-Archive -Path "scripts/handler.py" -DestinationPath "scripts/deploy-temp.zip" -Force
    $result = aws lambda update-function-code --function-name $fn --zip-file "fileb://scripts/deploy-temp.zip" --region us-east-1 --no-cli-pager --output text --query FunctionName 2>&1
    Write-Host "  -> $result"
}
Write-Host "Done! Deployed $count functions."