from fastapi import APIRouter, Depends, HTTPException
import logging
from src.models.schemas import RebalanceRequest, RebalanceResponse
from src.core.services.rebalancer_service import RebalancerService, rebalancer_service
from src.core.services.strategy import SentimentTiltedStrategy

logger = logging.getLogger(__name__)
router = APIRouter()

# Dependency Injection function
def get_rebalancer_service() -> RebalancerService:
    return rebalancer_service

@router.post("/rebalance", response_model=RebalanceResponse, status_code=200)
def trigger_rebalance(request: RebalanceRequest, rebalancer: RebalancerService = Depends(get_rebalancer_service)):
    """
    Manually triggers a portfolio rebalance using the requested quantitative strategy.
    """
    logger.info(f"Received manual rebalance request with strategy: {request.strategy}")
    try:
        if request.strategy == "SentimentTilted":
            rebalancer.strategy = SentimentTiltedStrategy(decay_lambda=request.decay_lambda)
            
        response = rebalancer.rebalance()
        return response
    except Exception as e:
        logger.error(f"Error during rebalancing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
