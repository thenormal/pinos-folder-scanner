@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Pino's Folder Scanner - run from source

rem Starts the program without building the .exe (handy while changing the code).

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo ERROR: Python is not installed. See README.md.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo First run: installing the required packages. An internet connection is needed...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :fail
)

start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:fail
echo.
echo Something went wrong. Please copy the text above and open an issue on GitHub.
pause
exit /b 1
