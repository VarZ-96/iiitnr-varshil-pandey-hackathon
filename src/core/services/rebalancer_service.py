import logging
from typing import List, Dict
from src.models.schemas import RiskSignal, RebalanceResponse, AllocationDetail
from src.core.services.event_bus import event_bus
from src.core.services.strategy import IRebalanceStrategy, SentimentTiltedStrategy

logger = logging.getLogger(__name__)

class RebalancerService:
    def __init__(self, strategy: IRebalanceStrategy = None):
        # 10-stock mock portfolio baseline weighting 1/N
        self.baseline_weights: Dict[str, float] = {
            "AAPL": 0.1, "MSFT": 0.1, "GOOGL": 0.1, "AMZN": 0.1, "NVDA": 0.1,
            "META": 0.1, "TSLA": 0.1, "BRK.B": 0.1, "UNH": 0.1, "JNJ": 0.1
        }
        self.strategy = strategy or SentimentTiltedStrategy()
        
        # Historical in-memory cache (acts as repository proxy for now)
        self.historical_signals: List[RiskSignal] = []

        # Subscribe to Event Bus to act as an ISignalObserver
        logger.info("Subscribing RebalancerService to 'risk_signal_generated' event")
        event_bus.subscribe("risk_signal_generated", self.handle_risk_signal)

    def handle_risk_signal(self, risk_signal: RiskSignal):
        logger.info(f"RebalancerService received RiskSignal for {risk_signal.ticker}. Initiating rebalance.")
        self.historical_signals.append(risk_signal)
        self.rebalance()

    def rebalance(self) -> RebalanceResponse:
        logger.info("Executing tactical portfolio rebalance with selected strategy...")
        
        # 1. Compute new target weights
        new_weights_dict = self.strategy.calculate_weights(self.baseline_weights, self.historical_signals)
        
        # 2. Package into strictly validated schemas
        allocations = []
        sum_weights = 0.0
        for ticker, weight in new_weights_dict.items():
            allocations.append(AllocationDetail(ticker=ticker, weight=weight))
            sum_weights += weight
            
        response = RebalanceResponse(
            weights=allocations,
            sum=sum_weights
        )
        
        # 3. Save to Repositories (Mocked via logging for now)
        logger.info(f"--- MOCK DB COMMIT STARTED ---")
        logger.info(f"INSERT INTO PORTFOLIO_SNAPSHOT (id, created_at) VALUES ('{response.snapshot_id}', NOW())")
        for alloc in response.weights:
            logger.info(f"INSERT INTO ALLOCATION_DETAIL (snapshot_id, ticker, weight) VALUES ('{response.snapshot_id}', '{alloc.ticker}', {alloc.weight:.5f})")
        logger.info(f"--- MOCK DB COMMIT ENDED. Sum: {response.sum:.5f} ---")
            
        return response

# Initialize singleton to automatically subscribe on module load
rebalancer_service = RebalancerService()
