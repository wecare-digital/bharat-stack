# Deploy 6 missing Lambda functions to match old account's 41 wecare-* functions
$ErrorActionPreference = "Continue"
$region = "us-east-1"
$role = if ($env:AWS_ACCOUNT_ID) { "arn:aws:iam::$($env:AWS_ACCOUNT_ID):role/wecare-digital-lambda-role" } else { "arn:aws:iam::775261844268:role/wecare-digital-lambda-role" }

# Functions to create (missing from new account)
$missing = @{
    "wecare-voice-cdr-webhook" = "amplify/functions/messaging/voice-in/cdr/handler.py"
    "wecare-outbound-voice" = "amplify/functions/messaging/outbound-voice/handler.py"
    "wecare-bulk-worker" = "amplify/functions/operations/bulk-worker/handler.py"
    "wecare-auth-middleware" = "amplify/functions/core/auth-middleware/handler.py"
    "wecare-voice-calls" = "amplify/functions/messaging/outbound-voice/handler.py"
    "wecare-whatsapp-template-management" = "amplify/functions/messaging/whatsapp-template-management/handler.py"
    "wecare-voice-calls-read" = "amplify/functions/messaging/voice-cdr-read/handler.py"
}

# Environment variables for each function
$envVars = @{
    "wecare-voice-cdr-webhook" = '{"Variables":{"VOICE_CDR_TABLE":"base-wecare-digital-VoiceCDRTable","MEDIA_BUCKET":"app.wecare.digital","LOG_LEVEL":"INFO"}}'
    "wecare-outbound-voice" = '{"Variables":{"VOICE_TABLE":"base-wecare-digital-VoiceCalls","CONTACTS_TABLE":"base-wecare-digital-ContactsTable","AIRTEL_SECRET":"wecare/airtel-iq","CDR_WEBHOOK_URL":"https://api.wecare.digital/voice-cdr-webhook","LOG_LEVEL":"INFO"}}'
    "wecare-bulk-worker" = '{"Variables":{"BULK_JOBS_TABLE":"base-wecare-digital-BulkJobsTable","BULK_RECIPIENTS_TABLE":"base-wecare-digital-BulkRecipientsTable","CONTACTS_TABLE":"base-wecare-digital-ContactsTable","OUTBOUND_TABLE":"base-wecare-digital-WhatsAppOutboundTable","SEND_MODE":"LIVE","DEFAULT_PHONE_NUMBER_ID":"phone-number-id-5e020cecd221429996f6ae721cc42206","LOG_LEVEL":"INFO"}}'
    "wecare-auth-middleware" = '{"Variables":{"COGNITO_USER_POOL_ID":"us-east-1_cSx0RHCIR","LOG_LEVEL":"INFO"}}'
    "wecare-voice-calls" = '{"Variables":{"VOICE_TABLE":"base-wecare-digital-VoiceCalls","CONTACTS_TABLE":"base-wecare-digital-ContactsTable","AIRTEL_SECRET":"wecare/airtel-iq","CDR_WEBHOOK_URL":"https://api.wecare.digital/voice-cdr-webhook","LOG_LEVEL":"INFO"}}'
    "wecare-whatsapp-template-management" = '{"Variables":{"MEDIA_BUCKET":"app.wecare.digital","LOG_LEVEL":"INFO"}}'
    "wecare-voice-calls-read" = '{"Variables":{"VOICE_CDR_TABLE":"base-wecare-digital-VoiceCDRTable","MEDIA_BUCKET":"app.wecare.digital","LOG_LEVEL":"INFO"}}'
}

$total = $missing.Count
$success = 0
$i = 0

foreach ($entry in $missing.GetEnumerator()) {
    $i++
    $funcName = $entry.Key
    $handlerPath = $entry.Value
    
    Write-Host "[$i/$total] Creating $funcName..." -NoNewline
    
    # Create zip
    $zipPath = "scripts/temp-$funcName.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path $handlerPath -DestinationPath $zipPath -Force
    
    # Check if function already exists
    $exists = aws lambda get-function --function-name $funcName --region $region 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        # Update existing
        $result = aws lambda update-function-code --function-name $funcName --zip-file "fileb://$zipPath" --region $region --output json 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " UPDATED" -ForegroundColor Cyan
            $success++
        } else {
            Write-Host " UPDATE FAILED" -ForegroundColor Red
        }
    } else {
        # Create new
        $env = $envVars[$funcName]
        $envFile = "scripts/env-$funcName.json"
        Set-Content -Path $envFile -Value $env
        
        $result = aws lambda create-function `
            --function-name $funcName `
            --runtime python3.12 `
            --handler handler.handler `
            --role $role `
            --zip-file "fileb://$zipPath" `
            --timeout 30 `
            --memory-size 256 `
            --environment "file://$envFile" `
            --region $region `
            --output json 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host " CREATED" -ForegroundColor Green
            $success++
        } else {
            Write-Host " FAILED" -ForegroundColor Red
            Write-Host "  $result"
        }
        
        if (Test-Path $envFile) { Remove-Item $envFile -Force }
    }
    
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
}

Write-Host ""
Write-Host "=== DONE: $success/$total ==="
