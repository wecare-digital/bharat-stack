# Create/deploy wecare-meta-business-agent (zip Python lambda; no external deps).
$ErrorActionPreference = "Continue"
$FN = "wecare-meta-business-agent"
$pkg = "scripts\_pkg_$FN"
if (Test-Path $pkg) { Remove-Item -Recurse -Force $pkg }
New-Item -ItemType Directory -Path $pkg -Force | Out-Null
Copy-Item "amplify\functions\messaging\meta-business-agent\handler.py" "$pkg\handler.py"
$zip = "scripts\$FN.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path "$pkg\*" -DestinationPath $zip -Force
$zipFull = (Resolve-Path $zip).Path

# exists?
aws lambda get-function --function-name $FN --region us-east-1 *> $null
if ($LASTEXITCODE -eq 0) {
    $r = aws lambda update-function-code --function-name $FN --zip-file "fileb://$zipFull" --region us-east-1 --query LastModified --output text 2>&1
    Write-Host "UPDATED: $r"
} else {
    $r = aws lambda create-function --function-name $FN `
        --runtime python3.12 --handler handler.lambda_handler `
        --role "arn:aws:iam::775261844268:role/wecare-digital-lambda-role" `
        --timeout 60 --memory-size 256 `
        --zip-file "fileb://$zipFull" --region us-east-1 --query FunctionArn --output text 2>&1
    Write-Host "CREATED: $r"
}
if (Test-Path $pkg) { Remove-Item -Recurse -Force $pkg }
if (Test-Path $zip) { Remove-Item -Force $zip }
