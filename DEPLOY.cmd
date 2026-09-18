@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Subtitle Tool Setup
echo Subtitle Tool setup started.
echo Log file: %~dp0install.log
echo [%date% %time%] started>install.log

where winget >nul 2>&1
if not exist "%SystemRoot%\System32\winget.exe" if not exist "%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe" (
  echo winget is not available. Install App Installer from Microsoft Store, then run this file again.
  echo winget missing>>install.log
  cmd /k
  exit /b
)

where py >nul 2>&1
if not errorlevel 1 goto python_ready
  echo Downloading and installing Python. Please wait...
winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
:python_ready
if exist settings.cmd goto settings_ready
echo A folder picker will open. Select a location for models and cache.
for /f "delims=" %%A in ('py -3 "%~dp0choose_folder.py"') do set "DATA_DIR=%%A"
if not defined DATA_DIR set "DATA_DIR=%~dp0data"
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
>settings.cmd echo set "HF_HOME=%DATA_DIR%\huggingface"
>>settings.cmd echo set "PIP_CACHE_DIR=%DATA_DIR%\pip-cache"
:settings_ready
call settings.cmd

where ffmpeg >nul 2>&1
if not errorlevel 1 goto ffmpeg_ready
echo Downloading and installing FFmpeg. Please wait...
winget install --id Gyan.FFmpeg.Shared -e --accept-source-agreements --accept-package-agreements
:ffmpeg_ready

if exist work\.venv\Scripts\python.exe goto env_ready
echo Downloading speech recognition components. Please wait and keep this window open...
py -3 -m venv work\.venv
work\.venv\Scripts\python.exe -m pip install --upgrade pip
work\.venv\Scripts\python.exe -m pip install -r requirements.txt
:env_ready

echo Setup complete. Models and cache: %DATA_DIR%
echo Double-click START.cmd to open the web tool.
echo [%date% %time%] finished>>install.log
cmd /k
