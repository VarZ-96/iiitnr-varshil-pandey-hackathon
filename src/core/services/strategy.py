from abc import ABC, abstractmethod
from typing import Dict, List
import datetime
import math
from src.models.schemas import RiskSignal

class IRebalanceStrategy(ABC):
    @abstractmethod
    def calculate_weights(self, baseline_weights: Dict[str, float], risk_signals: List[RiskSignal]) -> Dict[str, float]:
        """Calculates new target weights for the portfolio based on risk signals."""
        pass

class EqualWeightStrategy(IRebalanceStrategy):
    def calculate_weights(self, baseline_weights: Dict[str, float], risk_signals: List[RiskSignal]) -> Dict[str, float]:
        n = len(baseline_weights)
        if n == 0:
            return {}
        eq_weight = 1.0 / n
        return {ticker: eq_weight for ticker in baseline_weights}

import logging

logger = logging.getLogger(__name__)

class SentimentTiltedStrategy(IRebalanceStrategy):
    def __init__(self, alpha: float = 0.3, decay_lambda: float = 0.85):
        self.alpha = alpha
        self.decay_lambda = decay_lambda

    def _check_sentiment_volatility(self, ticker: str, risk_signals: List[RiskSignal]) -> bool:
        """
        Statistical Volatility Guard:
        Calculates rolling z-score against historical moving average.
        Returns True (flagged as FROZEN) if incoming signal shift > 3 standard deviations (|z| > 3.0).
        """
        ticker_signals = [s for s in risk_signals if s.ticker == ticker]
        if len(ticker_signals) < 3:
            return False

        # Sort chronologically
        sorted_signals = sorted(ticker_signals, key=lambda s: s.created_at)
        history_scores = [s.sentiment_score for s in sorted_signals[:-1]]
        latest_score = sorted_signals[-1].sentiment_score

        n = len(history_scores)
        mean_sentiment = sum(history_scores) / n
        variance = sum((x - mean_sentiment) ** 2 for x in history_scores) / n
        std_dev = math.sqrt(variance)

        if std_dev < 1e-4:
            # Flat historical baseline: any sudden large jump > 0.6 is a flash event
            is_anomaly = abs(latest_score - mean_sentiment) > 0.6
            if is_anomaly:
                logger.warning(f"VOLATILITY GUARD: Sudden sentiment shock on flat baseline for {ticker}. Freezing asset weight.")
            return is_anomaly

        z_score = abs(latest_score - mean_sentiment) / std_dev
        if z_score > 3.0:
            logger.warning(
                f"VOLATILITY GUARD TRIGGERED: Asset {ticker} sentiment shift |z|={z_score:.2f} > 3.0 standard deviations. "
                f"Flagging as FROZEN for current rebalance cycle."
            )
            return True
        return False

    def calculate_weights(self, baseline_weights: Dict[str, float], risk_signals: List[RiskSignal]) -> Dict[str, float]:
        # 1. Volatility Guard: Identify frozen assets due to sentiment flash crashes
        frozen_assets = set()
        for ticker in baseline_weights:
            if self._check_sentiment_volatility(ticker, risk_signals):
                frozen_assets.add(ticker)

        # 2. Calculate time-decayed aggregated sentiment (S_avg)
        current_time = datetime.datetime.now(datetime.timezone.utc)
        
        s_avg_map = {ticker: 0.0 for ticker in baseline_weights}
        decay_sum_map = {ticker: 0.0 for ticker in baseline_weights}
        
        for signal in risk_signals:
            if signal.ticker in s_avg_map:
                created = signal.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=datetime.timezone.utc)
                age_days = (current_time - created).total_seconds() / 86400.0
                if age_days < 0:
                    age_days = 0.0
                
                # Prevent float underflow with safe minimum bounding epsilon (1e-9)
                raw_decay = math.exp(-self.decay_lambda * age_days)
                decay_factor = max(raw_decay, 1e-9)
                
                impact_factor = signal.impact_score / 10.0
                weighted_sentiment = signal.sentiment_score * impact_factor * decay_factor
                
                s_avg_map[signal.ticker] += weighted_sentiment
                decay_sum_map[signal.ticker] += decay_factor

        # Normalize S_avg by decay factor weights using epsilon to prevent ZeroDivisionError
        for ticker in s_avg_map:
            if decay_sum_map[ticker] > 0:
                s_avg_map[ticker] = s_avg_map[ticker] / max(decay_sum_map[ticker], 1e-9)

        # 3. Sentiment Tilt Formulation (Frozen assets retain previous/baseline weight exactly)
        target_weights = {}
        for ticker, base_w in baseline_weights.items():
            if ticker in frozen_assets:
                # Maintain previous weight exactly
                target_weights[ticker] = base_w
                logger.info(f"Asset {ticker} is FROZEN. Maintaining fixed baseline weight {base_w:.4f}.")
            else:
                s_avg = s_avg_map[ticker]
                target_weights[ticker] = max(0.001, base_w * (1.0 + (self.alpha * s_avg)))

        # 4. Box-Constrained Normalization (Bounded in [0.02, 0.25], Sum == 1.0)
        return self._box_constrained_normalization(target_weights, frozen_tickers=frozen_assets)

    def _box_constrained_normalization(self, weights: Dict[str, float], frozen_tickers: set = None) -> Dict[str, float]:
        """
        O(N) Active-Set Box-Constrained Simplex Projection with Volatility Guard Support.
        Frozen assets remain locked from iteration 0 with their exact target weight.
        Residual portfolio mass is iteratively clipped and redistributed strictly across active assets.
        """
        MIN_WEIGHT = 0.02
        MAX_WEIGHT = 0.25
        MAX_ITERATIONS = 50
        frozen = frozen_tickers or set()
        
        tickers = list(weights.keys())
        n = len(tickers)
        if n == 0:
            return {}

        # Check feasibility
        if n * MIN_WEIGHT > 1.0 or n * MAX_WEIGHT < 1.0:
            return {t: 1.0 / n for t in tickers}
            
        current_weights = {t: float(weights[t]) for t in tickers}
        locked: Dict[str, bool] = {t: (t in frozen) for t in tickers}
        
        iteration = 0
        while iteration < MAX_ITERATIONS:
            iteration += 1
            active_tickers = [t for t in tickers if not locked[t]]
            if not active_tickers:
                break
                
            locked_sum = sum(current_weights[t] for t in tickers if locked[t])
            residual_weight = 1.0 - locked_sum
            active_sum = sum(current_weights[t] for t in active_tickers)
            
            # Rebalance active assets to sum to residual_weight
            if active_sum <= 1e-12:
                equal_share = residual_weight / len(active_tickers)
                for t in active_tickers:
                    current_weights[t] = equal_share
            else:
                scale_factor = residual_weight / active_sum
                for t in active_tickers:
                    current_weights[t] *= scale_factor
                    
            # Check for boundary violations among active assets and freeze them
            newly_frozen = False
            for t in active_tickers:
                if current_weights[t] < MIN_WEIGHT:
                    current_weights[t] = MIN_WEIGHT
                    locked[t] = True
                    newly_frozen = True
                elif current_weights[t] > MAX_WEIGHT:
                    current_weights[t] = MAX_WEIGHT
                    locked[t] = True
                    newly_frozen = True
                    
            # If no new assets were frozen in this iteration, active weights satisfy bounds
            if not newly_frozen:
                break
                
        # Final absorption of float precision error onto the largest active/unlocked asset
        active_tickers = [t for t in tickers if not locked[t]]
        target_pool = active_tickers if active_tickers else [t for t in tickers if t not in frozen]
        if not target_pool:
            target_pool = tickers
            
        total_sum = sum(current_weights.values())
        diff = 1.0 - total_sum
        
        if abs(diff) > 1e-12:
            best_ticker = max(target_pool, key=lambda t: current_weights[t])
            current_weights[best_ticker] = round(current_weights[best_ticker] + diff, 6)
            
        return {t: round(current_weights[t], 6) for t in tickers}


