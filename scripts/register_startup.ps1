<#
.SYNOPSIS  Register TW_Prophet_Web in Task Scheduler via XML (run at startup, SYSTEM, no window).
.NOTES     Requires administrator privileges.
#>

param(
    [string]$InstallDir = "",
    [string]$PythonExe  = "",
    [int]   $Port       = 8000,
    [string]$TaskName   = "TW_Prophet_Web"
)

if (-not $InstallDir) {
    $InstallDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

# --- Admin check ---
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
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

# --- Log dir ---
$logDir = Join-Path $env:ProgramData "TW_Prophet\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# --- Build Arguments field ---
$isBundled = ($exeToRun -match "TW_Prophet_Web\.exe$")
if ($isBundled) {
    $argField = ""
} else {
    $scriptPath = Join-Path $InstallDir "run_web.py"
    $argField = "`"$scriptPath`""
}

# --- Build Task XML (most reliable method, avoids all schtasks quoting issues) ---
# Escape XML special characters in paths
$xmlExe  = $exeToRun  -replace '&','&amp;' -replace '<','&lt;' -replace '>','&gt;' -replace '"','&quot;'
$xmlArgs = $argField  -replace '&','&amp;' -replace '<','&lt;' -replace '>','&gt;' -replace '"','&quot;'
$xmlDir  = $InstallDir -replace '&','&amp;' -replace '<','&lt;' -replace '>','&gt;' -replace '"','&quot;'

$taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>TW_Prophet Web service (auto-start, no window)</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT30S</Delay>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$xmlExe</Command>
      <Arguments>$xmlArgs</Arguments>
      <WorkingDirectory>$xmlDir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

# --- Delete existing task ---
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# --- Register via XML (most reliable) ---
try {
    Register-ScheduledTask -TaskName $TaskName -Xml $taskXml -Force | Out-Null
} catch {
    Write-Error "Register-ScheduledTask failed: $_"
    exit 1
}

# --- Verify ---
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Error "Task registration could not be verified."
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

Write-Host "OK: Task '$TaskName' registered. Starts 30s after next boot."
Write-Host "    Run now  : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "    Log      : $logDir\service.log"
