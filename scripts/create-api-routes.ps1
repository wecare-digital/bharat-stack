$API_ID = "zllr9lrg7j"
$REGION = "us-east-1"
$ACCOUNT = "775261844268"

# Route -> Lambda function mapping
$routes = @(
    # Contacts
    @("POST /contacts", "wecare-contacts-create"),
    @("GET /contacts", "wecare-contacts-read"),
    @("PUT /contacts", "wecare-contacts-update"),
    @("DELETE /contacts", "wecare-contacts-delete"),
    @("GET /contacts/search", "wecare-contacts-search"),
    
    # Messages
    @("GET /messages", "wecare-messages-read"),
    @("DELETE /messages", "wecare-messages-delete"),
    
    # WhatsApp
    @("POST /whatsapp/send", "wecare-outbound-whatsapp"),
    @("POST /whatsapp/inbound", "wecare-inbound-whatsapp"),
    @("GET /whatsapp/templates", "wecare-whatsapp-templates"),
    @("POST /whatsapp/templates", "wecare-whatsapp-templates"),
    @("DELETE /whatsapp/templates", "wecare-whatsapp-templates"),
    @("POST /whatsapp/calling", "wecare-whatsapp-calling"),
    @("GET /whatsapp/calling", "wecare-whatsapp-calling"),
    @("POST /whatsapp/voice", "wecare-whatsapp-voice"),
    @("GET /whatsapp/voice", "wecare-whatsapp-voice"),
    @("POST /whatsapp/business-api", "wecare-whatsapp-business-api"),
    @("GET /whatsapp/business-api", "wecare-whatsapp-business-api"),
    
    # WABA Management
    @("GET /waba", "wecare-waba-management"),
    @("POST /waba", "wecare-waba-management"),
    @("PUT /waba", "wecare-waba-management"),
    
    # SMS
    @("POST /sms/send", "wecare-outbound-sms"),
    @("POST /sms-aws/send", "wecare-sms-aws"),
    @("GET /sms-aws/send", "wecare-sms-aws"),
    @("POST /sms-in/airtel", "wecare-sms-in-airtel"),
    
    # Email
    @("POST /email/send", "wecare-outbound-email"),
    
    # Voice
    @("POST /voice-aws/send", "wecare-voice-aws"),
    @("GET /voice-aws/send", "wecare-voice-aws"),
    @("POST /voice-in/c2c", "wecare-voice-in-c2c"),
    @("POST /voice-in/obd", "wecare-voice-in-obd"),
    @("POST /voice-in/cdr", "wecare-voice-in-cdr"),
    @("POST /voice-cdr-webhook", "wecare-voice-cdr-read"),
    @("GET /voice-cdr-webhook", "wecare-voice-cdr-read"),
    
    # AI
    @("POST /ai/generate", "wecare-ai-generate-response"),
    @("POST /ai/query", "wecare-ai-query-kb"),
    @("GET /ai/internal/config", "wecare-ai-config-management"),
    @("PUT /ai/internal/config", "wecare-ai-config-management"),
    @("POST /ai/agent", "wecare-agent-action-group"),
    
    # Operations
    @("GET /billing", "wecare-billing"),
    @("POST /billing", "wecare-billing"),
    @("POST /bulk/create", "wecare-bulk-job-create"),
    @("POST /bulk/control", "wecare-bulk-job-control"),
    @("GET /bulk/control", "wecare-bulk-job-control"),
    @("POST /dlq/replay", "wecare-dlq-replay"),
    @("GET /dlq/replay", "wecare-dlq-replay"),
    
    # Scheduled Messages
    @("GET /scheduled", "wecare-scheduled-messages"),
    @("POST /scheduled", "wecare-scheduled-messages"),
    @("DELETE /scheduled", "wecare-scheduled-messages"),
    
    # Template Analytics
    @("GET /templates/analytics", "wecare-template-analytics"),
    @("POST /templates/analytics", "wecare-template-analytics"),
    
    # Payments
    @("GET /payments", "wecare-payments-read"),
    @("POST /payments/webhook", "wecare-razorpay-webhook")
)

$success = 0; $fail = 0
# Cache integrations to avoid duplicates
$integrationCache = @{}

foreach ($route in $routes) {
    $routeKey = $route[0]
    $funcName = $route[1]
    $funcArn = "arn:aws:lambda:${REGION}:${ACCOUNT}:function:${funcName}"
    
    Write-Host "Route: $routeKey -> $funcName..." -NoNewline
    
    # Create or reuse integration
    if (-not $integrationCache.ContainsKey($funcName)) {
        $intResult = aws apigatewayv2 create-integration --api-id $API_ID --integration-type AWS_PROXY --integration-uri $funcArn --payload-format-version "2.0" --region $REGION --query "IntegrationId" --output text 2>&1
        if ($LASTEXITCODE -eq 0) {
            $integrationCache[$funcName] = $intResult.Trim()
            
            # Add Lambda permission for API Gateway
            $stmtId = "apigw-$funcName-$(Get-Random)"
            aws lambda add-permission --function-name $funcName --statement-id $stmtId --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT}:${API_ID}/*" --region $REGION 2>$null | Out-Null
        } else {
            Write-Host " FAIL (integration)" -ForegroundColor Red
            $fail++
            continue
        }
    }
    
    $integrationId = $integrationCache[$funcName]
    
    # Create route
    $routeResult = aws apigatewayv2 create-route --api-id $API_ID --route-key $routeKey --target "integrations/$integrationId" --region $REGION 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $success++
    } else {
        Write-Host " FAIL (route)" -ForegroundColor Red
        $fail++
    }
}

Write-Host "`n=== API ROUTES SUMMARY ==="
Write-Host "Success: $success" -ForegroundColor Green
Write-Host "Failed:  $fail" -ForegroundColor $(if ($fail -gt 0) { "Red" } else { "Green" })
