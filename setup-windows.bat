@echo off
setlocal
cd /d "%~dp0"
echo Setting up LeafPress. The first setup downloads Python dependencies.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
    if errorlevel 1 goto python_missing
    py -3 -m venv .venv
) else (
    where python >nul 2>nul
    if errorlevel 1 goto python_missing
    python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
    if errorlevel 1 goto python_missing
    python -m venv .venv
)
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -e ".[gui]"
if errorlevel 1 goto failed
echo.
echo Setup complete. Double-click start-windows.bat to open LeafPress.
pause
exit /b 0

:python_missing
echo.
echo Install Python 3.12 or 3.13 from https://www.python.org/downloads/windows/
echo Enable the Python launcher or Add Python to PATH, then run this file again.
pause
exit /b 1

:failed
echo.
echo Setup failed. Read the error above, then run this file again after fixing it.
pause
exit /b 1
