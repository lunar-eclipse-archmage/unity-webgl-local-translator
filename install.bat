@echo off
setlocal
cd /d "%~dp0"
if not exist local.py copy /y local.example.py local.py >nul
set "TEMP=%~dp0tmp"
set "TMP=%~dp0tmp"
if not exist "%TEMP%" mkdir "%TEMP%"
python3 -m pip install --no-cache-dir --target "%~dp0python_libs" -r requirements.txt
if errorlevel 1 (
  echo Installation failed. Fix the error above before starting.
  pause
  exit /b 1
)
echo Installation complete.
pause
