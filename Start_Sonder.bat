@echo off
setlocal enabledelayedexpansion
title Sonder Engine

REM ---------------------------------------------------------------
REM  Double-click launcher for Sonder Engine.
REM  On first run it creates a virtual environment and installs
REM  dependencies. On later runs it just starts the server and
REM  opens your browser.
REM
REM  NOTE: the server below is started WITHOUT --reload, and that is
REM  deliberate. This is the launcher for PLAYING, and a code watcher
REM  buys a player nothing while costing real battery: uvicorn falls
REM  back to re-walking the whole folder and checking every .py file
REM  four times a second whenever watchfiles is missing, which
REM  measured 16% of a CPU core on an idle server. Sonder itself
REM  measures 0% sitting idle with a story open. If you are editing
REM  the code and want restarts, use "make run" instead.
REM ---------------------------------------------------------------

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8008"
set "URL=http://%HOST%:%PORT%"
set "VENV=.venv"
set "STAMP=%VENV%\.deps-installed"

REM --- Find a SUPPORTED Python ------------------------------------
REM Newest first, but only within the range this engine's pinned
REM dependencies are built for. `py -3` alone takes whatever is NEWEST on the
REM machine, which is how a reporter landed on 3.14.5: pydantic-core has no
REM wheel for it, so pip fell back to building from source, and that source
REM pins a PyO3 that refuses 3.14. The error arrives from a Rust compiler
REM three layers down and names neither Python nor this launcher.
set "PY="
for %%V in (3.13 3.12 3.11) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    REM No py launcher, or no supported version registered with it. A bare
    REM `python` is only accepted after it says what it is.
    for /f "delims=" %%O in ('python -c "import sys;print(1 if (3,11)<=sys.version_info[:2]<=(3,13) else 0)" 2^>nul') do set "PYOK=%%O"
    if "!PYOK!"=="1" set "PY=python"
)
if not defined PY (
    echo.
    echo [!] No supported Python was found.
    echo     Sonder needs Python 3.11, 3.12 or 3.13.
    echo.
    echo     A NEWER Python does not work yet: the pinned dependencies have no
    echo     prebuilt wheel for it, so pip tries to compile pydantic-core from
    echo     source and fails inside a Rust toolchain.
    echo.
    echo     Install one from https://www.python.org/downloads/
    echo     tick "Add Python to PATH", then run this file again.
    echo.
    pause
    exit /b 1
)
echo Using %PY%

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

REM --- An existing environment on an UNSUPPORTED interpreter ------
REM Reusing .venv is the whole point of a second run, so nothing above
REM re-checks which Python built it -- and a box that once had 3.14 keeps the
REM environment that failed, even after this launcher learned to choose
REM better. Detected, named, and never deleted: removing somebody's
REM environment to fix their environment is not this script's call to make.
REM The .sh has had this since it learned the ceiling; this file had not.
REM No `%` inside the -c string: in a batch file `%%d` is reduced by the
REM parser and FOR would read it as a second loop variable.
set "VENVOK=0"
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>&1
    if not errorlevel 1 set "VENVOK=1"
)
if "!VENVOK!"=="0" (
    for /f "delims=" %%O in ('"%VENV_PY%" -c "import sys;print('.'.join(str(v) for v in sys.version_info[:3]))" 2^>nul') do set "VENVVER=%%O"
    echo.
    REM Two separate lines on purpose: with delayed expansion on, an `!` in
    REM `[!]` pairs with the `!` opening `!VENVVER!` and eats the sentence.
    echo [!] This environment was built with an unsupported Python.
    echo     Found !VENVVER! in "%CD%\%VENV%"; the supported range is 3.11-3.13.
    echo.
    echo     Rename it ^(do not delete it -- it costs nothing to keep^):
    echo         move "%VENV%" "%VENV%-unsupported"
    echo.
    echo     then run this file again. It will build a new environment with a
    echo     supported Python and install the dependencies into it.
    echo.
    pause
    exit /b 1
)

REM --- Install / update dependencies -----------------------------
REM Three questions, not one. `if not exist "%STAMP%"` alone -- which is all
REM this file asked until 2026-08-19 -- means a player who takes an in-app
REM update across a dependency change runs the new code against the OLD
REM environment, permanently: `core/updates.py` never touches the stamp, and
REM `install_updates()` only says "Restart the server". The .sh has asked all
REM three for some time; this is the port.
REM
REM The stamp holds a DIGEST of the two dependency files rather than a date,
REM and both launchers now write the same thing. An mtime comparison is what
REM the .sh used and it is awkward in batch, but it is also wrong in a way
REM that matters here: a fresh `git clone` or a checkout gives every file the
REM same recent mtime, so "requirements is newer than the stamp" answers a
REM question about the filesystem rather than about the dependencies. A digest
REM answers the question that was meant.
set "NEED_DEPS="
set "WANT="
if not exist "%STAMP%" set "NEED_DEPS=1"
for /f "delims=" %%O in ('"%VENV_PY%" -c "import hashlib;h=hashlib.sha256();[h.update(open(f,'rb').read()) for f in ('requirements.txt','constraints.txt')];print(h.hexdigest())" 2^>nul') do set "WANT=%%O"
if not defined WANT set "NEED_DEPS=1"
if exist "%STAMP%" (
    set "HAVE="
    for /f "usebackq delims=" %%O in ("%STAMP%") do if not defined HAVE set "HAVE=%%O"
    if not "!HAVE!"=="!WANT!" (
        set "NEED_DEPS=1"
        echo Dependencies have changed since the last run; updating them.
    )
)
REM A stamp can outlive the environment it describes.
"%VENV_PY%" -c "import importlib.util as u,sys; sys.exit(0 if all(u.find_spec(m) for m in ('fastapi','uvicorn')) else 1)" >nul 2>&1
if errorlevel 1 (
    set "NEED_DEPS=1"
    echo The environment is missing packages it should have; reinstalling.
)

if defined NEED_DEPS (
    echo Installing dependencies ^(this may take a minute^)...
    "%VENV_PY%" -m pip install --upgrade pip
    REM -c constraints.txt: requirements.txt declares RANGES, and the range
    REM for fastapi resolves to versions CI never runs. One of them moved a
    REM Starlette internal this app had reached for, so a fresh install here
    REM could fail every api request while CI stayed green -- the people hit
    REM by that being exactly the ones running this launcher. Install what
    REM was actually tested.
    "%VENV_PY%" -m pip install -c constraints.txt -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [!] Failed to install dependencies.
        pause
        exit /b 1
    )
    REM The stamp records what was installed. If the digest could not be
    REM computed at all, write nothing rather than a placeholder: an absent
    REM stamp asks the question again next run, and a wrong one answers it.
    if defined WANT >"%STAMP%" echo !WANT!
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
echo   (No code watcher: idle, this costs near-zero CPU.)
echo ==================================================
echo.

REM  --timeout-graceful-shutdown: closing this window must actually close it.
REM  Uvicorn otherwise waits forever for a browser that has not finished
REM  reading a response, and a tab buffering an ambience bed is exactly that.
"%VENV_PY%" -m uvicorn web.app:app --host %HOST% --port %PORT% --timeout-graceful-shutdown 3

echo.
echo Server stopped.
pause
