@echo off
setlocal enabledelayedexpansion
title Sonder Engine

REM ---------------------------------------------------------------
REM  Double-click launcher for Sonder Engine.
REM  On first run it creates a virtual environment and installs
REM  dependencies. On later runs it just starts the server and
REM  opens your browser.
REM ---------------------------------------------------------------

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8008"
set "URL=http://%HOST%:%PORT%"
set "VENV=.venv"
set "STAMP=%VENV%\.deps-installed"

REM --- Find a usable Python launcher -----------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo.
    echo [!] Python was not found on this computer.
    echo     Install Python 3.11+ from https://www.python.org/downloads/
    echo     and be sure to tick "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

REM --- Create the virtual environment on first run ---------------
if not exist "%VENV%\Scripts\python.exe" (
    echo Creating virtual environment ^(first-time setup^)...
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo [!] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PY=%VENV%\Scripts\python.exe"

REM --- Install / update dependencies -----------------------------
if not exist "%STAMP%" (
    echo Installing dependencies ^(this may take a minute^)...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [!] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo done> "%STAMP%"
)

REM --- Open the browser once the server has had time to boot -----
start "" cmd /c "timeout /t 4 >nul & start "" %URL%"

REM --- Start the server ------------------------------------------
echo.
echo ==================================================
echo   Sonder Engine is starting...
echo   Opening %URL% in your browser.
echo   Keep this window open while you play.
echo   Close this window to stop the server.
echo ==================================================
echo.

"%VENV_PY%" -m uvicorn app:app --host %HOST% --port %PORT%

echo.
echo Server stopped.
pause
