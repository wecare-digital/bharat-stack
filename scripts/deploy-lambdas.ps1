# Deploy all Lambda functions to AWS account 775261844268
# Each function: zip handler.py -> create-function with wecare-digital-lambda-role

$ROLE_ARN = "arn:aws:iam::775261844268:role/wecare-digital-lambda-role"
$REGION = "us-east-1"
$RUNTIME = "python3.12"
$TIMEOUT = 30
$MEMORY = 256

# Function name -> handler.py path mapping
$functions = @{
    "wecare-agent-action-group"       = "amplify/functions/ai/agent-action-group"
    "wecare-ai-config-management"     = "amplify/functions/ai/ai-config-management"
    "wecare-ai-generate-response"     = "amplify/functions/ai/ai-generate-response"
    "wecare-ai-query-kb"              = "amplify/functions/ai/ai-query-kb"
    "wecare-contacts-create"          = "amplify/functions/core/contacts-create"
    "wecare-contacts-delete"          = "amplify/functions/core/contacts-delete"
    "wecare-contacts-read"            = "amplify/functions/core/contacts-read"
    "wecare-contacts-search"          = "amplify/functions/core/contacts-search"
    "wecare-contacts-update"          = "amplify/functions/core/contacts-update"
    "wecare-messages-delete"          = "amplify/functions/core/messages-delete"
    "wecare-messages-read"            = "amplify/functions/core/messages-read"
    "wecare-inbound-whatsapp"         = "amplify/functions/messaging/inbound-whatsapp-handler"
    "wecare-outbound-email"           = "amplify/functions/messaging/outbound-email"
    "wecare-outbound-sms"             = "amplify/functions/messaging/outbound-sms"
    "wecare-outbound-whatsapp"        = "amplify/functions/messaging/outbound-whatsapp"
    "wecare-scheduled-messages"       = "amplify/functions/messaging/scheduled-messages"
    "wecare-sms-aws"                  = "amplify/functions/messaging/sms-aws"
    "wecare-sms-in-airtel"            = "amplify/functions/messaging/sms-in/airtel"
    "wecare-template-analytics"       = "amplify/functions/messaging/template-analytics"
    "wecare-voice-aws"                = "amplify/functions/messaging/voice-aws"
    "wecare-voice-cdr-read"           = "amplify/functions/messaging/voice-cdr-read"
    "wecare-voice-in-c2c"             = "amplify/functions/messaging/voice-in/c2c"
    "wecare-voice-in-cdr"             = "amplify/functions/messaging/voice-in/cdr"
    "wecare-voice-in-obd"             = "amplify/functions/messaging/voice-in/obd"
    "wecare-waba-management"          = "amplify/functions/messaging/waba-management"
    "wecare-whatsapp-business-api"    = "amplify/functions/messaging/whatsapp-business-api"
    "wecare-whatsapp-calling"         = "amplify/functions/messaging/whatsapp-calling"
    "wecare-whatsapp-templates"       = "amplify/functions/messaging/whatsapp-template-management"
    "wecare-whatsapp-voice"           = "amplify/functions/messaging/whatsapp-voice"
    "wecare-billing"                  = "amplify/functions/operations/billing"
    "wecare-bulk-job-control"         = "amplify/functions/operations/bulk-job-control"
    "wecare-bulk-job-create"          = "amplify/functions/operations/bulk-job-create"
    "wecare-dlq-replay"               = "amplify/functions/operations/dlq-replay"
    "wecare-payments-read"            = "amplify/functions/payments/payments-read"
    "wecare-razorpay-webhook"         = "amplify/functions/payments/razorpay-webhook"
}

$successCount = 0
$failCount = 0
$tempDir = "scripts/lambda-zips"

# Create temp dir for zips
if (-not (Test-Path $tempDir)) { New-Item -ItemType Directory -Path $tempDir -Force | Out-Null }

foreach ($entry in $functions.GetEnumerator()) {
    $funcName = $entry.Key
    $srcDir = $entry.Value
    $handlerPath = "$srcDir/handler.py"
    $zipPath = "$tempDir/$funcName.zip"

    if (-not (Test-Path $handlerPath)) {
        Write-Host "SKIP: $funcName - handler.py not found at $handlerPath" -ForegroundColor Yellow
        $failCount++
        continue
    }

    Write-Host "Deploying $funcName..." -NoNewline

    # Create zip with handler.py
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path $handlerPath -DestinationPath $zipPath -Force

    # Check if function already exists
    $exists = $null
    try {
        $exists = aws lambda get-function --function-name $funcName --region $REGION 2>$null
    } catch {}

    if ($exists) {
        # Update existing function
        aws lambda update-function-code --function-name $funcName --zip-file "fileb://$zipPath" --region $REGION 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host " UPDATED" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host " FAILED (update)" -ForegroundColor Red
            $failCount++
        }
    } else {
        # Create new function
        $result = aws lambda create-function `
            --function-name $funcName `
            --runtime $RUNTIME `
            --role $ROLE_ARN `
            --handler "handler.lambda_handler" `
            --zip-file "fileb://$zipPath" `
            --timeout $TIMEOUT `
            --memory-size $MEMORY `
            --region $REGION `
            --environment "Variables={AWS_ACCOUNT_ID=775261844268,S3_BUCKET=app.wecare.digital,REGION=us-east-1}" 2>&1

        if ($LASTEXITCODE -eq 0) {
            Write-Host " CREATED" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host " FAILED" -ForegroundColor Red
            Write-Host "  Error: $result" -ForegroundColor DarkRed
            $failCount++
        }
    }
}

Write-Host ""
Write-Host "=== DEPLOYMENT SUMMARY ===" -ForegroundColor Cyan
Write-Host "Success: $successCount" -ForegroundColor Green
Write-Host "Failed:  $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host "Total:   $($successCount + $failCount)" -ForegroundColor Cyan
