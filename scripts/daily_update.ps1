# Daily ONE I refresh: new reporting in, events re-analysed, comments collected.
#
# Run by hand (from the repository root):
#   powershell -ExecutionPolicy Bypass -File scripts\daily_update.ps1
# Schedule daily (07:00), once, from an elevated PowerShell in the repository root:
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$PWD\scripts\daily_update.ps1`""
#   $trigger = New-ScheduledTaskTrigger -Daily -At 7am
#   $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
#   Register-ScheduledTask -TaskName "ONE I daily update" -Action $action -Trigger $trigger -Settings $settings

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$logDir = Join-Path $backend "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("update-" + (Get-Date -Format "yyyy-MM-dd") + ".log")

# PostgreSQL runs in Docker, which may not be up yet after a reboot.
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 5
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    }
}
Set-Location $root
docker compose up -d *>&1 | Out-File -FilePath $log
Start-Sleep -Seconds 5

Set-Location $backend
& (Join-Path $backend ".venv\Scripts\python.exe") -m app.cli update *>&1 |
    Tee-Object -FilePath $log -Append
