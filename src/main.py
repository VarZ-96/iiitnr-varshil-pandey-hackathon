import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.api.controllers import signal_controller, portfolio_controller

import os

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Setup rich console + file logging (Morgan style)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/backend.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("HTTP")


logger.info("Initializing FinTech Risk Engine...")

app = FastAPI(
    title="Autonomous AI/NLP Risk Engine & Tactical Index Rebalancing",
    description="S&P Global & CRISIL Hackathon Backend - Phase 4 REST APIs",
    version="1.0.0"
)

# Enable CORS for frontend dashboard communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Morgan-style HTTP Request Logger Middleware
@app.middleware("http")
async def morgan_logger_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    
    try:
        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000
        status_code = response.status_code
        
        # Colorized Morgan-style logging output in terminal
        logger.info(
            f"MORGAN :: {client_ip} - \"{method} {path}\" {status_code} - {process_time_ms:.2f}ms"
        )
        return response
    except Exception as exc:
        process_time_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"MORGAN :: {client_ip} - \"{method} {path}\" 500 ERROR ({exc}) - {process_time_ms:.2f}ms"
        )
        raise exc

# Wire up the API Routers
app.include_router(signal_controller.router, prefix="/api/v1/signals", tags=["Signals"])
app.include_router(portfolio_controller.router, prefix="/api/v1/portfolio", tags=["Portfolio Rebalancing"])

@app.on_event("startup")
def startup_event():
    logger.info("FastAPI Application Bootstrap Complete. Waiting for requests.")

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "online", "message": "Risk Engine is operational."}

