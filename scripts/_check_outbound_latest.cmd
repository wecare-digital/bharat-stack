@echo off
aws logs filter-log-events --log-group-name "/aws/lambda/wecare-outbound-whatsapp" --filter-pattern "outbound_whatsapp_start" --start-time 1740528000000 --limit 5 --query "events[*].{ts:timestamp,msg:message}" --output json
