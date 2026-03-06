# BI Agent Demo

A simplified demonstration of the **MAKER Framework** for Business Intelligence — a multi-agent SQL generation system that uses voting consensus to produce reliable queries.

## How It Works

The MAKER (Multi-Agent Knowledge-Enhanced Reasoning) framework generates SQL through a pipeline of specialized agents:

```
User Question
    ↓
Entry Agent → Complexity Analyzer → Retrieval Agent (File Search)
    ↓
Table Selector (Voting Consensus)
    ↓
Join Architect (Voting Consensus)
    ↓
SQL Synthesizer (Voting Consensus)
    ↓
Executor → Formatter + Visualization
    ↓
Natural Language Answer + Chart
```

### Voting Consensus (Ahead-by-K)

The core innovation is the **voting sub-network** pattern:

1. **Parallel Workers** generate K candidate responses using Gemini Flash
2. **Validator** filters out invalid responses (SQL injection, bad syntax, etc.)
3. **Vote Tally** counts votes for each unique response
4. **Consensus** applies ahead-by-K logic — the leader must be ahead of the runner-up by K votes
5. If no consensus, generate another batch (votes accumulate across rounds)

K is set adaptively based on question complexity:
- K=2 for simple queries ("How many customers?")
- K=3 for medium queries ("Revenue by category")
- K=4-5 for complex queries (multi-join, aggregation, date math)

## Quick Start

### 1. Set up the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 3. Seed the demo database

```bash
python demo_data/seed.py
```

### 3b. (Optional) Set up Google File Search

Upload the Knowledge Base files to a Google File Search store for grounded RAG retrieval. If skipped, the system falls back to a local schema provider.

```bash
python scripts/upload_kb.py
# Copy the store name from the output into your .env:
# GOOGLE_FILE_SEARCH_STORE=fileSearchStores/xxxxx
```

### 4. Start the backend

```bash
cd backend
uvicorn app:app --reload --port 8000
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Demo Database

The demo uses **Acme Analytics**, a fictional e-commerce company with:

| Table | Rows | Description |
|-------|------|-------------|
| customers | 50 | Customer profiles with city, state, lifetime value |
| products | 60 | Products across 6 categories with price and cost |
| categories | 6 | Electronics, Clothing, Home & Garden, Sports, Books, Food |
| orders | 200 | Orders with status (pending/shipped/delivered/cancelled) |
| order_items | ~600 | Line items linking orders to products |
| employees | 20 | Employees across 5 departments |
| departments | 5 | Engineering, Sales, Marketing, Support, Operations |

## Example Questions

- "What are the top 5 customers by lifetime value?"
- "Show me total revenue by product category"
- "How many orders were placed each month in 2024?"
- "Which products have the highest profit margin?"
- "What is the average salary by department?"

## Architecture

```
frontend/          React 19 + Vite + Tailwind CSS + Recharts
backend/
  app.py           FastAPI server
  agents/
    pipeline.py    Orchestrates the full agent pipeline
    state.py       MAKERState object (passed through pipeline)
    config.py      Configuration from environment
    complexity_analyzer.py   Scores question complexity, sets K
    retrieval_agent.py       Google File Search RAG (with local fallback)
    schema_provider.py       Local fallback schema provider
    table_selector.py        Voting consensus for table selection
    join_architect.py        Voting consensus for JOIN logic
    sql_synthesizer.py       Voting consensus for SQL generation
    voting_subnetwork.py     Core MAKER voting pattern (reusable)
    executor.py              Executes SQL against SQLite
    formatter.py             LLM-powered natural language formatting
    visualization.py         Auto-detects chart type, generates specs
demo_data/
  seed.py          Creates and populates the SQLite database
knowledge_base/    Schema docs, business rules, SQL patterns (for File Search)
scripts/
  upload_kb.py     Uploads KB files to Google File Search store
```

## Tech Stack

- **Backend**: Python, FastAPI, Google Gemini Flash
- **Frontend**: React 19, Vite, Tailwind CSS 4, Recharts
- **Database**: SQLite (demo), designed to work with any SQL database
- **AI**: Google Gemini API for worker generation and result formatting
- **RAG**: Google File Search for grounded schema retrieval from Knowledge Base
