# Quick restart script for ARQIVE services
# Run this in PowerShell

Write-Host "========================================"
Write-Host "ARQIVE Service Restart Script"
Write-Host "========================================"
Write-Host ""

# Check if services are running
Write-Host "Checking current services..."
Write-Host ""

# Check Ollama
$ollamaRunning = Get-Process ollama -ErrorAction SilentlyContinue
if ($ollamaRunning) {
    Write-Host "[Ollama] Running (PID: $($ollamaRunning.Id))"
} else {
    Write-Host "[Ollama] Not running"
}

# Check Backend
try {
    $backendHealth = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[Backend] Running - Status: $($backendHealth.status)"
} catch {
    Write-Host "[Backend] Not responding"
}

# Check Frontend
try {
    $frontend = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[Frontend] Running - Status: $($frontend.StatusCode)"
} catch {
    Write-Host "[Frontend] Not responding"
}

Write-Host ""
Write-Host "========================================"
Write-Host "To restart services:"
Write-Host ""
Write-Host "1. Ollama:"
Write-Host "   ollama serve"
Write-Host ""
Write-Host "2. Backend:"
Write-Host "   cd D:\Projects\ARQIVE\backend"
Write-Host "   .\venv\Scripts\Activate.ps1"
Write-Host "   python main.py"
Write-Host ""
Write-Host "3. Frontend:"
Write-Host "   cd D:\Projects\ARQIVE\frontend"
Write-Host "   npm run dev"
Write-Host ""
Write-Host "========================================"





