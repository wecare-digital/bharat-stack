$functions = @(
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

foreach ($fn in $functions) {
    $h = aws lambda get-function-configuration --function-name $fn --query Handler --output text --region us-east-1 --no-cli-pager 2>&1
    if ($h -match "lambda_handler") {
        Write-Host "NEEDS FIX: $fn -> $h"
    } else {
        Write-Host "OK: $fn -> $h"
    }
}