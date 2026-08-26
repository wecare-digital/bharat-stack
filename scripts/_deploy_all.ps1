$ErrorActionPreference = "Continue"
$region = "us-east-1"
$baseDir = Split-Path -Parent $PSScriptRoot
$sharedDir = "$baseDir\amplify\functions\shared"
$pkgDir = "$baseDir\scripts\_pkg_deploy"

# Map of Lambda function names to handler paths (relative to amplify/functions/)
$functions = @{
    "wecare-inbound-whatsapp"       = "messaging\inbound-whatsapp-handler"
    "wecare-outbound-whatsapp"      = "messaging\outbound-whatsapp"
    "wecare-whatsapp-calling"       = "messaging\whatsapp-calling"
    "wecare-whatsapp-business-api"  = "messaging\whatsapp-business-api"
    "wecare-whatsapp-templates"     = "messaging\whatsapp-templates"
    "wecare-whatsapp-template-management" = "messaging\whatsapp-template-management"
    "wecare-whatsapp-voice"         = "messaging\whatsapp-voice"
    "wecare-outbound-email"         = "messaging\outbound-email"
    "wecare-outbound-sms"           = "messaging\outbound-sms"
    "wecare-outbound-voice"         = "messaging\outbound-voice"
    "wecare-push-notifications"     = "messaging\push-notifications"
    "wecare-scheduled-messages"     = "messaging\scheduled-messages"
    "wecare-sms-aws"                = "messaging\sms-aws"
    "wecare-sms-in-airtel"          = "messaging\sms-in\airtel"
    "wecare-voice-aws"              = "messaging\voice-aws"
    "wecare-voice-cdr-read"         = "messaging\voice-cdr-read"
    "wecare-voice-in-c2c"           = "messaging\voice-in\c2c"
    "wecare-voice-in-cdr"           = "messaging\voice-in\cdr"
    "wecare-voice-in-obd"           = "messaging\voice-in\obd"
    "wecare-waba-management"        = "messaging\waba-management"
    "wecare-template-analytics"     = "messaging\template-analytics"
    "wecare-media-cleanup"          = "messaging\media-cleanup"
    "wecare-ai-generate-response"   = "ai\ai-generate-response"
    "wecare-ai-query-kb"            = "ai\ai-query-kb"
    "wecare-ai-config-management"   = "ai\ai-config-management"
    "wecare-agent-action-group"     = "ai\agent-action-group"
    "wecare-contacts"               = "core\contacts"
    "wecare-auth-middleware"        = "core\auth-middleware"
    "wecare-faq-handler"            = "core\faq-handler"
    "wecare-messages-read"          = "core\messages-read"
    "wecare-messages-delete"        = "core\messages-delete"
    "wecare-url-shortener"          = "core\url-shortener"
    "wecare-product-image-gen"      = "ecommerce\product-image-gen"
    "wecare-wix-store"              = "ecommerce\wix-store"
    "wecare-razorpay-webhook"       = "payments\razorpay-webhook"
    "wecare-invoice-engine"         = "payments\invoice-engine"
    "wecare-payments-read"          = "payments\payments-read"
    "wecare-billing"                = "operations\billing"
    "wecare-bulk-job-create"        = "operations\bulk-job-create"
    "wecare-bulk-job-control"       = "operations\bulk-job-control"
    "wecare-bulk-worker"            = "operations\bulk-worker"
    "wecare-dlq-replay"             = "operations\dlq-replay"
    "wecare-system-cleanup"         = "operations\system-cleanup"
}

$succeeded = 0
$failed = 0
$skipped = 0
$failedNames = @()

foreach ($entry in $functions.GetEnumerator()) {
    $funcName = $entry.Key
    $handlerRelPath = $entry.Value
    $handlerDir = "$baseDir\amplify\functions\$handlerRelPath"
    $handlerFile = "$handlerDir\handler.py"

    if (-not (Test-Path $handlerFile)) {
        Write-Host "SKIP $funcName - handler.py not found" -ForegroundColor Yellow
        $skipped++
        continue
    }

    Write-Host "Deploying $funcName..." -ForegroundColor Cyan -NoNewline

    # Clean package dir completely
    if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
    $null = New-Item -ItemType Directory -Path $pkgDir -Force
    $null = New-Item -ItemType Directory -Path "$pkgDir\lambda_utils" -Force

    # Copy handler
    Copy-Item -Path $handlerFile -Destination "$pkgDir\handler.py" -Force

    # Copy modules subdir if exists (e.g. inbound-whatsapp-handler/modules/)
    $modulesDir = "$handlerDir\modules"
    if (Test-Path $modulesDir) {
        Copy-Item -Recurse -Path $modulesDir -Destination "$pkgDir\modules" -Force
    }

    # Copy shared lambda_utils — copy each .py file explicitly to avoid race
    Get-ChildItem -Path "$sharedDir\lambda_utils" -Filter "*.py" | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination "$pkgDir\lambda_utils\$($_.Name)" -Force
    }

    # Copy static_knowledge_base.py if exists
    $skbPath = "$sharedDir\static_knowledge_base.py"
    if (Test-Path $skbPath) { Copy-Item -Path $skbPath -Destination "$pkgDir\" -Force }

    # Verify lambda_utils copied correctly before zipping
    $utilsCount = (Get-ChildItem "$pkgDir\lambda_utils\*.py" -ErrorAction SilentlyContinue).Count
    if ($utilsCount -lt 3) {
        Write-Host " FAILED: lambda_utils copy incomplete ($utilsCount files)" -ForegroundColor Red
        $failed++
        $failedNames += $funcName
        continue
    }

    # Create zip using .NET to avoid Compress-Archive race conditions
    $zipPath = "$baseDir\scripts\_deploy_$funcName.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($pkgDir, $zipPath)
    } catch {
        Write-Host " FAILED: zip creation error: $_" -ForegroundColor Red
        $failed++
        $failedNames += $funcName
        continue
    }

    if (-not (Test-Path $zipPath)) {
        Write-Host " FAILED: zip file not created" -ForegroundColor Red
        $failed++
        $failedNames += $funcName
        continue
    }

    $zipFull = (Resolve-Path $zipPath).Path

    # Deploy
    $result = aws lambda update-function-code --function-name $funcName --zip-file "fileb://$zipFull" --region $region --output text --query "FunctionName" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $succeeded++
    } else {
        Write-Host " FAILED: $result" -ForegroundColor Red
        $failed++
        $failedNames += $funcName
    }

    # Cleanup zip
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
}

# Final cleanup
if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }

Write-Host ""
Write-Host "Deploy complete: $succeeded succeeded, $failed failed, $skipped skipped" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Yellow" })
if ($failedNames.Count -gt 0) {
    Write-Host "Failed functions: $($failedNames -join ', ')" -ForegroundColor Red
}

# SnapStart: these functions are invoked via the ':live' alias by the API, so
# after updating $LATEST code we must publish a new version and move the alias.
Write-Host ""
Write-Host "Publishing SnapStart versions + moving 'live' alias..." -ForegroundColor Cyan
python scripts\snapstart_publish.py
