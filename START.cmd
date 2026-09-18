@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Subtitle Service
if exist settings.cmd call settings.cmd
if exist work\.venv\Scripts\python.exe goto ready
echo Setup is not complete. Run deployment script first.
pause
exit /b 1
:ready
echo Starting subtitle service. Keep the service window open.
start "Subtitle Service - keep this window open" cmd /k ""%~dp0work\.venv\Scripts\python.exe" "%~dp0subtitle_web.py""
echo Waiting for the local service, then opening the web page...
"%~dp0work\.venv\Scripts\python.exe" "%~dp0open_browser.py"
exit /b 0
