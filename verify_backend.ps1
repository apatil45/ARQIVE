# Simple backend verification
Write-Host "Checking Backend Status..." -ForegroundColor Yellow
Write-Host ""

try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "Backend Status: $($health.status)" -ForegroundColor Green
    Write-Host "Request ID: $($health.request_id)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Component Checks:" -ForegroundColor Yellow
    Write-Host "  SQLite: $($health.checks.sqlite.status)" -ForegroundColor White
    Write-Host "  ChromaDB: $($health.checks.chromadb.status)" -ForegroundColor White
    Write-Host "  Ollama: $($health.checks.ollama.status)" -ForegroundColor White
    Write-Host ""
    Write-Host "Backend is ready!" -ForegroundColor Green
} catch {
    Write-Host "Backend not responding yet" -ForegroundColor Yellow
    Write-Host "Check the backend PowerShell window for startup logs" -ForegroundColor Gray
}
