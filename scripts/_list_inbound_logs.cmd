@echo off
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/wecare --query logGroups[*].logGroupName --output json
