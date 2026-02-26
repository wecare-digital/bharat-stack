@echo off
aws logs filter-log-events --log-group-name "/aws/lambda/wecare-auth-middleware" --filter-pattern "8330919448" --start-time 1740560400000 --limit 20 --query "events[*].message" --output text
