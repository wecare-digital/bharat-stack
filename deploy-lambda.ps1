# Deploy ai-generate-response Lambda function
# PowerShell script for Windows

$FunctionName = "wecare-ai-generate-response"
$HandlerPath = "amplify/functions/ai/ai-generate-response"
$SharedPath = "amplify/functions/shared"
$ZipFile = "function.zip"
$TempDir = "lambda_package_temp"

Write-Host "Creating deployment package..." -ForegroundColor Green

# Create temp directory
if (Test-Path $TempDir) {
    Remove-Item $TempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $TempDir | Out-Null

# Copy handler
Copy-Item "$HandlerPath/handler.py" -Destination $TempDir

# Copy lambda_utils
Copy-Item "$SharedPath/lambda_utils" -Destination $TempDir -Recurse

# Copy static_knowledge_base.py
Copy-Item "$SharedPath/static_knowledge_base.py" -Destination $TempDir

# Create zip from temp directory
Set-Location $TempDir
Compress-Archive -Path * -DestinationPath "../$ZipFile" -Force
Set-Location ..

Write-Host "Deploying to AWS Lambda..." -ForegroundColor Green
aws lambda update-function-code `
  --function-name $FunctionName `
  --zip-file fileb://$ZipFile `
  --region us-east-1

Write-Host "Cleaning up..." -ForegroundColor Green
Remove-Item $ZipFile -Force
Remove-Item $TempDir -Recurse -Force

Write-Host "Deployment complete!" -ForegroundColor Green
