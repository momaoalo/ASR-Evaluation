@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No project environment found. Starting setup...
  call "%~dp0SETUP_WINDOWS.bat"
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -c "import flask, waitress, dotenv, yt_dlp" >nul 2>&1
if errorlevel 1 (
  echo Project dependencies are incomplete. Starting setup...
  call "%~dp0SETUP_WINDOWS.bat"
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" run_local.py
if errorlevel 1 pause
