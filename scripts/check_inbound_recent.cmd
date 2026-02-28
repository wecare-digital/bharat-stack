@echo off
for /f %%a in ('powershell -Command "[int64]((Get-Date).AddMinutes(-120).ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds"') do set START=%%a
aws logs filter-log-events --log-group-name /aws/lambda/wecare-inbound-whatsapp --start-time %START% --filter-pattern "payment" --limit 20 --region us-east-1 --output json --query "events[*].{time:timestamp,msg:message}"
