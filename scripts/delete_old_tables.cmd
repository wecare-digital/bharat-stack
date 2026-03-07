@echo off
REM Delete all old base-wecare-digital DynamoDB tables
REM These have been replaced by stack-wecare-digital tables

for %%T in (base-wecare-digital-AIInteractionsTable base-wecare-digital-AirtelC2CTable base-wecare-digital-AirtelSMSTable base-wecare-digital-AuditLogsTable base-wecare-digital-BulkJobsTable base-wecare-digital-BulkRecipientsTable base-wecare-digital-ContactsTable base-wecare-digital-ConversationHistoryTable base-wecare-digital-DLQMessagesTable base-wecare-digital-DLTTemplates) do (
    echo Deleting %%T...
    aws dynamodb delete-table --table-name %%T --region us-east-1 --no-cli-pager --output text --query "TableDescription.TableStatus" 2>nul
)

for %%T in (base-wecare-digital-InvoiceAssetsTable base-wecare-digital-InvoiceDeliveryLogTable base-wecare-digital-InvoiceItemsTable base-wecare-digital-InvoiceSequenceTable base-wecare-digital-InvoicesTable base-wecare-digital-MediaFilesTable base-wecare-digital-MessagesTable base-wecare-digital-OBDCampaigns base-wecare-digital-PayUWebhookLogTable base-wecare-digital-PaymentsTable) do (
    echo Deleting %%T...
    aws dynamodb delete-table --table-name %%T --region us-east-1 --no-cli-pager --output text --query "TableDescription.TableStatus" 2>nul
)

for %%T in (base-wecare-digital-RateLimitTable base-wecare-digital-RazorpayWebhookLogTable base-wecare-digital-ScheduledMessagesTable base-wecare-digital-SmsAwsTable base-wecare-digital-SmsInAirtelTable base-wecare-digital-SubmitRequestsTable base-wecare-digital-SystemConfigTable base-wecare-digital-TemplateAnalyticsTable base-wecare-digital-UsersTable base-wecare-digital-VoiceAwsTable) do (
    echo Deleting %%T...
    aws dynamodb delete-table --table-name %%T --region us-east-1 --no-cli-pager --output text --query "TableDescription.TableStatus" 2>nul
)

for %%T in (base-wecare-digital-VoiceCDRTable base-wecare-digital-VoiceCalls base-wecare-digital-WhatsAppCallingTable base-wecare-digital-WhatsAppInboundTable base-wecare-digital-WhatsAppOutboundTable base-wecare-digital-WhatsAppVoiceTable base-wecare-digital-WixOrderIds base-wecare-digital-WixOrdersCache base-wecare-digital-WixProductsCache) do (
    echo Deleting %%T...
    aws dynamodb delete-table --table-name %%T --region us-east-1 --no-cli-pager --output text --query "TableDescription.TableStatus" 2>nul
)

echo === All old base-wecare-digital tables deleted ===
