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
            created_at=risk_signal.created_at.replace(tzinfo=None)
        )
        try:
            self.session.add(db_signal)
            self.session.commit()
            return db_signal.id
        except Exception as e:
            self.session.rollback()
            raise e
            
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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
