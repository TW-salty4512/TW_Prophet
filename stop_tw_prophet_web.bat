@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ==============================
rem TW_Prophet Web Stopper
rem Usage:
rem   stop_tw_prophet_web.bat
rem   stop_tw_prophet_web.bat 8001
rem ==============================

set "APP_NAME=TW_Prophet Web"
set "PORT=8000"
if not "%~1"=="" set "PORT=%~1"
set "EXITCODE=0"

echo [%DATE% %TIME%] Stopping %APP_NAME% on port %PORT%...

set "FOUND=0"
set "PIDS= "

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "FOUND=1"
    rem # CHANGEPOINT dedupe PID before taskkill
    if "!PIDS: %%P =!"=="!PIDS!" (
        set "PIDS=!PIDS!%%P "
        echo [INFO] Stopping PID %%P ...
        taskkill /PID %%P /F >nul 2>&1
        if errorlevel 1 (
            echo [WARN] Failed to stop PID %%P.
        ) else (
            echo [OK] Stopped PID %%P.
        )
    )
)

if "%FOUND%"=="0" (
    echo [INFO] %APP_NAME% is not running on port %PORT%.
    set "EXITCODE=0"
    goto :finish
)

ping -n 2 127.0.0.1 >nul
set "REMAIN="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "REMAIN=1"
)

if defined REMAIN (
    echo [WARN] Port %PORT% is still in use.
    set "EXITCODE=1"
    goto :finish
)

echo [OK] %APP_NAME% stopped on port %PORT%.
set "EXITCODE=0"
goto :finish

:finish
exit /b %EXITCODE%
