@echo off
setlocal
cd /d "%~dp0"
echo === ASR Evaluation - Windows setup ===
echo Working folder: %CD%
if exist ".venv\Scripts\python.exe" goto install
echo Creating the project Python environment...
where py >nul 2>&1
if errorlevel 1 goto fallback
py -3.12 -m venv .venv >nul 2>&1
if not errorlevel 1 goto install
py -3 -m venv .venv >nul 2>&1
if not errorlevel 1 goto install
:fallback
python -m venv .venv
if errorlevel 1 goto error
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
".venv\Scripts\python.exe" diagnose.py
echo.
echo Python dependencies installed in .venv. For live audio, FFmpeg and FFprobe must also be installed.
where ffmpeg >nul 2>&1
if errorlevel 1 echo Install FFmpeg: winget install -e --id Gyan.FFmpeg
where ffprobe >nul 2>&1
if errorlevel 1 echo FFprobe is also required. It comes with the FFmpeg installation.
where deno >nul 2>&1
if errorlevel 1 echo YouTube reliability: consider installing Deno 2.3+ from https://deno.com/
echo.
echo Setup finished. Double-click START_WINDOWS.bat to launch.
pause
exit /b 0
:error
echo Setup failed. Confirm Python 3.12+ is installed and review the error above.
pause
exit /b 1
