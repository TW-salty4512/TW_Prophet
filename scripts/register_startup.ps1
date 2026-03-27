<#
.SYNOPSIS
    TW_Prophet Web サーバーを Windows タスクスケジューラに「起動時実行」で登録する。

.DESCRIPTION
    - タスク名: TW_Prophet_Web
    - トリガー: システム起動時 (At startup)
    - ユーザー: SYSTEM アカウント（ログイン不要・ウィンドウ非表示）
    - 実行: pythonw.exe run_web.py（コンソール非表示）
    - ログ: %ProgramData%\TW_Prophet\logs\service.log

.NOTES
    管理者権限が必要です。
#>

# Python (subprocess) からの呼び出し時に文字化けしないよう UTF-8 出力に固定
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding            = [System.Text.Encoding]::UTF8

param(
    [string]$InstallDir  = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PythonExe   = "",   # 空の場合は自動検索
    [int]   $Port        = 8000,
    [string]$TaskName    = "TW_Prophet_Web"
)

# ---------------------------------------------------------------------------
# 管理者権限チェック
# ---------------------------------------------------------------------------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "このスクリプトは管理者権限で実行してください。"
    exit 1
}

# ---------------------------------------------------------------------------
# Python 実行ファイルを解決（pythonw.exe を優先）
# ---------------------------------------------------------------------------
function Resolve-PythonExe {
    param([string]$Hint, [string]$InstallDir)

    # ヒントが直接 pythonw.exe を指している場合はそのまま使う
    if ($Hint -and (Test-Path $Hint)) { return $Hint }

    # ヒントが python.exe の場合、隣の pythonw.exe を探す
    if ($Hint -and $Hint -match "python\.exe$") {
        $pw = $Hint -replace "python\.exe$", "pythonw.exe"
        if (Test-Path $pw) { return $pw }
    }

    # 1. InstallDir 内の仮想環境
    $candidates = @(
        Join-Path $InstallDir ".venv\Scripts\pythonw.exe"
        Join-Path $InstallDir ".venv\Scripts\python.exe"
        Join-Path $InstallDir "venv\Scripts\pythonw.exe"
        Join-Path $InstallDir "venv\Scripts\python.exe"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }

    # 2. 環境変数 TW_PYTHON_EXE
    if ($env:TW_PYTHON_EXE -and (Test-Path $env:TW_PYTHON_EXE)) {
        return $env:TW_PYTHON_EXE
    }

    # 3. PATH 上の pythonw / python
    foreach ($cmd in @("pythonw", "python")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }

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
# settings.json に python_exe を保存（wizard がインストール済みパスを読めるように）
# ---------------------------------------------------------------------------
$settingsPath = "$env:ProgramData\TW_Prophet\data\config\settings.json"
if (Test-Path $settingsPath) {
    try {
        $s = Get-Content $settingsPath -Raw | ConvertFrom-Json
        $s | Add-Member -NotePropertyName "python_exe" -NotePropertyValue $pythonExeResolved -Force
        $s | ConvertTo-Json -Depth 5 | Set-Content $settingsPath -Encoding UTF8
    } catch {}
}

# ---------------------------------------------------------------------------
# ログディレクトリを作成
# ---------------------------------------------------------------------------
$logDir = "$env:ProgramData\TW_Prophet\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# ---------------------------------------------------------------------------
# 既存タスクを削除
# ---------------------------------------------------------------------------
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "既存タスクを削除します: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# ---------------------------------------------------------------------------
# タスクアクション
# TW_Prophet_Web.exe が渡された場合は直接実行（引数なし）
# python/pythonw の場合は run_web.py を引数に渡す
# ---------------------------------------------------------------------------
$isBundledExe = ($pythonExeResolved -match "TW_Prophet_Web\.exe$")

if ($isBundledExe) {
    $action = New-ScheduledTaskAction `
        -Execute          $pythonExeResolved `
        -WorkingDirectory $InstallDir
} else {
    $scriptFile = Join-Path $InstallDir "run_web.py"
    $action = New-ScheduledTaskAction `
        -Execute          $pythonExeResolved `
        -Argument         "`"$scriptFile`"" `
        -WorkingDirectory $InstallDir
}

# ---------------------------------------------------------------------------
# トリガー・設定
# ---------------------------------------------------------------------------
$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -Hidden

# ---------------------------------------------------------------------------
# SYSTEM アカウントで実行（ログイン不要・ウィンドウ非表示）
# ---------------------------------------------------------------------------
$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId    "SYSTEM" `
    -LogonType "ServiceAccount" `
    -RunLevel  "Highest"

$task = New-ScheduledTask `
    -Action      $action `
    -Trigger     $trigger `
    -Settings    $settings `
    -Principal   $taskPrincipal `
    -Description "TW_Prophet AI 需要予測 Web サービス（自動起動・ウィンドウ非表示）"

Register-ScheduledTask -TaskName $TaskName -InputObject $task

Write-Host ""
Write-Host "[OK] タスク '$TaskName' を登録しました。"
Write-Host "     次回 Windows 起動時から Port $Port で自動起動します（ウィンドウ非表示）。"
Write-Host "     今すぐ起動: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "     ログ確認  : $logDir\service.log"
