@echo off
REM Usage: deploy_lambda.cmd <function-name> <handler-path>
REM Example: deploy_lambda.cmd wecare-outbound-whatsapp amplify\functions\messaging\outbound-whatsapp\handler.py
set FUNC=%1
set HANDLER=%2
if "%FUNC%"=="" (echo Usage: deploy_lambda.cmd ^<function-name^> ^<handler-path^> && exit /b 1)
if "%HANDLER%"=="" (echo Usage: deploy_lambda.cmd ^<function-name^> ^<handler-path^> && exit /b 1)

echo === Deploying %FUNC% ===
if exist scripts\_pkg rmdir /s /q scripts\_pkg
mkdir scripts\_pkg
mkdir scripts\_pkg\lambda_utils
copy %HANDLER% scripts\_pkg\handler.py
copy amplify\functions\shared\lambda_utils\*.py scripts\_pkg\lambda_utils\
if exist amplify\functions\shared\static_knowledge_base.py copy amplify\functions\shared\static_knowledge_base.py scripts\_pkg\
powershell -Command "Compress-Archive -Path 'scripts/_pkg/*' -DestinationPath 'scripts/%FUNC%.zip' -Force"
aws lambda update-function-code --function-name %FUNC% --zip-file fileb://scripts/%FUNC%.zip --region us-east-1 --output json --query "FunctionName"
rmdir /s /q scripts\_pkg
echo === Done ===
