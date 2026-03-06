@echo off
aws dynamodb describe-table --table-name stack-wecare-digital-MessagesTable --query Table.ItemCount --output text
