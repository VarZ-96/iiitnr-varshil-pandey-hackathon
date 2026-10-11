# ==========================================================
# Automated Benchmark & Enterprise Guardrail Test Suite
# ==========================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Running Enterprise Guardrails & Latency Benchmark Suite" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$pythonExe = "python"
if (Test-Path "venv\Scripts\python.exe") {
    $pythonExe = "venv\Scripts\python.exe"
}

& $pythonExe -m pytest tests/test_benchmark_guardrails.py -v -s

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Benchmark Execution Complete!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
