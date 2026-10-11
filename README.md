# Event-Driven Quantitative NLP Pipeline & Tactical Index Rebalancing Platform

**Target:** S&P Global & CRISIL Campus Hackathon 2026 — Phase 3 Case Study  
**Architecture Pattern:** Layered MVC (Controller-Service-Repository) & SOLID Principles  

---

## 📌 Deliverables & Presentation Links

* 📺 **YouTube Demo Video:** [Watch Video (Link Placeholder)](https://youtube.com/placeholder-demo)
* 📑 **Presentation Deck:** [docs/presentation.pdf](docs/presentation.pdf)
* 📊 **Market Events Benchmark:** [`data/market_events_benchmark.json`](data/market_events_benchmark.json)

---

## 🏛️ Architecture Overview

The system implements a production-grade, ultra-low latency FinTech pipeline that asynchronously ingests unstructured financial market feeds, extracts deterministic risk signals using financial domain NLP transformers, and dynamically recalculates portfolio weights for an S&P 100 10-stock universe.

* **Ingestion Layer (`src/api/controllers/signal_controller.py`):** FastAPI async ASGI endpoints protected by a Circuit Breaker state machine (`CLOSED`, `OPEN`, `HALF_OPEN`) to prevent cascading upstream feed outages.
* **Inference Concurrency:** PyTorch transformer execution is offloaded from the main ASGI event loop using `starlette.concurrency.run_in_threadpool`, ensuring zero request blocking, with all tensor outputs cast to native Python floats to eliminate memory leakage.
* **Event Bus (`src/core/services/event_bus.py`):** Decoupled Observer pattern utilizing `asyncio.to_thread` and asynchronous tasks to dispatch risk signals without delaying the HTTP ingestion response.
* **Quant Rebalancing Engine (`src/core/services/rebalancer_service.py`):** Strategy pattern implementation (`SentimentTiltedStrategy`) utilizing exponential time-decay sentiment aggregation and an $O(N)$ active-set simplex projection algorithm to enforce box constraints (`[0.02, 0.25]`).
* **Persistence & Connection Pool (`src/db/repositories/portfolio_repo.py`):** SQLAlchemy ORM with a 20-connection `QueuePool`. Connection acquisition is isolated into brief, dedicated sessions that release connections prior to CPU-intensive mathematical execution, preventing pool starvation at high QPS.
* **Presentation Layer (`src/dashboard/app.py`):** Real-time interactive Streamlit dashboard rendering live portfolio reallocations, box-constraint guideline envelopes, and transparent NLP extraction telemetry.

---

## 🧠 Event-Driven Quantitative NLP Pipeline (FinBERT + Zero-Shot Classification)

Rather than relying on non-deterministic generative LLM agents, the system utilizes a specialized, deterministic NLP pipeline:

1. **Unstructured Feed Ingestion:** Raw news headlines, regulatory bulletins, and social media feeds are ingested and validated against strict Pydantic schemas.
2. **FinBERT Polarity Extraction:** `ProsusDE/finbert` (or deterministic keyword fallback under disconnected conditions) calculates positive, negative, and neutral probabilities, continuously mapped to a strict sentiment polarity score $S \in [-1.0, 1.0]$.
3. **Zero-Shot Event Categorization:** `valhalla/distilbart-mnli-12-1` categorizes the text into one of 5 canonical financial event classes:
   * **Macroeconomic**
   * **Credit Event**
   * **Merger/Acquisition**
   * **Product Launch**
   * **Geopolitical**
4. **Deterministic Impact Scoring:** Confidence intervals and event severity weights map each headline to an integer Impact Score $I \in [1, 10]$.
5. **Canonical Risk Signal Publishing:** The resulting `RiskSignal` is emitted to the asynchronous Event Bus, automatically triggering portfolio rebalancing without human intervention.

---

## 📐 Module A Quantitative Math Formulation

The `SentimentTiltedStrategy` implements the exact mathematical constraints specified for Module A:

### 1. Time-Decayed Sentiment Aggregation ($S_{avg}$)
Historical sentiment signals for each asset are smoothed using an exponential time-decay factor governed by $\lambda = 0.85$:
$$S_{avg} = \frac{\sum_{i=1}^{M} \left( S_i \times \frac{Impact_i}{10} \times \max\left(e^{-\lambda \cdot \Delta t_i}, 10^{-9}\right) \right)}{\max\left(\sum_{i=1}^{M} \max\left(e^{-\lambda \cdot \Delta t_i}, 10^{-9}\right), 10^{-9}\right)}$$
*Where $\Delta t_i$ is the signal age in days, and $10^{-9}$ is a safety epsilon preventing float underflow and `ZeroDivisionError` on legacy signals.*

### 2. Sentiment-Tilted Unnormalized Weights
$$W_{target} = W_{baseline} \times \left(1 + \alpha \cdot S_{avg}\right)$$
*Where $W_{baseline} = \frac{1}{N} = 0.10$ for a 10-stock basket, and sensitivity coefficient $\alpha = 0.30$.*

### 3. Active-Set Box-Constrained Simplex Projection
To enforce strict institutional risk limits, an active-set iterative projection algorithm guarantees:
$$\sum_{j=1}^{N} W_j = 1.000000 \quad \text{and} \quad 0.02 \le W_j \le 0.25 \quad \forall j$$
* Assets violating the $0.02$ floor or $0.25$ ceiling are frozen into a locked set.
* Residual weight is iteratively redistributed only across active, unlocked assets.
* The algorithm terminates in $O(N)$ iterations (bounded by `max_iterations = 50`), guaranteeing strict convergence.

---

## 📊 Dataset & Provenance

The repository contains curated financial evaluation datasets located in the [`data/`](data/) directory:

### 1. `data/market_events_benchmark.json`
A comprehensive benchmark dataset of **60 realistic financial headlines** covering all 10 portfolio tickers (`AAPL`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`, `META`, `TSLA`, `BRK.B`, `UNH`, `JNJ`) across all 5 event classes.

**Data Provenance Breakdown:**
* **Public RSS / Wire Services:** Reuters Technology, Bloomberg Deal Reporter, Financial Times, Wall Street Journal.
* **Historical SEC Filings:** Form 8-K (material events), Form 10-Q (quarterly filings), Form 10-K (annual reports), Form 424B2 (debt prospectuses).
* **Credit Rating Bulletins:** S&P Global Ratings Corporate Research, Moody's Investors Service, Fitch Ratings.
* **Synthetic Stress Tests:** Calibrated macroeconomic scenarios simulating high interest rate regimes, semiconductor export restrictions, supply chain disruptions, and tariff shocks.

### 2. `data/sample_news.json`
A lightweight test fixture containing sample headlines for quick functional testing during initial installation.

---

## 🚀 Quickstart & Local Setup

Follow these exact steps to clone, configure, and launch the platform:

```bash
# 1. Clone the repository
git clone https://github.com/VarZ-96/iiitnr-varshil-pandey-hackathon.git

# 2. Navigate to project root
cd iiitnr-varshil-pandey-hackathon

# 3. Create virtual environment
python -m venv venv

# 4. Activate virtual environment
# On Windows PowerShell:
.\venv\Scripts\activate
# On Linux / macOS:
# source venv/bin/activate

# 5. Install required dependencies
python -m pip install -r requirements.txt
```

### ⚡ Running the Platform

#### Method A: 1-Click Startup Script (Recommended)
```powershell
.\start.ps1
```
*(Or double-click `start.bat` in Windows Explorer)*

#### Method B: Manual Startup (Two Terminals)

**Terminal 1 (FastAPI Backend with Morgan Logger):**
```powershell
.\venv\Scripts\activate
uvicorn src.main:app --reload --port 8000
```
* Backend API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
* Interactive Swagger Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* Request Logs: Streamed live to terminal and written to [`logs/backend.log`](logs/backend.log)

**Terminal 2 (Streamlit Executive Dashboard):**
```powershell
.\venv\Scripts\activate
streamlit run src/dashboard/app.py --server.port 8501 --server.headless true
```
* Executive Dashboard: [http://localhost:8501](http://localhost:8501)
