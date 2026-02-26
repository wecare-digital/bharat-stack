@echo off
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/wecare-inbound" --query "logGroups[*].logGroupName" --output text
