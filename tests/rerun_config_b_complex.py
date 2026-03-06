"""Rerun Config B on the 3 complex queries that hung, with per-query timeout via multiprocessing."""

import sys
import json
import time
import logging
import multiprocessing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("rerun")

TEMPERATURES = [0.0, 0.1, 0.1, 0.1, 0.1]
COMPLEX_QUERIES = [
    "Show me total revenue by product category",
    "Which products have the highest profit margin?",
    "How many orders were placed each month in 2024?",
]
RUNS_PER_QUERY = 3
TIMEOUT_SECONDS = 180


def _run_query_in_process(question, temperatures, result_queue):
    """Run a single query in an isolated process (so we can kill it on timeout)."""
    import os
    os.environ.setdefault("PYTHONPATH", str(Path(__file__).resolve().parent.parent / "backend"))

    from agents.config import AgentConfig
    from agents.complexity_analyzer import ComplexityAnalyzer
    from agents.retrieval_agent import RetrievalAgent
    from temperature_benchmark import run_single_query

    config = AgentConfig.from_env()
    complexity = ComplexityAnalyzer()
    retrieval = RetrievalAgent(config)

    result = run_single_query(question, config, temperatures, complexity, retrieval)
    result_queue.put(result)


def run_with_timeout(question, temperatures, timeout):
    """Run a query with a hard process-level timeout."""
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=_run_query_in_process, args=(question, temperatures, q))
    p.start()
    p.join(timeout=timeout)

    if p.is_alive():
        p.terminate()
        p.join(timeout=5)
        if p.is_alive():
            p.kill()
            p.join()
        return None  # timed out

    if not q.empty():
        return q.get()
    return None


def _stats(values):
    import math
    n = len(values)
    if n == 0:
        return {"mean": 0, "std": 0}
    mean = sum(values) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1)) if n > 1 else 0
    return {"mean": mean, "std": std}


def main():
    results = {}

    for q in COMPLEX_QUERIES:
        results[q] = []
        for run_idx in range(RUNS_PER_QUERY):
            logger.info("--- [Run %d/%d] %s", run_idx + 1, RUNS_PER_QUERY, q)
            start = time.time()

            result = run_with_timeout(q, TEMPERATURES, TIMEOUT_SECONDS)

            if result is None:
                elapsed = int((time.time() - start) * 1000)
                logger.error("  TIMED OUT after %ds", TIMEOUT_SECONDS)
                results[q].append({
                    "question": q,
                    "total_rounds": -1,
                    "total_api_calls": -1,
                    "sql_correct": False,
                    "elapsed_ms": elapsed,
                    "error": f"timeout_{TIMEOUT_SECONDS}s",
                })
            else:
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

    # Print summary
    print("\n" + "=" * 80)
    print("CONFIG B COMPLEX QUERY RESULTS")
    print("=" * 80)

    for q in COMPLEX_QUERIES:
        runs = results[q]
        valid = [r for r in runs if r.get("total_rounds", -1) >= 0]
        timed_out = sum(1 for r in runs if "timeout" in str(r.get("error", "")))

        print(f"\n  {q}")
        if valid:
            rnd = _stats([r["total_rounds"] for r in valid])
            api = _stats([r["total_api_calls"] for r in valid])
            t = _stats([r["elapsed_ms"] / 1000 for r in valid])
            print(f"    Completed: {len(valid)}/{len(runs)} | Rounds: {rnd['mean']:.1f} +/- {rnd['std']:.1f} | API: {api['mean']:.1f} +/- {api['std']:.1f} | Time: {t['mean']:.1f}s")
        if timed_out:
            print(f"    Timed out: {timed_out}/{len(runs)} (>{TIMEOUT_SECONDS}s)")

    # Save results
    out_path = Path(__file__).resolve().parent / "config_b_complex_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    main()
