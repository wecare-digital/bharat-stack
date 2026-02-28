@echo off
REM Check from 14:00 UTC to now (covers the alarm period)
for /f %%a in ('powershell -Command "[int64]((Get-Date '2026-02-26T14:00:00Z').ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds"') do set START=%%a
aws logs filter-log-events --log-group-name /aws/lambda/wecare-outbound-whatsapp --start-time %START% --filter-pattern "outbound_whatsapp_start" --limit 30 --region us-east-1 --output json --query "events[*].{time:timestamp,msg:message}"
