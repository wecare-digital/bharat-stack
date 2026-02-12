$API_ID = "zllr9lrg7j"
$REGION = "us-east-1"
$ACCOUNT = if ($env:AWS_ACCOUNT_ID) { $env:AWS_ACCOUNT_ID } else { "775261844268" }

$routes = @(
    @("DELETE /scheduled", "wecare-scheduled-messages"),
    @("GET /billing", "wecare-billing"),
    @("GET /bulk/control", "wecare-bulk-job-control"),
    @("GET /dlq/replay", "wecare-dlq-replay"),
    @("GET /payments", "wecare-payments-read"),
    @("GET /scheduled", "wecare-scheduled-messages"),
    @("GET /templates/analytics", "wecare-template-analytics"),
    @("GET /ai/internal/config", "wecare-ai-config-management"),
    @("POST /ai/agent", "wecare-agent-action-group"),
    @("POST /ai/generate", "wecare-ai-generate-response"),
    @("POST /ai/query", "wecare-ai-query-kb"),
    @("POST /billing", "wecare-billing"),
    @("POST /bulk/control", "wecare-bulk-job-control"),
    @("POST /bulk/create", "wecare-bulk-job-create"),
    @("POST /dlq/replay", "wecare-dlq-replay"),
    @("POST /payments/webhook", "wecare-razorpay-webhook"),
    @("POST /scheduled", "wecare-scheduled-messages"),
    @("POST /templates/analytics", "wecare-template-analytics"),
    @("PUT /ai/internal/config", "wecare-ai-config-management"),
    @("POST /voice-cdr-webhook", "wecare-voice-cdr-read"),
    @("GET /voice-cdr-webhook", "wecare-voice-cdr-read")
)

$integrationCache = @{}
$success = 0; $fail = 0

foreach ($route in $routes) {
    $routeKey = $route[0]
    $funcName = $route[1]
    $funcArn = "arn:aws:lambda:${REGION}:${ACCOUNT}:function:${funcName}"
    
    Write-Host "Route: $routeKey -> $funcName..." -NoNewline
    
    if (-not $integrationCache.ContainsKey($funcName)) {
        $intResult = aws apigatewayv2 create-integration --api-id $API_ID --integration-type AWS_PROXY --integration-uri $funcArn --payload-format-version "2.0" --region $REGION --query "IntegrationId" --output text 2>&1
        if ($LASTEXITCODE -eq 0) {
            $integrationCache[$funcName] = $intResult.Trim()
            $stmtId = "apigw-$funcName-$(Get-Random)"
            aws lambda add-permission --function-name $funcName --statement-id $stmtId --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT}:${API_ID}/*" --region $REGION 2>$null | Out-Null
        } else {
            Write-Host " FAIL (integration)" -ForegroundColor Red
            $fail++
            continue
        }
    }
    
    $integrationId = $integrationCache[$funcName]
    $routeResult = aws apigatewayv2 create-route --api-id $API_ID --route-key $routeKey --target "integrations/$integrationId" --region $REGION 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $success++
    } else {
        Write-Host " FAIL" -ForegroundColor Red
        $fail++
    }
}

Write-Host "`nDone: $success OK, $fail failed"
