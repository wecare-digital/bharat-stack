$API_ID = "zllr9lrg7j"
$REGION = "us-east-1"

# Map function names to their integration IDs (using first found)
$funcToIntegration = @{
    "wecare-ai-config-management" = "k52gvfk"
    "wecare-agent-action-group" = "ocq769q"
    "wecare-ai-generate-response" = "jkhxmog"
    "wecare-ai-query-kb" = "6bfqhg0"
    "wecare-billing" = "2dc14fu"
    "wecare-bulk-job-control" = "5s4z6s1"
    "wecare-bulk-job-create" = "1q0mvjb"
    "wecare-dlq-replay" = "2m1b2jr"
    "wecare-scheduled-messages" = "2wl78f5"
    "wecare-template-analytics" = "dx7l2df"
    "wecare-voice-cdr-read" = "0kznima"
}

$missingRoutes = @(
    @("GET /ai/internal/config", "wecare-ai-config-management"),
    @("POST /ai/agent", "wecare-agent-action-group"),
    @("POST /ai/generate", "wecare-ai-generate-response"),
    @("POST /ai/query", "wecare-ai-query-kb"),
    @("POST /billing", "wecare-billing"),
    @("POST /bulk/control", "wecare-bulk-job-control"),
    @("POST /bulk/create", "wecare-bulk-job-create"),
    @("POST /dlq/replay", "wecare-dlq-replay"),
    @("POST /scheduled", "wecare-scheduled-messages"),
    @("POST /templates/analytics", "wecare-template-analytics"),
    @("PUT /ai/internal/config", "wecare-ai-config-management"),
    @("POST /voice-cdr-webhook", "wecare-voice-cdr-read"),
    @("GET /voice-cdr-webhook", "wecare-voice-cdr-read")
)

$success = 0; $fail = 0

foreach ($route in $missingRoutes) {
    $routeKey = $route[0]
    $funcName = $route[1]
    $integrationId = $funcToIntegration[$funcName]
    
    Write-Host "Route: $routeKey -> $funcName (int: $integrationId)..." -NoNewline
    
    aws apigatewayv2 create-route --api-id $API_ID --route-key $routeKey --target "integrations/$integrationId" --region $REGION 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $success++
    } else {
        Write-Host " FAIL" -ForegroundColor Red
        $fail++
    }
}

Write-Host "`nDone: $success OK, $fail failed"
