@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo [deploy] Docker was not found on this machine.
  echo [deploy] Install Docker Desktop: https://www.docker.com/products/docker-desktop/
  echo [deploy] Or run dev.bat to start WITHOUT Docker.
  set EXITCODE=1
  goto :end
)

echo [deploy] Building images and starting VeriGate (this may take a few minutes)...
docker compose up --build -d
if errorlevel 1 (
  set EXITCODE=1
  goto :end
)

echo.
echo ============================================================
echo  VeriGate is starting up
echo    Frontend : http://localhost:5173
echo    Backend  : http://localhost:8000
echo    API docs : http://localhost:8000/docs
echo.
echo  First boot seeds ~30 applications (~30 seconds).
echo  Watch progress with logs.bat, stop with stop.bat
echo ============================================================
set EXITCODE=0

:end
echo.
pause
exit /b %EXITCODE%
