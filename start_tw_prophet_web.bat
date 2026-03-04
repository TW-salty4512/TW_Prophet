@echo off
setlocal

rem # CHANGEPOINT Use gitignored local launcher first (dev/prod specific)
if exist "%~dp0start_tw_prophet_web.local.bat" (
    call "%~dp0start_tw_prophet_web.local.bat" %*
    exit /b %errorlevel%
)

rem # CHANGEPOINT Default: run run_web.py from this directory
pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot open script directory: "%~dp0"
    exit /b 1
)

python run_web.py
set "EXITCODE=%errorlevel%"
popd >nul 2>&1
exit /b %EXITCODE%
