$ACCT = if ($env:AWS_ACCOUNT_ID) { $env:AWS_ACCOUNT_ID } else { "775261844268" }
$ROLE_ARN = "arn:aws:iam::${ACCT}:role/wecare-digital-lambda-role"
$REGION = "us-east-1"
$ENV_VARS = "Variables={AWS_ACCOUNT_ID=${ACCT},S3_BUCKET=app.wecare.digital,REGION=us-east-1}"

# Already deployed: wecare-contacts-create, wecare-razorpay-webhook, wecare-contacts-search,
# wecare-outbound-sms, wecare-dlq-replay, wecare-messages-read, wecare-contacts-update, wecare-whatsapp-calling

$remaining = @(
    @("wecare-agent-action-group", "amplify/functions/ai/agent-action-group/handler.py"),
    @("wecare-ai-config-management", "amplify/functions/ai/ai-config-management/handler.py"),
    @("wecare-ai-generate-response", "amplify/functions/ai/ai-generate-response/handler.py"),
    @("wecare-ai-query-kb", "amplify/functions/ai/ai-query-kb/handler.py"),
    @("wecare-contacts-delete", "amplify/functions/core/contacts-delete/handler.py"),
    @("wecare-messages-delete", "amplify/functions/core/messages-delete/handler.py"),
    @("wecare-inbound-whatsapp", "amplify/functions/messaging/inbound-whatsapp-handler/handler.py"),
    @("wecare-outbound-email", "amplify/functions/messaging/outbound-email/handler.py"),
    @("wecare-outbound-whatsapp", "amplify/functions/messaging/outbound-whatsapp/handler.py"),
    @("wecare-scheduled-messages", "amplify/functions/messaging/scheduled-messages/handler.py"),
    @("wecare-sms-aws", "amplify/functions/messaging/sms-aws/handler.py"),
    @("wecare-sms-in-airtel", "amplify/functions/messaging/sms-in/airtel/handler.py"),
    @("wecare-template-analytics", "amplify/functions/messaging/template-analytics/handler.py"),
    @("wecare-voice-aws", "amplify/functions/messaging/voice-aws/handler.py"),
    @("wecare-voice-cdr-read", "amplify/functions/messaging/voice-cdr-read/handler.py"),
    @("wecare-voice-in-c2c", "amplify/functions/messaging/voice-in/c2c/handler.py"),
    @("wecare-voice-in-cdr", "amplify/functions/messaging/voice-in/cdr/handler.py"),
    @("wecare-voice-in-obd", "amplify/functions/messaging/voice-in/obd/handler.py"),
    @("wecare-waba-management", "amplify/functions/messaging/waba-management/handler.py"),
    @("wecare-whatsapp-business-api", "amplify/functions/messaging/whatsapp-business-api/handler.py"),
    @("wecare-whatsapp-templates", "amplify/functions/messaging/whatsapp-template-management/handler.py"),
    @("wecare-whatsapp-voice", "amplify/functions/messaging/whatsapp-voice/handler.py"),
    @("wecare-billing", "amplify/functions/operations/billing/handler.py"),
    @("wecare-bulk-job-control", "amplify/functions/operations/bulk-job-control/handler.py"),
    @("wecare-bulk-job-create", "amplify/functions/operations/bulk-job-create/handler.py"),
    @("wecare-payments-read", "amplify/functions/payments/payments-read/handler.py")
)

$tempDir = "scripts/lambda-zips"
if (-not (Test-Path $tempDir)) { New-Item -ItemType Directory -Path $tempDir -Force | Out-Null }

$success = 0; $fail = 0

foreach ($item in $remaining) {
    $name = $item[0]
    $handler = $item[1]
    $zip = "$tempDir/$name.zip"
    
    # Check if already exists
    $check = aws lambda get-function --function-name $name --region $REGION 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "$name - EXISTS (skip)" -ForegroundColor Yellow
        $success++
        continue
    }
    
    Write-Host "Creating $name..." -NoNewline
    
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path $handler -DestinationPath $zip -Force 2>$null
    
    aws lambda create-function --function-name $name --runtime python3.12 --role $ROLE_ARN --handler handler.lambda_handler --zip-file "fileb://$zip" --timeout 30 --memory-size 256 --region $REGION --environment $ENV_VARS 2>$null | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $success++
    } else {
        Write-Host " FAIL" -ForegroundColor Red
        $fail++
    }
}

Write-Host "`nDone: $success OK, $fail failed"
