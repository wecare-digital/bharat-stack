@echo off
REM Get logs from last 30 minutes
for /f %%a in ('powershell -Command "[int]((Get-Date).AddMinutes(-30).ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds"') do set START=%%a
aws logs filter-log-events --log-group-name /aws/lambda/wecare-outbound-whatsapp --start-time %START% --limit 50 --region us-east-1 --output json --query "events[*].message"
