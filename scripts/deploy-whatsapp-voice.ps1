#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy WhatsApp Voice Lambda (TTS via Polly + Audio Messages)
    1. Create DynamoDB table (WhatsAppVoiceTable)
    2. Create/Update Lambda function
    3. Create API Gateway routes
    4. Set Lambda permissions
#>

$ErrorActionPreference = "Stop"
$REGION = "us-east-1"
$ACCOUNT_ID = "809904170947"
$API_ID = "k4vqzmi07b"
$STAGE = "prod"
$LAMBDA_ROLE = "arn:aws:iam::${ACCOUNT_ID}:role/wecare-digital-lambda-role"

$TABLE_NAME = "base-wecare-digital-WhatsAppVoiceTable"
$LAMBDA_NAME = "wecare-whatsapp-voice"
$LAMBDA_ARN = "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${LAMBDA_NAME}"
$API_ARN = "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WhatsApp Voice Lambda Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Create DynamoDB Table
Write-Host "`n[1/4] Creating DynamoDB table..." -ForegroundColor Yellow
try {
    aws dynamodb describe-table --table-name $TABLE_NAME --region $REGION --output json 2>$null | Out-Null
    Write-Host "  -> $TABLE_NAME already exists" -ForegroundColor Green
} catch {
    aws dynamodb create-table `
        --table-name $TABLE_NAME `
        --attribute-definitions "AttributeName=messageId,AttributeType=S" `
        --key-schema "AttributeName=messageId,KeyType=HASH" `
        --billing-mode PAY_PER_REQUEST `
        --region $REGION `
        --tags "Key=Project,Value=wecare-digital" `
        --output json | Out-Null
    Write-Host "  -> $TABLE_NAME created" -ForegroundColor Green

    aws dynamodb update-time-to-live `
        --table-name $TABLE_NAME `
        --time-to-live-specification "Enabled=true,AttributeName=ttl" `
        --region $REGION --output json 2>$null | Out-Null
    Write-Host "  -> TTL enabled" -ForegroundColor Green
}

# Step 2: Package and Deploy Lambda
Write-Host "`n[2/4] Deploying Lambda..." -ForegroundColor Yellow
$handlerPath = "amplify/functions/messaging/whatsapp-voice/handler.py"
$zipPath = "amplify/functions/messaging/whatsapp-voice/lambda.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $handlerPath -DestinationPath $zipPath -Force

$ENV_VARS = "Variables={CONTACTS_TABLE=base-wecare-digital-ContactsTable,MESSAGES_TABLE=base-wecare-digital-WhatsAppInboundTable,VOICE_LOG_TABLE=$TABLE_NAME,MEDIA_BUCKET=auth.wecare.digital,WHATSAPP_PHONE_NUMBER_ID_1=phone-number-id-2ff05755631b41f29151c0573b7a4e2a,WHATSAPP_PHONE_NUMBER_ID_2=phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6,LOG_LEVEL=INFO}"

$exists = $false
try {
    aws lambda get-function --function-name $LAMBDA_NAME --region $REGION --output json 2>$null | Out-Null
    $exists = $true
} catch {}

if ($exists) {
    aws lambda update-function-code `
        --function-name $LAMBDA_NAME `
        --zip-file "fileb://$zipPath" `
        --region $REGION --output json | Out-Null
    Write-Host "  -> Code updated" -ForegroundColor Green
    Start-Sleep -Seconds 3
    aws lambda update-function-configuration `
        --function-name $LAMBDA_NAME `
        --environment $ENV_VARS `
        --timeout 60 `
        --memory-size 512 `
        --region $REGION --output json | Out-Null
    Write-Host "  -> Config updated" -ForegroundColor Green
} else {
    aws lambda create-function `
        --function-name $LAMBDA_NAME `
        --runtime python3.12 `
        --handler handler.handler `
        --role $LAMBDA_ROLE `
        --zip-file "fileb://$zipPath" `
        --timeout 60 `
        --memory-size 512 `
        --environment $ENV_VARS `
        --region $REGION `
        --tags "Project=wecare-digital" `
        --output json | Out-Null
    Write-Host "  -> Lambda created" -ForegroundColor Green
}

# Step 3: Create API Gateway Routes
Write-Host "`n[3/4] Creating API Gateway routes..." -ForegroundColor Yellow
$intResult = aws apigatewayv2 create-integration `
    --api-id $API_ID `
    --integration-type AWS_PROXY `
    --integration-uri $LAMBDA_ARN `
    --payload-format-version "2.0" `
    --region $REGION --output json 2>&1 | ConvertFrom-Json
$INT_ID = $intResult.IntegrationId
Write-Host "  -> Integration: $INT_ID" -ForegroundColor Green

$routes = @(
    @{ Method = "POST";   Path = "/whatsapp-voice/tts" },
    @{ Method = "POST";   Path = "/whatsapp-voice/send" },
    @{ Method = "GET";    Path = "/whatsapp-voice/voices" },
    @{ Method = "GET";    Path = "/whatsapp-voice/logs" },
    @{ Method = "DELETE"; Path = "/whatsapp-voice/clear-logs" }
)

foreach ($route in $routes) {
    $routeKey = "$($route.Method) $($route.Path)"
    Write-Host "  Creating: $routeKey"
    aws apigatewayv2 create-route `
        --api-id $API_ID `
        --route-key $routeKey `
        --target "integrations/$INT_ID" `
        --region $REGION --output json | Out-Null
}

# Step 4: Lambda Permission + Deploy
Write-Host "`n[4/4] Permissions & Deploy..." -ForegroundColor Yellow
try {
    aws lambda add-permission `
        --function-name $LAMBDA_NAME `
        --statement-id "apigateway-invoke-whatsapp-voice" `
        --action "lambda:InvokeFunction" `
        --principal "apigateway.amazonaws.com" `
        --source-arn "${API_ARN}/*/*" `
        --region $REGION --output json 2>$null | Out-Null
    Write-Host "  -> Permission added" -ForegroundColor Green
} catch {
    Write-Host "  -> Permission exists (OK)" -ForegroundColor Yellow
}

aws apigatewayv2 create-deployment `
    --api-id $API_ID `
    --stage-name $STAGE `
    --region $REGION --output json | Out-Null
Write-Host "  -> API deployed" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nEndpoints:" -ForegroundColor White
Write-Host "  POST   https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/whatsapp-voice/tts"
Write-Host "  POST   https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/whatsapp-voice/send"
Write-Host "  GET    https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/whatsapp-voice/voices"
Write-Host "  GET    https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/whatsapp-voice/logs"
Write-Host ""
