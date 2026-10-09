@echo off
setlocal
cd /d "%~dp0"
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312-arm64\python.exe"
if exist "%PYEXE%" goto chosen
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PYEXE%" goto chosen
set "PYEXE=python"
:chosen
"%PYEXE%" --version
if errorlevel 1 goto error
"%PYEXE%" -m pip install -r requirements.txt
if errorlevel 1 goto error
"%PYEXE%" diagnose.py
echo.
echo Setup finished. Open START_WINDOWS.bat next.
pause
exit /b 0
:error
echo.
echo Setup did not complete. Read the error above before starting.
pause
exit /b 1
