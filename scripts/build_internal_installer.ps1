<#
.SYNOPSIS
    TW_Prophet 社内専用設定インストーラをビルドする。

.DESCRIPTION
    mysql_config.internal.json を mysql_config.json として
    %ProgramData%\TW_Prophet\data\config\ に展開するインストーラを生成する。

    生成された exe は GitHub Release には上げず、社内でのみ配布すること。

.PARAMETER Version
    インストーラのバージョン番号。省略時は version.txt から読み込む。

.PARAMETER InnoSetupExe
    ISCC.exe のフルパス。

.EXAMPLE
    # version.txt のバージョンでビルド
    .\build_internal_installer.ps1

    # バージョン指定でビルド
    .\build_internal_installer.ps1 -Version "3.3.2"
#>

param(
    [string]$Version      = "",
    [string]$ProjectDir   = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$InnoSetupExe = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# バージョン解決
# ------------------------------------------------------------------
if (-not $Version) {
    $versionFile = Join-Path $ProjectDir "version.txt"
    if (Test-Path $versionFile) {
        $Version = (Get-Content $versionFile -Raw).Trim()
    } else {
        throw "バージョンを指定してください: -Version 3.3.2`nまたは version.txt を作成してください。"
    }
}
Write-Host "バージョン: $Version" -ForegroundColor Cyan

# ------------------------------------------------------------------
# 前提チェック
# ------------------------------------------------------------------
$internalConfig = Join-Path $ProjectDir "mysql_config.internal.json"
if (-not (Test-Path $internalConfig)) {
    throw "mysql_config.internal.json が見つかりません: $internalConfig`n`n" +
          "mysql_config.example.json をコピーして実際の接続情報を入力してください:`n" +
          "  Copy-Item mysql_config.example.json mysql_config.internal.json"
}

# 未入力チェック（example のままビルドしていないか確認）
$configContent = Get-Content $internalConfig -Raw
if ($configContent -match '"your_db_user"' -or $configContent -match '"your_db_password"') {
    Write-Warning "mysql_config.internal.json に未入力の項目があります。"
    $confirm = Read-Host "このままビルドしますか？ (y/N)"
    if ($confirm -ne 'y' -and $confirm -ne 'Y') {
        Write-Host "中断しました。mysql_config.internal.json を編集してから再実行してください。" -ForegroundColor Yellow
        exit 1
    }
}

if (-not (Test-Path $InnoSetupExe)) {
    throw "Inno Setup が見つかりません: $InnoSetupExe`nInno Setup 6 をインストールしてください。"
}

# ------------------------------------------------------------------
# ビルド
# ------------------------------------------------------------------
Push-Location $ProjectDir

try {
    Write-Host "`n=== 社内専用設定インストーラをビルド中 (v$Version) ===" -ForegroundColor Cyan
    & $InnoSetupExe "/DAppVersion=$Version" installer\tw_prophet_internal.iss
    if ($LASTEXITCODE -ne 0) { throw "インストーラのビルドに失敗しました。" }

    $outFile = Join-Path $ProjectDir "installer\Output\TW_Prophet_Internal_$Version.exe"
    if (-not (Test-Path $outFile)) {
        throw "出力ファイルが見つかりません: $outFile"
    }
    $size = [math]::Round((Get-Item $outFile).Length / 1MB, 2)
    Write-Host "[OK] $outFile ($size MB)" -ForegroundColor Green

    Write-Host "`n=== 完了 ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "注意: このファイルは GitHub Release に上げず、社内のみで配布してください。" -ForegroundColor Yellow
    Write-Host "      mysql_config.internal.json も社外に漏洩しないよう管理してください。" -ForegroundColor Yellow

} finally {
    Pop-Location
}
