@echo off
setlocal
cd /d "%~dp0"
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312-arm64\python.exe"
if exist "%PYEXE%" goto chosen
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PYEXE%" goto chosen
set "PYEXE=python"
:chosen
"%PYEXE%" -c "import flask, waitress, dotenv" >nul 2>&1
if errorlevel 1 (
  echo Python dependencies are missing for this interpreter.
  echo Run SETUP_WINDOWS.bat once, or select the Python used during setup.
  pause
  exit /b 1
)
"%PYEXE%" run_local.py
if errorlevel 1 pause
