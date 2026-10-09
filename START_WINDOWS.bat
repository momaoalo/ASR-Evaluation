@echo off
setlocal
cd /d "%~dp0"
rem Portable FFmpeg/Deno: never change global system PATH.
set "PATH=%~dp0.tools\ffmpeg;%~dp0.tools\deno;%PATH%"
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
