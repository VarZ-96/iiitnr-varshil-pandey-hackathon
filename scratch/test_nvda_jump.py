import asyncio
import httpx
from src.main import app
from src.db.repositories.portfolio_repo import SessionLocal, DBPortfolioSnapshot

async def run():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headline = "Nvidia announces massive record profit and Blackwell chip supply surge exceeding all targets"
        print(f"Ingesting headline for NVDA: '{headline}'")
        resp = await client.post("/api/v1/signals/ingest", json={
            "ticker": "NVDA",
            "text": headline,
            "source": "Reuters"
        })
        print(f"HTTP Status: {resp.status_code}")
        data = resp.json()
        print(f"Signal: Ticker={data['ticker']}, Sentiment={data['sentiment_score']}, Event={data['event_type']}, Confidence={data['confidence_score']}, Status={data['status']}")
        
        await asyncio.sleep(0.5)
        
        with SessionLocal() as session:
            latest = session.query(DBPortfolioSnapshot).order_by(DBPortfolioSnapshot.created_at.desc()).first()
            if latest and latest.allocations:
                weights = {a.ticker: round(float(a.weight), 4) for a in latest.allocations}
                print("\n=== LATEST DB PORTFOLIO SNAPSHOT ALLOCATIONS ===")
                for t, w in sorted(weights.items(), key=lambda x: -x[1]):
                    print(f"  {t:6s}: {w*100:5.1f}% ({w:.4f})")
                print(f"Total Sum: {sum(weights.values()):.4f}")
                nvda_w = weights.get("NVDA", 0)
                print(f"\nResult: NVDA is at {nvda_w*100:.1f}% ({nvda_w:.4f})")
                assert nvda_w > 0.15, f"NVDA did not jump noticeably above 0.15: {nvda_w}"
                print("SUCCESS: NVDA jumped noticeably above 0.15 on the rebalanced portfolio snapshot!")

if __name__ == "__main__":
    asyncio.run(run())
