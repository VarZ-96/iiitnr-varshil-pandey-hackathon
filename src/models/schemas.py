from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from uuid import UUID, uuid4

class IngestFeedRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    text: str = Field(..., description="Unstructured financial news or social media text")
    source: str = Field(..., description="Source of the text (e.g., NewsAPI, Twitter)")

class RiskSignal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    ticker: str
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    event_type: str
    impact_score: int = Field(..., ge=1, le=10)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RebalanceRequest(BaseModel):
    strategy: str = Field(default="SentimentTilted")
    decay_lambda: float = Field(default=0.85)

class AllocationDetail(BaseModel):
    ticker: str
    weight: float

class RebalanceResponse(BaseModel):
    snapshot_id: UUID = Field(default_factory=uuid4)
    weights: List[AllocationDetail]
    sum: float
