# Deploy WhatsApp Business API Lambda
# Handles: Business Profile, Flows, Webhooks, Groups
$ErrorActionPreference = "Stop"
$REGION = "us-east-1"
$FUNCTION_NAME = "wecare-whatsapp-business-api"
$API_ID = "zllr9lrg7j"
$ACCOUNT_ID = if ($env:AWS_ACCOUNT_ID) { $env:AWS_ACCOUNT_ID } else { "775261844268" }
$HANDLER_PATH = "amplify/functions/messaging/whatsapp-business-api"
$ROLE_ARN = "arn:aws:iam::${ACCOUNT_ID}:role/wecare-digital-lambda-role"

Write-Host "=== Deploying $FUNCTION_NAME ===" -ForegroundColor Cyan

# Package
Write-Host "Packaging Lambda..."
Copy-Item "$HANDLER_PATH/handler.py" "$HANDLER_PATH/lambda_handler.py" -Force
Compress-Archive -Path "$HANDLER_PATH/lambda_handler.py" -DestinationPath "$HANDLER_PATH/lambda.zip" -Force
Remove-Item "$HANDLER_PATH/lambda_handler.py" -Force

# Check if function exists
$exists = $false
try {
    aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>$null | Out-Null
    $exists = $true
} catch {}

if ($exists) {
    Write-Host "Updating existing function..."
    aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file "fileb://$HANDLER_PATH/lambda.zip" --region $REGION --output text --query 'FunctionArn'
} else {
    Write-Host "Creating new function..."
    aws lambda create-function `
        --function-name $FUNCTION_NAME `
        --runtime python3.12 `
        --handler handler.handler `
        --role $ROLE_ARN `
        --zip-file "fileb://$HANDLER_PATH/lambda.zip" `
        --timeout 30 `
        --memory-size 256 `
        --environment "Variables={META_TOKEN_SECRET=wecare/meta-system-user-token,META_API_VERSION=v20.0,LOG_LEVEL=INFO}" `
        --region $REGION `
        --output text --query 'FunctionArn'
}

# Wait for function to be active
Write-Host "Waiting for function to be active..."
aws lambda wait function-active-v2 --function-name $FUNCTION_NAME --region $REGION

# API Gateway routes
$ROUTES = @(
    @{ Method = "GET";    Path = "/wa-business/profile" },
    @{ Method = "POST";   Path = "/wa-business/profile" },
    @{ Method = "GET";    Path = "/wa-business/flows" },
    @{ Method = "POST";   Path = "/wa-business/flows" },
    @{ Method = "PUT";    Path = "/wa-business/flows" },
    @{ Method = "DELETE"; Path = "/wa-business/flows" },
    @{ Method = "POST";   Path = "/wa-business/flows/publish" },
    @{ Method = "POST";   Path = "/wa-business/flows/deprecate" },
    @{ Method = "POST";   Path = "/wa-business/flows/preview" },
    @{ Method = "GET";    Path = "/wa-business/webhooks" },
    @{ Method = "POST";   Path = "/wa-business/webhooks" },
    @{ Method = "DELETE"; Path = "/wa-business/webhooks" },
    @{ Method = "GET";    Path = "/wa-business/groups" },
    @{ Method = "POST";   Path = "/wa-business/groups" },
    @{ Method = "PUT";    Path = "/wa-business/groups" },
    @{ Method = "DELETE"; Path = "/wa-business/groups" },
    @{ Method = "POST";   Path = "/wa-business/groups/participants" },
    @{ Method = "POST";   Path = "/wa-business/groups/send" },
    @{ Method = "GET";    Path = "/wa-business/phone-settings" },
    @{ Method = "POST";   Path = "/wa-business/phone-settings" },
    @{ Method = "OPTIONS"; Path = "/wa-business/{proxy+}" }
)

# Get Lambda ARN
$LAMBDA_ARN = aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.FunctionArn' --output text
$INTEGRATION_URI = $LAMBDA_ARN

# Check/create integration
Write-Host "Setting up API Gateway integration..."
$INTEGRATIONS = aws apigatewayv2 get-integrations --api-id $API_ID --region $REGION --output json | ConvertFrom-Json
$EXISTING = $INTEGRATIONS.Items | Where-Object { $_.IntegrationUri -eq $INTEGRATION_URI }

if ($EXISTING) {
    $INTEGRATION_ID = $EXISTING[0].IntegrationId
    Write-Host "Using existing integration: $INTEGRATION_ID"
} else {
    $INTEGRATION_ID = aws apigatewayv2 create-integration `
        --api-id $API_ID `
        --integration-type AWS_PROXY `
        --integration-uri $INTEGRATION_URI `
        --payload-format-version "2.0" `
        --region $REGION `
        --output text --query 'IntegrationId'
    Write-Host "Created integration: $INTEGRATION_ID"
}

# Create routes
$EXISTING_ROUTES = aws apigatewayv2 get-routes --api-id $API_ID --region $REGION --output json | ConvertFrom-Json
foreach ($route in $ROUTES) {
    $routeKey = "$($route.Method) $($route.Path)"
    $exists = $EXISTING_ROUTES.Items | Where-Object { $_.RouteKey -eq $routeKey }
    if ($exists) {
        Write-Host "  Route exists: $routeKey"
    } else {
        aws apigatewayv2 create-route --api-id $API_ID --route-key $routeKey --target "integrations/$INTEGRATION_ID" --region $REGION --output text --query 'RouteId'
        Write-Host "  Created route: $routeKey"
    }
}

# Add Lambda permission for API Gateway
try {
    aws lambda add-permission `
        --function-name $FUNCTION_NAME `
        --statement-id "apigateway-invoke-wa-business" `
        --action "lambda:InvokeFunction" `
        --principal "apigateway.amazonaws.com" `
        --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*" `
        --region $REGION 2>$null
    Write-Host "Added Lambda permission"
} catch {
    Write-Host "Lambda permission already exists"
}

# Deploy API
aws apigatewayv2 create-deployment --api-id $API_ID --region $REGION --output text --query 'DeploymentId'
Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Lambda: $FUNCTION_NAME"
Write-Host "API: https://api.wecare.digital/wa-business/"
Write-Host "Routes: $($ROUTES.Count) configured"
