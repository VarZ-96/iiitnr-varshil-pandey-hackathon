from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool
import logging
from src.models.schemas import IngestFeedRequest, RiskSignal
from src.core.services.nlp_service import NLPService, nlp_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Dependency Injection function
def get_nlp_service() -> NLPService:
    return nlp_service

@router.post("/ingest", response_model=RiskSignal, status_code=201)
async def ingest_signal(request: IngestFeedRequest, nlp: NLPService = Depends(get_nlp_service)):
    """
    Ingests unstructured feed text, processes it through the NLP Service asynchronously 
    on a background threadpool to avoid blocking ASGI event loop, and returns the canonical Risk Signal.
    """
    logger.info(f"Received ingest request for ticker: {request.ticker}")
    try:
        signal = await run_in_threadpool(nlp.extract_signal, request.ticker, request.text)
        return signal
    except Exception as e:
        logger.error(f"Error processing signal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



