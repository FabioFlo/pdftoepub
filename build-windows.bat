@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup-windows.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -e ".[gui,build]"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name LeafPress --collect-all pymupdf --hidden-import leafpress.gui launcher.py
if errorlevel 1 goto failed
echo.
echo Created dist\LeafPress\LeafPress.exe
echo Keep the whole dist\LeafPress folder together when copying the application.
pause
exit /b 0
:failed
echo.
echo Build failed. Read the error above.
pause
exit /b 1
