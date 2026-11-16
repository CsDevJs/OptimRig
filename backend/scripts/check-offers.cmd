@echo off
rem Double-click to check every offer's product page and update price, sale price
rem and stock. See check_offers.py.
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m scripts.check_offers %*
pause
