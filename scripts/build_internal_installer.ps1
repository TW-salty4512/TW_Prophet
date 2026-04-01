<#
.SYNOPSIS
    Build TW_Prophet internal config installer.

.DESCRIPTION
    Packages mysql_config.internal.json as mysql_config.json and deploys it
    to %ProgramData%\TW_Prophet\data\config\ via Inno Setup installer.

    Do NOT upload the generated exe to GitHub Releases.
    Distribute internally only.

.PARAMETER Version
    Version string (e.g. "3.3.2"). Reads from version.txt if omitted.

.PARAMETER InnoSetupExe
    Full path to ISCC.exe.

.EXAMPLE
    .\build_internal_installer.ps1
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
# Resolve version
# ------------------------------------------------------------------
if (-not $Version) {
    $versionFile = Join-Path $ProjectDir "version.txt"
    if (Test-Path $versionFile) {
        $Version = (Get-Content $versionFile -Raw).Trim()
    } else {
        throw "Specify -Version 3.3.2 or create version.txt."
    }
}
Write-Host "Version: $Version" -ForegroundColor Cyan

# ------------------------------------------------------------------
# Pre-flight checks
# ------------------------------------------------------------------
$internalConfig = Join-Path $ProjectDir "mysql_config.internal.json"
if (-not (Test-Path $internalConfig)) {
    throw "mysql_config.internal.json not found: $internalConfig`n`n" +
          "Copy mysql_config.example.json and fill in real credentials:`n" +
          "  Copy-Item mysql_config.example.json mysql_config.internal.json"
}

$configContent = Get-Content $internalConfig -Raw
if ($configContent -match '"your_db_user"' -or $configContent -match '"your_db_password"') {
    Write-Warning "mysql_config.internal.json still contains placeholder values."
    $confirm = Read-Host "Build anyway? (y/N)"
    if ($confirm -ne 'y' -and $confirm -ne 'Y') {
        Write-Host "Aborted. Edit mysql_config.internal.json and retry." -ForegroundColor Yellow
        exit 1
    }
}

if (-not (Test-Path $InnoSetupExe)) {
    throw "Inno Setup not found: $InnoSetupExe`nInstall Inno Setup 6."
}

# ------------------------------------------------------------------
# Build
# ------------------------------------------------------------------
Push-Location $ProjectDir

try {
    Write-Host "`n=== Building internal config installer (v$Version) ===" -ForegroundColor Cyan
    & $InnoSetupExe "/DAppVersion=$Version" installer\tw_prophet_internal.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed." }

    $outFile = Join-Path $ProjectDir "installer\Output\TW_Prophet_Internal_$Version.exe"
    if (-not (Test-Path $outFile)) {
        throw "Output file not found: $outFile"
    }
    $sizeMB = [math]::Round((Get-Item $outFile).Length / 1MB, 2)
    Write-Host "[OK] $outFile ($sizeMB MB)" -ForegroundColor Green

    Write-Host ""
    Write-Host "=== Done ===" -ForegroundColor Green
    Write-Host "WARNING: Do NOT upload this exe to GitHub Releases." -ForegroundColor Yellow
    Write-Host "         Distribute internally only." -ForegroundColor Yellow

} finally {
    Pop-Location
}
