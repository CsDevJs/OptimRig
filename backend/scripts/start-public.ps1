# Starts the API on this computer and makes it reachable from the internet through
# an ngrok tunnel on your fixed ngrok domain, so the website can reach it.
#
# By hand (stops when you close the window or press Ctrl+C):
#   powershell -ExecutionPolicy Bypass -File scripts\start-public.ps1
#   (or double-click scripts\start-public.cmd)
#
# Always on: scripts\install-autostart.ps1 registers a Windows task that runs this
# script with -Unattended when the computer starts.
#
# The domain comes from -Domain or from NGROK_DOMAIN in backend\.env.
param(
    [string]$Domain,
    [int]$Port = 8000,
    # ngrok's full path, for the startup task (it runs as SYSTEM, without your PATH).
    [string]$Ngrok = 'ngrok',
    # Your ngrok.yml (holds your authtoken), for the startup task.
    [string]$NgrokConfig,
    # No window: log to backend\logs\public\, wait for the database as long as it
    # takes, and restart the API or the tunnel whenever either one stops.
    [switch]$Unattended
)
$ErrorActionPreference = 'Stop'

$backend = Split-Path $PSScriptRoot -Parent
Set-Location $backend

$logDir = Join-Path $backend 'logs\public'
if ($Unattended) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    Start-Transcript -Path (Join-Path $logDir 'start-public.log') -Append | Out-Null
}
function Log([string]$message) { Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $message" }

if (-not $Domain) {
    $line = Get-Content (Join-Path $backend '.env') -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*NGROK_DOMAIN\s*=' } | Select-Object -First 1
    if ($line) { $Domain = ($line -split '=', 2)[1].Trim().Trim('"', "'") }
}
if (-not $Domain) {
    throw 'Set NGROK_DOMAIN in backend\.env (e.g. NGROK_DOMAIN=your-name.ngrok-free.app) or pass -Domain.'
}
$Domain = ($Domain -replace '^https?://', '').TrimEnd('/')

$ngrokCommand = Get-Command $Ngrok -ErrorAction SilentlyContinue
if (-not $ngrokCommand) {
    throw 'ngrok is not installed or not on PATH. Install it (winget install ngrok.ngrok) and run "ngrok config add-authtoken <token>" once.'
}
$ngrokExe = $ngrokCommand.Source

$python = Join-Path $backend '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "No virtual environment at $python. See backend\README.md, Setup." }

function Start-Api {
    $apiArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port")
    if ($Unattended) {
        Start-Process -FilePath $python -ArgumentList ($apiArgs + '--no-access-log') -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDir 'api.out.log') `
            -RedirectStandardError (Join-Path $logDir 'api.err.log')
    } else {
        Start-Process -FilePath $python -ArgumentList $apiArgs -NoNewWindow -PassThru
    }
}

# True once the API answers and reaches the database; false if it stopped or timed out.
function Wait-Api($process, [int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if ($process.HasExited) { return $false }
        try {
            Invoke-RestMethod "http://127.0.0.1:$Port/health/db" -TimeoutSec 2 | Out-Null
            return $true
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

function Stop-Proc($process) {
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
}

if (-not $Unattended) {
    Log "Starting the API on http://127.0.0.1:$Port ..."
    $api = Start-Api
    try {
        if (-not (Wait-Api $api 60)) {
            throw 'The API or its database did not answer within 60 seconds. Is PostgreSQL running? See the messages above.'
        }
        Log "API is up. Opening the tunnel: https://$Domain -> http://127.0.0.1:$Port"
        Log 'The site works while this window stays open. Press Ctrl+C to stop.'
        $ngrokArgs = @('http', "--url=$Domain", "$Port")
        if ($NgrokConfig) { $ngrokArgs += "--config=$NgrokConfig" }
        & $ngrokExe @ngrokArgs
    } finally {
        Stop-Proc $api
        Log 'Stopped the API and the tunnel.'
    }
    return
}

# Unattended: keep both running. Start-Process joins arguments with spaces, so a
# config path with spaces (C:\Users\First Last\...) has to be quoted here.
$tunnelArgs = @('http', "--url=$Domain", "$Port", '--log=stdout', '--log-level=warn')
if ($NgrokConfig) { $tunnelArgs += "--config=`"$NgrokConfig`"" }

$api = $null
$tunnel = $null
try {
    while ($true) {
        if (-not $api -or $api.HasExited) {
            Stop-Proc $tunnel
            $tunnel = $null
            Log 'Starting the API'
            $api = Start-Api
            if (-not (Wait-Api $api 120)) {
                Log 'The API or the database is not ready yet (see api.err.log). Retrying in 15 s.'
                Stop-Proc $api
                $api = $null
                Start-Sleep -Seconds 15
                continue
            }
            Log 'API is up'
        }
        if (-not $tunnel -or $tunnel.HasExited) {
            if ($tunnel) { Log "The tunnel stopped (exit code $($tunnel.ExitCode), see ngrok.log). Restarting it." }
            Log "Opening the tunnel https://$Domain -> http://127.0.0.1:$Port"
            $tunnel = Start-Process -FilePath $ngrokExe -ArgumentList $tunnelArgs -PassThru -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $logDir 'ngrok.log') `
                -RedirectStandardError (Join-Path $logDir 'ngrok.err.log')
        }
        Start-Sleep -Seconds 10
    }
} finally {
    Stop-Proc $tunnel
    Stop-Proc $api
    Log 'Stopped the API and the tunnel.'
}
