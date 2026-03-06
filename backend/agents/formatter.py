"""Formatter Agent - transforms query results into natural language."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from google import genai
from google.genai import types

from .state import MAKERState
from .config import AgentConfig

logger = logging.getLogger(__name__)


class FormatterAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = genai.Client(api_key=config.google_api_key)

    def format(self, state: MAKERState) -> str:
        if state.query_results is None:
            return "No query was executed."

        if len(state.query_results) == 0:
            return self._format_empty(state)

        if len(state.query_results) == 1 and len(state.query_results[0]) == 1:
            return self._format_single(state)

        return self._format_multi(state)

    def _format_empty(self, state: MAKERState) -> str:
        return (
            f"No results matched your query. "
            f"Try widening the date range or relaxing filters."
        )

    def _format_single(self, state: MAKERState) -> str:
        row = state.query_results[0]
        col = list(row.keys())[0]
        val = row[col]
        formatted = self._fmt_value(val)

        try:
            response = self.client.models.generate_content(
                model="gemini-flash-latest",
                contents=(
                    f"The SQL query for '{state.user_question}' returned: "
                    f"{col} = {formatted}. Write a 1-2 sentence natural language answer. "
                    f"Format numbers with commas. Prefix monetary values with $."
                ),
            )
            return (response.text or "").strip() or f"The {col} is {formatted}."
        except Exception:
            return f"The {col} is {formatted}."

    def _format_multi(self, state: MAKERState) -> str:
        results = state.query_results
        n = len(results)
        preview = self._table_preview(results[:10])

        try:
            response = self.client.models.generate_content(
                model="gemini-flash-latest",
                contents=(
                    f"The SQL query for '{state.user_question}' returned {n} rows:\n\n"
                    f"{preview}\n\n"
                    f"Write a 2-4 sentence natural language summary. "
                    f"Format numbers with commas. Prefix monetary values with $."
                ),
            )
            return (response.text or "").strip() or f"Found {n} rows of results."
        except Exception:
            return f"Found {n} rows of results."

    def _table_preview(self, rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return "(empty)"
        cols = list(rows[0].keys())
        lines = [" | ".join(cols)]
        lines.append("-" * len(lines[0]))
        for row in rows:
            lines.append(" | ".join(str(self._fmt_value(row.get(c))) for c in cols))
        return "\n".join(lines)

    @staticmethod
    def _fmt_value(val: Any) -> str:
        if val is None:
            return "NULL"
        if isinstance(val, float):
            if val.is_integer():
                return f"{int(val):,}"
            return f"{val:,.2f}"
        if isinstance(val, int):
            return f"{val:,}"
        return str(val)
