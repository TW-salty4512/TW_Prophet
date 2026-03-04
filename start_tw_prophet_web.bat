@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ==============================
rem TW_Prophet Web Starter
rem Usage:
rem   start_tw_prophet_web.bat
rem   start_tw_prophet_web.bat 8001
rem ==============================

set "APP_NAME=TW_Prophet Web"
set "ENV_NAME=tw_prophet_web"
set "PORT=8000"
if not "%~1"=="" set "PORT=%~1"

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

rem ---- already running check ----
set "PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "PORT_PID=%%P"
    goto :already_running
)
goto :resolve_python

:already_running
echo [%DATE% %TIME%] %APP_NAME% is already running on port %PORT% (PID !PORT_PID!).
exit /b 0

:resolve_python
set "PYTHONW_EXE="
set "PYTHON_EXE="

rem CHANGED: auto-detect for dev/prod users.
for %%F in (
    "C:\Users\%USERNAME%\anaconda3\envs\%ENV_NAME%\pythonw.exe"
    "%USERPROFILE%\anaconda3\envs\%ENV_NAME%\pythonw.exe"
    "C:\Users\tsalt\anaconda3\envs\%ENV_NAME%\pythonw.exe"
    "C:\Users\techw\anaconda3\envs\%ENV_NAME%\pythonw.exe"
) do (
    if not defined PYTHONW_EXE if exist %%~F set "PYTHONW_EXE=%%~F"
)

for %%F in (
    "C:\Users\%USERNAME%\anaconda3\envs\%ENV_NAME%\python.exe"
    "%USERPROFILE%\anaconda3\envs\%ENV_NAME%\python.exe"
    "C:\Users\tsalt\anaconda3\envs\%ENV_NAME%\python.exe"
    "C:\Users\techw\anaconda3\envs\%ENV_NAME%\python.exe"
) do (
    if not defined PYTHON_EXE if exist %%~F set "PYTHON_EXE=%%~F"
)

if defined PYTHON_EXE (
    set "PY_LAUNCHER=!PYTHON_EXE!"
) else if defined PYTHONW_EXE (
    set "PY_LAUNCHER=!PYTHONW_EXE!"
) else (
    echo [ERROR] Python executable was not found for env "%ENV_NAME%".
    echo         Checked:
    echo         C:\Users\%USERNAME%\anaconda3\envs\%ENV_NAME%\pythonw.exe
    echo         C:\Users\%USERNAME%\anaconda3\envs\%ENV_NAME%\python.exe
    echo         C:\Users\tsalt\anaconda3\envs\%ENV_NAME%\pythonw.exe
    echo         C:\Users\techw\anaconda3\envs\%ENV_NAME%\pythonw.exe
    exit /b 1
)

echo [%DATE% %TIME%] Using Python launcher: !PY_LAUNCHER!
echo [%DATE% %TIME%] Starting %APP_NAME% on port %PORT%...

set "PORT=%PORT%"
start "%APP_NAME%" /min "!PY_LAUNCHER!" "%SCRIPT_DIR%run_web.py"
if errorlevel 1 (
    echo [ERROR] Failed to start process.
    exit /b 1
)

timeout /t 2 >nul
set "NEW_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "NEW_PID=%%P"
    goto :started
)

echo [WARN] Start command was issued but port %PORT% is not listening yet.
echo        Wait a few seconds and retry.
exit /b 0

:started
echo [OK] %APP_NAME% started on port %PORT% (PID !NEW_PID!).
exit /b 0
