@echo off
aws logs filter-log-events --log-group-name "/aws/lambda/wecare-inbound-whatsapp-handler" --filter-pattern "8330919448" --start-time 1740700800000 --limit 10 --query "events[*].message" --output text
