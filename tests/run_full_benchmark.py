"""Run full benchmark: all 3 configs x 8 queries x 3 runs = 72 tests.

Uses gemini-2.5-flash and File Search for all runs.
Results are saved incrementally so partial progress is preserved on interruption.
"""

import sys
import json
import logging
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

os.environ["DB_PATH"] = str(Path(__file__).resolve().parent.parent / "demo_data" / "demo.db")

from agents.config import AgentConfig
from agents.complexity_analyzer import ComplexityAnalyzer
from agents.retrieval_agent import RetrievalAgent
from temperature_benchmark import run_single_query, CONFIGS, TEST_QUERIES, _stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("full_benchmark")

RUNS_PER_COMBO = 3
OUT_PATH = Path(__file__).resolve().parent / "full_benchmark_results.json"


def load_existing():
    """Load partial results if they exist."""
    if OUT_PATH.exists():
        with open(OUT_PATH) as f:
            return json.load(f)
    return {}


def save_results(all_results):
    """Save results incrementally."""
    with open(OUT_PATH, "w") as f:
        json.dump(all_results, f, indent=2, default=str)


def count_existing(all_results, config_name, query):
    """Count how many runs already exist for a config/query combo."""
    config_data = all_results.get(config_name, {})
    return len(config_data.get(query, []))


def main():
    config = AgentConfig.from_env()
    complexity = ComplexityAnalyzer()
    retrieval = RetrievalAgent(config)

    all_results = load_existing()

    total = len(CONFIGS) * len(TEST_QUERIES) * RUNS_PER_COMBO
    done = sum(
        len(all_results.get(cn, {}).get(q, []))
        for cn in CONFIGS
        for q in TEST_QUERIES
    )
    logger.info("Total tests needed: %d, already completed: %d, remaining: %d", total, done, total - done)

    for config_name, temps in CONFIGS.items():
        if config_name not in all_results:
            all_results[config_name] = {}

        logger.info("=" * 70)
        logger.info("CONFIG: %s  temps=%s", config_name, temps)
        logger.info("=" * 70)

        for q in TEST_QUERIES:
            if q not in all_results[config_name]:
                all_results[config_name][q] = []

            existing = len(all_results[config_name][q])
            remaining = RUNS_PER_COMBO - existing

            if remaining <= 0:
                logger.info("  SKIP %s — already have %d runs", q[:50], existing)
                continue

            for run_idx in range(remaining):
                run_num = existing + run_idx + 1
                logger.info("--- [%s] [Run %d/%d] %s", config_name, run_num, RUNS_PER_COMBO, q)
                try:
                    result = run_single_query(q, config, temps, complexity, retrieval)
                    all_results[config_name][q].append(result)
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
                    all_results[config_name][q].append({
                        "question": q,
                        "total_rounds": -1,
                        "total_api_calls": -1,
                        "sql_correct": False,
                        "error": str(e),
                    })

                # Save after every run
                save_results(all_results)

                # Cool-down between runs to avoid rate limits
                time.sleep(2)

    # Print summary
    print_summary(all_results)
    logger.info("Results saved to: %s", OUT_PATH)


def print_summary(all_results):
    print("\n" + "=" * 120)
    print(f"FULL BENCHMARK RESULTS  ({RUNS_PER_COMBO} runs per config/query, {len(TEST_QUERIES)} queries)")
    print("=" * 120)

    for i, q in enumerate(TEST_QUERIES):
        print(f"\n{'─' * 120}")
        print(f"Q{i+1}: {q}")
        print(f"{'─' * 120}")
        print(f"{'Config':<20} {'K':>3} {'Rounds (avg +/- std)':>22} {'API Calls (avg +/- std)':>25} {'Correct':>9} {'Time (avg +/- std)':>22}")
        print(f"{'─'*20} {'─'*3} {'─'*22} {'─'*25} {'─'*9} {'─'*22}")

        for config_name in CONFIGS:
            runs = all_results.get(config_name, {}).get(q, [])
            valid = [r for r in runs if r.get("total_rounds", -1) >= 0]
            if not valid:
                print(f"{config_name:<20} {'NO DATA':>70}")
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

    # Aggregate
    print(f"\n{'=' * 120}")
    print("AGGREGATE SUMMARY")
    print(f"{'=' * 120}")
    print(f"{'Config':<20} {'Avg Rounds':>14} {'Std Rounds':>12} {'Avg API':>10} {'Std API':>10} {'Correct %':>10} {'Avg Time':>10}")
    print(f"{'─'*20} {'─'*14} {'─'*12} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    for config_name in CONFIGS:
        all_runs = []
        for q in TEST_QUERIES:
            all_runs.extend(all_results.get(config_name, {}).get(q, []))
        valid = [r for r in all_runs if r.get("total_rounds", -1) >= 0]
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


if __name__ == "__main__":
    main()
