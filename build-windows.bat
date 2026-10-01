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
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name PdfToEpubConverter --collect-all pymupdf --hidden-import pdftoepub.gui launcher.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" tools\check_frozen.py dist\PdfToEpubConverter\PdfToEpubConverter.exe examples\conversion-lab.pdf
if errorlevel 1 goto failed
copy /y LICENSE dist\PdfToEpubConverter\LICENSE >nul
copy /y THIRD_PARTY_NOTICES.md dist\PdfToEpubConverter\THIRD_PARTY_NOTICES.md >nul
copy /y START_HERE_IT.md dist\PdfToEpubConverter\START_HERE_IT.md >nul
xcopy /e /i /y examples dist\PdfToEpubConverter\examples >nul
".venv\Scripts\python.exe" tools\package_source.py dist\PdfToEpubConverter\PdfToEpubConverter-source.zip
if errorlevel 1 goto failed
echo.
echo Created dist\PdfToEpubConverter\PdfToEpubConverter.exe
echo Keep the whole dist\PdfToEpubConverter folder together when copying the application.
pause
exit /b 0
:failed
echo.
echo Build failed. Read the error above.
pause
exit /b 1
