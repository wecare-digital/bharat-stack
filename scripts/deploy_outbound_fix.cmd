@echo off
echo === Building outbound-whatsapp zip with correct structure ===
if exist scripts\outbound-whatsapp.zip del scripts\outbound-whatsapp.zip
if exist scripts\_pkg rmdir /s /q scripts\_pkg
mkdir scripts\_pkg
mkdir scripts\_pkg\lambda_utils
copy amplify\functions\messaging\outbound-whatsapp\handler.py scripts\_pkg\handler.py
copy amplify\functions\shared\lambda_utils\*.py scripts\_pkg\lambda_utils\
powershell -Command "Compress-Archive -Path 'scripts/_pkg/*' -DestinationPath 'scripts/outbound-whatsapp.zip' -Force"
echo === Deploying ===
aws lambda update-function-code --function-name wecare-outbound-whatsapp --zip-file fileb://scripts/outbound-whatsapp.zip --region us-east-1 --output json --query "FunctionName"
echo === Cleaning up ===
rmdir /s /q scripts\_pkg
echo === Done ===
