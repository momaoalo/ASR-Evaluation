@echo off
setlocal
cd /d "%~dp0"
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312-arm64\python.exe"
if exist "%PYEXE%" goto chosen
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PYEXE%" goto chosen
set "PYEXE=python"
:chosen
"%PYEXE%" run_tests.py
pause
