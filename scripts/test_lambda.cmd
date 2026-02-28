@echo off
echo === Testing outbound-whatsapp Lambda import ===
aws lambda invoke --function-name wecare-outbound-whatsapp --payload "{}" --region us-east-1 scripts\_test_output.json --output json --query "StatusCode"
type scripts\_test_output.json
echo.
echo === Checking for recent errors after fix ===
for /f %%a in ('powershell -Command "[int64]((Get-Date).AddMinutes(-3).ToUniversalTime() - [datetime]''1970-01-01'').TotalMilliseconds"') do set START=%%a
aws logs filter-log-events --log-group-name /aws/lambda/wecare-outbound-whatsapp --start-time %START% --filter-pattern "ERROR" --limit 5 --region us-east-1 --output json --query "events[*].message"
