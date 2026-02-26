@echo off
aws dynamodb describe-table --table-name base-wecare-digital-MessagesTable --query Table.ItemCount --output text
