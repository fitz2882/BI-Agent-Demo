"""FastAPI server for the BI Agent Demo."""

import json
import logging
import os
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """SSE endpoint that streams pipeline steps, then the final result."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if len(request.question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long (max 1000 chars)")

    step_queue: queue.Queue = queue.Queue()

    def on_step(agent: str, detail: str):
        step_queue.put({"agent": agent, "detail": detail})

    def generate():
        # Run pipeline in a thread so we can yield steps as they arrive
        result_holder = {}
        error_holder = {}

        def run_pipeline():
            try:
                pipeline = get_pipeline()
                result_holder["data"] = pipeline.run(request.question, on_step=on_step)
            except Exception as e:
                error_holder["error"] = str(e)
            finally:
                step_queue.put(None)  # Sentinel

        thread = threading.Thread(target=run_pipeline)
        thread.start()

        while True:
            item = step_queue.get()
            if item is None:
                break
            yield f"event: step\ndata: {json.dumps(item)}\n\n"

        if error_holder:
            yield f"event: error\ndata: {json.dumps({'detail': error_holder['error']})}\n\n"
        elif result_holder:
            yield f"event: result\ndata: {json.dumps(result_holder['data'])}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/schema")
async def get_schema():
    """Return the demo database schema for reference."""
    from agents.schema_provider import DEMO_SCHEMA
    return DEMO_SCHEMA


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
