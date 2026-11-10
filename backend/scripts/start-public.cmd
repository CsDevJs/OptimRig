@echo off
rem Double-click to start the API and the public tunnel. See start-public.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-public.ps1" %*
if errorlevel 1 pause
