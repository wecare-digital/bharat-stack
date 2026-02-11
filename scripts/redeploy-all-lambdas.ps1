# Re-deploy all 35 Lambda functions with updated handler.py code
# This updates the function code after codebase migration fixes

$ErrorActionPreference = "Continue"
$region = "us-east-1"

# Mapping: function-name -> handler.py path
$functions = @{
    "wecare-contacts-create" = "amplify/functions/core/contacts-create/handler.py"
    "wecare-contacts-read" = "amplify/functions/core/contacts-read/handler.py"
    "wecare-contacts-update" = "amplify/functions/core/contacts-update/handler.py"
    "wecare-contacts-delete" = "amplify/functions/core/contacts-delete/handler.py"
    "wecare-contacts-search" = "amplify/functions/core/contacts-search/handler.py"
    "wecare-messages-read" = "amplify/functions/core/messages-read/handler.py"
    "wecare-messages-delete" = "amplify/functions/core/messages-delete/handler.py"
    "wecare-inbound-whatsapp" = "amplify/functions/messaging/inbound-whatsapp-handler/handler.py"
    "wecare-outbound-whatsapp" = "amplify/functions/messaging/outbound-whatsapp/handler.py"
    "wecare-outbound-sms" = "amplify/functions/messaging/outbound-sms/handler.py"
    "wecare-outbound-email" = "amplify/functions/messaging/outbound-email/handler.py"
    "wecare-scheduled-messages" = "amplify/functions/messaging/scheduled-messages/handler.py"
    "wecare-template-analytics" = "amplify/functions/messaging/template-analytics/handler.py"
    "wecare-waba-management" = "amplify/functions/messaging/waba-management/handler.py"
    "wecare-whatsapp-templates" = "amplify/functions/messaging/whatsapp-template-management/handler.py"
    "wecare-whatsapp-calling" = "amplify/functions/messaging/whatsapp-calling/handler.py"
    "wecare-whatsapp-business-api" = "amplify/functions/messaging/whatsapp-business-api/handler.py"
    "wecare-sms-aws" = "amplify/functions/messaging/sms-aws/handler.py"
    "wecare-voice-aws" = "amplify/functions/messaging/voice-aws/handler.py"
    "wecare-voice-cdr-read" = "amplify/functions/messaging/voice-cdr-read/handler.py"
    "wecare-sms-in-airtel" = "amplify/functions/messaging/sms-in/airtel/handler.py"
    "wecare-voice-in-c2c" = "amplify/functions/messaging/voice-in/c2c/handler.py"
    "wecare-voice-in-obd" = "amplify/functions/messaging/voice-in/obd/handler.py"
    "wecare-voice-in-cdr" = "amplify/functions/messaging/voice-in/cdr/handler.py"
    "wecare-whatsapp-voice" = "amplify/functions/messaging/whatsapp-calling/handler.py"
    "wecare-ai-query-kb" = "amplify/functions/ai/ai-query-kb/handler.py"
    "wecare-ai-generate-response" = "amplify/functions/ai/ai-generate-response/handler.py"
    "wecare-ai-config-management" = "amplify/functions/ai/ai-config-management/handler.py"
    "wecare-agent-action-group" = "amplify/functions/ai/agent-action-group/handler.py"
    "wecare-billing" = "amplify/functions/operations/billing/handler.py"
    "wecare-bulk-job-create" = "amplify/functions/operations/bulk-job-create/handler.py"
    "wecare-bulk-job-control" = "amplify/functions/operations/bulk-job-control/handler.py"
    "wecare-dlq-replay" = "amplify/functions/operations/dlq-replay/handler.py"
    "wecare-payments-read" = "amplify/functions/operations/payments-read/handler.py"
    "wecare-razorpay-webhook" = "amplify/functions/operations/razorpay-webhook/handler.py"
}

$total = $functions.Count
$success = 0
$failed = 0
$i = 0

foreach ($entry in $functions.GetEnumerator()) {
    $i++
    $funcName = $entry.Key
    $handlerPath = $entry.Value
    
    Write-Host "[$i/$total] Deploying $funcName..." -NoNewline
    
    if (-not (Test-Path $handlerPath)) {
        Write-Host " SKIP (handler not found: $handlerPath)" -ForegroundColor Yellow
        $failed++
        continue
    }
    
    # Create temp zip
    $zipPath = "scripts/temp-$funcName.zip"
    
    # Remove old zip if exists
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    
    # Create zip with handler.py
    Compress-Archive -Path $handlerPath -DestinationPath $zipPath -Force
    
    # Update function code
    $result = aws lambda update-function-code --function-name $funcName --zip-file "fileb://$zipPath" --region $region --output json 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $success++
    } else {
        Write-Host " FAILED" -ForegroundColor Red
        Write-Host "  Error: $result"
        $failed++
    }
    
    # Cleanup temp zip
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
}

Write-Host ""
Write-Host "=== DEPLOYMENT COMPLETE ==="
Write-Host "Success: $success / $total"
Write-Host "Failed: $failed / $total"
