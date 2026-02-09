# Quick service status check
Write-Host "=== ARQIVE Service Status ===" -ForegroundColor Cyan
Write-Host ""

# Check Ollama
$ollama = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "[OK] Ollama: Running (PID: $($ollama.Id))" -ForegroundColor Green
} else {
    Write-Host "[X] Ollama: Not running" -ForegroundColor Red
}

# Check Backend
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[OK] Backend: Running - Status: $($health.status)" -ForegroundColor Green
    if ($health.request_id) {
        Write-Host "     Request ID: $($health.request_id)" -ForegroundColor Gray
    }
} catch {
    Write-Host "[X] Backend: Not responding" -ForegroundColor Red
}

# Check Frontend
try {
    $frontend = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[OK] Frontend: Running (Status: $($frontend.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "[X] Frontend: Not responding" -ForegroundColor Red
}

Write-Host ""
