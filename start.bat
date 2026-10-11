@echo off
title FinTech Risk Engine Launcher
echo ==========================================================
echo  Starting FinTech Autonomous AI/NLP Risk Engine Platform
echo ==========================================================

if not exist "%~dp0venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in %~dp0venv!
    echo Please create it with: python -m venv venv and install dependencies.
    pause
    exit /b 1
)

echo.
echo [1/2] Launching FastAPI Backend (Port 8000)...
start "FastAPI Backend" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate.bat && uvicorn src.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] Launching Streamlit Dashboard (Port 8501)...
start "Streamlit Dashboard" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate.bat && streamlit run src/dashboard/app.py --server.port 8501 --server.headless true"

echo.
echo Both services launched in separate windows!
echo  - Backend Docs: http://127.0.0.1:8000/docs
echo  - Dashboard:    http://localhost:8501

