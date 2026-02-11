# Audit Lambda env vars for all 42 wecare-* functions
$functions = @(
    "wecare-scheduled-messages",
    "wecare-bulk-job-create",
    "wecare-bulk-job-control",
    "wecare-bulk-worker",
    "wecare-inbound-whatsapp",
    "wecare-outbound-whatsapp",
    "wecare-outbound-email",
    "wecare-outbound-sms",
    "wecare-outbound-voice",
    "wecare-whatsapp-calling",
    "wecare-whatsapp-business-api",
    "wecare-sms-in-airtel",
    "wecare-voice-in-c2c",
    "wecare-voice-in-obd",
    "wecare-contacts-create",
    "wecare-contacts-read",
    "wecare-contacts-update",
    "wecare-contacts-delete",
    "wecare-contacts-search",
    "wecare-messages-read",
    "wecare-messages-delete",
    "wecare-ai-generate-response",
    "wecare-ai-query-kb",
    "wecare-ai-config-management",
    "wecare-agent-action-group",
    "wecare-template-analytics",
    "wecare-waba-management",
    "wecare-sms-aws",
    "wecare-voice-aws",
    "wecare-voice-cdr-read",
    "wecare-voice-cdr-webhook",
    "wecare-voice-calls",
    "wecare-voice-calls-read",
    "wecare-whatsapp-templates",
    "wecare-whatsapp-template-management",
    "wecare-whatsapp-voice",
    "wecare-razorpay-webhook",
    "wecare-payments-read",
    "wecare-billing",
    "wecare-dlq-replay",
    "wecare-auth-middleware",
    "wecare-voice-in-cdr"
)

foreach ($fn in $functions) {
    Write-Host "=== $fn ==="
    $result = cmd /c "aws lambda get-function-configuration --function-name $fn --query Environment.Variables --output json --region us-east-1 --no-cli-pager" 2>&1
    Write-Host $result
    Write-Host ""
}
