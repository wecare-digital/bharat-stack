@echo off
for /f %%a in ('powershell -Command "[int64]((Get-Date).AddMinutes(-5).ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds"') do set START=%%a
aws logs filter-log-events --log-group-name /aws/lambda/wecare-outbound-whatsapp --start-time %START% --filter-pattern "ERROR" --limit 10 --region us-east-1 --output json --query "events[*].message"
