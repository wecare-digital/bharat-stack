@echo off
aws logs filter-log-events --log-group-name "/aws/lambda/wecare-outbound-whatsapp" --filter-pattern "error" --start-time 1740528000000 --limit 10 --query "events[*].message" --output text
