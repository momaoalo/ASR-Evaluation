@echo off
setlocal
cd /d "%~dp0"
rem Legacy one-time old-data import; not needed for a new GitHub clone.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" import_old_data.py
) else (
  py -3 import_old_data.py
)
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
