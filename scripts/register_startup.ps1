<#
.SYNOPSIS
    TW_Prophet Web サーバーを Windows タスクスケジューラに「起動時実行」で登録する。

.DESCRIPTION
    - タスク名: TW_Prophet_Web
    - トリガー: システム起動時 (At startup)
    - ユーザー: SYSTEM アカウント（ログイン不要・ウィンドウ非表示）
    - schtasks.exe を使用（PowerShell コマンドレットのバージョン依存を回避）

.NOTES
    管理者権限が必要です。
#>

param(
    [string]$InstallDir = "",
    [string]$PythonExe  = "",
    [int]   $Port       = 8000,
    [string]$TaskName   = "TW_Prophet_Web"
)

# InstallDir の既定値をここで解決（param()内でのResolve-Pathはfrozen環境で失敗することがある）
if (-not $InstallDir) {
    $InstallDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

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
# 実行ファイルを解決
# ---------------------------------------------------------------------------
function Resolve-ExeToRun {
    param([string]$Hint, [string]$Dir)

    if ($Hint -and (Test-Path $Hint)) { return $Hint }

    # python.exe -> pythonw.exe
    if ($Hint -and $Hint -match "python\.exe$") {
        $pw = $Hint -replace "python\.exe$", "pythonw.exe"
        if (Test-Path $pw) { return $pw }
    }

    # 仮想環境
    foreach ($rel in @(".venv\Scripts\pythonw.exe", ".venv\Scripts\python.exe")) {
        $c = Join-Path $Dir $rel
        if (Test-Path $c) { return $c }
    }

    # PATH 上の python
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }

    return $null
}

$exeToRun = Resolve-ExeToRun -Hint $PythonExe -Dir $InstallDir
if (-not $exeToRun) {
    Write-Error "実行ファイルが見つかりません。"
    exit 1
}

Write-Host "Install Dir : $InstallDir"
Write-Host "Exe         : $exeToRun"
Write-Host "Port        : $Port"
Write-Host "Task Name   : $TaskName"

# ---------------------------------------------------------------------------
# ログディレクトリを作成
# ---------------------------------------------------------------------------
$logDir = Join-Path $env:ProgramData "TW_Prophet\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# ---------------------------------------------------------------------------
# 実行コマンドを組み立て
# TW_Prophet_Web.exe → 直接実行、python/pythonw → run_web.py を引数に
# ---------------------------------------------------------------------------
$isBundled = ($exeToRun -match "TW_Prophet_Web\.exe$")
if ($isBundled) {
    $runExe = $exeToRun
    $runArg = ""
} else {
    $runExe = $exeToRun
    $runArg = "`"$(Join-Path $InstallDir 'run_web.py')`""
}

# ---------------------------------------------------------------------------
# 既存タスクを削除してから schtasks.exe で新規登録
# schtasks.exe は PowerShell コマンドレットより安定しており
# バックティック継続行の問題が起きない
# ---------------------------------------------------------------------------
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

if ($runArg) {
    $result = schtasks /Create /TN $TaskName /TR "`"$runExe`" $runArg" /SC ONSTART /RU SYSTEM /RL HIGHEST /F /DELAY 0000:10 2>&1
} else {
    $result = schtasks /Create /TN $TaskName /TR "`"$runExe`"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F /DELAY 0000:10 2>&1
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "schtasks /Create に失敗しました: $result"
    exit 1
}

# ---------------------------------------------------------------------------
# settings.json に python_exe を保存
# ---------------------------------------------------------------------------
$settingsPath = Join-Path $env:ProgramData "TW_Prophet\data\config\settings.json"
if (Test-Path $settingsPath) {
    try {
        $s = Get-Content $settingsPath -Raw | ConvertFrom-Json
        $s | Add-Member -NotePropertyName "python_exe" -NotePropertyValue $exeToRun -Force
        $s | ConvertTo-Json -Depth 5 | Set-Content $settingsPath -Encoding UTF8
    } catch {}
}

Write-Host ""
Write-Host "[OK] タスク '$TaskName' を登録しました。"
Write-Host "     次回 Windows 起動時から Port $Port で自動起動します。"
Write-Host "     今すぐ起動: schtasks /Run /TN $TaskName"
Write-Host "     ログ確認  : $logDir\service.log"
