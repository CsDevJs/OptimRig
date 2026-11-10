# Makes the backend always on: registers a Windows task that runs start-public.ps1
# when the computer starts (before anyone logs in, no window) and keeps the API and
# the ngrok tunnel running. Starts it right away too.
#
# Run once from PowerShell opened as administrator, in backend\:
#   powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
# Remove it again:
#   powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1 -Uninstall
#
# Run it again after moving the project folder or reinstalling ngrok.
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$taskName = 'PC Configurator backend'
$backend = Split-Path $PSScriptRoot -Parent
$python = Join-Path $backend '.venv\Scripts\python.exe'

$identity = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open PowerShell as administrator (right-click it > Run as administrator) and run this again.'
}

# Stopping the task doesn't stop the programs it started, so stop those too.
function Stop-Backend {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'ngrok.exe'" | Where-Object {
        ($_.Name -eq 'python.exe' -and $_.ExecutablePath -eq $python -and $_.CommandLine -like '*uvicorn*app.main:app*') -or
        ($_.Name -eq 'ngrok.exe' -and $_.CommandLine -like '*--log=stdout*')
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if ($Uninstall) {
    Stop-Backend
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed the '$taskName' task and stopped the backend. It won't start with Windows any more."
    return
}

if (-not (Test-Path $python)) { throw "No virtual environment at $python. See backend\README.md, Setup." }

$envFile = Join-Path $backend '.env'
$line = Get-Content $envFile -ErrorAction SilentlyContinue |
    Where-Object { $_ -match '^\s*NGROK_DOMAIN\s*=' } | Select-Object -First 1
if (-not $line) { throw 'Add NGROK_DOMAIN=your-name.ngrok-free.app to backend\.env first.' }
$domain = (($line -split '=', 2)[1].Trim().Trim('"', "'") -replace '^https?://', '').TrimEnd('/')

# The task runs as SYSTEM, which has neither your PATH nor your ngrok sign-in, so it
# gets ngrok's full path and your ngrok.yml (which holds the authtoken).
$ngrokCommand = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrokCommand) { throw 'ngrok is not installed or not on PATH. Install it: winget install ngrok.ngrok' }
$ngrok = $ngrokCommand.Source
$item = Get-Item $ngrok
if ($item.LinkType -and $item.Target) { $ngrok = @($item.Target)[0] }

$config = $null
$check = (& $ngrok config check 2>&1 | Out-String)
if ($check -match '(?m)\bat\s+(.+\.yml)\s*$') { $config = $Matches[1].Trim() }
if (-not $config -or -not (Test-Path $config)) { $config = Join-Path $env:LOCALAPPDATA 'ngrok\ngrok.yml' }
if (-not (Test-Path $config) -or -not (Select-String -Path $config -Pattern 'authtoken' -Quiet)) {
    throw 'No ngrok authtoken found. Run "ngrok config add-authtoken <your token>" (token from the ngrok dashboard) first.'
}

Stop-Backend

$script = Join-Path $PSScriptRoot 'start-public.ps1'
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Unattended -Ngrok `"$ngrok`" -NgrokConfig `"$config`""
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $backend
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description 'PC Configurator API + ngrok tunnel (backend\scripts\start-public.ps1)' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "Registered '$taskName': it starts with Windows and is starting now."

Write-Host 'Checking that the site can reach it (up to 2 minutes)...'
$deadline = (Get-Date).AddMinutes(2)
$ok = $false
while (-not $ok -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    try {
        Invoke-RestMethod "https://$domain/health/db" -Headers @{ 'ngrok-skip-browser-warning' = '1' } -TimeoutSec 5 | Out-Null
        $ok = $true
    } catch { }
}
$logs = Join-Path $backend 'logs\public'
if ($ok) {
    Write-Host "Done. https://$domain answers, so the website works whenever this computer is on."
} else {
    Write-Host "https://$domain doesn't answer yet. Look in $logs (start-public.log, api.err.log, ngrok.log)."
    exit 1
}
