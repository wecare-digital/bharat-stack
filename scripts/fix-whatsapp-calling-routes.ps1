# Fix WhatsApp Calling API Gateway Routes
# Root cause: deploy-whatsapp-calling.ps1 used "api.wecare.digital" instead of the real API ID "zllr9lrg7j"
# This script creates the missing routes for the whatsapp-calling Lambda

$API_ID = "zllr9lrg7j"
$REGION = "us-east-1"
$ACCOUNT = if ($env:AWS_ACCOUNT_ID) { $env:AWS_ACCOUNT_ID } else { "775261844268" }
$LAMBDA_NAME = "wecare-whatsapp-calling"
$LAMBDA_ARN = "arn:aws:lambda:${REGION}:${ACCOUNT}:function:${LAMBDA_NAME}"

Write-Host "=== Fixing WhatsApp Calling Routes ===" -ForegroundColor Cyan
Write-Host "API ID: $API_ID"
Write-Host "Lambda: $LAMBDA_NAME"

# Step 1: Check Lambda exists
Write-Host "`n[1/4] Checking Lambda exists..."
$lambdaCheck = aws lambda get-function --function-name $LAMBDA_NAME --region $REGION --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Lambda $LAMBDA_NAME not found. Run deploy-whatsapp-calling.ps1 first." -ForegroundColor Red
    exit 1
}
Write-Host "  Lambda exists" -ForegroundColor Green

# Step 2: Create integration
Write-Host "`n[2/4] Creating API Gateway integration..."
$INTEGRATION_URI = "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations"

$intResult = aws apigatewayv2 create-integration `
    --api-id $API_ID `
    --integration-type AWS_PROXY `
    --integration-uri $INTEGRATION_URI `
    --payload-format-version "2.0" `
    --region $REGION `
    --output json 2>&1

if ($LASTEXITCODE -eq 0) {
    $intJson = $intResult | ConvertFrom-Json
    $INTEGRATION_ID = $intJson.IntegrationId
    Write-Host "  Integration created: $INTEGRATION_ID" -ForegroundColor Green
} else {
    Write-Host "  Integration may already exist, checking..." -ForegroundColor Yellow
    # Find existing integration for this Lambda
    $allInts = aws apigatewayv2 get-integrations --api-id $API_ID --region $REGION --output json | ConvertFrom-Json
    $existing = $allInts.Items | Where-Object { $_.IntegrationUri -like "*${LAMBDA_NAME}*" }
    if ($existing) {
        $INTEGRATION_ID = $existing[0].IntegrationId
        Write-Host "  Using existing integration: $INTEGRATION_ID" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Could not create or find integration" -ForegroundColor Red
        exit 1
    }
}

# Step 3: Create all routes
Write-Host "`n[3/4] Creating routes..."
$routes = @(
    "GET /whatsapp-calling",
    "POST /whatsapp-calling",
    "DELETE /whatsapp-calling",
    "GET /whatsapp-calling/logs",
    "GET /whatsapp-calling/active",
    "POST /whatsapp-calling/accept",
    "POST /whatsapp-calling/reject",
    "POST /whatsapp-calling/hangup",
    "POST /whatsapp-calling/outbound",
    "GET /whatsapp-calling/config",
    "POST /whatsapp-calling/config"
)

foreach ($routeKey in $routes) {
    Write-Host "  $routeKey ... " -NoNewline
    $result = aws apigatewayv2 create-route `
        --api-id $API_ID `
        --route-key $routeKey `
        --target "integrations/$INTEGRATION_ID" `
        --region $REGION `
        --output json 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "CREATED" -ForegroundColor Green
    } else {
        Write-Host "EXISTS (or error)" -ForegroundColor Yellow
    }
}

# Step 4: Ensure Lambda permission
Write-Host "`n[4/4] Adding Lambda invoke permission..."
aws lambda add-permission `
    --function-name $LAMBDA_NAME `
    --statement-id "apigw-invoke-calling-fix" `
    --action "lambda:InvokeFunction" `
    --principal "apigateway.amazonaws.com" `
    --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT}:${API_ID}/*" `
    --region $REGION 2>$null | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  Permission added" -ForegroundColor Green
} else {
    Write-Host "  Permission already exists (OK)" -ForegroundColor Yellow
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test webhook verification:" -ForegroundColor White
Write-Host '  curl "https://api.wecare.digital/whatsapp-calling?hub.mode=subscribe&hub.verify_token=wecare_calling_verify_2026&hub.challenge=test123"' -ForegroundColor Green
Write-Host ""
Write-Host "Expected response: test123" -ForegroundColor White
Write-Host ""
Write-Host "Then go to Meta App Dashboard (App ID: 891766673609917):" -ForegroundColor White
Write-Host "  Callback URL: https://api.wecare.digital/whatsapp-calling" -ForegroundColor Green
Write-Host "  Verify Token: wecare_calling_verify_2026" -ForegroundColor Green
Write-Host "  Subscribe to: calls" -ForegroundColor Green
