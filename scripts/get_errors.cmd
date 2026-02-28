@echo off
REM Alarm triggered at 14:58 UTC on 26/02/26, errors at 14:53 UTC. Check from 14:45 to 15:10 UTC
REM 14:45 UTC = 1772116500000 (approx), let's use a wider window
for /f %%a in ('powershell -Command "[int64]((Get-Date '2026-02-26T14:45:00Z').ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds"') do set START=%%a
for /f %%a in ('powershell -Command "[int64]((Get-Date).ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds"') do set END=%%a
aws logs filter-log-events --log-group-name /aws/lambda/wecare-outbound-whatsapp --start-time %START% --end-time %END% --filter-pattern "ERROR" --limit 30 --region us-east-1 --output json --query "events[*].message"
