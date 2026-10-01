@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup-windows.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m leafpress gui
if errorlevel 1 pause
