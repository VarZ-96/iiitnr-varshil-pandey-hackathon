import streamlit as st
import requests
import pandas as pd
import altair as alt

# --- Configuration ---
API_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(
    page_title="FinTech Risk Engine", 
    page_icon="📈", 
    layout="wide"
)

st.title("📈 Tactical Index Rebalancing Platform")
st.markdown("### Powered by Autonomous AI/NLP")

# --- Session State Management ---
if "portfolio_weights" not in st.session_state:
    st.session_state.portfolio_weights = {
        "AAPL": 0.1, "MSFT": 0.1, "GOOGL": 0.1, "AMZN": 0.1, "NVDA": 0.1,
        "META": 0.1, "TSLA": 0.1, "BRK.B": 0.1, "UNH": 0.1, "JNJ": 0.1
    }

if "recent_signals" not in st.session_state:
    st.session_state.recent_signals = []

# --- Sidebar: Ingestion Form ---
st.sidebar.header("📡 Ingest Market Feed")
with st.sidebar.form(key="ingest_form"):
    ticker = st.text_input("Ticker Symbol", value="AAPL")
    text = st.text_area("News Text", value="Factory shutdown halts production due to global supply chain crisis.")
    source = st.selectbox("Source", ["NewsAPI", "Twitter", "Bloomberg"])
    submit = st.form_submit_button(label="Process Signal")
    
    if submit:
        with st.spinner("Processing NLP Signal..."):
            try:
                # 1. Post to Ingest Endpoint
                res = requests.post(
                    f"{API_URL}/signals/ingest", 
                    json={"ticker": ticker.upper(), "text": text, "source": source}
                )
                if res.status_code == 201:
                    signal_data = res.json()
                    st.session_state.recent_signals.insert(0, signal_data)
                    st.sidebar.success("Signal Successfully Extracted!")
                    
                    # 2. Trigger Rebalance Endpoint
                    reb_res = requests.post(
                        f"{API_URL}/portfolio/rebalance",
                        json={"strategy": "SentimentTilted", "decay_lambda": 0.85}
                    )
                    if reb_res.status_code == 200:
                        new_allocations = reb_res.json()["weights"]
                        st.session_state.portfolio_weights = {a["ticker"]: a["weight"] for a in new_allocations}
                        st.sidebar.info("Portfolio Dynamically Rebalanced!")
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
    st.metric(label="Sum of All Weights", value=f"{sum(st.session_state.portfolio_weights.values()):.4f}", help="Strictly normalized to exactly 1.0")
    st.metric(label="Algorithm", value="Iterative Simplex")

st.divider()

# --- Risk Signals Table ---
st.subheader("Recent Risk Signals")
if st.session_state.recent_signals:
    df_signals = pd.DataFrame(st.session_state.recent_signals)
    # Reorder columns for presentation
    df_signals = df_signals[['created_at', 'ticker', 'event_type', 'sentiment_score', 'impact_score']]
    st.dataframe(
        df_signals.style.format({'sentiment_score': '{:.4f}'}),
        use_container_width=True
    )
else:
    st.info("No risk signals processed yet. Use the sidebar to ingest unstructured market news.")
