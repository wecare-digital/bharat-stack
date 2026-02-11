$functions = @(
    "wecare-voice-cdr-webhook",
    "wecare-waba-management",
    "wecare-voice-in-cdr",
    "wecare-voice-calls-read",
    "wecare-whatsapp-templates",
    "wecare-ai-generate-response",
    "wecare-contacts-create",
    "wecare-voice-calls",
    "wecare-outbound-whatsapp",
    "wecare-outbound-email",
    "wecare-voice-in-obd",
    "wecare-payments-read",
    "wecare-razorpay-webhook",
    "wecare-template-analytics",
    "wecare-contacts-search",
    "wecare-billing",
    "wecare-whatsapp-template-management",
    "wecare-scheduled-messages",
    "wecare-outbound-sms",
    "wecare-sms-aws",
    "wecare-outbound-voice",
    "wecare-dlq-replay",
    "wecare-messages-read",
    "wecare-whatsapp-voice",
    "wecare-agent-action-group",
    "wecare-messages-delete",
    "wecare-contacts-read",
    "wecare-ai-config-management",
    "wecare-ai-query-kb",
    "wecare-whatsapp-business-api",
    "wecare-bulk-job-create",
    "wecare-inbound-whatsapp",
    "wecare-voice-in-c2c",
    "wecare-contacts-delete",
    "wecare-contacts-update",
    "wecare-bulk-job-control",
    "wecare-bulk-worker",
    "wecare-whatsapp-calling",
    "wecare-sms-in-airtel",
    "wecare-auth-middleware",
    "wecare-voice-aws",
    "wecare-voice-cdr-read"
)

$count = 0
foreach ($fn in $functions) {
    $count++
    Write-Host "[$count/42] Fixing handler: $fn"
    aws lambda update-function-configuration --function-name $fn --handler "handler.handler" --region us-east-1 --no-cli-pager --output text --query "FunctionName" 2>&1
}
Write-Host "Done! Fixed $count functions."