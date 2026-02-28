@echo off
aws logs filter-log-events --log-group-name /aws/lambda/wecare-outbound-whatsapp --start-time %1 --filter-pattern "payment" --limit 30 --region us-east-1 --output json --query "events[*].message"
