@echo off
aws dynamodb scan --table-name base-wecare-digital-MessagesTable --select COUNT --output json
