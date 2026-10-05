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

class SentimentTiltedStrategy(IRebalanceStrategy):
    def __init__(self, alpha: float = 0.3, decay_lambda: float = 0.85):
        self.alpha = alpha
        self.decay_lambda = decay_lambda

    def calculate_weights(self, baseline_weights: Dict[str, float], risk_signals: List[RiskSignal]) -> Dict[str, float]:
        # 1. Calculate time-decayed aggregated sentiment (S_avg)
        current_time = datetime.datetime.now(datetime.timezone.utc)
        
        s_avg_map = {ticker: 0.0 for ticker in baseline_weights}
        
        for signal in risk_signals:
            if signal.ticker in s_avg_map:
                age_days = (current_time - signal.created_at).total_seconds() / 86400.0
                if age_days < 0:
                    age_days = 0
                
                decay_factor = math.exp(-self.decay_lambda * age_days)
                impact_factor = signal.impact_score / 10.0
                weighted_sentiment = signal.sentiment_score * impact_factor * decay_factor
                
                s_avg_map[signal.ticker] += weighted_sentiment

        # 2. Sentiment Tilt Formulation
        target_weights = {}
        for ticker, base_w in baseline_weights.items():
            s_avg = s_avg_map[ticker]
            # Target_Weight = Baseline_Weight * (1 + (Alpha * S_avg))
            target_weights[ticker] = base_w * (1 + (self.alpha * s_avg))

        # 3. Box-Constrained Normalization
        return self._box_constrained_normalization(target_weights)

    def _box_constrained_normalization(self, weights: Dict[str, float]) -> Dict[str, float]:
        MIN_WEIGHT = 0.02
        MAX_WEIGHT = 0.25
        
        tickers = list(weights.keys())
        if not tickers:
            return {}
            
        current_weights = {t: weights[t] for t in tickers}
        locked = {t: False for t in tickers}
        
        MAX_ITERATIONS = 50
        for _ in range(MAX_ITERATIONS):
            unlocked_tickers = [t for t in tickers if not locked[t]]
            if not unlocked_tickers:
                break
                
            total_sum = sum(current_weights.values())
            error = 1.0 - total_sum
            
            if abs(error) < 1e-6:
                break
                
            unlocked_sum = sum(current_weights[t] for t in unlocked_tickers)
            
            if unlocked_sum <= 0:
                adjustment = error / len(unlocked_tickers)
                for t in unlocked_tickers:
                    current_weights[t] += adjustment
            else:
                for t in unlocked_tickers:
                    current_weights[t] += error * (current_weights[t] / unlocked_sum)
                    
            newly_locked = False
            for t in unlocked_tickers:
                if current_weights[t] < MIN_WEIGHT:
                    current_weights[t] = MIN_WEIGHT
                    locked[t] = True
                    newly_locked = True
                elif current_weights[t] > MAX_WEIGHT:
                    current_weights[t] = MAX_WEIGHT
                    locked[t] = True
                    newly_locked = True
                    
            if not newly_locked:
                break
                
        # Final pass to guarantee strict 1.0 sum, assigning remainder to the largest unlocked component
        final_sum = sum(current_weights.values())
        if abs(final_sum - 1.0) > 1e-9:
            max_ticker = max(unlocked_tickers if unlocked_tickers else tickers, key=lambda t: current_weights[t])
            current_weights[max_ticker] += (1.0 - final_sum)

        return current_weights
