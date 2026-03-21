$ErrorActionPreference = "Continue"

function Remove-WithRetry {
    param([string]$Path, [int]$MaxRetries = 3)
    for ($i = 0; $i -lt $MaxRetries; $i++) {
        if (-not (Test-Path $Path)) { return }
        try {
            Remove-Item -Recurse -Force $Path -ErrorAction Stop
            return
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    # Final attempt — let it error naturally if still locked
    if (Test-Path $Path) { Remove-Item -Recurse -Force $Path }
}

function Deploy-Lambda {
    param([string]$FuncName, [string]$HandlerPath, [string]$ModulesDir)
    
    Write-Host "=== Deploying $FuncName ===" -ForegroundColor Cyan
    
    # Use a unique staging dir per function to avoid file-lock races
    $pkgDir = "scripts\_pkg_$FuncName"
    Remove-WithRetry $pkgDir
    New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null
    New-Item -ItemType Directory -Path "$pkgDir\lambda_utils" -Force | Out-Null
    
    Copy-Item $HandlerPath "$pkgDir\handler.py"
    Copy-Item "amplify\functions\shared\lambda_utils\*.py" "$pkgDir\lambda_utils\"
    
    if ($ModulesDir -and (Test-Path $ModulesDir)) {
        New-Item -ItemType Directory -Path "$pkgDir\modules" -Force | Out-Null
        Copy-Item "$ModulesDir\*.py" "$pkgDir\modules\"
    }
    
    $skbPath = "amplify\functions\shared\static_knowledge_base.py"
    if (Test-Path $skbPath) { Copy-Item $skbPath "$pkgDir\" }
    
    $zipPath = Join-Path (Get-Location) "scripts\$FuncName.zip"
    Remove-WithRetry $zipPath
    Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipPath -Force
    
    if (-not (Test-Path $zipPath)) {
        Write-Host "FAIL: $FuncName (zip creation failed)" -ForegroundColor Red
        Remove-WithRetry $pkgDir
        return $false
    }
    
    $zipFull = (Resolve-Path $zipPath).Path
    aws lambda update-function-code --function-name $FuncName --zip-file "fileb://$zipFull" --region us-east-1 --output text --query "FunctionName" 2>$null
    $exitCode = $LASTEXITCODE
    
    Remove-WithRetry $pkgDir
    Remove-WithRetry $zipPath
    
    if ($exitCode -eq 0) {
        Write-Host "OK: $FuncName" -ForegroundColor Green
        return $true
    } else {
        Write-Host "FAIL: $FuncName" -ForegroundColor Red
        return $false
    }
}

$results = @()

# === Core ===
$results += Deploy-Lambda "wecare-auth-middleware" "amplify\functions\core\auth-middleware\handler.py" ""
$results += Deploy-Lambda "wecare-contacts" "amplify\functions\core\contacts\handler.py" ""
$results += Deploy-Lambda "wecare-messages-read" "amplify\functions\core\messages-read\handler.py" ""
$results += Deploy-Lambda "wecare-messages-delete" "amplify\functions\core\messages-delete\handler.py" ""
$results += Deploy-Lambda "wecare-faq-handler" "amplify\functions\core\faq-handler\handler.py" ""
$results += Deploy-Lambda "wecare-url-shortener" "amplify\functions\core\url-shortener\handler.py" ""

# === WhatsApp ===
$results += Deploy-Lambda "wecare-inbound-whatsapp" "amplify\functions\messaging\inbound-whatsapp-handler\handler.py" "amplify\functions\messaging\inbound-whatsapp-handler\modules"
$results += Deploy-Lambda "wecare-outbound-whatsapp" "amplify\functions\messaging\outbound-whatsapp\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-voice" "amplify\functions\messaging\whatsapp-voice\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-calling" "amplify\functions\messaging\whatsapp-calling\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-templates" "amplify\functions\messaging\whatsapp-templates\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-template-management" "amplify\functions\messaging\whatsapp-template-management\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-business-api" "amplify\functions\messaging\whatsapp-business-api\handler.py" ""
$results += Deploy-Lambda "wecare-waba-management" "amplify\functions\messaging\waba-management\handler.py" ""
$results += Deploy-Lambda "wecare-media-cleanup" "amplify\functions\messaging\media-cleanup\handler.py" ""
$results += Deploy-Lambda "wecare-template-analytics" "amplify\functions\messaging\template-analytics\handler.py" ""

# === SMS ===
$results += Deploy-Lambda "wecare-outbound-sms" "amplify\functions\messaging\outbound-sms\handler.py" ""
$results += Deploy-Lambda "wecare-outbound-email" "amplify\functions\messaging\outbound-email\handler.py" ""
$results += Deploy-Lambda "wecare-sms-aws" "amplify\functions\messaging\sms-aws\handler.py" ""
$results += Deploy-Lambda "wecare-sms-in-airtel" "amplify\functions\messaging\sms-in\airtel\handler.py" ""

# === Voice ===
$results += Deploy-Lambda "wecare-voice-aws" "amplify\functions\messaging\voice-aws\handler.py" ""
$results += Deploy-Lambda "wecare-voice-in-c2c" "amplify\functions\messaging\voice-in\c2c\handler.py" ""
$results += Deploy-Lambda "wecare-voice-in-obd" "amplify\functions\messaging\voice-in\obd\handler.py" ""
$results += Deploy-Lambda "wecare-voice-in-cdr" "amplify\functions\messaging\voice-in\cdr\handler.py" ""
$results += Deploy-Lambda "wecare-voice-cdr-read" "amplify\functions\messaging\voice-cdr-read\handler.py" ""
$results += Deploy-Lambda "wecare-outbound-voice" "amplify\functions\messaging\outbound-voice\handler.py" ""

# === Scheduled & Bulk ===
$results += Deploy-Lambda "wecare-push-notifications" "amplify\functions\messaging\push-notifications\handler.py" ""
$results += Deploy-Lambda "wecare-scheduled-messages" "amplify\functions\messaging\scheduled-messages\handler.py" ""
$results += Deploy-Lambda "wecare-bulk-job-create" "amplify\functions\operations\bulk-job-create\handler.py" ""
$results += Deploy-Lambda "wecare-bulk-worker" "amplify\functions\operations\bulk-worker\handler.py" ""
$results += Deploy-Lambda "wecare-bulk-job-control" "amplify\functions\operations\bulk-job-control\handler.py" ""

# === AI ===
$results += Deploy-Lambda "wecare-ai-query-kb" "amplify\functions\ai\ai-query-kb\handler.py" ""
$results += Deploy-Lambda "wecare-ai-generate-response" "amplify\functions\ai\ai-generate-response\handler.py" ""
$results += Deploy-Lambda "wecare-ai-config-management" "amplify\functions\ai\ai-config-management\handler.py" ""
$results += Deploy-Lambda "wecare-agent-action-group" "amplify\functions\ai\agent-action-group\handler.py" ""

# === Operations ===
$results += Deploy-Lambda "wecare-dlq-replay" "amplify\functions\operations\dlq-replay\handler.py" ""
$results += Deploy-Lambda "wecare-billing" "amplify\functions\operations\billing\handler.py" ""
$results += Deploy-Lambda "wecare-system-cleanup" "amplify\functions\operations\system-cleanup\handler.py" ""

# === Payments ===
$results += Deploy-Lambda "wecare-razorpay-webhook" "amplify\functions\payments\razorpay-webhook\handler.py" ""
$results += Deploy-Lambda "wecare-payu-webhook" "amplify\functions\payments\payu-webhook\handler.py" ""
$results += Deploy-Lambda "wecare-payments-read" "amplify\functions\payments\payments-read\handler.py" ""
$results += Deploy-Lambda "wecare-invoice-engine" "amplify\functions\payments\invoice-engine\handler.py" ""

# === Ecommerce ===
$results += Deploy-Lambda "wecare-wix-store" "amplify\functions\ecommerce\wix-store\handler.py" ""
$results += Deploy-Lambda "wecare-product-image-gen" "amplify\functions\ecommerce\product-image-gen\handler.py" ""

$ok = ($results | Where-Object { $_ -eq $true }).Count
$fail = ($results | Where-Object { $_ -eq $false }).Count
Write-Host "`n=== FIRST PASS: $ok succeeded, $fail failed ===" -ForegroundColor Yellow

# --- Auto-retry any failures ---
if ($fail -gt 0) {
    Write-Host "`nRetrying failed deployments..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2

    # Build lookup of function name -> args for retry
    $allFunctions = @(
        @("wecare-auth-middleware", "amplify\functions\core\auth-middleware\handler.py", ""),
        @("wecare-contacts", "amplify\functions\core\contacts\handler.py", ""),
        @("wecare-messages-read", "amplify\functions\core\messages-read\handler.py", ""),
        @("wecare-messages-delete", "amplify\functions\core\messages-delete\handler.py", ""),
        @("wecare-faq-handler", "amplify\functions\core\faq-handler\handler.py", ""),
        @("wecare-url-shortener", "amplify\functions\core\url-shortener\handler.py", ""),
        @("wecare-inbound-whatsapp", "amplify\functions\messaging\inbound-whatsapp-handler\handler.py", "amplify\functions\messaging\inbound-whatsapp-handler\modules"),
        @("wecare-outbound-whatsapp", "amplify\functions\messaging\outbound-whatsapp\handler.py", ""),
        @("wecare-whatsapp-voice", "amplify\functions\messaging\whatsapp-voice\handler.py", ""),
        @("wecare-whatsapp-calling", "amplify\functions\messaging\whatsapp-calling\handler.py", ""),
        @("wecare-whatsapp-templates", "amplify\functions\messaging\whatsapp-templates\handler.py", ""),
        @("wecare-whatsapp-template-management", "amplify\functions\messaging\whatsapp-template-management\handler.py", ""),
        @("wecare-whatsapp-business-api", "amplify\functions\messaging\whatsapp-business-api\handler.py", ""),
        @("wecare-waba-management", "amplify\functions\messaging\waba-management\handler.py", ""),
        @("wecare-media-cleanup", "amplify\functions\messaging\media-cleanup\handler.py", ""),
        @("wecare-template-analytics", "amplify\functions\messaging\template-analytics\handler.py", ""),
        @("wecare-outbound-sms", "amplify\functions\messaging\outbound-sms\handler.py", ""),
        @("wecare-outbound-email", "amplify\functions\messaging\outbound-email\handler.py", ""),
        @("wecare-sms-aws", "amplify\functions\messaging\sms-aws\handler.py", ""),
        @("wecare-sms-in-airtel", "amplify\functions\messaging\sms-in\airtel\handler.py", ""),
        @("wecare-voice-aws", "amplify\functions\messaging\voice-aws\handler.py", ""),
        @("wecare-voice-in-c2c", "amplify\functions\messaging\voice-in\c2c\handler.py", ""),
        @("wecare-voice-in-obd", "amplify\functions\messaging\voice-in\obd\handler.py", ""),
        @("wecare-voice-in-cdr", "amplify\functions\messaging\voice-in\cdr\handler.py", ""),
        @("wecare-voice-cdr-read", "amplify\functions\messaging\voice-cdr-read\handler.py", ""),
        @("wecare-outbound-voice", "amplify\functions\messaging\outbound-voice\handler.py", ""),
        @("wecare-push-notifications", "amplify\functions\messaging\push-notifications\handler.py", ""),
        @("wecare-scheduled-messages", "amplify\functions\messaging\scheduled-messages\handler.py", ""),
        @("wecare-bulk-job-create", "amplify\functions\operations\bulk-job-create\handler.py", ""),
        @("wecare-bulk-worker", "amplify\functions\operations\bulk-worker\handler.py", ""),
        @("wecare-bulk-job-control", "amplify\functions\operations\bulk-job-control\handler.py", ""),
        @("wecare-ai-query-kb", "amplify\functions\ai\ai-query-kb\handler.py", ""),
        @("wecare-ai-generate-response", "amplify\functions\ai\ai-generate-response\handler.py", ""),
        @("wecare-ai-config-management", "amplify\functions\ai\ai-config-management\handler.py", ""),
        @("wecare-agent-action-group", "amplify\functions\ai\agent-action-group\handler.py", ""),
        @("wecare-dlq-replay", "amplify\functions\operations\dlq-replay\handler.py", ""),
        @("wecare-billing", "amplify\functions\operations\billing\handler.py", ""),
        @("wecare-system-cleanup", "amplify\functions\operations\system-cleanup\handler.py", ""),
        @("wecare-razorpay-webhook", "amplify\functions\payments\razorpay-webhook\handler.py", ""),
        @("wecare-payu-webhook", "amplify\functions\payments\payu-webhook\handler.py", ""),
        @("wecare-payments-read", "amplify\functions\payments\payments-read\handler.py", ""),
        @("wecare-invoice-engine", "amplify\functions\payments\invoice-engine\handler.py", ""),
        @("wecare-wix-store", "amplify\functions\ecommerce\wix-store\handler.py", ""),
        @("wecare-product-image-gen", "amplify\functions\ecommerce\product-image-gen\handler.py", "")
    )

    $retryResults = @()
    for ($i = 0; $i -lt $results.Count; $i++) {
        if ($results[$i] -eq $false) {
            $fn = $allFunctions[$i]
            $retryResults += Deploy-Lambda $fn[0] $fn[1] $fn[2]
        }
    }

    $retryOk = ($retryResults | Where-Object { $_ -eq $true }).Count
    $retryFail = ($retryResults | Where-Object { $_ -eq $false }).Count
    $totalOk = $ok + $retryOk
    $totalFail = $fail - $retryOk
    Write-Host "`n=== RETRY: $retryOk recovered, $retryFail still failed ===" -ForegroundColor Yellow
    Write-Host "=== FINAL: $totalOk/$($results.Count) succeeded ===" -ForegroundColor $(if ($totalFail -eq 0) { "Green" } else { "Yellow" })
} else {
    Write-Host "=== ALL $ok FUNCTIONS DEPLOYED SUCCESSFULLY ===" -ForegroundColor Green
}
