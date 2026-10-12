@echo off
setlocal
pushd "%~dp0" || exit /b 1
echo Installing Codex-Swarm Python requirements...
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "scripts\bootstrap.py"
    goto finished
)
where python >nul 2>nul
if not errorlevel 1 (
    python "scripts\bootstrap.py"
    goto finished
)
echo Python was not found. Install Python 3.11 or newer from python.org.
echo Select Add Python to PATH, reopen this window, and try again.
set "result=1"
goto return
:finished
set "result=%errorlevel%"
:return
popd
if /I not "%~1"=="--no-pause" pause
exit /b %result%
