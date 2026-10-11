from transformers import pipeline
import logging
from src.models.schemas import RiskSignal
from src.core.services.event_bus import event_bus

logger = logging.getLogger(__name__)

class NLPService:
    def __init__(self):
        self._sentiment_analyzer = None
        self._zero_shot_classifier = None
        self.event_classes = [
            "Geopolitical", 
            "Macroeconomic", 
            "Credit Event", 
            "Merger/Acquisition", 
            "Product Launch"
        ]

    def _get_sentiment_pipeline(self):
        if self._sentiment_analyzer is None:
            try:
                logger.info("Initializing FinBERT pipeline (ProsusDE/finbert)...")
                self._sentiment_analyzer = pipeline("sentiment-analysis", model="ProsusDE/finbert")
            except Exception as e:
                logger.warning(f"Could not load FinBERT pipeline: {e}. Using deterministic heuristic.")
                self._sentiment_analyzer = "fallback"
        return self._sentiment_analyzer

    def _get_zero_shot_pipeline(self):
        if self._zero_shot_classifier is None:
            try:
                logger.info("Initializing Zero-Shot pipeline (valhalla/distilbart-mnli-12-1)...")
                self._zero_shot_classifier = pipeline("zero-shot-classification", model="valhalla/distilbart-mnli-12-1")
            except Exception as e:
                logger.warning(f"Could not load Zero-Shot pipeline: {e}. Using deterministic heuristic.")
                self._zero_shot_classifier = "fallback"
        return self._zero_shot_classifier

    def _calculate_polarity(self, label: str, score: float) -> float:
        """
        Convert FinBERT labels (positive, negative, neutral) to a 
        continuous polarity score between -1.0 and 1.0.
        """
        label = label.lower()
        if label == "positive":
            return round(score, 4)
        elif label == "negative":
            return round(-score, 4)
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
        impact = int(base_impact.get(event_type, 5) * (0.5 + 0.5 * score))
        return max(1, min(10, impact))

    def _heuristic_sentiment(self, text: str):
        negative_words = ["halt", "shutdown", "slump", "drop", "probe", "lawsuit", "decline", "cut", "risk", "loss"]
        positive_words = ["surge", "growth", "record", "profit", "deal", "exceed", "beat", "rally", "secure", "expansion"]
        lower = text.lower()
        neg_count = sum(1 for w in negative_words if w in lower)
        pos_count = sum(1 for w in positive_words if w in lower)
        if pos_count > neg_count:
            return {"label": "positive", "score": min(0.95, 0.6 + 0.1 * pos_count)}
        elif neg_count > pos_count:
            return {"label": "negative", "score": min(0.95, 0.6 + 0.1 * neg_count)}
        return {"label": "neutral", "score": 0.5}

    def _heuristic_zero_shot(self, text: str):
        lower = text.lower()
        if any(w in lower for w in ["war", "sanction", "export", "tariffs", "geopolitical", "ban"]):
            return {"labels": ["Geopolitical"], "scores": [0.85]}
        if any(w in lower for w in ["inflation", "rates", "fed", "recession", "gdp", "macro"]):
            return {"labels": ["Macroeconomic"], "scores": [0.82]}
        if any(w in lower for w in ["debt", "default", "rating", "credit", "bankruptcy", "bond"]):
            return {"labels": ["Credit Event"], "scores": [0.88]}
        if any(w in lower for w in ["merger", "acquisition", "acquire", "bought", "takeover", "deal"]):
            return {"labels": ["Merger/Acquisition"], "scores": [0.84]}
        return {"labels": ["Product Launch"], "scores": [0.78]}

    def extract_signal(self, ticker: str, text: str) -> RiskSignal:
        """
        Extract deterministic risk signals from text using FinBERT and Zero-Shot classification.
        Ensures all tensor outputs are converted to native Python floats to prevent memory leaks.
        """
        logger.info(f"Extracting risk signal for ticker: {ticker}")
        
        # 1. Sentiment Analysis
        pipe_sent = self._get_sentiment_pipeline()
        if pipe_sent != "fallback":
            try:
                sentiment_result = pipe_sent(text)[0]
            except Exception as e:
                logger.warning(f"FinBERT inference error: {e}. Falling back to heuristics.")
                sentiment_result = self._heuristic_sentiment(text)
        else:
            sentiment_result = self._heuristic_sentiment(text)

        raw_score = sentiment_result['score']
        # Convert any tensor/numpy types to native float to prevent GPU/CPU memory leak
        py_score = raw_score.item() if hasattr(raw_score, "item") else float(raw_score)
        sentiment_polarity = self._calculate_polarity(
            str(sentiment_result['label']), 
            py_score
        )
        
        # 2. Event Classification
        pipe_zs = self._get_zero_shot_pipeline()
        if pipe_zs != "fallback":
            try:
                classification_result = pipe_zs(text, candidate_labels=self.event_classes)
            except Exception as e:
                logger.warning(f"Zero-Shot inference error: {e}. Falling back to heuristics.")
                classification_result = self._heuristic_zero_shot(text)
        else:
            classification_result = self._heuristic_zero_shot(text)
        
        best_event = str(classification_result['labels'][0])
        best_score_raw = classification_result['scores'][0]
        best_score = best_score_raw.item() if hasattr(best_score_raw, "item") else float(best_score_raw)
        
        # 3. Determine Impact Score
        impact_score = self._determine_impact(best_event, best_score)
        
        # 4. Confidence-Based Routing & Status Determination
        confidence_score = round(float(py_score), 4)
        if confidence_score < 0.75:
            status = "REQUIRES_HUMAN_REVIEW"
        else:
            status = "AUTO_PROCESSED"

        # 5. Construct canonical Pydantic Risk Signal
        risk_signal = RiskSignal(
            ticker=ticker,
            sentiment_score=float(sentiment_polarity),
            event_type=best_event,
            impact_score=int(impact_score),
            confidence_score=confidence_score,
            status=status
        )
        
        # 6. Persist to Database immediately
        try:
            from src.db.repositories.portfolio_repo import SessionLocal, PortfolioRepository
            with SessionLocal() as session:
                repo = PortfolioRepository(session)
                repo.save_risk_signal(risk_signal)
        except Exception as db_err:
            logger.warning(f"Could not persist risk signal to DB: {db_err}")

        # 7. Event Bus Dispatch: Only trigger rebalancing if AUTO_PROCESSED
        if status == "AUTO_PROCESSED":
            logger.info(f"Publishing 'risk_signal_generated' event for {ticker} (Confidence: {confidence_score:.2f})")
            event_bus.publish("risk_signal_generated", risk_signal)
        else:
            logger.warning(
                f"SIGNAL GUARD: Asset {ticker} confidence {confidence_score:.2f} < 0.75. "
                f"Flagged as REQUIRES_HUMAN_REVIEW. Halting automated rebalance."
            )
            event_bus.publish("risk_signal_review_required", risk_signal)
        
        return risk_signal


    # Backward compatibility alias
    def process_text(self, ticker: str, text: str) -> RiskSignal:
        return self.extract_signal(ticker=ticker, text=text)

# Global singleton instance for Dependency Injection
nlp_service = NLPService()

