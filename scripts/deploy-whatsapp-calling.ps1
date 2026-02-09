# Deploy WhatsApp Calling Webhook Lambda
# Creates: DynamoDB table, Lambda function, API Gateway routes

$ErrorActionPreference = "Stop"
$REGION = "us-east-1"
$ACCOUNT = "809904170947"
$API_ID = "k4vqzmi07b"
$LAMBDA_NAME = "wecare-whatsapp-calling"
$TABLE_NAME = "base-wecare-digital-WhatsAppCallingTable"
$ROLE_ARN = "arn:aws:iam::${ACCOUNT}:role/wecare-digital-lambda-role"
$HANDLER_PATH = "amplify/functions/messaging/whatsapp-calling"

Write-Host "=== Deploying WhatsApp Calling Webhook ===" -ForegroundColor Cyan

# Step 1: Create DynamoDB table
Write-Host "`n[1/5] Creating DynamoDB table: $TABLE_NAME"
try {
    aws dynamodb create-table `
        --table-name $TABLE_NAME `
        --attribute-definitions AttributeName=id,AttributeType=S `
        --key-schema AttributeName=id,KeyType=HASH `
        --billing-mode PAY_PER_REQUEST `
        --region $REGION `
        --no-cli-pager 2>$null
    Write-Host "  Table created" -ForegroundColor Green
} catch {
    Write-Host "  Table already exists or error: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Enable TTL
try {
    aws dynamodb update-time-to-live `
        --table-name $TABLE_NAME `
        --time-to-live-specification "Enabled=true,AttributeName=ttl" `
        --region $REGION `
        --no-cli-pager 2>$null
    Write-Host "  TTL enabled" -ForegroundColor Green
} catch {
    Write-Host "  TTL already enabled or error" -ForegroundColor Yellow
}

# Step 2: Package Lambda
Write-Host "`n[2/5] Packaging Lambda"
$zipPath = "$HANDLER_PATH/lambda.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath }
Compress-Archive -Path "$HANDLER_PATH/handler.py" -DestinationPath $zipPath -Force
Write-Host "  Packaged: $zipPath" -ForegroundColor Green

# Step 3: Create or update Lambda
Write-Host "`n[3/5] Deploying Lambda: $LAMBDA_NAME"
$lambdaExists = $false
try {
    aws lambda get-function --function-name $LAMBDA_NAME --region $REGION --no-cli-pager 2>$null | Out-Null
    $lambdaExists = $true
} catch {}

if ($lambdaExists) {
    aws lambda update-function-code `
        --function-name $LAMBDA_NAME `
        --zip-file "fileb://$zipPath" `
        --region $REGION `
        --no-cli-pager
    Write-Host "  Lambda code updated" -ForegroundColor Green
    
    Start-Sleep -Seconds 3
    
    aws lambda update-function-configuration `
        --function-name $LAMBDA_NAME `
        --environment "Variables={VERIFY_TOKEN=wecare_calling_verify_2026,CALL_LOG_TABLE=$TABLE_NAME,META_TOKEN_SECRET=wecare/meta-system-user-token,META_API_VERSION=v20.0,LOG_LEVEL=INFO,AUTO_PICKUP_ENABLED=true,AUTO_PICKUP_IVR_URL=https://auth.wecare.digital/stream/media/ivr/IVR+1.mp3,SYSTEM_CONFIG_TABLE=base-wecare-digital-SystemConfigTable}" `
        --timeout 30 `
        --memory-size 256 `
        --region $REGION `
        --no-cli-pager
    Write-Host "  Lambda config updated" -ForegroundColor Green
} else {
    aws lambda create-function `
        --function-name $LAMBDA_NAME `
        --runtime python3.12 `
        --handler handler.handler `
        --role $ROLE_ARN `
        --zip-file "fileb://$zipPath" `
        --timeout 30 `
        --memory-size 256 `
        --environment "Variables={VERIFY_TOKEN=wecare_calling_verify_2026,CALL_LOG_TABLE=$TABLE_NAME,META_TOKEN_SECRET=wecare/meta-system-user-token,META_API_VERSION=v20.0,LOG_LEVEL=INFO,AUTO_PICKUP_ENABLED=true,AUTO_PICKUP_IVR_URL=https://auth.wecare.digital/stream/media/ivr/IVR+1.mp3,SYSTEM_CONFIG_TABLE=base-wecare-digital-SystemConfigTable}" `
        --region $REGION `
        --no-cli-pager
    Write-Host "  Lambda created" -ForegroundColor Green
}

# Step 4: API Gateway integration
Write-Host "`n[4/5] Setting up API Gateway routes"

# Get or create integration
$LAMBDA_ARN = "arn:aws:lambda:${REGION}:${ACCOUNT}:function:${LAMBDA_NAME}"
$INTEGRATION_URI = "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations"

$intResult = aws apigatewayv2 create-integration `
    --api-id $API_ID `
    --integration-type AWS_PROXY `
    --integration-uri $INTEGRATION_URI `
    --payload-format-version "2.0" `
    --region $REGION `
    --no-cli-pager 2>$null | ConvertFrom-Json

$INTEGRATION_ID = $intResult.IntegrationId
Write-Host "  Integration: $INTEGRATION_ID" -ForegroundColor Green

# Create routes
$routes = @(
    @{ method = "GET";    path = "/whatsapp-calling" },
    @{ method = "POST";   path = "/whatsapp-calling" },
    @{ method = "DELETE"; path = "/whatsapp-calling" },
    @{ method = "GET";    path = "/whatsapp-calling/logs" },
    @{ method = "GET";    path = "/whatsapp-calling/active" },
    @{ method = "POST";   path = "/whatsapp-calling/accept" },
    @{ method = "POST";   path = "/whatsapp-calling/reject" },
    @{ method = "POST";   path = "/whatsapp-calling/hangup" },
    @{ method = "POST";   path = "/whatsapp-calling/outbound" },
    @{ method = "GET";    path = "/whatsapp-calling/config" },
    @{ method = "POST";   path = "/whatsapp-calling/config" }
)

foreach ($route in $routes) {
    $routeKey = "$($route.method) $($route.path)"
    try {
        aws apigatewayv2 create-route `
            --api-id $API_ID `
            --route-key $routeKey `
            --target "integrations/$INTEGRATION_ID" `
            --region $REGION `
            --no-cli-pager 2>$null | Out-Null
        Write-Host "  Route: $routeKey" -ForegroundColor Green
    } catch {
        Write-Host "  Route exists: $routeKey" -ForegroundColor Yellow
    }
}

# Step 5: Lambda permission for API Gateway
Write-Host "`n[5/5] Adding API Gateway invoke permission"
try {
    aws lambda add-permission `
        --function-name $LAMBDA_NAME `
        --statement-id "apigateway-invoke-calling" `
        --action "lambda:InvokeFunction" `
        --principal "apigateway.amazonaws.com" `
        --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT}:${API_ID}/*" `
        --region $REGION `
        --no-cli-pager 2>$null
    Write-Host "  Permission added" -ForegroundColor Green
} catch {
    Write-Host "  Permission already exists" -ForegroundColor Yellow
}

Write-Host "`n=== Deployment Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Webhook URL for Meta Dashboard:" -ForegroundColor White
Write-Host "  https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/whatsapp-calling" -ForegroundColor Green
Write-Host ""
Write-Host "Verify Token:" -ForegroundColor White
Write-Host "  wecare_calling_verify_2026" -ForegroundColor Green
Write-Host ""
Write-Host "Subscribe to field: calls" -ForegroundColor White
