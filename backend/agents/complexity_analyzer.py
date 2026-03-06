"""Complexity Analyzer - scores question complexity and sets adaptive K threshold."""

import re
import logging
from typing import Set
from .state import MAKERState

logger = logging.getLogger(__name__)

# SQL operations that indicate complexity
SQL_OPERATIONS = {
    "join", "group by", "having", "order by", "union",
    "subquery", "sum", "count", "avg", "max", "min",
    "distinct", "case when", "partition by",
}

# Business entities
BUSINESS_ENTITIES = {
    "user", "users", "customer", "customers", "order", "orders",
    "product", "products", "category", "categories",
    "payment", "payments", "sale", "sales", "revenue",
    "employee", "employees", "department", "departments",
}


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
        score = min(len(question) / 200.0, 0.3)
        score += self._count_entities(question) * 0.1
        score += self._count_operations(question) * 0.15
        return max(0.0, min(1.0, score))

    def _count_entities(self, question: str) -> int:
        found: Set[str] = set()
        for entity in BUSINESS_ENTITIES:
            if re.search(rf"\b{re.escape(entity)}\b", question):
                found.add(entity)
        return len(found)

    def _count_operations(self, question: str) -> int:
        count = 0
        for op in SQL_OPERATIONS:
            if op in question:
                count += 1
        if re.search(r"\b(top|first|last)\s+\d+", question):
            count += 1
        if re.search(r"\b(per|by|for each)\b", question):
            count += 1
        if re.search(r"\b(total|sum|average|mean)\b", question):
            count += 1
        return count

    @staticmethod
    def _k_threshold(score: float) -> int:
        if score < 0.3:
            return 2
        elif score < 0.7:
            return 3
        elif score < 0.85:
            return 4
        return 5
