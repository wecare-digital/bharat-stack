@echo off
REM Check all outbound logs from last 60 minutes
for /f %%a in ('powershell -Command "[int64]((Get-Date).AddMinutes(-60).ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds"') do set START=%%a
aws logs filter-log-events --log-group-name /aws/lambda/wecare-outbound-whatsapp --start-time %START% --filter-pattern "event" --limit 50 --region us-east-1 --output json --query "events[*].{time:timestamp,msg:message}"
