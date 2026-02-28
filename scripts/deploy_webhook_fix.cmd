@echo off
echo === Building razorpay-webhook zip with correct structure ===
if exist scripts\razorpay-webhook.zip del scripts\razorpay-webhook.zip
if exist scripts\_pkg rmdir /s /q scripts\_pkg
mkdir scripts\_pkg
mkdir scripts\_pkg\lambda_utils
copy amplify\functions\payments\razorpay-webhook\handler.py scripts\_pkg\handler.py
copy amplify\functions\shared\lambda_utils\*.py scripts\_pkg\lambda_utils\
powershell -Command "Compress-Archive -Path 'scripts/_pkg/*' -DestinationPath 'scripts/razorpay-webhook.zip' -Force"
echo === Deploying ===
aws lambda update-function-code --function-name wecare-razorpay-webhook --zip-file fileb://scripts/razorpay-webhook.zip --region us-east-1 --output json --query "FunctionName"
echo === Cleaning up ===
rmdir /s /q scripts\_pkg
echo === Done ===
