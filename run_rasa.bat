@echo off

:: Check if the script is running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c %~s0' -Verb RunAs"
    exit /b
)

:: Change to drive D:
D:

:: Navigate to the directory
cd D:\CelcomDigi\chatbot-rasa

:: Activate virtual environment
call venv\Scripts\activate

:: Run the Rasa actions server
rasa run actions --port 5055
