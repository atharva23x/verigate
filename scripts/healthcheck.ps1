# Verifies that a running VeriGate deployment is healthy.
$ErrorActionPreference = "Continue"
$ok = $true

function Test-Url($name, $url, $mustContain) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 8
        if ($mustContain -and $r.Content -notlike "*$mustContain*") {
            Write-Host "  $name : RESPONDED but unexpected content ($url)" -ForegroundColor Yellow
            return $false
        }
        Write-Host "  $name : OK ($url, HTTP $($r.StatusCode))" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "  $name : NOT REACHABLE ($url) - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Write-Host "VeriGate health check" -ForegroundColor Cyan
$backendOk  = Test-Url "Backend " "http://localhost:8000/health" "status"
$frontendOk = Test-Url "Frontend" "http://localhost:5173" "<"

if ($backendOk -and $frontendOk) {
    Write-Host "All good -> open http://localhost:5173" -ForegroundColor Green
    exit 0
}
Write-Host "Something is down. Start the stack with deploy.bat (Docker) or dev.bat (local)," -ForegroundColor Red
Write-Host "and check logs with logs.bat." -ForegroundColor Red
exit 1
