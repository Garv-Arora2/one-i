# Daily ONE I refresh: new reporting in, events re-analysed, comments collected.
#
# Run by hand (from the repository root):
#   powershell -ExecutionPolicy Bypass -File scripts\daily_update.ps1
# Schedule daily (07:00), once, from an elevated PowerShell in the repository root:
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$PWD\scripts\daily_update.ps1`""
#   $trigger = New-ScheduledTaskTrigger -Daily -At 7am
#   Register-ScheduledTask -TaskName "ONE I daily update" -Action $action -Trigger $trigger

$backend = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"
$logDir = Join-Path $backend "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("update-" + (Get-Date -Format "yyyy-MM-dd") + ".log")

Set-Location $backend
& (Join-Path $backend ".venv\Scripts\python.exe") -m app.cli update *>&1 |
    Tee-Object -FilePath $log
