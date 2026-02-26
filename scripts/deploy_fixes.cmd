@echo off
echo === Deploying outbound-whatsapp (messageType fix) ===
powershell -Command "Compress-Archive -Path 'amplify/functions/messaging/outbound-whatsapp/handler.py','amplify/functions/shared/lambda_utils/*' -DestinationPath 'scripts/outbound-whatsapp.zip' -Force"
aws lambda update-function-code --function-name wecare-outbound-whatsapp --zip-file fileb://scripts/outbound-whatsapp.zip --region us-east-1 --output json --query "FunctionName"

echo === Deploying razorpay-webhook (invoice paid fix) ===
powershell -Command "Compress-Archive -Path 'amplify/functions/payments/razorpay-webhook/handler.py','amplify/functions/shared/lambda_utils/*' -DestinationPath 'scripts/razorpay-webhook.zip' -Force"
aws lambda update-function-code --function-name wecare-razorpay-webhook --zip-file fileb://scripts/razorpay-webhook.zip --region us-east-1 --output json --query "FunctionName"

echo === Done ===
