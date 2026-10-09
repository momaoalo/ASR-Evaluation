@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" diagnose_ui.py
) else (
  echo Project venv not found. Run SETUP_WINDOWS.bat first.
  python diagnose_ui.py
)
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
