@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_MEDIA_WINDOWS.ps1" %*
if errorlevel 1 (
  echo.
  echo Media setup did not complete. Please review the error above.
  pause
  exit /b 1
)
echo.
echo Media tools are installed in this project's .tools folder.
pause
exit /b 0
