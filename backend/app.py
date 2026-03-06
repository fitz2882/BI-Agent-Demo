"""FastAPI server for the BI Agent Demo."""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.pipeline import Pipeline
from agents.config import AgentConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Ensure demo database exists
DB_PATH = os.getenv("DB_PATH", "demo_data/demo.db")
if not Path(DB_PATH).exists():
    logger.warning("Demo database not found at %s. Run: python demo_data/seed.py", DB_PATH)

app = FastAPI(
    title="BI Agent Demo",
    description="Multi-Agent Business Intelligence System - Demo",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize pipeline (lazy)
_pipeline = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        config = AgentConfig.from_env()
        config.db_path = DB_PATH
        _pipeline = Pipeline(config)
    return _pipeline


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    trace_id: str
    answer: str
    sql: str | None = None
    results: list = []
    chart: dict | None = None
    steps: list = []
    execution_time_ms: int = 0
    complexity: dict = {}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bi-agent-demo"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if len(request.question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long (max 1000 chars)")

    try:
        pipeline = get_pipeline()
        result = pipeline.run(request.question)
        return QueryResponse(**result)
    except Exception as e:
        logger.exception("Pipeline error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema")
async def get_schema():
    """Return the demo database schema for reference."""
    from agents.schema_provider import DEMO_SCHEMA
    return DEMO_SCHEMA


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
