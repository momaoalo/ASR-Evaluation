@echo off
setlocal
cd /d "%~dp0"
rem Portable FFmpeg/Deno: never change global system PATH.
set "PATH=%~dp0.tools\ffmpeg;%~dp0.tools\deno;%PATH%"
if not exist ".venv\Scripts\python.exe" (
  echo Run SETUP_WINDOWS.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run_tests.py
if errorlevel 1 echo Some checks failed. Review the output above.
pause
