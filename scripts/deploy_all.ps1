$ErrorActionPreference = "Continue"

function Deploy-Lambda {
    param([string]$FuncName, [string]$HandlerPath, [string]$ModulesDir)
    
    Write-Host "=== Deploying $FuncName ===" -ForegroundColor Cyan
    
    $pkgDir = "scripts\_pkg"
    if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
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
    if (Test-Path $zipPath) { Remove-Item $zipPath }
    Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipPath -Force
    
    $zipFull = (Resolve-Path $zipPath).Path
    aws lambda update-function-code --function-name $FuncName --zip-file "fileb://$zipFull" --region us-east-1 --output text --query "FunctionName" 2>$null
    $exitCode = $LASTEXITCODE
    
    if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
    if (Test-Path $zipPath) { Remove-Item $zipPath }
    
    if ($exitCode -eq 0) {
        Write-Host "OK: $FuncName" -ForegroundColor Green
        return $true
    } else {
        Write-Host "FAIL: $FuncName" -ForegroundColor Red
        return $false
    }
}

$results = @()
$results += Deploy-Lambda "wecare-inbound-whatsapp" "amplify\functions\messaging\inbound-whatsapp-handler\handler.py" "amplify\functions\messaging\inbound-whatsapp-handler\modules"
$results += Deploy-Lambda "wecare-outbound-whatsapp" "amplify\functions\messaging\outbound-whatsapp\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-voice" "amplify\functions\messaging\whatsapp-voice\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-calling" "amplify\functions\messaging\whatsapp-calling\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-templates" "amplify\functions\messaging\whatsapp-templates\handler.py" ""
$results += Deploy-Lambda "wecare-whatsapp-template-management" "amplify\functions\messaging\whatsapp-template-management\handler.py" ""
$results += Deploy-Lambda "wecare-waba-management" "amplify\functions\messaging\waba-management\handler.py" ""
$results += Deploy-Lambda "wecare-voice-in-cdr" "amplify\functions\messaging\voice-in\cdr\handler.py" ""
$results += Deploy-Lambda "wecare-voice-in-c2c" "amplify\functions\messaging\voice-in\c2c\handler.py" ""
$results += Deploy-Lambda "wecare-voice-in-obd" "amplify\functions\messaging\voice-in\obd\handler.py" ""
$results += Deploy-Lambda "wecare-invoice-engine" "amplify\functions\payments\invoice-engine\handler.py" ""
$results += Deploy-Lambda "wecare-bulk-job-control" "amplify\functions\operations\bulk-job-control\handler.py" ""
$results += Deploy-Lambda "wecare-system-cleanup" "amplify\functions\operations\system-cleanup\handler.py" ""
$results += Deploy-Lambda "wecare-wix-store" "amplify\functions\ecommerce\wix-store\handler.py" ""
$results += Deploy-Lambda "wecare-product-image-gen" "amplify\functions\ecommerce\product-image-gen\handler.py" ""

$ok = ($results | Where-Object { $_ -eq $true }).Count
$fail = ($results | Where-Object { $_ -eq $false }).Count
Write-Host "`n=== DONE: $ok succeeded, $fail failed ===" -ForegroundColor Yellow
