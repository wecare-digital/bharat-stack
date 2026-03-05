@echo off
setlocal enabledelayedexpansion

set SUCCESS=0
set FAIL=0

call :deploy wecare-inbound-whatsapp amplify\functions\messaging\inbound-whatsapp-handler\handler.py amplify\functions\messaging\inbound-whatsapp-handler\modules
call :deploy wecare-outbound-whatsapp amplify\functions\messaging\outbound-whatsapp\handler.py ""
call :deploy wecare-whatsapp-voice amplify\functions\messaging\whatsapp-voice\handler.py ""
call :deploy wecare-whatsapp-calling amplify\functions\messaging\whatsapp-calling\handler.py ""
call :deploy wecare-whatsapp-templates amplify\functions\messaging\whatsapp-templates\handler.py ""
call :deploy wecare-whatsapp-template-management amplify\functions\messaging\whatsapp-template-management\handler.py ""
call :deploy wecare-waba-management amplify\functions\messaging\waba-management\handler.py ""
call :deploy wecare-voice-in-cdr amplify\functions\messaging\voice-in\cdr\handler.py ""
call :deploy wecare-voice-in-c2c amplify\functions\messaging\voice-in\c2c\handler.py ""
call :deploy wecare-voice-in-obd amplify\functions\messaging\voice-in\obd\handler.py ""
call :deploy wecare-invoice-engine amplify\functions\payments\invoice-engine\handler.py ""
call :deploy wecare-bulk-job-control amplify\functions\operations\bulk-job-control\handler.py ""
call :deploy wecare-system-cleanup amplify\functions\operations\system-cleanup\handler.py ""
call :deploy wecare-wix-store amplify\functions\ecommerce\wix-store\handler.py ""
call :deploy wecare-product-image-gen amplify\functions\ecommerce\product-image-gen\handler.py ""

echo.
echo === RESULTS: %SUCCESS% succeeded, %FAIL% failed ===
goto :eof

:deploy
set FUNC=%~1
set HANDLER=%~2
set MODULES=%~3

echo --- %FUNC% ---
if exist scripts\_pkg rmdir /s /q scripts\_pkg
mkdir scripts\_pkg
mkdir scripts\_pkg\lambda_utils

copy /y %HANDLER% scripts\_pkg\handler.py >nul
copy /y amplify\functions\shared\lambda_utils\*.py scripts\_pkg\lambda_utils\ >nul

if not "%MODULES%"=="" if exist "%MODULES%" (
    mkdir scripts\_pkg\modules 2>nul
    copy /y "%MODULES%\*.py" scripts\_pkg\modules\ >nul
)

if exist amplify\functions\shared\static_knowledge_base.py copy /y amplify\functions\shared\static_knowledge_base.py scripts\_pkg\ >nul

powershell -NoProfile -Command "Compress-Archive -Path 'scripts\_pkg\*' -DestinationPath 'scripts\%FUNC%.zip' -Force" 2>nul

aws lambda update-function-code --function-name %FUNC% --zip-file fileb://scripts/%FUNC%.zip --region us-east-1 --no-cli-pager --output text --query FunctionName 2>nul
if !errorlevel! equ 0 (
    echo OK: %FUNC%
    set /a SUCCESS+=1
) else (
    echo FAIL: %FUNC%
    set /a FAIL+=1
)

if exist scripts\_pkg rmdir /s /q scripts\_pkg
if exist scripts\%FUNC%.zip del scripts\%FUNC%.zip
goto :eof
