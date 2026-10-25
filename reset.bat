@echo off
setlocal
cd /d "%~dp0"
echo [reset] This STOPS VeriGate and DELETES all data (database + uploads).
set /p CONFIRM=Type YES to continue:
if /i not "%CONFIRM%"=="YES" (
  echo [reset] Cancelled.
  goto :end
)
docker compose down -v
echo [reset] Done. Next deploy.bat will reseed a fresh demo dataset.
:end
pause
