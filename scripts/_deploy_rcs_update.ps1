# Deploy updated sinch_rcs.py to all Lambdas that use it
# Lambdas: wecare-voice-in-cdr, wecare-whatsapp-calling, wecare-rcs-send

$ErrorActionPreference = "Stop"
$region = "us-east-1"
$baseDir = Split-Path -Parent $PSScriptRoot
$sharedDir = "$baseDir\amplify\functions\shared"
$pkgDir = "$baseDir\scripts\_pkg_deploy"

$lambdas = @{
    "wecare-voice-in-cdr"       = "messaging\voice-in\cdr"
    "wecare-whatsapp-calling"   = "messaging\whatsapp-calling"
    "wecare-rcs-send"           = "messaging\rcs-send"
}

$success = 0
$failed = 0

foreach ($funcName in $lambdas.Keys) {
    $handlerDir = $lambdas[$funcName]
    $handlerPath = "$baseDir\amplify\functions\$handlerDir\handler.py"
    
    Write-Host "`n── Deploying: $funcName ──" -ForegroundColor Cyan
    
    if (-not (Test-Path $handlerPath)) {
        Write-Host "  SKIP: handler not found at $handlerPath" -ForegroundColor Yellow
        $failed++
        continue
    }
    
    # Clean and create package directory
    if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
    $null = New-Item -ItemType Directory -Path $pkgDir -Force
    $null = New-Item -ItemType Directory -Path "$pkgDir\lambda_utils" -Force
    
    # Copy handler
    Copy-Item $handlerPath "$pkgDir\handler.py"
    
    # Copy shared lambda_utils
    Get-ChildItem -Path "$sharedDir\lambda_utils" -Filter "*.py" | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination "$pkgDir\lambda_utils\$($_.Name)" -Force
    }
    
    # Copy static_knowledge_base.py if exists
    $skbPath = "$sharedDir\static_knowledge_base.py"
    if (Test-Path $skbPath) { Copy-Item -Path $skbPath -Destination "$pkgDir\" -Force }
    
    # Copy modules subdir if exists (for whatsapp-calling)
    $modulesDir = "$baseDir\amplify\functions\$handlerDir\modules"
    if (Test-Path $modulesDir) {
        Copy-Item -Recurse -Path $modulesDir -Destination "$pkgDir\modules" -Force
    }
    
    # Copy flows subdir if exists
    $flowsDir = "$baseDir\amplify\functions\$handlerDir\flows"
    if (Test-Path $flowsDir) {
        Copy-Item -Recurse -Path $flowsDir -Destination "$pkgDir\flows" -Force
    }
    
    # Verify lambda_utils copied
    $utilsCount = (Get-ChildItem "$pkgDir\lambda_utils\*.py" -ErrorAction SilentlyContinue).Count
    if ($utilsCount -lt 3) {
        Write-Host "  FAILED: lambda_utils copy incomplete ($utilsCount files)" -ForegroundColor Red
        $failed++
        continue
    }
    
    # Create zip
    $zipPath = "$baseDir\scripts\$funcName.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipPath -Force
    
    $zipSize = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
    Write-Host "  Package: $zipSize MB ($utilsCount utils)"
    
    # Deploy
    try {
        aws lambda update-function-code `
            --function-name $funcName `
            --zip-file "fileb://$zipPath" `
            --region $region `
            --output text `
            --query "FunctionName" 2>&1 | Out-Null
        Write-Host "  ✅ Deployed: $funcName" -ForegroundColor Green
        $success++
    } catch {
        Write-Host "  ❌ Deploy failed: $_" -ForegroundColor Red
        $failed++
    }
    
    # Cleanup zip
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
}

# Cleanup
if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }

Write-Host "`n$('=' * 60)"
Write-Host "DEPLOYMENT COMPLETE: $success succeeded, $failed failed"
Write-Host "$('=' * 60)"
