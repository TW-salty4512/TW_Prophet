<#
.SYNOPSIS
    TW_Prophet Web サーバーを Windows タスクスケジューラに「起動時実行」で登録する。

.DESCRIPTION
    - タスク名: TW_Prophet_Web
    - トリガー: システム起動時 (At startup)
    - ユーザー: SYSTEM アカウント（ログイン不要）
    - 起動スクリプト: scripts\launch_web.ps1

.NOTES
    管理者権限で実行してください:
        右クリック → "管理者として実行"
    または:
        Start-Process powershell -Verb RunAs -ArgumentList "-File register_startup.ps1"
#>

param(
    [string]$InstallDir  = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PythonExe   = "",         # 空の場合は conda env を自動検索
    [int]   $Port        = 8000,
    [string]$TaskName    = "TW_Prophet_Web"
)

# ---------------------------------------------------------------------------
# Python 実行ファイルを解決
# ---------------------------------------------------------------------------
function Resolve-PythonExe {
    param([string]$Hint, [string]$InstallDir)

    if ($Hint -and (Test-Path $Hint)) { return $Hint }

    # 1. InstallDir\.venv または .conda_env 内
    $candidates = @(
        Join-Path $InstallDir ".venv\Scripts\python.exe"
        Join-Path $InstallDir "venv\Scripts\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }

    # 2. 環境変数 TW_PYTHON_EXE
    if ($env:TW_PYTHON_EXE -and (Test-Path $env:TW_PYTHON_EXE)) {
        return $env:TW_PYTHON_EXE
    }

    # 3. PATH 上の python
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }

    return $null
}

$pythonExeResolved = Resolve-PythonExe -Hint $PythonExe -InstallDir $InstallDir
if (-not $pythonExeResolved) {
    Write-Error "Python 実行ファイルが見つかりません。-PythonExe オプションまたは TW_PYTHON_EXE 環境変数で指定してください。"
    exit 1
}

Write-Host "Install Dir : $InstallDir"
Write-Host "Python      : $pythonExeResolved"
Write-Host "Port        : $Port"
Write-Host "Task Name   : $TaskName"

# ---------------------------------------------------------------------------
# 既存タスクを削除
# ---------------------------------------------------------------------------
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "既存タスクを削除します: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# ---------------------------------------------------------------------------
# 起動コマンド
# ---------------------------------------------------------------------------
$scriptFile = Join-Path $InstallDir "run_web.py"
$action = New-ScheduledTaskAction `
    -Execute  $pythonExeResolved `
    -Argument "`"$scriptFile`"" `
    -WorkingDirectory $InstallDir

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

# ---------------------------------------------------------------------------
# 環境変数をタスクに埋め込む
# ---------------------------------------------------------------------------
$principal = New-ScheduledTaskPrincipal `
    -UserId    "SYSTEM" `
    -LogonType "ServiceAccount" `
    -RunLevel  "Highest"

# PORT は環境変数 PATH に追加して渡す
$envBlock = @(
    "PORT=$Port"
    "TW_PROPHET_PATH=$InstallDir"
)
# ScheduledTask の EnvironmentVariables は直接設定できないため、
# run_web.py が settings.json から読む方式を採用（上記の config.py 参照）。
# 必要なら %ProgramData%\TW_Prophet\settings.json を更新する。

# ---------------------------------------------------------------------------
# タスクを登録
# ---------------------------------------------------------------------------
Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Description "TW_Prophet AI 需要予測 Web サービス（自動起動）"

Write-Host ""
Write-Host "[OK] タスク '$TaskName' を登録しました。"
Write-Host "     次回起動時から自動的に Port $Port で起動します。"
Write-Host "     今すぐ起動: Start-ScheduledTask -TaskName '$TaskName'"
