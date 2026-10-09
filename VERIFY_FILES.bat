@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" verify_package.py
) else (
  python verify_package.py
)
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
