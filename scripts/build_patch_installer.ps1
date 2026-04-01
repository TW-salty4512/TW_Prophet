<#
.SYNOPSIS
    TW_Prophet パッチインストーラをビルドし、オプションで GitHub Release を作成する。

.DESCRIPTION
    1. PyInstaller で TW_Prophet_Web.exe をビルド
    2. PyInstaller で TW_Prophet_Setup_Wizard.exe をビルド
    3. Inno Setup で TW_Prophet_Patch_x.x.x.exe をビルド
    4. -Release スイッチ指定時: GitHub Release を作成してアップロード

.PARAMETER Version
    リリースバージョン（例: "3.3.2"）。省略時は version.txt から読み込む。

.PARAMETER Release
    指定すると GitHub Release を作成する（gh CLI が必要）。

.PARAMETER ReleaseNotes
    GitHub Release のリリースノート。省略時はデフォルトのメッセージを使用。

.PARAMETER InnoSetupExe
    ISCC.exe のフルパス。デフォルト: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

.PARAMETER PyInstallerExe
    pyinstaller.exe のフルパス。省略時は conda env tw_prophet_web を自動検索。

.EXAMPLE
    # バージョン自動読み込みでビルドのみ
    .\build_patch_installer.ps1

    # バージョン指定でビルド + GitHub Release 作成
    .\build_patch_installer.ps1 -Version "3.3.2" -Release
#>

param(
    [string]$Version        = "",
    [switch]$Release,
    [string]$ReleaseNotes   = "",
    [string]$ProjectDir     = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$InnoSetupExe   = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    [string]$PyInstallerExe = ""
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
# PyInstaller 検索
# ------------------------------------------------------------------
if (-not $PyInstallerExe) {
    $candidates = @(
        "$env:USERPROFILE\anaconda3\envs\tw_prophet_web\Scripts\pyinstaller.exe",
        "$env:USERPROFILE\miniconda3\envs\tw_prophet_web\Scripts\pyinstaller.exe",
        "$env:LOCALAPPDATA\anaconda3\envs\tw_prophet_web\Scripts\pyinstaller.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $PyInstallerExe = $c; break }
    }
    if (-not $PyInstallerExe) {
        $found = Get-Command pyinstaller -ErrorAction SilentlyContinue
        if ($found) { $PyInstallerExe = $found.Source }
    }
    if (-not $PyInstallerExe) {
        throw "PyInstaller が見つかりません。-PyInstallerExe でパスを指定してください。"
    }
}
Write-Host "PyInstaller: $PyInstallerExe" -ForegroundColor DarkGray

# ------------------------------------------------------------------
# Inno Setup 確認
# ------------------------------------------------------------------
if (-not (Test-Path $InnoSetupExe)) {
    throw "Inno Setup が見つかりません: $InnoSetupExe`nInno Setup 6 をインストールしてください。"
}

Push-Location $ProjectDir

try {
    # --------------------------------------------------------------
    # 1. TW_Prophet_Web.exe
    # --------------------------------------------------------------
    Write-Host "`n=== [1/3] TW_Prophet_Web.exe をビルド中 ===" -ForegroundColor Cyan
    & $PyInstallerExe installer\run_web.spec `
        --distpath installer\dist `
        --workpath installer\build `
        --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "TW_Prophet_Web.exe のビルドに失敗しました。" }
    Write-Host "[OK] installer\dist\TW_Prophet_Web.exe" -ForegroundColor Green

    # --------------------------------------------------------------
    # 2. TW_Prophet_Setup_Wizard.exe
    # --------------------------------------------------------------
    Write-Host "`n=== [2/3] TW_Prophet_Setup_Wizard.exe をビルド中 ===" -ForegroundColor Cyan
    & $PyInstallerExe installer\setup_wizard.spec `
        --distpath installer\dist `
        --workpath installer\build `
        --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "TW_Prophet_Setup_Wizard.exe のビルドに失敗しました。" }
    Write-Host "[OK] installer\dist\TW_Prophet_Setup_Wizard.exe" -ForegroundColor Green

    # --------------------------------------------------------------
    # 3. パッチインストーラ
    # --------------------------------------------------------------
    Write-Host "`n=== [3/3] パッチインストーラをビルド中 (v$Version) ===" -ForegroundColor Cyan
    & $InnoSetupExe "/DAppVersion=$Version" installer\tw_prophet_patch.iss
    if ($LASTEXITCODE -ne 0) { throw "パッチインストーラのビルドに失敗しました。" }

    $patchExe = Join-Path $ProjectDir "installer\Output\TW_Prophet_Patch_$Version.exe"
    if (-not (Test-Path $patchExe)) {
        throw "出力ファイルが見つかりません: $patchExe"
    }
    $size = [math]::Round((Get-Item $patchExe).Length / 1MB, 1)
    Write-Host "[OK] $patchExe ($size MB)" -ForegroundColor Green

    # --------------------------------------------------------------
    # 4. GitHub Release（-Release スイッチ指定時）
    # --------------------------------------------------------------
    if ($Release) {
        Write-Host "`n=== [4/4] GitHub Release を作成中 (v$Version) ===" -ForegroundColor Cyan

        $ghCmd = Get-Command gh -ErrorAction SilentlyContinue
        if (-not $ghCmd) { throw "gh CLI が見つかりません。https://cli.github.com/ からインストールしてください。" }

        if (-not $ReleaseNotes) {
            $ReleaseNotes = "## パッチ v$Version`n`n既存インストールに exe のみ適用するパッチインストーラです。`nウィザードなしで自動更新します。"
        }

        $tag = "v$Version"

        # 同タグのリリースが既にあれば資産を差し替え、なければ新規作成
        $existing = gh release view $tag --repo TW-salty4512/TW_Prophet 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "既存リリース $tag にパッチ exe をアップロード中..." -ForegroundColor Yellow
            gh release upload $tag $patchExe --repo TW-salty4512/TW_Prophet --clobber
        } else {
            Write-Host "新規リリース $tag を作成中..." -ForegroundColor Yellow
            gh release create $tag $patchExe `
                --repo TW-salty4512/TW_Prophet `
                --title "v$Version パッチ" `
                --notes $ReleaseNotes
        }
        if ($LASTEXITCODE -ne 0) { throw "GitHub Release の作成に失敗しました。" }
        Write-Host "[OK] https://github.com/TW-salty4512/TW_Prophet/releases/tag/$tag" -ForegroundColor Green
    }

    Write-Host "`n=== 完了 ===" -ForegroundColor Green
    Get-ChildItem (Join-Path $ProjectDir "installer\Output\*.exe") |
        Select-Object Name,
                      @{N="Size(MB)"; E={[math]::Round($_.Length/1MB,1)}},
                      LastWriteTime |
        Format-Table -AutoSize

} finally {
    Pop-Location
}
