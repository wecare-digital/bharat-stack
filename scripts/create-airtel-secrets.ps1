# Create Airtel API secrets in AWS Secrets Manager
# Run this script once to set up the secrets

$region = "us-east-1"

# C2C (Click-to-Call) Secret - Kong HMAC Auth
$c2cSecret = @{
    app_id = "WECAREDIG_fD4BKqUbC8k90jNrPR0n"
    api_key = "u^5KLtH@11"
    caller_id = "8047311032"
} | ConvertTo-Json -Compress

Write-Host "Creating wecare/airtel/c2c secret..."
try {
    aws secretsmanager create-secret `
        --name "wecare/airtel/c2c" `
        --description "Airtel Click-to-Call API credentials (Kong HMAC auth)" `
        --secret-string $c2cSecret `
        --region $region
    Write-Host "  Created successfully"
} catch {
    Write-Host "  Secret may already exist, updating..."
    aws secretsmanager update-secret `
        --secret-id "wecare/airtel/c2c" `
        --secret-string $c2cSecret `
        --region $region
}

# OBD (Outbound Dialer) Secret - Basic Auth
$obdSecret = @{
    customer_id = "WECAREDIG_v6J1SyLLI2auy7Lw9JrW"
    auth = "RElHSVRBTF9WSV9MS2lwdFBzTTZqWHBtQ0NtNWduSDpec3g3OzF5fUReciQ7X20/S2p5VlZW"
    campaign_auth = "TUVFU0hPX1RFQ181bjVid2RMdnpjOXdSMlhqd29ySjpxLGRpdWotbFUwTiEjRzY5VWs="
    app_id = "IRONMAN"
    call_flow_id = "dfbeda76-f641-420f-95e7-b78d562a941f"
    caller_id = "8040761117"
    template_id = "69818654d9e8e260e60b16a7"
} | ConvertTo-Json -Compress

Write-Host "Creating wecare/airtel/obd secret..."
try {
    aws secretsmanager create-secret `
        --name "wecare/airtel/obd" `
        --description "Airtel OBD Campaign API credentials (Basic auth)" `
        --secret-string $obdSecret `
        --region $region
    Write-Host "  Created successfully"
} catch {
    Write-Host "  Secret may already exist, updating..."
    aws secretsmanager update-secret `
        --secret-id "wecare/airtel/obd" `
        --secret-string $obdSecret `
        --region $region
}

# SMS (Airtel IQ Messaging) Secret - Basic Auth
# Username: WECAREDIG_v6J1SyLLI2auy7Lw9JrW
# Password: sN$~|(I@112
$smsSecret = @{
    customer_id = "WECAREDIG_v6J1SyLLI2auy7Lw9JrW"
    auth_token = "V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy"
    sender_id = "WDBEEP"
    entity_id = "1201161991108627443"
    dlt_template_id = "1007974344269130859"
    dlt_template_id_2 = "1007101741507674990"
} | ConvertTo-Json -Compress

Write-Host "Creating wecare/airtel/sms secret..."
try {
    aws secretsmanager create-secret `
        --name "wecare/airtel/sms" `
        --description "Airtel IQ SMS API credentials (Basic auth)" `
        --secret-string $smsSecret `
        --region $region
    Write-Host "  Created successfully"
} catch {
    Write-Host "  Secret may already exist, updating..."
    aws secretsmanager update-secret `
        --secret-id "wecare/airtel/sms" `
        --secret-string $smsSecret `
        --region $region
}

Write-Host ""
Write-Host "Done! Secrets created/updated."
Write-Host ""
Write-Host "Lambda functions using these secrets:"
Write-Host "  - wecare-voice-in-c2c   -> wecare/airtel/c2c"
Write-Host "  - wecare-voice-in-obd   -> wecare/airtel/obd"
Write-Host "  - wecare-sms-in-airtel  -> wecare/airtel/sms"
Write-Host ""
Write-Host "Required IAM Policy for Lambda:"
Write-Host '  {
    "Effect": "Allow",
    "Action": ["secretsmanager:GetSecretValue"],
    "Resource": ["arn:aws:secretsmanager:us-east-1:809904170947:secret:wecare/airtel/*"]
  }'
