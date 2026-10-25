@echo off
setlocal
cd /d "%~dp0"
echo [stop] Stopping VeriGate (data is kept)...
docker compose down
echo.
echo Done. Start again with deploy.bat
pause
