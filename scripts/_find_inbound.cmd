@echo off
aws lambda get-function --function-name wecare-inbound-whatsapp-handler --query Configuration.FunctionName --output text
