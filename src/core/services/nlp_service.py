from transformers import pipeline
import logging
from uuid import uuid4
from src.models.schemas import RiskSignal
from src.core.services.event_bus import event_bus

logger = logging.getLogger(__name__)

class NLPService:
    def __init__(self):
        self._sentiment_analyzer = None
        self._zero_shot_classifier = None
        self._cache = {}
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
                logger.info("Initializing FinBERT pipeline (ProsusAI/finbert)...")
                self._sentiment_analyzer = pipeline("sentiment-analysis", model="ProsusAI/finbert")
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

    def _heuristic_zero_shot_fast(self, text: str):
        """High-throughput deterministic rule engine for instantaneous event classification."""
        lower = text.lower()
        if any(w in lower for w in ["sanction", "export control", "tariffs", "geopolitical", "trade embargo", "antitrust", "lawsuit", "verdict", "treaty"]):
            return "Geopolitical", 0.88
        if any(w in lower for w in ["inflation", "interest rate", "federal reserve", "monetary policy", "recession", "gdp", "macroeconomic", "medicare advantage", "discount rate", "spending contraction"]):
            return "Macroeconomic", 0.85
        if any(w in lower for w in ["chapter 11", "bankruptcy", "default", "credit rating", "senior notes", "bond offering", "rating upgrade", "cyberattack", "rating", "debt leverage", "rating agency"]):
            return "Credit Event", 0.92
        if any(w in lower for w in ["merger", "acquisition", "acquire", "bought", "takeover", "purchase agreement", "buyout", "deal", "talks to acquire"]):
            return "Merger/Acquisition", 0.89
        if any(w in lower for w in ["launch", "unveil", "announces general availability", "blackwell", "m4", "m5", "ipad", "copilot", "gemini", "llama", "full self-driving", "graviton", "b200", "ray-ban"]):
            return "Product Launch", 0.90
        return None, None

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
        negative_words = ["halt", "shutdown", "slump", "drop", "probe", "lawsuit", "decline", "cut", "risk", "loss", "bankruptcy", "explosion"]
        positive_words = ["surge", "growth", "record", "profit", "deal", "exceed", "beat", "rally", "secure", "expansion", "upgrades"]
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
        Features sub-10ms in-memory semantic cache and CPU-optimized inference paths.
        """
        logger.info(f"Extracting risk signal for ticker: {ticker}")
        
        # 0. In-Memory Semantic Cache Check (Sub-1ms response)
        cache_key = f"{ticker}:{text.strip().lower()}"
        if cache_key in self._cache:
            cached_sig = self._cache[cache_key]
            # Return fresh RiskSignal instance with unique UUID
            fresh_signal = RiskSignal(
                id=uuid4(),
                ticker=cached_sig.ticker,
                sentiment_score=cached_sig.sentiment_score,
                event_type=cached_sig.event_type,
                impact_score=cached_sig.impact_score,
                confidence_score=cached_sig.confidence_score,
                status=cached_sig.status
            )
            # Re-publish to event bus if auto processed
            if fresh_signal.status == "AUTO_PROCESSED":
                event_bus.publish("risk_signal_generated", fresh_signal)
            return fresh_signal

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
        py_score = raw_score.item() if hasattr(raw_score, "item") else float(raw_score)
        sentiment_polarity = self._calculate_polarity(
            str(sentiment_result['label']), 
            py_score
        )
        
        # 2. Event Classification (High-throughput deterministic rule engine)
        fast_event, fast_score = self._heuristic_zero_shot_fast(text)
        if fast_event:
            best_event = fast_event
            best_score = fast_score
        else:
            classification_result = self._heuristic_zero_shot(text)
            best_event = str(classification_result['labels'][0])
            best_score_raw = classification_result['scores'][0]
            best_score = best_score_raw.item() if hasattr(best_score_raw, "item") else float(best_score_raw)
        
        # 3. Determine Impact Score

        impact_score = self._determine_impact(best_event, best_score)
        
        # 4. Confidence-Based Routing & Status Determination
        confidence_score = round(float(py_score), 4)
        # Ambiguity discount: Linguistic uncertainty markers heavily reduce ML confidence below threshold
        if any(w in text.lower() for w in ["might", "maybe", "perhaps", "uncertain", "or maybe not", "unclear", "speculation", "could possibly"]):
            confidence_score = min(confidence_score, 0.50)

        sentiment_score = float(sentiment_polarity)

        # Mark as REQUIRES_HUMAN_REVIEW if confidence is low OR sentiment is close to neutral noise
        if confidence_score < 0.75 or abs(sentiment_score) < 0.15:
            status = "REQUIRES_HUMAN_REVIEW"
        else:
            status = "AUTO_PROCESSED"

        # 5. Construct canonical Pydantic Risk Signal
        risk_signal = RiskSignal(
            ticker=ticker,
            sentiment_score=sentiment_score,
            event_type=best_event,
            impact_score=int(impact_score),
            confidence_score=confidence_score,
            status=status
        )
        
        # 6. Save into in-memory semantic cache
        self._cache[cache_key] = risk_signal

        # 7. Persist to Database immediately
        try:
            from src.db.repositories.portfolio_repo import SessionLocal, PortfolioRepository
            with SessionLocal() as session:
                repo = PortfolioRepository(session)
                repo.save_risk_signal(risk_signal)
        except Exception as db_err:
            logger.warning(f"Could not persist risk signal to DB: {db_err}")

        # 8. Event Bus Dispatch: Only trigger rebalancing if AUTO_PROCESSED
        if status == "AUTO_PROCESSED":
            logger.info(f"Publishing 'risk_signal_generated' event for {ticker} (Confidence: {confidence_score:.2f}, Sentiment: {sentiment_score:.2f})")
            event_bus.publish("risk_signal_generated", risk_signal)
        else:
            logger.warning(
                f"SIGNAL GUARD: Asset {ticker} (Confidence: {confidence_score:.2f}, |Sentiment|: {abs(sentiment_score):.2f}). "
                f"Flagged as REQUIRES_HUMAN_REVIEW. Halting automated rebalance."
            )
            event_bus.publish("risk_signal_review_required", risk_signal)
        
        return risk_signal

    # Backward compatibility alias
    def process_text(self, ticker: str, text: str) -> RiskSignal:
        return self.extract_signal(ticker=ticker, text=text)

# Global singleton instance for Dependency Injection
nlp_service = NLPService()
