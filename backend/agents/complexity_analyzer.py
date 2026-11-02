"""Complexity Analyzer - scores question complexity and sets adaptive K threshold.

The score is a deterministic heuristic (no LLM call). Each *kind* of SQL work a
question implies is counted once, so a simple "total X by Y" question isn't
scored as complex just because it uses several related words.
"""

import re
import logging
from typing import Set
from .state import MAKERState

logger = logging.getLogger(__name__)

# Business entities. Singular and plural forms map to one concept so
# "product" and "products" count once.
BUSINESS_ENTITIES = {
    "user": "user", "users": "user",
    "customer": "customer", "customers": "customer",
    "order": "order", "orders": "order",
    "product": "product", "products": "product",
    "category": "category", "categories": "category",
    "payment": "payment", "payments": "payment",
    "sale": "sale", "sales": "sale",
    "revenue": "revenue",
    "employee": "employee", "employees": "employee",
    "department": "department", "departments": "department",
}

# Each signal is scored at most once, however many of its words appear.
# Basic shaping (aggregate, group, rank) is cheap; harder SQL costs more.
BASIC_SIGNALS = {
    "aggregation": r"\b(total|sum|count|how many|number of|average|avg|mean|max|maximum|min|minimum)\b",
    "grouping": r"\b(by|per|each|for each|group by|breakdown)\b",
    "ranking": r"\b(top|bottom|highest|lowest|most|least|best|worst|rank|order by)\b",
}
HARD_SIGNALS = {
    "time_comparison": r"\b(year[- ]over[- ]year|yoy|month[- ]over[- ]month|growth|trend|compared? to|vs\.?|versus)\b",
    "ratio": r"\b(ratio|percent(age)?|share of|margin|rate)\b",
    "filter_on_aggregate": r"\b(having|more than \d+|at least \d+|fewer than \d+|above average|below average)\b",
    "window": r"\b(running total|cumulative|rolling|moving average|partition)\b",
    "set_logic": r"\b(never|without|not in|neither|both|union|distinct)\b",
    "date_math": r"\b(between|since|last \d+ (days|weeks|months|years)|in \d{4}|quarter|q[1-4])\b",
}

BASIC_WEIGHT = 0.1
HARD_WEIGHT = 0.2
ENTITY_WEIGHT = 0.1  # per entity beyond the first


class ComplexityAnalyzer:
    def analyze(self, state: MAKERState) -> MAKERState:
        question = state.user_question.lower()
        score = self._compute_score(question)
        k = self._k_threshold(score)

        state.complexity_score = score
        state.k_threshold = k

        label = "Simple" if k == 2 else "Medium" if k == 3 else "Complex"
        state.log_step("ComplexityAnalyzer", f"Score={score:.2f} ({label}) -> K={k}")
        logger.info("Complexity: score=%.2f, K=%d", score, k)
        return state

    # -- internals --

    def _compute_score(self, question: str) -> float:
        score = min(len(question) / 300.0, 0.2)
        score += max(0, self._count_entities(question) - 1) * ENTITY_WEIGHT
        score += sum(BASIC_WEIGHT for p in BASIC_SIGNALS.values() if re.search(p, question))
        score += sum(HARD_WEIGHT for p in HARD_SIGNALS.values() if re.search(p, question))
        return round(max(0.0, min(1.0, score)), 3)

    def _count_entities(self, question: str) -> int:
        found: Set[str] = set()
        for word, concept in BUSINESS_ENTITIES.items():
            if re.search(rf"\b{re.escape(word)}\b", question):
                found.add(concept)
        return len(found)

    @staticmethod
    def _k_threshold(score: float) -> int:
        if score < 0.3:
            return 2
        elif score < 0.7:
            return 3
        elif score < 0.85:
            return 4
        return 5
