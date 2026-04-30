$ErrorActionPreference = "Continue"

function Deploy-Lambda {
    param([string]$FuncName, [string]$HandlerDir)
    Write-Host "=== Deploying $FuncName ===" -ForegroundColor Cyan
    $baseDir = Split-Path -Parent $PSScriptRoot
    $pkgDir = "$baseDir\scripts\_pkg_$FuncName"
    if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
    New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null
    New-Item -ItemType Directory -Path "$pkgDir\lambda_utils" -Force | Out-Null
    Copy-Item "$baseDir\amplify\functions\$HandlerDir\handler.py" "$pkgDir\handler.py"
    Get-ChildItem -Path "$baseDir\amplify\functions\shared\lambda_utils" -Filter "*.py" | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination "$pkgDir\lambda_utils\$($_.Name)" -Force
    }
    $skb = "$baseDir\amplify\functions\shared\static_knowledge_base.py"
    if (Test-Path $skb) { Copy-Item $skb "$pkgDir\" }
    # Copy modules subdir if exists
    $modulesDir = "$baseDir\amplify\functions\$HandlerDir\modules"
    if (Test-Path $modulesDir) { Copy-Item -Recurse -Path $modulesDir -Destination "$pkgDir\modules" -Force }
    $zipPath = "$baseDir\scripts\_deploy_$FuncName.zip"
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($pkgDir, $zipPath)
    $zipFull = (Resolve-Path $zipPath).Path
    $result = aws lambda update-function-code --function-name $FuncName --zip-file "fileb://$zipFull" --region us-east-1 --output text --query "FunctionName" 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Host "  OK: $FuncName" -ForegroundColor Green }
    else { Write-Host "  FAIL: $FuncName - $result" -ForegroundColor Red }
    if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
}

Write-Host "Deploying inbox notification fix - 3 Lambdas" -ForegroundColor Yellow
Write-Host ""

Deploy-Lambda "wecare-voice-in-cdr" "messaging\voice-in\cdr"
Deploy-Lambda "wecare-whatsapp-calling" "messaging\whatsapp-calling"
Deploy-Lambda "wecare-outbound-sms" "messaging\outbound-sms"

Write-Host ""
Write-Host "=== All 3 Lambdas deployed ===" -ForegroundColor Green
