@echo off
:: TW_Prophet Web サービスを手動起動するバッチ
:: Python / conda 環境は TW_PYTHON_EXE 環境変数または settings.json で設定してください。

setlocal

:: InstallDir = このバッチの1つ上のディレクトリ
set "INSTALL_DIR=%~dp0.."
pushd "%INSTALL_DIR%"

:: Python 実行ファイルを解決
if defined TW_PYTHON_EXE (
    set "PYTHON=%TW_PYTHON_EXE%"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

echo [TW_Prophet] Starting Web service...
echo [TW_Prophet] INSTALL_DIR = %INSTALL_DIR%
echo [TW_Prophet] PYTHON      = %PYTHON%

"%PYTHON%" run_web.py
if errorlevel 1 (
    echo [TW_Prophet] ERROR: サービスの起動に失敗しました。
    pause
)

popd
endlocal
