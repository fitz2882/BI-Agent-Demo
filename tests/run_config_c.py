"""Run Config C (Graduated) across all 8 queries x 3 runs with File Search."""

import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Override DB_PATH for running from project root (not backend/)
os.environ["DB_PATH"] = str(Path(__file__).resolve().parent.parent / "demo_data" / "demo.db")

from agents.config import AgentConfig
from agents.complexity_analyzer import ComplexityAnalyzer
from agents.retrieval_agent import RetrievalAgent
from temperature_benchmark import run_single_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("config_c")

TEMPERATURES = [0.0, 0.2, 0.3, 0.4, 0.5]
QUERIES = [
    # Only the remaining complex queries (simple/medium already completed)
    "Show me total revenue by product category",
    "Which products have the highest profit margin?",
    "How many orders were placed each month in 2024?",
]
RUNS_PER_QUERY = 3


def main():
    config = AgentConfig.from_env()
    complexity = ComplexityAnalyzer()
    retrieval = RetrievalAgent(config)

    results = {}

    for q in QUERIES:
        results[q] = []
        for run_idx in range(RUNS_PER_QUERY):
            logger.info("--- [Run %d/%d] %s", run_idx + 1, RUNS_PER_QUERY, q)
            try:
                result = run_single_query(q, config, TEMPERATURES, complexity, retrieval)
                results[q].append(result)
                logger.info(
                    "  Rounds: TS=%d JA=%d SQL=%d | Total=%d | API=%d | Correct=%s | %dms",
                    result["table_selection_rounds"],
                    result["join_rounds"],
                    result["sql_rounds"],
                    result["total_rounds"],
                    result["total_api_calls"],
                    result["sql_correct"],
                    result["elapsed_ms"],
                )
            except Exception as e:
                logger.error("  FAILED: %s", e)
                results[q].append({
                    "question": q,
                    "total_rounds": -1,
                    "total_api_calls": -1,
                    "sql_correct": False,
                    "error": str(e),
                })

    out_path = Path(__file__).resolve().parent / "config_c_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
