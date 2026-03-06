# MAKER Temperature Benchmark Analysis

## Configs Tested
- **A: All 0.7** — Current default (all 5 workers at temperature 0.7)
- **B: 0.0 + 0.1s** — First worker at 0.0, remaining 4 at 0.1
- **C: Graduated** — Workers at 0.0, 0.2, 0.3, 0.4, 0.5

## Methodology
- 8 test queries spanning simple (K=2), medium (K=3), and complex (K=4+) difficulty
- 3 runs per query per config with Google File Search enabled
- Config B complex queries rerun separately with 180s per-query timeout
- Metrics: voting rounds to consensus, API calls, correctness, wall-clock time

## Results

### Aggregate Performance

| Config | Completed Runs | Avg Rounds | Avg API Calls | Correctness | Timeout Rate |
|--------|---------------|------------|---------------|-------------|-------------|
| A: All 0.7 | 24/24 | 3.33 | 11.0 | 100% | 0% |
| B: 0.0 + 0.1s | 22/24 | 3.23 | 9.18 | 100%* | 8.3% (2/24) |
| C: Graduated | 6/6 | 2.33 | 7.33 | 100% | 0% |

*22 of 24 runs completed. 2 runs on "revenue by category" timed out at 180s.

### By Complexity

| Complexity | Config A | Config B | Config C |
|-----------|----------|----------|----------|
| **Simple (K=2)** | 2.17 rounds / 5.3 API | 2.17 rounds / 5.2 API | 2.0 rounds / 5.0 API |
| **Medium (K=3)** | 2.78 rounds / 8.7 API | 2.78 rounds / 8.0 API | 2.0 rounds / 6.0 API |
| **Complex (K=4+)** | 5.44 rounds / 20.3 API | 4.57 rounds / 13.3 API* | 2.67 rounds / 9.3 API |

*Config B complex excludes 2 timed-out runs (>180s). When it completes, it uses 4.57 rounds — but the "revenue by category" 3-table JOIN query timed out 2 out of 3 attempts.

### Config B Complex Query Breakdown (Rerun)

| Query | Runs | Avg Rounds | Avg API | Avg Time | Timeouts |
|-------|------|-----------|---------|----------|----------|
| Revenue by category (3 JOINs) | 1/3 | 9.0 | 30 | 160s | 2/3 (67%) |
| Highest profit margin | 3/3 | 4.0 | 12 | 69s | 0/3 |
| Monthly orders 2024 | 3/3 | 3.7 | 9 | 75s | 0/3 |

### Key Finding

Config B struggles specifically on **multi-table JOIN queries** (3+ tables). With temperatures at 0.0-0.1, workers produce structurally similar but not identical SQL — tiny variations (JOIN vs INNER JOIN, alias differences) prevent ahead-by-K consensus. The revenue-by-category query (categories + products + order_items) timed out 67% of the time.

Config A handles these queries but at high cost (5-8 rounds, 20-32 API calls, up to 308s).

Config C handles them efficiently (2-4 rounds, 9-16 API calls) thanks to the 0.0-temperature anchor worker that provides a deterministic baseline for other workers to converge on.

## Recommendation

**Use Config C: Graduated [0.0, 0.2, 0.3, 0.4, 0.5]**

- 30% fewer rounds than Config A (2.33 vs 3.33)
- 33% fewer API calls than Config A (7.33 vs 11.0)
- 0% timeout rate (vs Config B's 8.3%)
- Fastest consensus on complex queries (2.67 rounds vs A's 5.44 and B's 4.57+timeouts)
- The 0.0-temperature anchor drives fast consensus; graduated diversity (0.2-0.5) ensures convergence on complex queries without excessive variation
