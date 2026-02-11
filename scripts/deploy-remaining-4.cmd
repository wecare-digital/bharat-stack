@echo off
echo [1/4] wecare-outbound-whatsapp
powershell -Command "Compress-Archive -Path amplify\functions\messaging\outbound-whatsapp\handler.py -DestinationPath scripts\_tmp.zip -Force; cmd /c 'aws lambda update-function-code --function-name wecare-outbound-whatsapp --zip-file fileb://scripts/_tmp.zip --region us-east-1 --no-cli-pager --query FunctionName --output text'"
echo [2/4] wecare-whatsapp-business-api
powershell -Command "Compress-Archive -Path amplify\functions\messaging\whatsapp-business-api\handler.py -DestinationPath scripts\_tmp.zip -Force; cmd /c 'aws lambda update-function-code --function-name wecare-whatsapp-business-api --zip-file fileb://scripts/_tmp.zip --region us-east-1 --no-cli-pager --query FunctionName --output text'"
echo [3/4] wecare-waba-management
powershell -Command "Compress-Archive -Path amplify\functions\messaging\waba-management\handler.py -DestinationPath scripts\_tmp.zip -Force; cmd /c 'aws lambda update-function-code --function-name wecare-waba-management --zip-file fileb://scripts/_tmp.zip --region us-east-1 --no-cli-pager --query FunctionName --output text'"
echo [4/4] wecare-payments-read
powershell -Command "Compress-Archive -Path amplify\functions\payments\payments-read\handler.py -DestinationPath scripts\_tmp.zip -Force; cmd /c 'aws lambda update-function-code --function-name wecare-payments-read --zip-file fileb://scripts/_tmp.zip --region us-east-1 --no-cli-pager --query FunctionName --output text'"
echo === DONE ===
