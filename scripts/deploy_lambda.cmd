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

REM Copy handler
copy %HANDLER% scripts\_pkg\handler.py
if errorlevel 1 (echo ERROR: Failed to copy handler && exit /b 1)

REM Copy shared utils
copy amplify\functions\shared\lambda_utils\*.py scripts\_pkg\lambda_utils\
if errorlevel 1 (echo ERROR: Failed to copy lambda_utils && exit /b 1)

REM Copy modules directory if it exists alongside the handler (e.g. inbound-whatsapp-handler)
for %%H in (%HANDLER%) do set HANDLER_DIR=%%~dpH
if exist "%HANDLER_DIR%modules" (
    echo Copying modules directory...
    mkdir scripts\_pkg\modules 2>nul
    copy "%HANDLER_DIR%modules\*.py" scripts\_pkg\modules\
)

REM Copy static knowledge base if exists
if exist amplify\functions\shared\static_knowledge_base.py copy amplify\functions\shared\static_knowledge_base.py scripts\_pkg\

REM Create zip
powershell -Command "Compress-Archive -Path 'scripts/_pkg/*' -DestinationPath 'scripts/%FUNC%.zip' -Force"
if not exist "scripts\%FUNC%.zip" (echo ERROR: Zip file not created && exit /b 1)

REM Deploy to AWS
aws lambda update-function-code --function-name %FUNC% --zip-file fileb://scripts/%FUNC%.zip --region us-east-1 --output json --query "FunctionName"
if errorlevel 1 (
    echo ERROR: Lambda deployment failed for %FUNC%
    rmdir /s /q scripts\_pkg
    exit /b 1
)

REM Verify deployment
echo Verifying deployment...
aws lambda get-function --function-name %FUNC% --region us-east-1 --query "Configuration.{State:State,LastModified:LastModified}" --output table 2>nul
if errorlevel 1 (echo WARNING: Could not verify deployment status)

REM Cleanup
rmdir /s /q scripts\_pkg
if exist "scripts\%FUNC%.zip" del "scripts\%FUNC%.zip"
echo === Done ===
