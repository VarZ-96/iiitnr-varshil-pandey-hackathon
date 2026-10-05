from transformers import pipeline
import logging
from src.models.schemas import RiskSignal
from src.core.services.event_bus import event_bus

logger = logging.getLogger(__name__)

class NLPService:
    def __init__(self):
        # Initialize FinBERT for sentiment
        logger.info("Initializing FinBERT pipeline...")
        self.sentiment_analyzer = pipeline("sentiment-analysis", model="ProsusDE/finbert")
        
        # Initialize Zero-Shot classifier for event categorization
        # Using a fast model for zero-shot classification to keep latency low
        logger.info("Initializing Zero-Shot pipeline...")
        self.zero_shot_classifier = pipeline("zero-shot-classification", model="valhalla/distilbart-mnli-12-1")
        
        self.event_classes = [
            "Geopolitical", 
            "Macroeconomic", 
            "Credit Event", 
            "Merger/Acquisition", 
            "Product Launch"
        ]

    def _calculate_polarity(self, label: str, score: float) -> float:
        """
        Convert FinBERT labels (positive, negative, neutral) to a 
        continuous polarity score between -1.0 and 1.0.
        """
        label = label.lower()
        if label == "positive":
            return score
        elif label == "negative":
            return -score
        else:
            return 0.0

    def _determine_impact(self, event_type: str, score: float) -> int:
        """
        Deterministic impact scoring [1-10] based on event type and confidence.
        """
        base_impact = {
            "Geopolitical": 8,
            "Macroeconomic": 7,
            "Credit Event": 9,
            "Merger/Acquisition": 6,
            "Product Launch": 5
        }
        
        # Scale base impact by model confidence score
        impact = int(base_impact.get(event_type, 5) * (0.5 + 0.5 * score))
        return max(1, min(10, impact))

    def process_text(self, ticker: str, text: str) -> RiskSignal:
        logger.info(f"Processing text for ticker: {ticker}")
        
        # 1. Sentiment Analysis
        sentiment_result = self.sentiment_analyzer(text)[0]
        sentiment_polarity = self._calculate_polarity(
            sentiment_result['label'], 
            sentiment_result['score']
        )
        
        # 2. Event Classification
        classification_result = self.zero_shot_classifier(
            text, 
            candidate_labels=self.event_classes
        )
        
        best_event = classification_result['labels'][0]
        best_score = classification_result['scores'][0]
        
        # 3. Determine Impact Score
        impact_score = self._determine_impact(best_event, best_score)
        
        # 4. Construct validated Pydantic Risk Signal
        risk_signal = RiskSignal(
            ticker=ticker,
            sentiment_score=sentiment_polarity,
            event_type=best_event,
            impact_score=impact_score
        )
        
        # 5. Publish to Event Bus
        logger.info(f"Publishing 'risk_signal_generated' event for {ticker}")
        event_bus.publish("risk_signal_generated", risk_signal)
        
        return risk_signal
