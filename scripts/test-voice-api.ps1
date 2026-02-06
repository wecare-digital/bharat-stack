# Test Voice API Endpoints
# Run: .\scripts\test-voice-api.ps1

$baseUrl = "https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod"

Write-Host "Voice API Tests" -ForegroundColor Cyan
Write-Host "===============" -ForegroundColor Cyan
Write-Host ""

# Test 1: CDR Webhook
Write-Host "1. Testing CDR Webhook..." -ForegroundColor Yellow
$cdrPayload = @{
    vmSessionId = "test-session-$(Get-Date -Format 'yyyyMMddHHmmss')"
    clientCorrelationId = "Xchange123456"
    customerId = "WECAREDIG"
    callType = "OUTBOUND"
    overallCallStatus = "Answered"
    startTime = [long](Get-Date -UFormat %s) * 1000
    endTime = ([long](Get-Date -UFormat %s) + 60) * 1000
    duration = 60000
    conversationDuration = 45000
    callerNumber = "8130078559"
    destinationNumber = "7080003969"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/voice-cdr-webhook" -Method POST -ContentType "application/json" -Body $cdrPayload
    Write-Host "  Status: OK" -ForegroundColor Green
    Write-Host "  Response: $($response | ConvertTo-Json -Compress)"
} catch {
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# Test 2: C2C Call (will fail without proper auth, but tests endpoint)
Write-Host "2. Testing C2C Endpoint (dry run)..." -ForegroundColor Yellow
$c2cPayload = @{
    fromNumber = "8130078559"
    toNumber = "7080003969"
    enableRecording = $true
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/voice-c2c" -Method POST -ContentType "application/json" -Body $c2cPayload
    Write-Host "  Status: OK" -ForegroundColor Green
    Write-Host "  Response: $($response | ConvertTo-Json -Compress)"
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status: $statusCode (expected if secrets not configured)" -ForegroundColor Yellow
}

Write-Host ""

# Test 3: OBD List Campaigns
Write-Host "3. Testing OBD List Campaigns..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/voice-obd/list" -Method GET -ContentType "application/json"
    Write-Host "  Status: OK" -ForegroundColor Green
    Write-Host "  Campaigns: $($response.count)"
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status: $statusCode" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===============" -ForegroundColor Cyan
Write-Host "Webhook URL for Airtel:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  CDR Webhook:    $baseUrl/voice-cdr-webhook" -ForegroundColor White
Write-Host "  Events Webhook: $baseUrl/voice-cdr-webhook" -ForegroundColor White
Write-Host ""
Write-Host "Use these URLs in your Airtel C2C callBackURLs configuration." -ForegroundColor Gray
