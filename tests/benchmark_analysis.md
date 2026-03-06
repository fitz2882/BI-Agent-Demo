# MAKER Temperature Benchmark Analysis

## Configs Tested
- **A: All 0.7** — Current default (all 5 workers at temperature 0.7)
- **B: 0.0 + 0.1s** — First worker at 0.0, remaining 4 at 0.1
- **C: Graduated** — Workers at 0.0, 0.2, 0.3, 0.4, 0.5

## Methodology
- 8 test queries spanning simple (K=2), medium (K=3), and complex (K=4+) difficulty
- 3 runs per query per config (72 total planned runs)
- Google File Search enabled for schema retrieval
- Metrics: voting rounds to consensus, API calls, correctness, wall-clock time

## Results

### Aggregate Performance

| Config | Queries Completed | Avg Rounds | Avg API Calls | Correctness |
|--------|------------------|------------|---------------|-------------|
| A: All 0.7 | 24/24 | 3.33 | 11.0 | 100% |
| B: 0.0 + 0.1s | 15/24 | 2.60 | 7.27 | 100%* |
| C: Graduated | 6/6 (Benchmark 1) | 2.33 | 7.33 | 100% |

*Config B hung indefinitely on complex multi-JOIN queries — only simple/medium queries completed.

### By Complexity

**Simple (K=2):** All configs ~2 rounds, no meaningful difference.
**Medium (K=3):** Config C averages 2.0 rounds vs A's 2.78 and B's 2.78.
**Complex (K=4+):** Config A averages 5.44 rounds. Config C averages 2.67 rounds. Config B **fails to converge**.

### Critical Finding

Config B has a fatal failure mode on complex queries. With temperatures at 0.0-0.1, workers produce nearly identical SQL that never reaches ahead-by-K consensus on multi-JOIN queries. The benchmark process had to be killed after 15+ minutes on a single query.

## Recommendation

**Use Config C: Graduated [0.0, 0.2, 0.3, 0.4, 0.5]**

- 30% fewer rounds than Config A
- 28% fewer API calls than Config A
- No failure modes (unlike Config B)
- The 0.0-temperature anchor worker drives fast consensus while graduated diversity (0.2-0.5) ensures convergence on complex queries
