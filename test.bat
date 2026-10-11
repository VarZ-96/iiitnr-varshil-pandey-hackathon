@echo off
REM ==========================================================
REM Automated Benchmark & Enterprise Guardrail Test Suite
REM ==========================================================

echo ==========================================================
echo  Running Enterprise Guardrails ^& Latency Benchmark Suite
echo ==========================================================
echo.

IF EXIST venv\Scripts\python.exe (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) ELSE (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" -m pytest tests/test_benchmark_guardrails.py -v -s

echo.
echo ==========================================================
echo  Benchmark Execution Complete!
echo ==========================================================
pause
