# Add missing API Gateway routes for the 6 new functions
$ErrorActionPreference = "Continue"
$region = "us-east-1"
$apiId = "zllr9lrg7j"
$accountId = "775261844268"

$routes = @(
    @("GET /voice/calls", "wecare-voice-calls"),
    @("POST /voice/call", "wecare-outbound-voice"),
    @("DELETE /voice/calls", "wecare-voice-calls"),
    @("GET /voice/calls-read", "wecare-voice-calls-read"),
    @("POST /auth/validate", "wecare-auth-middleware"),
    @("GET /bulk/worker", "wecare-bulk-worker"),
    @("GET /whatsapp/template-management", "wecare-whatsapp-template-management"),
    @("POST /whatsapp/template-management", "wecare-whatsapp-template-management"),
    @("DELETE /whatsapp/template-management", "wecare-whatsapp-template-management"),
    @("GET /whatsapp/template-library", "wecare-whatsapp-template-management"),
    @("POST /whatsapp/template-from-library", "wecare-whatsapp-template-management")
)

$success = 0
foreach ($route in $routes) {
    $routeKey = $route[0]
    $funcName = $route[1]
    
    Write-Host "Adding route: $routeKey -> $funcName..." -NoNewline
    
    # Create integration
    $integUri = "arn:aws:apigateway:${region}:lambda:path/2015-03-31/functions/arn:aws:lambda:${region}:${accountId}:function:${funcName}/invocations"
    
    $integResult = aws apigatewayv2 create-integration --api-id $apiId --integration-type AWS_PROXY --integration-uri $integUri --payload-format-version "2.0" --region $region --output json 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host " INTEG FAILED" -ForegroundColor Red
        continue
    }
    
    $integId = ($integResult | ConvertFrom-Json).IntegrationId
    
    # Create route
    $routeResult = aws apigatewayv2 create-route --api-id $apiId --route-key $routeKey --target "integrations/$integId" --region $region --output json 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $success++
        
        # Add Lambda permission
        $stmtId = "apigateway-$($funcName)-$($routeKey.Replace(' ','-').Replace('/','-'))-$(Get-Random)"
        aws lambda add-permission --function-name $funcName --statement-id $stmtId --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:${region}:${accountId}:${apiId}/*" --region $region --output json 2>$null | Out-Null
    } else {
        Write-Host " ROUTE FAILED" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Added $success routes ==="
