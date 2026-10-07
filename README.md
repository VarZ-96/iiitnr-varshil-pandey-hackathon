# Autonomous AI/NLP Risk Engine & Tactical Index Rebalancing Platform

This project is a submission for the **S&P Global & CRISIL Campus Hackathon 2026 — Phase 3 Case Study**. It implements a highly resilient, ultra-low latency FinTech pipeline that asynchronously ingests unstructured financial news, extracts semantic risk signals using FinBERT and Zero-Shot Classification, and dynamically rebalances a 10-stock portfolio.

## 🏛️ Architecture Overview

The application strictly follows an **MVC (Controller-Service-Repository)** pattern and utilizes SOLID principles.

*   **Ingestion Layer**: A FastAPI endpoint accepts unstructured text. A Circuit Breaker pattern is in place to protect against external API failures.
*   **AI/NLP Service**: Utilizes `ProsusDE/finbert` for continuous Sentiment Polarity extraction [-1.0 to 1.0] and `valhalla/distilbart-mnli-12-1` for fast Zero-Shot event classification.
*   **Event Bus**: Employs the Observer pattern. The NLP service publishes extracted canonical Pydantic `RiskSignals` to the bus autonomously.
*   **Quant Rebalancer Engine**: Subscribes to the Event Bus. Utilizes the Strategy Pattern (`SentimentTiltedStrategy`) to recalculate target weights and enforce box constraints via iterative simplex clipping.
*   **Data Layer**: SQLAlchemy ORM with a `QueuePool` (size 20) persists data to SQLite/PostgreSQL, ensuring strict ACID transactions.
*   **Presentation Layer**: An interactive Streamlit dashboard provides executive real-time visualization of the portfolio state.

## 🧠 Agentic AI Workflow

1.  **Ingest**: Unstructured text arrives at the ingestion controller.
2.  **Analyze (FinBERT)**: Text is scored for positive/negative probability, converting into a strict polarity float.
3.  **Classify (Zero-Shot)**: Text is deterministically categorized into one of 5 strict Hackathon event classes without human intervention.
4.  **Impact Rating**: An impact score [1-10] is heuristically derived from confidence intervals.
5.  **Signal Generation**: A strict Pydantic `RiskSignal` is emitted to the Event Bus, automatically triggering the Quantitative Rebalancer.

## 📐 Module A Quantitative Math

The `SentimentTiltedStrategy` implements the mathematical constraints of the case study:

1.  **Time-Decayed Sentiment ($S_{avg}$)**: 
    $S_{avg} = \sum [Sentiment \times (Impact/10) \times e^{-\lambda \times Age_{days}}]$
2.  **Target Weight Tilt**: 
    $W_{target} = W_{baseline} \times (1 + (\alpha \times S_{avg}))$
3.  **Iterative Box-Constrained Normalization**: 
    An O(N) iterative clipping algorithm executes over the target array, clamping values below **2% (0.02)** and above **25% (0.25)**. The remaining unconstrained mass is proportionally redistributed until the portfolio weight error is $< 10^{-6}$ and precisely sums to **1.0 (100%)**.

## 🚀 How to Run Locally

### 1. Environment Setup
Create a virtual environment and install requirements:
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On MacOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
```

### 2. Start the FastAPI Backend
Start the high-performance Uvicorn server:
```bash
# Ensure you are at the project root
uvicorn src.main:app --reload
```
The API will be available at: http://127.0.0.1:8000
Swagger Documentation: http://127.0.0.1:8000/docs

### 3. Start the Streamlit Dashboard
In a new terminal window, activate the venv and start Streamlit:
```bash
streamlit run src/dashboard/app.py
```
The executive dashboard will open at: http://localhost:8501
