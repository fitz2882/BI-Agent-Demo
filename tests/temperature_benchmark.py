"""Temperature Benchmark - compares voting consensus speed across temperature configs.

Tests 3 configurations of per-worker temperatures within voting batches:
  Config A: All workers at 0.7 (current default)
  Config B: Worker 1 at 0.0, workers 2-5 at 0.1
  Config C: Workers at 0.0, 0.2, 0.3, 0.4, 0.5 (graduated)

Measures rounds-to-consensus, SQL correctness, and total API calls.
"""

import sys
import os
import json
import time
import sqlite3
import logging
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable, Tuple
from copy import deepcopy

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Override DB_PATH for running from project root (not backend/)
import os as _os
_os.environ["DB_PATH"] = str(Path(__file__).resolve().parent.parent / "demo_data" / "demo.db")

from google import genai
from google.genai import types as genai_types

from agents.config import AgentConfig
from agents.state import MAKERState
from agents.complexity_analyzer import ComplexityAnalyzer
from agents.retrieval_agent import RetrievalAgent
from agents.table_selector import TableSelector
from agents.join_architect import JoinArchitect
from agents.sql_synthesizer import SqlSynthesizer
from agents.executor import ExecutorAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("benchmark")

# ---------------------------------------------------------------------------
# Temperature configurations
# ---------------------------------------------------------------------------

CONFIGS = {
    "A: All 0.7": [0.7, 0.7, 0.7, 0.7, 0.7],
    "B: 0.0 + 0.1s": [0.0, 0.1, 0.1, 0.1, 0.1],
    "C: Graduated": [0.0, 0.2, 0.3, 0.4, 0.5],
}

# ---------------------------------------------------------------------------
# Test queries (mix of simple, medium, complex)
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    # Simple (K=2)
    "How many customers are there?",
    "What is the average employee salary?",
    # Medium (K=3)
    "What are the top 5 customers by lifetime value?",
    "What is the total number of orders per status?",
    "Which department has the most employees?",
    # Complex (K=4)
    "Show me total revenue by product category",
    "Which products have the highest profit margin?",
    # Complex (K=4+)
    "How many orders were placed each month in 2024?",
]

RUNS_PER_COMBO = 3  # Number of runs per config/query combination

# ---------------------------------------------------------------------------
# Patched WorkerPool that uses per-worker temperatures
# ---------------------------------------------------------------------------

# Rate limiter: space out API calls to avoid 503/429
_last_api_call = 0.0
_API_CALL_DELAY = 0.5  # minimum seconds between batch starts

MAX_RETRIES = 4
RETRY_BACKOFF = [2, 5, 10, 20]  # seconds to wait after each retry


def _api_call_with_retry(client, prompt: str, temp: float, worker_idx: int) -> str:
    """Single API call with exponential backoff on 503/429."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(temperature=temp),
            )
            return (response.text or "").strip()
        except Exception as e:
            err_str = str(e)
            is_retryable = "503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str or "RESOURCE_EXHAUSTED" in err_str
            if is_retryable and attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                logger.warning("Worker %d attempt %d failed (%s), retrying in %ds...", worker_idx, attempt + 1, err_str[:80], wait)
                time.sleep(wait)
            else:
                raise


class TempAwareWorkerPool:
    """Workers with individual temperature assignments and rate limiting."""

    def __init__(self, config: AgentConfig, temperatures: List[float]):
        self.config = config
        self.temperatures = temperatures

    def generate_batch(self, prompt: str, state: MAKERState, batch_size: Optional[int] = None) -> List[str]:
        global _last_api_call
        count = batch_size or len(self.temperatures)
        responses: List[str] = []

        # Rate limit: wait if we're calling too fast
        elapsed = time.time() - _last_api_call
        if elapsed < _API_CALL_DELAY:
            time.sleep(_API_CALL_DELAY - elapsed)
        _last_api_call = time.time()

        def _run_one(idx: int) -> str:
            temp = self.temperatures[idx % len(self.temperatures)]
            client = genai.Client(api_key=self.config.google_api_key)
            return _api_call_with_retry(client, prompt, temp, idx)

        with ThreadPoolExecutor(max_workers=count) as executor:
            futures = {executor.submit(_run_one, i): i for i in range(count)}
            for future in as_completed(futures):
                try:
                    text = future.result()
                    if text:
                        responses.append(text)
                except Exception as e:
                    logger.warning("Worker %d failed after retries: %s", futures[future], e)

        return responses


# ---------------------------------------------------------------------------
# Instrumented VotingSubNetwork that tracks round counts
# ---------------------------------------------------------------------------

class InstrumentedVoting:
    """Voting sub-network with metrics collection."""

    def __init__(self, config: AgentConfig, temperatures: List[float], name: str = "voting"):
        self.config = config
        self.name = name
        self.workers = TempAwareWorkerPool(config, temperatures)
        self.metrics = {"rounds": 0, "total_candidates": 0, "valid_candidates": 0}

    def execute(
        self,
        prompt: str,
        state: MAKERState,
        step: str,
        normalizer: Optional[Callable[[str], str]] = None,
    ) -> Tuple[str, bool]:
        accumulated: Dict[str, int] = {}
        batch = 0
        max_batches = self.config.max_retry_batches

        while True:
            batch += 1
            self.metrics["rounds"] += 1

            responses = self.workers.generate_batch(prompt, state, batch_size=state.k_threshold)
            self.metrics["total_candidates"] += len(responses)

            if normalizer:
                responses = [normalizer(r) for r in responses]

            valid = self._validate(responses, step)
            self.metrics["valid_candidates"] += len(valid)

            if not valid:
                if batch >= max_batches:
                    if accumulated:
                        best = max(accumulated, key=accumulated.get)
                        return best, True
                    return "", True
                continue

            batch_votes = dict(Counter(valid))
            for resp, count in batch_votes.items():
                accumulated[resp] = accumulated.get(resp, 0) + count

            winner, needs_regen = self._check_consensus(accumulated, state.k_threshold)

            if winner:
                state.log_step(f"Voting({self.name})", f"Consensus in {batch} batch(es)")
                return winner, False

            if batch >= max_batches and accumulated:
                best = max(accumulated, key=accumulated.get)
                return best, True

        return "", True

    def _validate(self, responses: List[str], step: str) -> List[str]:
        valid = []
        for r in responses:
            if not r or len(r.strip()) < 2:
                continue
            if step == "sql":
                upper = r.upper()
                if any(kw in upper for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]):
                    continue
                if not upper.strip().startswith("SELECT"):
                    continue
            valid.append(r)
        return valid

    @staticmethod
    def _check_consensus(votes: Dict[str, int], k: int) -> Tuple[Optional[str], bool]:
        if not votes:
            return None, True
        sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_votes) == 1:
            if sorted_votes[0][1] >= k:
                return sorted_votes[0][0], False
            return None, True
        if sorted_votes[0][1] - sorted_votes[1][1] >= k:
            return sorted_votes[0][0], False
        return None, True


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_single_query(
    question: str,
    config: AgentConfig,
    temperatures: List[float],
    complexity_analyzer: ComplexityAnalyzer,
    retrieval_agent: RetrievalAgent,
) -> Dict[str, Any]:
    """Run a single query through the pipeline with instrumented voting."""

    state = MAKERState(user_question=question.strip())
    start = time.time()

    # 1. Complexity
    state = complexity_analyzer.analyze(state)

    # 2. Retrieval
    state = retrieval_agent.retrieve(state)

    # 3. Table selection (voting)
    ts_voting = InstrumentedVoting(config, temperatures, name="TableSelector")
    schema_ddl = state.schema_context.get("ddl", "")
    tables = state.schema_context.get("tables", [])
    ts_prompt = f"""Given the user question and database schema, identify the minimum set of tables needed to answer the question.

Question: {state.user_question}

Available tables: {', '.join(tables)}

Schema:
{schema_ddl}

Rules:
- Only include tables directly needed to answer the question
- Use exact table names from the schema
- Separate table names with commas
- No additional text or explanation
- Output ONLY the comma-separated table names

Output format: table1,table2,table3"""

    def ts_normalize(resp: str) -> str:
        names = sorted(set(t.strip().lower() for t in resp.split(",") if t.strip()))
        return ",".join(names)

    winner, _ = ts_voting.execute(ts_prompt, state, step="tables", normalizer=ts_normalize)
    state.step_outputs.table_selection = winner

    # 4. Join architecture (voting)
    ja_voting = InstrumentedVoting(config, temperatures, name="JoinArchitect")
    selected_tables = state.step_outputs.table_selection or ""

    if "," in selected_tables:
        ja_prompt = f"""Given the selected tables and schema, determine the JOIN clauses needed.

Question: {state.user_question}
Selected Tables: {selected_tables}

Schema:
{schema_ddl}

Rules:
- Use proper SQL JOIN syntax
- Reference only the selected tables
- Use column names from the schema
- If only one table, output "NO_JOINS"
- Output ONLY the JOIN clause(s), nothing else

Output format: JOIN clause string (e.g., "INNER JOIN order_items ON orders.id = order_items.order_id")"""

        join_winner, _ = ja_voting.execute(ja_prompt, state, step="joins")
        state.step_outputs.join_logic = join_winner
    else:
        state.step_outputs.join_logic = "NO_JOINS"

    # 5. SQL synthesis (voting)
    sql_voting = InstrumentedVoting(config, temperatures, name="SqlSynthesizer")
    joins = state.step_outputs.join_logic or ""
    business_rules = state.schema_context.get("business_rules", [])

    sql_prompt = f"""Generate a complete SQL query to answer the user's question.

Question: {state.user_question}
Selected Tables: {selected_tables}
Join Logic: {joins}

Schema:
{schema_ddl}

Business Rules:
{chr(10).join('- ' + r for r in business_rules)}

Rules:
- Generate a complete, executable SQLite-compatible SQL query
- Use only the selected tables and join logic
- Reference only columns from the schema
- Query must be read-only (SELECT only)
- No INSERT, UPDATE, DELETE, DROP, or ALTER statements
- Use SQLite date functions (e.g., date(), strftime()) not MySQL-specific ones
- Output ONLY the SQL query, no explanation or markdown

Output: Complete SQL SELECT statement"""

    def sql_normalize(resp: str) -> str:
        text = resp.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        return text

    sql_winner, _ = sql_voting.execute(sql_prompt, state, step="sql", normalizer=sql_normalize)
    state.step_outputs.final_sql = sql_winner

    # 6. Execute SQL
    executor = ExecutorAgent(config)
    state = executor.execute(state)

    elapsed_ms = int((time.time() - start) * 1000)

    sql_correct = state.step_outputs.execution_error is None
    result_count = len(state.query_results) if state.query_results else 0

    return {
        "question": question,
        "complexity_score": state.complexity_score,
        "k_threshold": state.k_threshold,
        "table_selection_rounds": ts_voting.metrics["rounds"],
        "join_rounds": ja_voting.metrics["rounds"],
        "sql_rounds": sql_voting.metrics["rounds"],
        "total_rounds": ts_voting.metrics["rounds"] + ja_voting.metrics["rounds"] + sql_voting.metrics["rounds"],
        "total_api_calls": (
            ts_voting.metrics["total_candidates"]
            + ja_voting.metrics["total_candidates"]
            + sql_voting.metrics["total_candidates"]
        ),
        "sql_correct": sql_correct,
        "result_count": result_count,
        "execution_error": state.step_outputs.execution_error,
        "final_sql": state.step_outputs.final_sql,
        "elapsed_ms": elapsed_ms,
    }


def run_benchmark():
    """Run the full benchmark across all configs and queries with multiple runs."""
    config = AgentConfig.from_env()
    complexity = ComplexityAnalyzer()
    retrieval = RetrievalAgent(config)

    # Structure: {config_name: {query: [run1_result, run2_result, ...]}}
    all_results = {}

    for config_name, temps in CONFIGS.items():
        logger.info("=" * 60)
        logger.info("CONFIG: %s  temps=%s", config_name, temps)
        logger.info("=" * 60)

        config_results = {}
        for q in TEST_QUERIES:
            config_results[q] = []
            for run_idx in range(RUNS_PER_COMBO):
                logger.info("--- [Run %d/%d] Query: %s", run_idx + 1, RUNS_PER_COMBO, q)
                try:
                    result = run_single_query(q, config, temps, complexity, retrieval)
                    config_results[q].append(result)
                    logger.info(
                        "  Rounds: TS=%d JA=%d SQL=%d | Total=%d | API calls=%d | Correct=%s | %dms",
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
                    config_results[q].append({
                        "question": q,
                        "total_rounds": -1,
                        "total_api_calls": -1,
                        "sql_correct": False,
                        "error": str(e),
                    })

        all_results[config_name] = config_results

    return all_results


def _stats(values: List[float]) -> Dict[str, float]:
    """Compute mean and std dev for a list of values."""
    import math
    n = len(values)
    if n == 0:
        return {"mean": 0, "std": 0, "min": 0, "max": 0, "n": 0}
    mean = sum(values) / n
    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)
    else:
        std = 0
    return {"mean": mean, "std": std, "min": min(values), "max": max(values), "n": n}


def _flatten_results(all_results: Dict[str, Dict[str, List[Dict]]]) -> Dict[str, List[Dict]]:
    """Flatten {config: {query: [runs]}} -> {config: [all_runs]}."""
    flat = {}
    for config_name, query_map in all_results.items():
        flat[config_name] = []
        for q, runs in query_map.items():
            flat[config_name].extend(runs)
    return flat


def print_summary(all_results: Dict[str, Dict[str, List[Dict]]]):
    """Print a summary table with mean +/- std across runs."""
    print("\n" + "=" * 120)
    print(f"TEMPERATURE BENCHMARK RESULTS  ({RUNS_PER_COMBO} runs per config/query)")
    print("=" * 120)

    # Per-query breakdown
    for i, q in enumerate(TEST_QUERIES):
        print(f"\n{'─' * 120}")
        print(f"Q{i+1}: {q}")
        print(f"{'─' * 120}")
        print(f"{'Config':<20} {'K':>3} {'Rounds (avg +/- std)':>22} {'API Calls (avg +/- std)':>25} {'Correct':>9} {'Time (avg +/- std)':>22}")
        print(f"{'─'*20} {'─'*3} {'─'*22} {'─'*25} {'─'*9} {'─'*22}")

        for config_name in CONFIGS:
            runs = all_results[config_name][q]
            valid = [r for r in runs if r.get("total_rounds", -1) >= 0]
            if not valid:
                print(f"{config_name:<20} {'ALL FAILED':>70}")
                continue

            k = valid[0].get("k_threshold", "?")
            rnd_s = _stats([r["total_rounds"] for r in valid])
            api_s = _stats([r["total_api_calls"] for r in valid])
            correct = sum(1 for r in valid if r["sql_correct"])
            time_s = _stats([r.get("elapsed_ms", 0) / 1000 for r in valid])

            print(
                f"{config_name:<20} {k:>3} "
                f"{rnd_s['mean']:>6.1f} +/- {rnd_s['std']:>4.1f} [{rnd_s['min']:.0f}-{rnd_s['max']:.0f}]  "
                f"{api_s['mean']:>7.1f} +/- {api_s['std']:>5.1f} [{api_s['min']:.0f}-{api_s['max']:.0f}]  "
                f"{correct}/{len(valid):>6} "
                f"{time_s['mean']:>6.1f}s +/- {time_s['std']:>4.1f}s"
            )

    # Aggregated summary
    print(f"\n{'=' * 120}")
    print("AGGREGATE SUMMARY (across all queries and runs)")
    print(f"{'=' * 120}")
    print(f"{'Config':<20} {'Avg Rounds':>14} {'Std Rounds':>12} {'Avg API':>10} {'Std API':>10} {'Correct %':>10} {'Avg Time':>10}")
    print(f"{'─'*20} {'─'*14} {'─'*12} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    flat = _flatten_results(all_results)
    for config_name in CONFIGS:
        valid = [r for r in flat[config_name] if r.get("total_rounds", -1) >= 0]
        if not valid:
            print(f"{config_name:<20} {'NO DATA':>60}")
            continue

        rnd_s = _stats([r["total_rounds"] for r in valid])
        api_s = _stats([r["total_api_calls"] for r in valid])
        correct_pct = sum(1 for r in valid if r["sql_correct"]) / len(valid) * 100
        time_s = _stats([r.get("elapsed_ms", 0) / 1000 for r in valid])

        print(
            f"{config_name:<20} {rnd_s['mean']:>14.2f} {rnd_s['std']:>12.2f} "
            f"{api_s['mean']:>10.1f} {api_s['std']:>10.1f} "
            f"{correct_pct:>9.1f}% {time_s['mean']:>8.1f}s"
        )


def save_results(all_results: Dict[str, Dict[str, List[Dict]]]):
    """Save raw results to JSON."""
    out_path = Path(__file__).resolve().parent / "benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nRaw results saved to: {out_path}")
    return out_path


def generate_chart(all_results: Dict[str, Dict[str, List[Dict]]]):
    """Generate comparison charts with error bars."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("\nmatplotlib not installed — skipping chart generation")
        return

    config_names = list(CONFIGS.keys())
    short_names = ["A: All 0.7", "B: 0.0+0.1s", "C: Graduated"]
    colors = ["#4285F4", "#EA4335", "#34A853"]
    query_labels = [f"Q{i+1}" for i in range(len(TEST_QUERIES))]
    n_queries = len(TEST_QUERIES)

    fig, axes = plt.subplots(2, 2, figsize=(20, 14))
    fig.suptitle(
        f"Temperature Configuration Benchmark ({RUNS_PER_COMBO} runs/combo, {n_queries} queries)",
        fontsize=16, fontweight="bold",
    )

    x = np.arange(n_queries)
    width = 0.25

    # --- Chart 1: Avg rounds per query with error bars ---
    ax = axes[0][0]
    for i, (cname, sname) in enumerate(zip(config_names, short_names)):
        means, stds = [], []
        for q in TEST_QUERIES:
            valid = [r for r in all_results[cname][q] if r.get("total_rounds", -1) >= 0]
            s = _stats([r["total_rounds"] for r in valid])
            means.append(s["mean"])
            stds.append(s["std"])
        ax.bar(x + i * width, means, width, yerr=stds, capsize=3,
               label=sname, color=colors[i], alpha=0.85)
    ax.set_ylabel("Total Voting Rounds")
    ax.set_title("Avg Rounds to Consensus per Query")
    ax.set_xticks(x + width)
    ax.set_xticklabels(query_labels, fontsize=8)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # --- Chart 2: Avg API calls per query with error bars ---
    ax = axes[0][1]
    for i, (cname, sname) in enumerate(zip(config_names, short_names)):
        means, stds = [], []
        for q in TEST_QUERIES:
            valid = [r for r in all_results[cname][q] if r.get("total_rounds", -1) >= 0]
            s = _stats([r["total_api_calls"] for r in valid])
            means.append(s["mean"])
            stds.append(s["std"])
        ax.bar(x + i * width, means, width, yerr=stds, capsize=3,
               label=sname, color=colors[i], alpha=0.85)
    ax.set_ylabel("Total API Calls")
    ax.set_title("Avg API Calls per Query")
    ax.set_xticks(x + width)
    ax.set_xticklabels(query_labels, fontsize=8)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # --- Chart 3: Aggregate box-style comparison ---
    ax = axes[1][0]
    flat = _flatten_results(all_results)
    agg_metrics = []
    for cname in config_names:
        valid = [r for r in flat[cname] if r.get("total_rounds", -1) >= 0]
        agg_metrics.append({
            "rounds": _stats([r["total_rounds"] for r in valid]),
            "api": _stats([r["total_api_calls"] for r in valid]),
            "correct": sum(1 for r in valid if r["sql_correct"]) / len(valid) * 100 if valid else 0,
        })

    metric_labels = ["Avg Rounds", "Avg API Calls", "Correct %"]
    x2 = np.arange(3)
    for i, (sname, agg) in enumerate(zip(short_names, agg_metrics)):
        vals = [agg["rounds"]["mean"], agg["api"]["mean"], agg["correct"]]
        errs = [agg["rounds"]["std"], agg["api"]["std"], 0]
        ax.bar(x2 + i * width, vals, width, yerr=errs, capsize=3,
               label=sname, color=colors[i], alpha=0.85)
    ax.set_title("Aggregate Metrics (mean +/- std)")
    ax.set_xticks(x2 + width)
    ax.set_xticklabels(metric_labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # --- Chart 4: Execution time with error bars ---
    ax = axes[1][1]
    for i, (cname, sname) in enumerate(zip(config_names, short_names)):
        means, stds = [], []
        for q in TEST_QUERIES:
            valid = [r for r in all_results[cname][q] if r.get("total_rounds", -1) >= 0]
            s = _stats([r.get("elapsed_ms", 0) / 1000 for r in valid])
            means.append(s["mean"])
            stds.append(s["std"])
        ax.bar(x + i * width, means, width, yerr=stds, capsize=3,
               label=sname, color=colors[i], alpha=0.85)
    ax.set_ylabel("Time (seconds)")
    ax.set_title("Avg Execution Time per Query")
    ax.set_xticks(x + width)
    ax.set_xticklabels(query_labels, fontsize=8)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # Query legend at bottom
    legend_text = "\n".join(f"Q{i+1}: {q}" for i, q in enumerate(TEST_QUERIES))
    fig.text(0.5, -0.02, legend_text, ha="center", fontsize=7, family="monospace",
             bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    plt.tight_layout(rect=[0, 0.06, 1, 0.96])
    chart_path = Path(__file__).resolve().parent / "benchmark_chart.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    print(f"\nChart saved to: {chart_path}")
    plt.close()


if __name__ == "__main__":
    results = run_benchmark()
    print_summary(results)
    save_results(results)
    generate_chart(results)
