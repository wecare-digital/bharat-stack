@echo off
aws logs filter-log-events --log-group-name "/aws/lambda/wecare-outbound-whatsapp" --filter-pattern "invoice" --start-time 1740700800000 --limit 20 --query "events[*].message" --output text
