$REGION = "us-east-1"

$tables = @(
    @{Name="base-wecare-digital-ContactsTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-WhatsAppInboundTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-WhatsAppOutboundTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-BulkJobsTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-BulkRecipientsTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-UsersTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-MediaFilesTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-DLQMessagesTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-AuditLogsTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-AIInteractionsTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-RateLimitTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-SystemConfigTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-SmsAwsTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-VoiceAwsTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-VoiceCalls"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-VoiceInC2CTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-VoiceInOBDTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-VoiceCDRTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-SmsInAirtelTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-ScheduledMessagesTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-TemplateAnalyticsTable"; PK="id"; PKType="S"},
    @{Name="base-wecare-digital-PaymentsTable"; PK="id"; PKType="S"}
)

$success = 0; $fail = 0

foreach ($t in $tables) {
    Write-Host "Creating $($t.Name)..." -NoNewline
    
    $check = aws dynamodb describe-table --table-name $t.Name --region $REGION 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " EXISTS" -ForegroundColor Yellow
        $success++
        continue
    }
    
    aws dynamodb create-table --table-name $t.Name --attribute-definitions "AttributeName=$($t.PK),AttributeType=$($t.PKType)" --key-schema "AttributeName=$($t.PK),KeyType=HASH" --billing-mode PAY_PER_REQUEST --region $REGION 2>$null | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $success++
    } else {
        Write-Host " FAIL" -ForegroundColor Red
        $fail++
    }
}

Write-Host "`nDone: $success OK, $fail failed"
