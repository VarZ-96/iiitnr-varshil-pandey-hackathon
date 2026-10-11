import logging
from typing import List, Dict
from src.models.schemas import RiskSignal, RebalanceResponse, AllocationDetail
from src.core.services.event_bus import event_bus
from src.core.services.strategy import IRebalanceStrategy, SentimentTiltedStrategy
from src.db.repositories.portfolio_repo import (
    fetch_historical_signals_and_close,
    save_rebalance_and_close,
)

logger = logging.getLogger(__name__)

class RebalancerService:
    def __init__(self, strategy: IRebalanceStrategy = None):
        # 10-stock mock portfolio baseline weighting 1/N
        self.baseline_weights: Dict[str, float] = {
            "AAPL": 0.1, "MSFT": 0.1, "GOOGL": 0.1, "AMZN": 0.1, "NVDA": 0.1,
            "META": 0.1, "TSLA": 0.1, "BRK.B": 0.1, "UNH": 0.1, "JNJ": 0.1
        }
        self.strategy = strategy or SentimentTiltedStrategy()
        
        # In-memory signal cache
        self.historical_signals: List[RiskSignal] = []

        # Subscribe to Event Bus to act as an ISignalObserver
        logger.info("Subscribing RebalancerService to 'risk_signal_generated' event")
        event_bus.subscribe("risk_signal_generated", self.handle_risk_signal)

    def handle_risk_signal(self, risk_signal: RiskSignal):
        logger.info(f"RebalancerService received RiskSignal for {risk_signal.ticker}. Initiating rebalance.")
        self.historical_signals.append(risk_signal)
        self.rebalance()

    def rebalance(self) -> RebalanceResponse:
        """
        Executes tactical portfolio rebalancing with strict connection pool management:
        1. Fetches historical signals and immediately closes DB session.
        2. Executes CPU-bound quant math in memory with ZERO DB connections held open.
        3. Opens a brief, dedicated session solely to atomically commit the rebalance snapshot.
        """
        logger.info("Executing tactical portfolio rebalance with selected strategy...")
        
        # 1. Fetch historical signals and immediately release DB connection
        try:
            db_signals = fetch_historical_signals_and_close(limit=100)
            existing_ids = {d.id for d in db_signals}
            combined_signals = db_signals + [s for s in self.historical_signals if s.id not in existing_ids]
        except Exception as e:
            logger.warning(f"Could not load historical signals from DB: {e}. Using in-memory buffer.")
            combined_signals = self.historical_signals
        
        # 2. Run heavy math purely in memory (ZERO connections held open in QueuePool)
        new_weights_dict = self.strategy.calculate_weights(self.baseline_weights, combined_signals)
        
        # 3. Package into strictly validated schemas
        allocations = []
        sum_weights = 0.0
        for ticker, weight in new_weights_dict.items():
            allocations.append(AllocationDetail(ticker=ticker, weight=weight))
            sum_weights += weight
            
        response = RebalanceResponse(
            weights=allocations,
            sum=round(sum_weights, 6)
        )
        
        # 4. Open brief new session solely for atomic INSERT
        try:
            save_rebalance_and_close(response)
            logger.info(f"Successfully committed PORTFOLIO_SNAPSHOT {response.snapshot_id} to DB.")
        except Exception as e:
            logger.error(f"Failed to persist rebalance snapshot to DB: {e}")
            
        return response

# Initialize singleton to automatically subscribe on module load
rebalancer_service = RebalancerService()

