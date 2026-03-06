"""Benchmark: Compare temperature strategies for the MAKER voting sub-network.

Tests 3 strategies across multiple queries, measuring:
- Rounds to consensus (or safety valve)
- Whether the SQL executes correctly
- Whether the SQL returns correct results
- Total API calls made

Usage:
    cd backend
    python ../scripts/benchmark_temperatures.py
"""

import os
import sys
import time
import json
import sqlite3
import logging
from typing import List, Dict, Optional, Callable, Any, Tuple
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from google import genai
from google.genai import types

# ── Setup ──────────────────────────────────────────────────────────────────

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

API_KEY = os.getenv("GOOGLE_API_KEY")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "demo_data", "demo.db")
MODEL = "gemini-flash-latest"
K = 2  # ahead-by-K threshold for benchmark (keep small for speed)
WORKERS_PER_BATCH = 5
MAX_BATCHES = 5

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("benchmark")

# ── Temperature Strategies ─────────────────────────────────────────────────

STRATEGIES = {
    "A: All 0.7": [0.7, 0.7, 0.7, 0.7, 0.7],
    "B: 0.0 + 4×0.1": [0.0, 0.1, 0.1, 0.1, 0.1],
    "C: Escalating": [0.0, 0.2, 0.3, 0.4, 0.5],
}

# ── Test Queries ───────────────────────────────────────────────────────────

SCHEMA_DDL = """CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, city TEXT, state TEXT, signup_date DATE, lifetime_value REAL);
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER, price REAL, cost REAL, stock_quantity INTEGER);
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, order_date DATE, status TEXT, total_amount REAL);
CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER, quantity INTEGER, unit_price REAL);
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department_id INTEGER, hire_date DATE, salary REAL);
CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT);"""

BUSINESS_RULES = [
    "orders.status can be: 'pending', 'shipped', 'delivered', 'cancelled'",
    "Exclude cancelled orders from revenue calculations",
    "products.price is retail price; products.cost is wholesale cost",
    "customers.lifetime_value is total amount spent",
]

TEST_QUERIES = [
    {
        "question": "How many customers are there?",
        "expected_check": lambda rows: len(rows) == 1 and rows[0].get("count", rows[0].get(list(rows[0].keys())[0])) == 50,
        "difficulty": "simple",
    },
    {
        "question": "What is the total revenue excluding cancelled orders?",
        "expected_check": lambda rows: len(rows) == 1 and any(isinstance(v, (int, float)) and v > 0 for v in rows[0].values()),
        "difficulty": "simple",
    },
    {
        "question": "How many orders are in each status?",
        "expected_check": lambda rows: len(rows) >= 3,
        "difficulty": "medium",
    },
    {
        "question": "What are the top 5 customers by lifetime value?",
        "expected_check": lambda rows: len(rows) == 5,
        "difficulty": "simple",
    },
    {
        "question": "Show total revenue by product category, excluding cancelled orders",
        "expected_check": lambda rows: len(rows) >= 4,
        "difficulty": "medium",
    },
    {
        "question": "What is the average salary by department?",
        "expected_check": lambda rows: len(rows) >= 3,
        "difficulty": "medium",
    },
]


# ── Voting Engine (parameterized by temperature list) ──────────────────────

def build_sql_prompt(question: str) -> str:
    rules_str = "\n".join(f"- {r}" for r in BUSINESS_RULES)
    return f"""Generate a complete SQL query to answer the user's question.

Question: {question}

Schema:
{SCHEMA_DDL}

Business Rules:
{rules_str}

Rules:
- Generate a complete, executable SQLite-compatible SQL query
- Reference only columns from the schema
- Query must be read-only (SELECT only)
- Use SQLite date functions (e.g., date(), strftime()) not MySQL-specific ones
- Output ONLY the SQL query, no explanation or markdown

Output: Complete SQL SELECT statement"""


def normalize_sql(resp: str) -> str:
    text = resp.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def generate_batch(prompt: str, temperatures: List[float]) -> List[str]:
    """Run workers in parallel with specified temperatures."""
    responses = []

    def call_worker(idx: int, temp: float) -> Optional[str]:
        client = genai.Client(api_key=API_KEY)
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temp),
            )
            return (resp.text or "").strip()
        except Exception as e:
            return None

    with ThreadPoolExecutor(max_workers=len(temperatures)) as executor:
        futures = {executor.submit(call_worker, i, t): i for i, t in enumerate(temperatures)}
        for future in as_completed(futures):
            result = future.result()
            if result:
                normalized = normalize_sql(result)
                upper = normalized.upper().strip()
                if upper.startswith("SELECT"):
                    responses.append(normalized)

    return responses


def run_voting(prompt: str, temperatures: List[float], k: int) -> Dict[str, Any]:
    """Run ahead-by-K voting and return metrics."""
    accumulated: Dict[str, int] = {}
    total_api_calls = 0

    for batch_num in range(1, MAX_BATCHES + 1):
        responses = generate_batch(prompt, temperatures)
        total_api_calls += len(temperatures)

        batch_votes = dict(Counter(responses))
        for resp, count in batch_votes.items():
            accumulated[resp] = accumulated.get(resp, 0) + count

        # Check consensus
        if accumulated:
            sorted_votes = sorted(accumulated.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_votes) == 1 and sorted_votes[0][1] >= k:
                return {
                    "winner": sorted_votes[0][0],
                    "rounds": batch_num,
                    "total_votes": sum(accumulated.values()),
                    "total_api_calls": total_api_calls,
                    "consensus": True,
                    "unique_candidates": len(accumulated),
                }
            elif len(sorted_votes) >= 2:
                if sorted_votes[0][1] - sorted_votes[1][1] >= k:
                    return {
                        "winner": sorted_votes[0][0],
                        "rounds": batch_num,
                        "total_votes": sum(accumulated.values()),
                        "total_api_calls": total_api_calls,
                        "consensus": True,
                        "unique_candidates": len(accumulated),
                    }

    # Safety valve
    if accumulated:
        best = max(accumulated, key=accumulated.get)
        return {
            "winner": best,
            "rounds": MAX_BATCHES,
            "total_votes": sum(accumulated.values()),
            "total_api_calls": total_api_calls,
            "consensus": False,
            "unique_candidates": len(accumulated),
        }

    return {
        "winner": None,
        "rounds": MAX_BATCHES,
        "total_votes": 0,
        "total_api_calls": total_api_calls,
        "consensus": False,
        "unique_candidates": 0,
    }


def execute_sql(sql: str) -> Tuple[bool, List[Dict], str]:
    """Execute SQL and return (success, rows, error)."""
    if not sql:
        return False, [], "No SQL"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return True, rows, ""
    except Exception as e:
        return False, [], str(e)


# ── Main Benchmark ─────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        print("ERROR: GOOGLE_API_KEY not set")
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Demo database not found at {DB_PATH}")
        print("Run: python demo_data/seed.py")
        sys.exit(1)

    print("=" * 80)
    print("MAKER Voting Temperature Benchmark")
    print(f"K={K}, Workers/batch={WORKERS_PER_BATCH}, Max batches={MAX_BATCHES}")
    print(f"Queries: {len(TEST_QUERIES)}")
    print("=" * 80)

    all_results = {}

    for strategy_name, temps in STRATEGIES.items():
        print(f"\n{'─' * 80}")
        print(f"Strategy: {strategy_name}")
        print(f"Temperatures: {temps}")
        print(f"{'─' * 80}")

        strategy_results = []

        for qi, tq in enumerate(TEST_QUERIES):
            question = tq["question"]
            check_fn = tq["expected_check"]
            difficulty = tq["difficulty"]

            print(f"\n  Q{qi+1} [{difficulty}]: {question}")

            prompt = build_sql_prompt(question)
            start = time.time()
            vote_result = run_voting(prompt, temps, K)
            elapsed = time.time() - start

            sql = vote_result["winner"]
            rounds = vote_result["rounds"]
            consensus = vote_result["consensus"]
            unique = vote_result["unique_candidates"]
            api_calls = vote_result["total_api_calls"]

            # Execute the SQL
            if sql:
                success, rows, error = execute_sql(sql)
                correct = success and check_fn(rows) if success else False
            else:
                success, rows, error = False, [], "No winner"
                correct = False

            result = {
                "question": question,
                "difficulty": difficulty,
                "rounds": rounds,
                "consensus": consensus,
                "correct": correct,
                "executes": success,
                "unique_candidates": unique,
                "api_calls": api_calls,
                "elapsed_s": round(elapsed, 1),
                "sql": (sql or "")[:120],
                "error": error[:80] if error else "",
            }
            strategy_results.append(result)

            status = "CORRECT" if correct else ("EXECUTES" if success else "FAILED")
            consensus_str = f"consensus R{rounds}" if consensus else f"safety-valve R{rounds}"
            print(f"    → {status} | {consensus_str} | {unique} unique | {api_calls} calls | {result['elapsed_s']}s")
            if not success and error:
                print(f"    → Error: {error[:80]}")

        all_results[strategy_name] = strategy_results

    # ── Summary Table ──────────────────────────────────────────────────────

    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Header
    print(f"\n{'Query':<55} ", end="")
    for sname in STRATEGIES:
        label = sname.split(":")[0].strip()
        print(f"| {label:^22} ", end="")
    print()
    print(f"{'─'*55} ", end="")
    for _ in STRATEGIES:
        print(f"| {'─'*22} ", end="")
    print()

    # Per-query rows
    for qi in range(len(TEST_QUERIES)):
        q = TEST_QUERIES[qi]["question"][:52]
        print(f"{q:<55} ", end="")
        for sname in STRATEGIES:
            r = all_results[sname][qi]
            status = "OK" if r["correct"] else ("EX" if r["executes"] else "FL")
            c = "C" if r["consensus"] else "S"
            print(f"| {status} R{r['rounds']} {r['unique_candidates']}u {r['api_calls']}api {c:>1} ", end="")
        print()

    # Aggregate stats
    print(f"\n{'─'*55} ", end="")
    for _ in STRATEGIES:
        print(f"| {'─'*22} ", end="")
    print()

    print(f"{'TOTALS':<55} ", end="")
    for sname in STRATEGIES:
        results = all_results[sname]
        correct = sum(1 for r in results if r["correct"])
        executes = sum(1 for r in results if r["executes"])
        consensus = sum(1 for r in results if r["consensus"])
        avg_rounds = sum(r["rounds"] for r in results) / len(results)
        total_api = sum(r["api_calls"] for r in results)
        total_time = sum(r["elapsed_s"] for r in results)
        label = sname.split(":")[0].strip()
        print(f"| {correct}/{len(results)} correct        ", end="")
    print()

    print(f"{'':<55} ", end="")
    for sname in STRATEGIES:
        results = all_results[sname]
        consensus = sum(1 for r in results if r["consensus"])
        print(f"| {consensus}/{len(results)} consensus      ", end="")
    print()

    print(f"{'':<55} ", end="")
    for sname in STRATEGIES:
        results = all_results[sname]
        avg_rounds = sum(r["rounds"] for r in results) / len(results)
        print(f"| avg {avg_rounds:.1f} rounds      ", end="")
    print()

    print(f"{'':<55} ", end="")
    for sname in STRATEGIES:
        results = all_results[sname]
        avg_unique = sum(r["unique_candidates"] for r in results) / len(results)
        print(f"| avg {avg_unique:.1f} unique      ", end="")
    print()

    print(f"{'':<55} ", end="")
    for sname in STRATEGIES:
        results = all_results[sname]
        total_api = sum(r["api_calls"] for r in results)
        print(f"| {total_api:>3} total API calls ", end="")
    print()

    print(f"{'':<55} ", end="")
    for sname in STRATEGIES:
        results = all_results[sname]
        total_time = sum(r["elapsed_s"] for r in results)
        print(f"| {total_time:>5.1f}s total time   ", end="")
    print()

    # ── Save JSON for charting ─────────────────────────────────────────────

    output_path = os.path.join(os.path.dirname(__file__), "..", "benchmark_results.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nRaw results saved to: {output_path}")

    # ── Legend ──────────────────────────────────────────────────────────────
    print("\nLegend: OK=correct results, EX=executes but wrong, FL=failed")
    print("        C=consensus reached, S=safety valve (max batches)")
    print(f"        R=rounds, u=unique candidates, api=API calls")


if __name__ == "__main__":
    main()
