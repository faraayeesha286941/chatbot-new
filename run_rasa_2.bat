@echo off

:: Check if the script is running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c %~s0' -Verb RunAs"
    exit /b
)

:: Change to drive D:
C:

:: Navigate to the directory
cd C:\Users\noora\Desktop\GITHUB CD\internal\chatbot-new

:: Activate virtual environment
call venv\Scripts\activate

:: Run the Rasa actions server
rasa run --cors "*" --enable-api --port 5005
