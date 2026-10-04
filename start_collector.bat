@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0python_libs"
python3 collector.py
pause
