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
set "EXITCODE=0"

set "DEV_APP_DIR=C:\Users\tsalt\Dev\TW_Prophet\project\"
set "SCRIPT_DIR="
set "PROD_APP_DIR="

rem # CHANGEPOINT allow explicit override by env var
if defined TW_PROPHET_APP_DIR set "SCRIPT_DIR=%TW_PROPHET_APP_DIR%"

rem # CHANGEPOINT default to dev path for tsalt
if not defined SCRIPT_DIR if /I "%USERNAME%"=="tsalt" if exist "%DEV_APP_DIR%run_web.py" set "SCRIPT_DIR=%DEV_APP_DIR%"

rem # CHANGEPOINT fallback to script location
if not defined SCRIPT_DIR if exist "%~dp0run_web.py" set "SCRIPT_DIR=%~dp0"

rem # CHANGEPOINT fallback to production UNC path on file-server
if not defined SCRIPT_DIR call :find_prod_app_dir
if not defined SCRIPT_DIR if defined PROD_APP_DIR set "SCRIPT_DIR=%PROD_APP_DIR%"

if not defined SCRIPT_DIR (
    echo [ERROR] App directory was not resolved.
    echo         Expected dev: "%DEV_APP_DIR%"
    echo         Expected prod: "\\file-server\...\TW_Prophet\"
    set "EXITCODE=1"
    goto :finish
)

call :normalize_script_dir
if not exist "%SCRIPT_DIR%run_web.py" (
    if exist "%SCRIPT_DIR%project\run_web.py" set "SCRIPT_DIR=%SCRIPT_DIR%project\"
)

if not exist "%SCRIPT_DIR%run_web.py" (
    echo [ERROR] run_web.py was not found.
    echo         Resolved app dir: "%SCRIPT_DIR%"
    set "EXITCODE=1"
    goto :finish
)

pushd "%SCRIPT_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to open app directory: "%SCRIPT_DIR%"
    set "EXITCODE=1"
    goto :finish
)

rem ---- already running check ----
set "PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "PORT_PID=%%P"
    goto :already_running
)
goto :resolve_python

:already_running
echo [%DATE% %TIME%] %APP_NAME% is already running on port %PORT% (PID !PORT_PID!).
set "EXITCODE=0"
goto :finish

:resolve_python
set "PYTHONW_EXE="
set "PYTHON_EXE="

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
    set "EXITCODE=1"
    goto :finish
)

echo [%DATE% %TIME%] App dir: "%SCRIPT_DIR%"
echo [%DATE% %TIME%] Using Python launcher: !PY_LAUNCHER!
echo [%DATE% %TIME%] Starting %APP_NAME% on port %PORT%...

set "PORT=%PORT%"
start "%APP_NAME%" /min "!PY_LAUNCHER!" "%SCRIPT_DIR%run_web.py"
if errorlevel 1 (
    echo [ERROR] Failed to start process.
    set "EXITCODE=1"
    goto :finish
)

ping -n 21 127.0.0.1 >nul
set "NEW_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "NEW_PID=%%P"
    goto :started
)

echo [WARN] Start command was issued but port %PORT% is not listening yet.
echo        Wait a few seconds and retry.
set "EXITCODE=0"
goto :finish

:started
echo [OK] %APP_NAME% started on port %PORT% (PID !NEW_PID!).
set "EXITCODE=0"
goto :finish

:find_prod_app_dir
for /d %%D in ("\\file-server\*\TW_Prophet") do (
    if not defined PROD_APP_DIR if exist "%%~fD\project\run_web.py" set "PROD_APP_DIR=%%~fD\project\"
    if not defined PROD_APP_DIR if exist "%%~fD\run_web.py" set "PROD_APP_DIR=%%~fD\"
)
exit /b 0

:normalize_script_dir
if not "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR%\"
exit /b 0

:finish
popd >nul 2>&1
exit /b %EXITCODE%
