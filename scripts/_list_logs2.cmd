@echo off
aws lambda list-functions --query "Functions[?starts_with(FunctionName,'wecare-inbound')].FunctionName" --output text
