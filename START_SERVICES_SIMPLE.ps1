# Simple service starter for ARQIVE
# Starts all services in separate windows

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ARQIVE - Starting All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$rootPath = $PSScriptRoot

# 1. Start Ollama
Write-Host "[1/3] Starting Ollama..." -ForegroundColor Yellow
try {
    $ollama = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
    if ($ollama) {
        Write-Host "  ✓ Ollama already running" -ForegroundColor Green
    } else {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 2
        Write-Host "  ✓ Ollama started" -ForegroundColor Green
    }
} catch {
    Write-Host "  ⚠ Ollama not found - install from https://ollama.ai" -ForegroundColor Yellow
}

Write-Host ""

# 2. Start Backend
Write-Host "[2/3] Starting Backend..." -ForegroundColor Yellow
$backendPath = Join-Path $rootPath "backend"
$backendCmd = "cd '$backendPath'; Write-Host 'ARQIVE Backend Server' -ForegroundColor Cyan; Write-Host ''; .\venv\Scripts\Activate.ps1; python main.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Sleep -Seconds 2
Write-Host "  ✓ Backend starting in new window" -ForegroundColor Green

Write-Host ""

# 3. Start Frontend
Write-Host "[3/3] Starting Frontend..." -ForegroundColor Yellow
$frontendPath = Join-Path $rootPath "frontend"
$frontendCmd = "cd '$frontendPath'; Write-Host 'ARQIVE Frontend Server' -ForegroundColor Cyan; Write-Host ''; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd
Start-Sleep -Seconds 2
Write-Host "  ✓ Frontend starting in new window" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Services Starting!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  • Ollama:     http://localhost:11434" -ForegroundColor White
Write-Host "  • Backend:    http://localhost:8000" -ForegroundColor White
Write-Host "  • Frontend:   http://localhost:3000" -ForegroundColor White
Write-Host "  • Health:     http://localhost:8000/health" -ForegroundColor White
Write-Host "  • API Docs:   http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Wait 10-15 seconds for services to start, then check:" -ForegroundColor Yellow
Write-Host "  .\check_services.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "Default Login:" -ForegroundColor Yellow
Write-Host "  Username: admin" -ForegroundColor White
Write-Host "  Password: admin" -ForegroundColor White
Write-Host ""
