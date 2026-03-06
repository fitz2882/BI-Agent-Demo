# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A demo of the BI Agent Demo. Users ask natural language business questions; a multi-agent pipeline pulls relevant database tables, fields, business rules from Google File Search (RAG), generates SQL via voting consensus, executes it, and returns formatted answers with charts.

## Commands

### Backend (from repo root)
```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn app:app --reload --port 8000          # run from backend/
python demo_data/seed.py                       # seed SQLite DB (run from repo root)
```

### Frontend (from frontend/)
```bash
npm install
npm run dev          # dev server on :5173, proxies /api -> :8000
npm run build        # production build
```

### Environment
Copy `.env.example` to `.env` and set `GOOGLE_API_KEY` and `GOOGLE_FILE_SEARCH_STORE` for RAG via Google File Search (otherwise falls back to local schema provider).

## Architecture

**Pipeline flow** (`backend/agents/pipeline.py`):
```
Question -> ComplexityAnalyzer -> RetrievalAgent -> TableSelector(voting)
         -> JoinArchitect(voting) -> SqlSynthesizer(voting)
         -> Executor -> Formatter + Visualization -> Response
```

**Core pattern** - `VotingSubNetwork` (`backend/agents/voting_subnetwork.py`):
- Reused by TableSelector, JoinArchitect, and SqlSynthesizer
- Spawns parallel Gemini Flash workers, validates responses, tallies votes, applies ahead-by-K consensus
- K is adaptive based on complexity score (2-5)
- Votes accumulate across batches and continues until one answer is ahead-by-k

**State** - `MAKERState` (`backend/agents/state.py`):
- Single Pydantic model passed through the entire pipeline
- Holds trace_id, schema_context, step_outputs (table_selection, join_logic, final_sql), query_results, agent_steps

**API** - FastAPI app (`backend/app.py`):
- `POST /query` - main endpoint, runs pipeline, returns answer + SQL + chart spec + agent steps
- `GET /schema` - returns demo DB schema
- `GET /health` - health check
- Vite dev server proxies `/api/*` to `:8000` (strips `/api` prefix)

**Frontend** - React 19 + Vite + Tailwind CSS 4 + Recharts:
- `App.jsx` - chat interface, renders messages with SQL display, charts, and agent step traces
- `services/api.js` - calls backend via `/api` proxy
- No router; single-page chat UI

**Database** - SQLite at `demo_data/demo.db`:
- 7 tables: departments, employees, categories, products, customers, orders, order_items
- Seeded by `demo_data/seed.py` with deterministic random data (seed=42)

**Knowledge Base** (`knowledge_base/`):
- Schema docs, business rules, SQL patterns for Google File Search RAG
- Upload via `scripts/upload_kb.py`

## Key Design Decisions

- All LLM calls use `google-genai` SDK with `gemini-flash-latest` model
- Workers use `temperature=0.7`; each worker creates its own `genai.Client`
- SQL validation rejects any non-SELECT statements (write protection)
- Pipeline has a retry loop (max 2 retries) for SQL execution errors
- Frontend uses CSS custom properties (`var(--color-*)`) for theming
