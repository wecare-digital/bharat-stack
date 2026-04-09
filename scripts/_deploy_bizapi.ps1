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
