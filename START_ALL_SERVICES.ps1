# ARQIVE - Start All Services Script
# This script starts: Ollama, Backend (with venv), and Frontend

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ARQIVE - Starting All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is installed
Write-Host "[1/3] Checking Ollama..." -ForegroundColor Yellow
try {
    $ollamaCheck = ollama list 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Ollama is installed" -ForegroundColor Green
        
        # Check if Ollama is already running
        $ollamaProcess = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
        if ($ollamaProcess) {
            Write-Host "  ✓ Ollama is already running" -ForegroundColor Green
        } else {
            Write-Host "  → Starting Ollama server..." -ForegroundColor Yellow
            Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
            Start-Sleep -Seconds 3
            Write-Host "  ✓ Ollama server started" -ForegroundColor Green
        }
    } else {
        Write-Host "  ⚠ Ollama not found. Please install from https://ollama.ai" -ForegroundColor Red
        Write-Host "  → Continuing without Ollama (RAG queries will fail)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠ Ollama not found. Please install from https://ollama.ai" -ForegroundColor Red
    Write-Host "  → Continuing without Ollama (RAG queries will fail)" -ForegroundColor Yellow
}

Write-Host ""

# Start Backend
Write-Host "[2/3] Starting Backend Server..." -ForegroundColor Yellow
$backendPath = Join-Path $PSScriptRoot "backend"

if (Test-Path $backendPath) {
    Set-Location $backendPath
    
    # Check if venv exists
    $venvPath = Join-Path $backendPath "venv"
    if (Test-Path $venvPath) {
        Write-Host "  → Activating virtual environment..." -ForegroundColor Yellow
        
        # Activate venv
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
        if (Test-Path $activateScript) {
            & $activateScript
            Write-Host "  ✓ Virtual environment activated" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ venv activation script not found" -ForegroundColor Red
        }
    } else {
        Write-Host "  ⚠ venv not found. Creating one..." -ForegroundColor Yellow
        python -m venv venv
        & .\venv\Scripts\Activate.ps1
        Write-Host "  ✓ Virtual environment created and activated" -ForegroundColor Green
    }
    
    # Check if dependencies are installed
    Write-Host "  → Checking dependencies..." -ForegroundColor Yellow
    try {
        python -c "import fastapi; import psutil" 2>&1 | Out-Null
        Write-Host "  ✓ Dependencies appear to be installed" -ForegroundColor Green
    } catch {
        Write-Host "  → Installing dependencies (including new: psutil)..." -ForegroundColor Yellow
        pip install -r requirements.txt
        Write-Host "  ✓ Dependencies installed" -ForegroundColor Green
    }
    
    # Check if .env file exists
    if (-not (Test-Path ".env")) {
        Write-Host "  ⚠ .env file not found. Creating from template..." -ForegroundColor Yellow
        if (Test-Path "ENV_TEMPLATE.md") {
            Write-Host "  → Please create .env file manually (see ENV_TEMPLATE.md)" -ForegroundColor Yellow
            Write-Host "  → Minimum required: SECRET_KEY=your-secure-key-here-minimum-32-chars" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ✓ .env file found" -ForegroundColor Green
    }
    
    # Start backend server in new window
    Write-Host "  → Starting backend server on http://localhost:8000..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; .\venv\Scripts\Activate.ps1; python main.py" -WindowStyle Normal
    Start-Sleep -Seconds 3
    Write-Host "  ✓ Backend server started in new window" -ForegroundColor Green
} else {
    Write-Host "  ✗ Backend directory not found!" -ForegroundColor Red
}

Write-Host ""

# Start Frontend
Write-Host "[3/3] Starting Frontend Server..." -ForegroundColor Yellow
$frontendPath = Join-Path $PSScriptRoot "frontend"

if (Test-Path $frontendPath) {
    Set-Location $frontendPath
    
    # Check if node_modules exists
    if (-not (Test-Path "node_modules")) {
        Write-Host "  → Installing dependencies..." -ForegroundColor Yellow
        npm install
        Write-Host "  ✓ Dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "  ✓ Dependencies already installed" -ForegroundColor Green
    }
    
    # Start frontend server in new window
    Write-Host "  → Starting frontend server on http://localhost:3000..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev" -WindowStyle Normal
    Start-Sleep -Seconds 3
    Write-Host "  ✓ Frontend server started in new window" -ForegroundColor Green
} else {
    Write-Host "  ✗ Frontend directory not found!" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All Services Started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  • Ollama:     http://localhost:11434" -ForegroundColor White
Write-Host "  • Backend:    http://localhost:8000" -ForegroundColor White
Write-Host "  • Frontend:   http://localhost:3000" -ForegroundColor White
Write-Host "  • API Docs:   http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Default Login:" -ForegroundColor Yellow
Write-Host "  Username: admin" -ForegroundColor White
Write-Host "  Password: admin" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit this script (services will continue running)..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")



