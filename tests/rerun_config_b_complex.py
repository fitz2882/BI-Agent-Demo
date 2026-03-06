"""Rerun Config B on the 3 complex queries that hung, with per-query timeout."""

import sys
import signal
import json
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from agents.config import AgentConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("rerun")

# Import from the main benchmark
sys.path.insert(0, str(Path(__file__).resolve().parent))
from temperature_benchmark import (
    run_single_query, ComplexityAnalyzer, RetrievalAgent, _stats
)

TEMPERATURES = [0.0, 0.1, 0.1, 0.1, 0.1]
COMPLEX_QUERIES = [
    "Show me total revenue by product category",
    "Which products have the highest profit margin?",
    "How many orders were placed each month in 2024?",
]
RUNS_PER_QUERY = 3
TIMEOUT_SECONDS = 180  # 3 min hard timeout per run


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Query exceeded timeout")


def main():
    config = AgentConfig.from_env()
    complexity = ComplexityAnalyzer()
    retrieval = RetrievalAgent(config)

    results = {}

    for q in COMPLEX_QUERIES:
        results[q] = []
        for run_idx in range(RUNS_PER_QUERY):
            logger.info("--- [Run %d/%d] %s", run_idx + 1, RUNS_PER_QUERY, q)

            # Set alarm timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(TIMEOUT_SECONDS)

            try:
                result = run_single_query(q, config, TEMPERATURES, complexity, retrieval)
                signal.alarm(0)  # Cancel alarm
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
            except TimeoutError:
                signal.alarm(0)
                logger.error("  TIMED OUT after %ds", TIMEOUT_SECONDS)
                results[q].append({
                    "question": q,
                    "total_rounds": -1,
                    "total_api_calls": -1,
                    "sql_correct": False,
                    "elapsed_ms": TIMEOUT_SECONDS * 1000,
                    "error": f"timeout_{TIMEOUT_SECONDS}s",
                })
            except Exception as e:
                signal.alarm(0)
                logger.error("  FAILED: %s", e)
                results[q].append({
                    "question": q,
                    "total_rounds": -1,
                    "total_api_calls": -1,
                    "sql_correct": False,
                    "elapsed_ms": 0,
                    "error": str(e),
                })

    # Print summary
    print("\n" + "=" * 80)
    print("CONFIG B COMPLEX QUERY RESULTS")
    print("=" * 80)

    for q in COMPLEX_QUERIES:
        runs = results[q]
        valid = [r for r in runs if r.get("total_rounds", -1) >= 0]
        timed_out = sum(1 for r in runs if r.get("error", "").startswith("timeout"))
        failed = sum(1 for r in runs if r.get("total_rounds", -1) < 0 and not r.get("error", "").startswith("timeout"))

        print(f"\n  {q}")
        if valid:
            rnd = _stats([r["total_rounds"] for r in valid])
            api = _stats([r["total_api_calls"] for r in valid])
            print(f"    Completed: {len(valid)}/{len(runs)} | Rounds: {rnd['mean']:.1f} +/- {rnd['std']:.1f} | API: {api['mean']:.1f} +/- {api['std']:.1f}")
        if timed_out:
            print(f"    Timed out: {timed_out}/{len(runs)}")
        if failed:
            print(f"    Failed: {failed}/{len(runs)}")

    # Save results
    out_path = Path(__file__).resolve().parent / "config_b_complex_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
