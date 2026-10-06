import logging
from fastapi import FastAPI
from src.api.controllers import signal_controller, portfolio_controller

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

logger.info("Initializing FinTech Risk Engine...")

# Important: Imports below will automatically initialize singletons 
# (event_bus, nlp_service, rebalancer_service) via module-level initialization 
# ensuring Dependency Injection targets are ready and Event Observers are wired up.

app = FastAPI(
    title="Autonomous AI/NLP Risk Engine & Tactical Index Rebalancing",
    description="S&P Global & CRISIL Hackathon Backend - Phase 4 REST APIs",
    version="1.0.0"
)

# Wire up the API Routers
app.include_router(signal_controller.router, prefix="/api/v1/signals", tags=["Signals"])
app.include_router(portfolio_controller.router, prefix="/api/v1/portfolio", tags=["Portfolio Rebalancing"])

@app.on_event("startup")
def startup_event():
    logger.info("FastAPI Application Bootstrap Complete. Waiting for requests.")

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "online", "message": "Risk Engine is operational."}
