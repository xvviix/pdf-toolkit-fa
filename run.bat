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
echo  [2] Install all required libraries
echo      from requirements.txt - first run only
echo  [3] Launch the program automatically
echo.
echo Note: First run takes a few minutes.
echo       Next runs take only seconds.
echo.
pause

echo.
echo ============================================================
echo  [1/3] Checking Python ...
echo ============================================================
python --version >nul 2>&1
if errorlevel 1 goto no_python
for /f "delims=" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo  [OK] Python found: %PYVER%

REM Check Python version is suitable for OCR - 3.8 to 3.12
python -c "import sys; sys.exit(0 if (3,8) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>&1
if errorlevel 1 goto py_version_warn
goto install_deps

:no_python
echo.
echo  [ERROR] Python was not found on this system!
echo.
echo  Please do the following:
echo   1 - Go to python.org
echo   2 - Download Python 3.10 to 3.12
echo   3 - During install, CHECK the option
echo      'Add Python to PATH'
echo   4 - After install, run this file again
echo.
pause
exit /b 1

:py_version_warn
echo  [WARNING] Your Python version is 3.13 or newer.
echo  Automatic name detection OCR may not work.
echo  It is recommended to install Python 3.12.
echo.

:install_deps
echo.
echo ============================================================
echo  [2/3] Installing required libraries ...
echo ============================================================
echo  This step only takes long on the first run.
echo  Already installed packages are skipped.
echo.
python -m pip install -r requirements.txt
if errorlevel 1 goto install_fail
echo.
echo  [OK] All libraries are ready.
echo.
goto run_app

:install_fail
echo.
echo  [WARNING] Some libraries failed to install.
echo  The program will still open.
echo  If automatic name detection does not work,
echo  check your internet connection and run again.
echo.

:run_app
echo.
echo ============================================================
echo  [3/3] Launching the program ...
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
