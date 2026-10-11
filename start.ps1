Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting FinTech Autonomous AI/NLP Risk Engine Platform " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found at .\venv" -ForegroundColor Red
    Write-Host "Please create one using: python -m venv venv and install dependencies." -ForegroundColor Yellow
    exit 1
}

Write-Host "`n[1/2] Launching FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Green
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .\venv\Scripts\activate; uvicorn src.main:app --reload --port 8000"

Start-Sleep -Seconds 3

Write-Host "`n[2/2] Launching Streamlit Dashboard on http://localhost:8501..." -ForegroundColor Green
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .\venv\Scripts\activate; streamlit run src/dashboard/app.py --server.port 8501 --server.headless true"

Write-Host "`nBoth processes are running in dedicated windows!" -ForegroundColor Yellow
Write-Host " - Backend Swagger Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host " - Frontend Dashboard:   http://localhost:8501" -ForegroundColor White

