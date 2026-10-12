@echo off
setlocal
pushd "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    call install_requirements.bat --no-pause
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" "main.py" %*
set "result=%errorlevel%"
if not "%result%"=="0" goto failed
popd
exit /b 0
:failed
echo.
echo Codex-Swarm could not start. Read the error above.
echo If dependencies are missing, run install_requirements.bat again.
popd
pause
exit /b 1
