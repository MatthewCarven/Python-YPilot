@echo off
REM Double-click-friendly wrapper for build.py. Passes any extra args
REM through to the Python script (so `build.bat --clean` works too).
REM
REM Output: dist\YPilot.exe
REM
REM Requires Python on PATH plus pygame-ce installed. PyInstaller
REM auto-installs on first run if missing.

setlocal
cd /d "%~dp0"
python build.py %*
set EXIT=%ERRORLEVEL%
if %EXIT% NEQ 0 (
    echo.
    echo Build failed with exit code %EXIT%.
)
echo.
pause
endlocal
