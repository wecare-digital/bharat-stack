$ErrorActionPreference = "Continue"
function Deploy-Lambda {
    param([string]$FuncName, [string]$HandlerPath)
    Write-Host "=== Deploying $FuncName ===" -ForegroundColor Cyan
    $pkgDir = "scripts\_pkg_$FuncName"
    if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
    New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null
    New-Item -ItemType Directory -Path "$pkgDir\lambda_utils" -Force | Out-Null
    Copy-Item $HandlerPath "$pkgDir\handler.py"
    Copy-Item "amplify\functions\shared\lambda_utils\*.py" "$pkgDir\lambda_utils\"
    $zipPath = "scripts\$FuncName.zip"
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
    Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipPath -Force
    $zipFull = (Resolve-Path $zipPath).Path
    $result = aws lambda update-function-code --function-name $FuncName --zip-file "fileb://$zipFull" --region us-east-1 --output text --query "LastModified" 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Host "  OK: $FuncName ($result)" -ForegroundColor Green }
    else { Write-Host "  FAIL: $FuncName - $result" -ForegroundColor Red }
    if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
}
Deploy-Lambda "wecare-outbound-sms" "amplify\functions\messaging\outbound-sms\handler.py"
