import uuid
import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import QueuePool

Base = declarative_base()

class DBRiskSignal(Base):
    __tablename__ = 'risk_signal'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticker = Column(String, index=True, nullable=False)
    sentiment_score = Column(Float, nullable=False)
    event_type = Column(String, nullable=False)
    impact_score = Column(Integer, nullable=False)
    confidence_score = Column(Float, default=0.85, nullable=False)
    status = Column(String, default="AUTO_PROCESSED", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_risk_signal_ticker_created', 'ticker', 'created_at'),
    )


class DBPortfolioSnapshot(Base):
    __tablename__ = 'portfolio_snapshot'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    allocations = relationship("DBAllocationDetail", back_populates="snapshot", cascade="all, delete-orphan")

class DBAllocationDetail(Base):
    __tablename__ = 'allocation_detail'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id = Column(String, ForeignKey('portfolio_snapshot.id'), nullable=False)
    ticker = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    
    snapshot = relationship("DBPortfolioSnapshot", back_populates="allocations")

# Setup PostgreSQL Engine with QueuePool for concurrent writes
DATABASE_URL = "sqlite:///./fintech.db"  # Using sqlite for local dev, simulating connection pool

engine = create_engine(
    DATABASE_URL, 
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Create tables
Base.metadata.create_all(bind=engine)

# Backward-compatible auto-migration for dev SQLite database
with engine.connect() as conn:
    from sqlalchemy import text
    try:
        conn.execute(text("ALTER TABLE risk_signal ADD COLUMN confidence_score FLOAT DEFAULT 0.85"))
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE risk_signal ADD COLUMN status VARCHAR DEFAULT 'AUTO_PROCESSED'"))
        conn.commit()
    except Exception:
        pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class PortfolioRepository:
    def __init__(self, session):
        self.session = session
        
    def save_risk_signal(self, risk_signal) -> str:
        """ACID compliant commit for a single Risk Signal."""
        db_signal = DBRiskSignal(
            id=str(risk_signal.id),
            ticker=risk_signal.ticker,
            sentiment_score=risk_signal.sentiment_score,
            event_type=risk_signal.event_type,
            impact_score=risk_signal.impact_score,
            confidence_score=getattr(risk_signal, 'confidence_score', 0.85),
            status=getattr(risk_signal, 'status', 'AUTO_PROCESSED'),
            created_at=risk_signal.created_at.replace(tzinfo=None)
        )
        try:
            self.session.add(db_signal)
            self.session.commit()
            return db_signal.id
        except Exception as e:
            self.session.rollback()
            raise e
            
    def get_historical_signals(self, limit: int = 100):
        """
        Reads recent historical risk signals from the database.
        """
        records = (
            self.session.query(DBRiskSignal)
            .order_by(DBRiskSignal.created_at.desc())
            .limit(limit)
            .all()
        )
        return records

    def save_portfolio_rebalance(self, rebalance_response) -> str:
        """ACID compliant transaction spanning snapshot and all details."""
        try:
            db_snapshot = DBPortfolioSnapshot(
                id=str(rebalance_response.snapshot_id)
            )
            self.session.add(db_snapshot)
            
            for alloc in rebalance_response.weights:
                db_alloc = DBAllocationDetail(
                    snapshot_id=db_snapshot.id,
                    ticker=alloc.ticker,
                    weight=alloc.weight
                )
                self.session.add(db_alloc)
                
            self.session.commit()
            return db_snapshot.id
        except Exception as e:
            self.session.rollback()
            raise e

def fetch_historical_signals_and_close(limit: int = 100):
    """
    Acquires a connection from QueuePool, fetches data, and releases the connection
    IMMEDIATELY before any CPU-intensive quant mathematics begin.
    """
    from src.models.schemas import RiskSignal
    with SessionLocal() as session:
        repo = PortfolioRepository(session)
        records = repo.get_historical_signals(limit=limit)
        # Detach into Pydantic models with UTC datetimes
        signals = [
            RiskSignal(
                id=uuid.UUID(r.id),
                ticker=r.ticker,
                sentiment_score=float(r.sentiment_score),
                event_type=r.event_type,
                impact_score=int(r.impact_score),
                confidence_score=float(getattr(r, 'confidence_score', 0.85)),
                status=str(getattr(r, 'status', 'AUTO_PROCESSED')),
                created_at=r.created_at.replace(tzinfo=datetime.timezone.utc)
            )
            for r in records
        ]
        return signals


def save_rebalance_and_close(rebalance_response) -> str:
    """
    Acquires a brief connection ONLY for the final atomic INSERT transaction,
    committing and releasing the connection back to the QueuePool immediately.
    """
    with SessionLocal() as session:
        repo = PortfolioRepository(session)
        return repo.save_portfolio_rebalance(rebalance_response)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

