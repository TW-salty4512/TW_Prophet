<#
.SYNOPSIS
    TW_Prophet インストーラを一括ビルドする。

.DESCRIPTION
    1. PyInstaller で TW_Prophet_Web.exe をビルド
    2. PyInstaller で TW_Prophet_Setup_Wizard.exe をビルド
    3. Inno Setup ISCC で TW_Prophet_Setup_x.x.x.exe をビルド

.NOTES
    実行前の準備:
      pip install pyinstaller
      Inno Setup 6 をインストール済みであること
#>

param(
    [string]$ProjectDir  = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$InnoSetupExe = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location $ProjectDir

try {
    # ------------------------------------------------------------------
    # 1. TW_Prophet_Web.exe
    # ------------------------------------------------------------------
    Write-Host "`n=== [1/3] TW_Prophet_Web.exe をビルド中 ===" -ForegroundColor Cyan
    pyinstaller installer\run_web.spec `
        --distpath installer\dist `
        --workpath installer\build `
        --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "TW_Prophet_Web.exe のビルドに失敗しました。" }
    Write-Host "[OK] installer\dist\TW_Prophet_Web.exe" -ForegroundColor Green

    # ------------------------------------------------------------------
    # 2. TW_Prophet_Setup_Wizard.exe
    # ------------------------------------------------------------------
    Write-Host "`n=== [2/3] TW_Prophet_Setup_Wizard.exe をビルド中 ===" -ForegroundColor Cyan
    pyinstaller installer\setup_wizard.spec `
        --distpath installer\dist `
        --workpath installer\build `
        --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "TW_Prophet_Setup_Wizard.exe のビルドに失敗しました。" }
    Write-Host "[OK] installer\dist\TW_Prophet_Setup_Wizard.exe" -ForegroundColor Green

    # ------------------------------------------------------------------
    # 3. Inno Setup インストーラ
    # ------------------------------------------------------------------
    Write-Host "`n=== [3/3] Inno Setup インストーラをビルド中 ===" -ForegroundColor Cyan
    if (-not (Test-Path $InnoSetupExe)) {
        throw "Inno Setup が見つかりません: $InnoSetupExe`nInno Setup 6 をインストールしてください。"
    }
    & $InnoSetupExe installer\tw_prophet.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup のビルドに失敗しました。" }
    Write-Host "[OK] installer\Output\TW_Prophet_Setup_*.exe" -ForegroundColor Green

    Write-Host "`n=== 全ビルド完了 ===" -ForegroundColor Green
    Get-ChildItem installer\Output\*.exe | Select-Object Name, Length, LastWriteTime

} finally {
    Pop-Location
}
