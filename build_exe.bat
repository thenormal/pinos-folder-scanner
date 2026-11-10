@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Building Pinos_Folder_Scanner.exe

echo ============================================================
echo   Pino's Folder Scanner - building the .exe
echo ============================================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo ERROR: Python is not installed.
    echo Download it from https://www.python.org/downloads/ and, during setup,
    echo tick "Add python.exe to PATH". Then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating the build environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
) else (
    echo [1/4] Build environment already there.
)
set "VPY=.venv\Scripts\python.exe"

echo [2/4] Installing the required packages. An internet connection is needed; the first run takes a few minutes...
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

if not exist "assets\icon.ico" (
    echo [3/4] Creating the icon...
    "%VPY%" tools\make_icon.py
    if errorlevel 1 goto :fail
) else (
    echo [3/4] Icon already there.
)

echo [4/4] Building the executable. This takes about a minute...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "Pinos_Folder_Scanner" ^
  --icon "assets\icon.ico" ^
  --collect-submodules reportlab.pdfbase ^
  --collect-data reportlab ^
  --collect-submodules openpyxl ^
  --exclude-module tkinter ^
  main.py
if errorlevel 1 goto :fail
if not exist "dist\Pinos_Folder_Scanner.exe" goto :fail

echo.
echo ============================================================
echo   DONE! The program is here:
echo   %~dp0dist\Pinos_Folder_Scanner.exe
echo   It is a single file: copy it wherever you like.
echo ============================================================
echo.
explorer "%~dp0dist"
pause
exit /b 0

:fail
echo.
echo ------------------------------------------------------------
echo   Something went wrong. Please copy the text above and open
echo   an issue on GitHub, so it can be looked at.
echo ------------------------------------------------------------
pause
exit /b 1
