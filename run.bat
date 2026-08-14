@echo off
chcp 65001 >nul
title PDF Toolkit v12 - Launcher
cd /d "%~dp0"

echo ============================================================
echo        PDF Toolkit v12  -  One-Click Launcher
echo ============================================================
echo.
echo This script will:
echo -----------------------------------------------
echo  [1] Check that Python is installed
echo  [2] Install the core libraries (light)
echo      from requirements.txt - first run only
echo  [3] Ask about OCR (optional, ~1GB)
echo  [4] Launch the program automatically
echo.
echo Note: First run takes a few minutes.
echo       Next runs take only seconds.
echo.
pause

echo.
echo ============================================================
echo  [1/4] Checking Python ...
echo ============================================================
python --version >nul 2>&1
if errorlevel 1 goto no_python
for /f "delims=" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo  [OK] Python found: %PYVER%

REM Supported: 3.10 - 3.13.  Python 3.14+ has no paddle wheels yet.
python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>&1
if errorlevel 1 goto py_version_warn
goto install_deps

:no_python
echo.
echo  [ERROR] Python was not found on this system!
echo.
echo  Please do the following:
echo   1 - Go to python.org
echo   2 - Download Python 3.10, 3.11, 3.12 or 3.13
echo   3 - During install, CHECK the option
echo      'Add Python to PATH'
echo   4 - After install, run this file again
echo.
pause
exit /b 1

:py_version_warn
echo.
echo  [WARNING] Unsupported Python version!
echo  The OCR stack (paddlepaddle) only supports
echo  Python 3.10 to 3.13. Python 3.14+ will fail.
echo.
echo  Please install Python 3.12 or 3.13 and run again.
echo.
pause
exit /b 1

:install_deps
echo.
echo ============================================================
echo  [2/4] Installing core libraries ...
echo ============================================================
echo  This step only takes long on the first run.
echo  Already installed packages are skipped.
echo.
python -m pip install -r requirements.txt
if errorlevel 1 goto install_fail
echo.
echo  [OK] Core libraries are ready.
echo.

:ask_ocr
echo ============================================================
echo  [3/4] OCR (optional, ~1GB download)
echo ============================================================
echo  OCR adds the "Automatic (OCR)" name detection
echo  for scanned PDFs. The app works fine without it
echo  (you can name files manually).
echo.
set /p OCR_CHOICE="Install OCR now? [y/N]: "
if /i "%OCR_CHOICE%"=="y" goto install_ocr
if /i "%OCR_CHOICE%"=="Y" goto install_ocr
echo  Skipping OCR - manual naming mode only.
goto run_app

:install_ocr
echo.
echo  Installing OCR stack (this can take a while)...
python -m pip install -r requirements-ocr.txt
if errorlevel 1 (
  echo  [WARNING] OCR install failed. The app will still
  echo  open, but automatic name detection needs OCR.
)
goto run_app

:install_fail
echo.
echo  [WARNING] Some libraries failed to install.
echo  The program will still open.
echo  Check your internet connection and run again.
echo.

:run_app
echo.
echo ============================================================
echo  [4/4] Launching the program ...
echo ============================================================
python pdf_toolkit_v12.py
if errorlevel 1 goto run_fail
goto end

:run_fail
echo.
echo  [ERROR] The program closed with an error.
echo  If it is related to OCR, make sure you have
echo  an internet connection - models download on
echo  the first run.
echo.

:end
echo.
echo  Program closed. Run this file again to restart.
echo.
pause
