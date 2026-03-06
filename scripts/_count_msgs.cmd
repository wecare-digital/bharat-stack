@echo off
aws dynamodb scan --table-name stack-wecare-digital-MessagesTable --select COUNT --output json
