$ErrorActionPreference = "Continue"
$FuncName = "wecare-whatsapp-business-api"
$HandlerPath = "amplify\functions\messaging\whatsapp-business-api\handler.py"
Write-Host "=== Deploying $FuncName ===" -ForegroundColor Cyan
$pkgDir = "scripts\_pkg_$FuncName"
if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null
New-Item -ItemType Directory -Path "$pkgDir\lambda_utils" -Force | Out-Null
Copy-Item $HandlerPath "$pkgDir\handler.py"
Copy-Item "amplify\functions\shared\lambda_utils\*.py" "$pkgDir\lambda_utils\"

# Copy flows directory (required for WhatsApp Flow endpoint handling)
$flowsDir = "amplify\functions\messaging\whatsapp-business-api\flows"
if (Test-Path $flowsDir) {
    Copy-Item -Recurse $flowsDir "$pkgDir\flows"
    Get-ChildItem -Recurse "$pkgDir\flows" -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
}

# Copy service_api.py (required for service module handlers)
$svcApi = "amplify\functions\messaging\whatsapp-business-api\service_api.py"
if (Test-Path $svcApi) { Copy-Item $svcApi "$pkgDir\" }

$skb = "amplify\functions\shared\static_knowledge_base.py"
if (Test-Path $skb) { Copy-Item $skb "$pkgDir\" }
$zipPath = "scripts\$FuncName.zip"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipPath -Force
$zipFull = (Resolve-Path $zipPath).Path
aws lambda update-function-code --function-name $FuncName --zip-file "fileb://$zipFull" --region us-east-1 --output text --query "FunctionName"
if ($LASTEXITCODE -eq 0) { Write-Host "OK: $FuncName" -ForegroundColor Green }
else { Write-Host "FAIL: $FuncName" -ForegroundColor Red }
if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
