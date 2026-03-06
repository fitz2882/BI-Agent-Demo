"""Executor Agent - executes SQL queries against the SQLite demo database."""

import logging
import re
import sqlite3
import time
from typing import List, Dict, Any, Optional, Tuple

from .state import MAKERState
from .config import AgentConfig

logger = logging.getLogger(__name__)


class ExecutorAgent:
    """Executes SQL against the SQLite demo database."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.db_path = config.db_path

    def execute(self, state: MAKERState) -> MAKERState:
        sql = (state.step_outputs.final_sql or "").strip()
        if not sql:
            state.step_outputs.execution_error = "No SQL query to execute"
            state.log_step("Executor", "Error: No SQL query")
            return state

        # Safety check: read-only
        if not self._is_read_only(sql):
            state.step_outputs.execution_error = "Only SELECT queries are allowed"
            state.log_step("Executor", "Rejected: non-SELECT query")
            return state

        try:
            start = time.time()
            results = self._run_query(sql)
            elapsed_ms = int((time.time() - start) * 1000)

            # Truncate large results
            if len(results) > 20:
                truncated = results[:5] + [{"_summary": f"... {len(results) - 10} rows omitted ...", "_total_rows": len(results)}] + results[-5:]
                results = truncated

            state.query_results = results
            state.execution_time_ms = elapsed_ms
            state.step_outputs.execution_error = None
            state.log_step("Executor", f"{len(results)} rows in {elapsed_ms}ms")
            logger.info("Query returned %d rows in %dms", len(results), elapsed_ms)

            # Zero-results retry for complex queries
            if len(results) == 0 and state.complexity_score >= 0.7 and state.retry_count < 2:
                state.step_outputs.execution_error = (
                    "Query returned zero results. Consider checking date ranges, "
                    "join conditions, or filter criteria."
                )
                state.retry_count += 1
                state.log_step("Executor", "Zero results on complex query, will retry")

            return state

        except Exception as e:
            error_msg = str(e)
            state.step_outputs.execution_error = error_msg
            state.query_results = []
            state.log_step("Executor", f"Error: {error_msg[:100]}")
            logger.error("Query execution failed: %s", error_msg)
            return state

    def _run_query(self, sql: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return rows
        finally:
            conn.close()

    @staticmethod
    def _is_read_only(sql: str) -> bool:
        upper = sql.upper().strip()
        if not upper.startswith("SELECT"):
            return False
        for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]:
            if re.search(rf"\b{kw}\b", upper):
                return False
        return True
