# Intent Detection Agent

Intent Detection Agent is an open-source system for discovering B2B sales prospects from live web signals. It transforms natural language queries into ranked company lists by orchestrating web search, signal ingestion, classification, and scoring in a modular multi-agent pipeline.

##  Key Features

* **Multi-agent pipeline**: Structured workflow using LangGraph
* **Knowledge graph integration**: Neo4j-based company–signal relationships
* **Semantic search**: Vector retrieval with Qdrant
* **Explainable scoring**: Transparent fit-score computation
* **API-based deployment**: FastAPI backend for real-world integration

---

##  System Architecture

The system consists of four main stages:

1. **Web Search** – Collects real-time signals from the web using Perplexity API
2. **Ingestion** – Cleans, deduplicates, and stores signals (Neo4j + Qdrant)
3. **Classification** – Assigns signal type and sentiment using LLM + rules
4. **Scoring** – Aggregates signals into company-level fit scores

Pipeline flow:

```
web_search → ingest → classify → score
```

---

##  Impact

*  Reduces manual prospect research from **2–3 hours → < 1 minute**
*  Estimated cost per query: **~$0.11**
*  Enables scalable B2B lead generation and market intelligence workflows

---

##  Tech Stack

* **Backend**: Python, FastAPI
* **Orchestration**: LangGraph
* **Databases**: Neo4j (graph), Qdrant (vector)
* **APIs**: OpenAI, Perplexity
* **Frontend**: Next.js, TypeScript

---

##  Setup Instructions

### Prerequisites

* Python 3.11+
* Node.js 18+
* PostgreSQL-compatible database
* API keys for:

  * OpenAI
  * Perplexity

### Installation

```bash
git clone https://github.com/1Ninad/Intent-Detection-Agent.git
cd Intent-Detection-Agent
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Run backend:

```bash
uvicorn app.main:app --reload
```

Run frontend:

```bash
cd frontend
npm install
npm run dev
```

---

##  Repository Structure

```
backend/
frontend/
evaluation/
```

* `backend/` – Core pipeline and API
* `frontend/` – UI for query input and results
* `evaluation/` – Sample outputs and evaluation artifacts

---

##  Evaluation

* Classification accuracy: **63.3%**
* Sentiment accuracy: **96.7%**
* Average cost: **~$0.11/query**

---

##  Limitations

* Depends on external APIs (OpenAI, Perplexity)
* Performance may vary with web signal quality
* Latency primarily influenced by web search stage

---

##  Future Work

* Improve classification accuracy for minority signal types
* Reduce end-to-end latency
* Expand domain-specific signal taxonomies
* Improve reproducibility packaging

---

##  License

This project is licensed under the **MIT License**.

---
