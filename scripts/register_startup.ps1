<#
.SYNOPSIS  Register TW_Prophet_Web in Task Scheduler (run at startup, SYSTEM, no window).
.NOTES     Requires administrator privileges.
#>

param(
    [string]$InstallDir = "",
    [string]$PythonExe  = "",
    [int]   $Port       = 8000,
    [string]$TaskName   = "TW_Prophet_Web"
)

# Resolve InstallDir default here (not inside param() to avoid issues in some environments)
if (-not $InstallDir) {
    $InstallDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

# --- Admin check ---
$id  = [Security.Principal.WindowsIdentity]::GetCurrent()
$p   = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run as administrator."
    exit 1
}

# --- Resolve executable ---
function Resolve-Exe {
    param([string]$Hint, [string]$Dir)
    if ($Hint -and (Test-Path $Hint)) { return $Hint }
    if ($Hint -match "python\.exe$") {
        $pw = $Hint -replace "python\.exe$","pythonw.exe"
        if (Test-Path $pw) { return $pw }
    }
    foreach ($rel in @(".venv\Scripts\pythonw.exe",".venv\Scripts\python.exe")) {
        $c = Join-Path $Dir $rel
        if (Test-Path $c) { return $c }
    }
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }
    return $null
}

$exeToRun = Resolve-Exe -Hint $PythonExe -Dir $InstallDir
if (-not $exeToRun) { Write-Error "Executable not found."; exit 1 }

Write-Host "InstallDir : $InstallDir"
Write-Host "Exe        : $exeToRun"
Write-Host "Port       : $Port"
Write-Host "TaskName   : $TaskName"

# --- Create log dir ---
$logDir = Join-Path $env:ProgramData "TW_Prophet\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# --- Build task run string ---
$isBundled = ($exeToRun -match "TW_Prophet_Web\.exe$")
if ($isBundled) {
    $tr = "`"$exeToRun`""
} else {
    $script = Join-Path $InstallDir "run_web.py"
    $tr = "`"$exeToRun`" `"$script`""
}

# --- Delete existing task ---
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

# --- Register with schtasks.exe ---
$out = schtasks /Create /TN $TaskName /TR $tr /SC ONSTART /RU SYSTEM /RL HIGHEST /F /DELAY 0000:10 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "schtasks failed: $out"
    exit 1
}

# --- Save python_exe to settings.json ---
$cfg = Join-Path $env:ProgramData "TW_Prophet\data\config\settings.json"
if (Test-Path $cfg) {
    try {
        $s = Get-Content $cfg -Raw | ConvertFrom-Json
        $s | Add-Member -NotePropertyName "python_exe" -NotePropertyValue $exeToRun -Force
        $s | ConvertTo-Json -Depth 5 | Set-Content $cfg -Encoding UTF8
    } catch {}
}

Write-Host "OK: Task '$TaskName' registered. Starts at next boot."
Write-Host "    Run now: schtasks /Run /TN $TaskName"
Write-Host "    Log    : $logDir\service.log"
