@echo off
aws lambda get-function-url-config --function-name wecare-outbound-whatsapp --output json 2>&1
