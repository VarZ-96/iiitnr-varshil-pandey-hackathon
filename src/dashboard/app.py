import os
import sys
import json
import time
import requests
import pandas as pd
import altair as alt
import streamlit as st

# Ensure repository root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# --- Configuration ---
API_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(
    page_title="Tactical Index Rebalancing Platform", 
    page_icon="📈", 
    layout="wide"
)

st.title("📈 Tactical Index Rebalancing Platform")
st.markdown("### Powered by Event-Driven NLP & Iterative Simplex Rebalancing")

# --- Helper: Database Snapshot & Signal Fetching ---
def fetch_latest_portfolio_snapshot():
    try:
        from src.db.repositories.portfolio_repo import SessionLocal, DBPortfolioSnapshot
        with SessionLocal() as session:
            latest = (
                session.query(DBPortfolioSnapshot)
                .order_by(DBPortfolioSnapshot.created_at.desc())
                .first()
            )
            if latest and latest.allocations:
                return {a.ticker: float(a.weight) for a in latest.allocations}
    except Exception:
        pass
    return None

def fetch_recent_signals(limit=25):
    try:
        from src.db.repositories.portfolio_repo import SessionLocal, DBRiskSignal
        with SessionLocal() as session:
            records = (
                session.query(DBRiskSignal)
                .order_by(DBRiskSignal.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
                    "ticker": r.ticker,
                    "event_type": r.event_type,
                    "sentiment_score": round(float(r.sentiment_score), 4),
                    "impact_score": r.impact_score,
                    "confidence_score": round(float(getattr(r, "confidence_score", 0.85)), 4),
                    "status": getattr(r, "status", "AUTO_PROCESSED")
                }
                for r in records
            ]
    except Exception:
        pass
    return []

# --- Helper: Benchmark Dataset Loader ---
def load_benchmark_events():
    benchmark_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "market_events_benchmark.json")
    if not os.path.exists(benchmark_path):
        benchmark_path = "data/market_events_benchmark.json"
    if os.path.exists(benchmark_path):
        try:
            with open(benchmark_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

benchmark_events = load_benchmark_events()
scenario_options = ["Select a scenario..."] + [
    f"{ev['ticker']} | {ev.get('event_type', 'Event')}: {ev['text'][:60]}..."
    for ev in benchmark_events
]

# --- Session State Management ---
if "portfolio_weights" not in st.session_state:
    initial_weights = fetch_latest_portfolio_snapshot()
    if initial_weights:
        st.session_state.portfolio_weights = initial_weights
    else:
        st.session_state.portfolio_weights = {
            "AAPL": 0.1, "MSFT": 0.1, "GOOGL": 0.1, "AMZN": 0.1, "NVDA": 0.1,
            "META": 0.1, "TSLA": 0.1, "BRK.B": 0.1, "UNH": 0.1, "JNJ": 0.1
        }

if "recent_signals" not in st.session_state:
    st.session_state.recent_signals = fetch_recent_signals()

if "ticker_input" not in st.session_state:
    st.session_state.ticker_input = "AAPL"
if "text_input" not in st.session_state:
    st.session_state.text_input = "Factory shutdown halts production due to global supply chain crisis."

# Callback when user selects an item from the benchmark dataset
def on_scenario_select():
    choice = st.session_state.get("selected_scenario")
    if choice and choice != "Select a scenario...":
        idx = scenario_options.index(choice) - 1
        if 0 <= idx < len(benchmark_events):
            item = benchmark_events[idx]
            st.session_state.ticker_input = item["ticker"]
            st.session_state.text_input = item["text"]

# --- Sidebar: Ingestion Form & Benchmark Pre-Load ---
st.sidebar.header("📡 Ingest Market Feed")

# Benchmark Pre-Load Dropdown above manual inputs
st.sidebar.selectbox(
    "Load from Benchmark Dataset...",
    options=scenario_options,
    key="selected_scenario",
    on_change=on_scenario_select,
    help="Pre-populate manual fields with benchmark events from data/market_events_benchmark.json"
)

with st.sidebar.form(key="ingest_form"):
    ticker = st.text_input("Ticker Symbol", key="ticker_input")
    text = st.text_area("News Text", key="text_input", height=120)
    source = st.selectbox("Source", ["Reuters", "Bloomberg", "SEC_EDGAR", "NewsAPI", "Twitter", "BenchmarkDataset"])
    submit = st.form_submit_button(label="Process Signal")
    
    if submit:
        with st.spinner("Processing NLP Signal..."):
            try:
                # 1. Post to Ingest Endpoint
                res = requests.post(
                    f"{API_URL}/signals/ingest", 
                    json={"ticker": ticker.strip().upper(), "text": text.strip(), "source": source}
                )
                if res.status_code == 201:
                    signal_data = res.json()
                    st.session_state.recent_signals.insert(0, signal_data)
                    status_flag = signal_data.get("status", "AUTO_PROCESSED")
                    st.sidebar.success(f"Signal Extracted! [{status_flag}]")
                    
                    # 2. Brief wait for asynchronous EventBus rebalancer to commit
                    time.sleep(0.35)
                    
                    # 3. Pull latest snapshot from database
                    updated_weights = fetch_latest_portfolio_snapshot()
                    if updated_weights:
                        st.session_state.portfolio_weights = updated_weights
                    
                    # 4. Trigger UI rerun to redraw updated weights dynamically
                    st.rerun()
                else:
                    st.sidebar.error(f"Error: {res.text}")
            except Exception as e:
                st.sidebar.error(f"Failed to connect to API Backend. Is FastAPI running? Exception: {e}")

# --- Main Dashboard ---
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Current Portfolio Allocation")
    df_alloc = pd.DataFrame(
        list(st.session_state.portfolio_weights.items()),
        columns=["Ticker", "Weight"]
    )
    
    # Altair Bar Chart
    chart = alt.Chart(df_alloc).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X('Ticker:N', sort='-y'),
        y=alt.Y('Weight:Q', scale=alt.Scale(domain=[0, 0.3])),
        color=alt.condition(
            alt.datum.Weight > 0.1,
            alt.value('#1f77b4'),     # Greater than baseline
            alt.value('#ff7f0e')      # Less than baseline
        ),
        tooltip=['Ticker', alt.Tooltip('Weight:Q', format='.4f')]
    ).properties(height=450)
    
    # Render Box Constraint Guidelines
    rule_min = alt.Chart(pd.DataFrame({'y': [0.02]})).mark_rule(color='red', strokeWidth=2, strokeDash=[5,5]).encode(y='y:Q')
    rule_max = alt.Chart(pd.DataFrame({'y': [0.25]})).mark_rule(color='green', strokeWidth=2, strokeDash=[5,5]).encode(y='y:Q')
    
    st.altair_chart(chart + rule_min + rule_max, use_container_width=True)

with col2:
    st.subheader("Optimization Constraints")
    st.info("""
    **Box Constraints Enforced:**
    - **Max Weight:** 25% (0.25)
    - **Min Weight:** 2% (0.02)
    """)
    st.metric(
        label="Sum of All Weights", 
        value=f"{sum(st.session_state.portfolio_weights.values()):.4f}", 
        help="Strictly normalized to exactly 1.0"
    )
    st.metric(label="Algorithm", value="Iterative Simplex")

st.divider()

# --- Risk Signals Table ---
st.subheader("Recent Risk Signals")
current_signals = fetch_recent_signals() or st.session_state.recent_signals
if current_signals:
    df_signals = pd.DataFrame(current_signals)
    cols_to_show = [c for c in ['created_at', 'ticker', 'event_type', 'sentiment_score', 'impact_score', 'confidence_score', 'status'] if c in df_signals.columns]
    df_signals = df_signals[cols_to_show]
    st.dataframe(
        df_signals,
        use_container_width=True
    )
else:
    st.info("No risk signals processed yet. Use the sidebar to ingest unstructured market news.")
