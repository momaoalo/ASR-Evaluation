@echo off
setlocal
cd /d "%~dp0"
rem Legacy upgrade for a complete archived ZIP, never for a Git checkout.
if exist ".git" (
  echo This is a GitHub clone. Use git pull --ff-only then SETUP_WINDOWS.bat instead.
  echo UPDATE_EXISTING.bat is ONLY for the historical full ZIP release.
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" update_existing.py
) else (
  py -3 update_existing.py
)
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
