# Starts the API on this computer and makes it reachable from the internet through
# an ngrok tunnel on your fixed ngrok domain, so the Vercel site works while this
# window is open. Ctrl+C (or closing the window) stops both.
#
#   powershell -ExecutionPolicy Bypass -File scripts\start-public.ps1
#   (or double-click scripts\start-public.cmd)
#
# The domain comes from -Domain or from NGROK_DOMAIN in backend\.env.
param(
    [string]$Domain,
    [int]$Port = 8000
)
$ErrorActionPreference = 'Stop'

$backend = Split-Path $PSScriptRoot -Parent
Set-Location $backend

if (-not $Domain) {
    $line = Get-Content (Join-Path $backend '.env') -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*NGROK_DOMAIN\s*=' } | Select-Object -First 1
    if ($line) { $Domain = ($line -split '=', 2)[1].Trim().Trim('"', "'") }
}
if (-not $Domain) {
    throw 'Set NGROK_DOMAIN in backend\.env (e.g. NGROK_DOMAIN=your-name.ngrok-free.app) or pass -Domain.'
}
$Domain = ($Domain -replace '^https?://', '').TrimEnd('/')

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    throw 'ngrok is not installed or not on PATH. Install it (winget install ngrok.ngrok) and run "ngrok config add-authtoken <token>" once.'
}
$python = Join-Path $backend '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "No virtual environment at $python. See backend\README.md, Setup." }

Write-Host "Starting the API on http://127.0.0.1:$Port ..."
$api = Start-Process -FilePath $python -NoNewWindow -PassThru `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port"

try {
    # Wait until the API answers before opening the tunnel.
    $deadline = (Get-Date).AddSeconds(60)
    $up = $false
    while (-not $up -and (Get-Date) -lt $deadline) {
        if ($api.HasExited) { throw "The API stopped while starting (exit code $($api.ExitCode)). See the messages above." }
        try {
            Invoke-RestMethod "http://127.0.0.1:$Port/health/db" -TimeoutSec 2 | Out-Null
            $up = $true
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $up) { throw 'The API or its database did not answer within 60 seconds. Is PostgreSQL running?' }

    Write-Host "API is up. Opening the tunnel: https://$Domain -> http://127.0.0.1:$Port"
    Write-Host 'The site works while this window stays open. Press Ctrl+C to stop.'
    & ngrok http "--url=$Domain" "$Port"
} finally {
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
    Write-Host 'Stopped the API and the tunnel.'
}
