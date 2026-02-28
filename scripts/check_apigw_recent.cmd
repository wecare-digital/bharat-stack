@echo off
REM Check API Gateway logs for recent /whatsapp/send calls
for /f %%a in ('powershell -Command "[int64]((Get-Date).AddMinutes(-120).ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds"') do set START=%%a
aws logs filter-log-events --log-group-name /aws/lambda/wecare-outbound-whatsapp --start-time %START% --limit 50 --region us-east-1 --output json --query "events[*].{time:timestamp,msg:message}"
