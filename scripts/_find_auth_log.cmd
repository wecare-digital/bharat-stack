@echo off
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/wecare-auth" --query "logGroups[*].logGroupName" --output text
