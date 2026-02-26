@echo off
aws logs filter-log-events --log-group-name "/aws/lambda/wecare-whatsapp-business-api" --filter-pattern "flow_submit" --start-time 1740355200000 --limit 10 --query "events[*].message" --output text
