"""Visualization Agent - generates Recharts-compatible chart specifications."""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from .state import MAKERState

logger = logging.getLogger(__name__)


class VisualizationAgent:
    """Analyzes query results and recommends chart type + generates spec."""

    def generate(self, state: MAKERState) -> Optional[Dict[str, Any]]:
        results = state.query_results
        if not results or len(results) < 2:
            return None

        columns = list(results[0].keys())
        # Filter out summary rows
        columns = [c for c in columns if not c.startswith("_")]

        time_cols = self._find_time_columns(columns, results)
        numeric_cols = self._find_numeric_columns(columns, results)
        categorical_cols = [c for c in columns if c not in time_cols and c not in numeric_cols and not c.startswith("_")]

        spec = self._select_chart(time_cols, numeric_cols, categorical_cols, results)
        if spec:
            spec["data"] = self._clean_data(results)
            state.log_step("Visualization", f"{spec['type'].title()} chart: X={spec['xKey']}, Y={spec['yKey']}")
        return spec

    def _select_chart(self, time_cols, numeric_cols, categorical_cols, results):
        # Time-series -> line
        if time_cols and numeric_cols:
            return {"type": "line", "xKey": time_cols[0], "yKey": numeric_cols[0], "title": "Trend"}

        # Two numerics -> scatter
        if len(numeric_cols) == 2 and not categorical_cols:
            return {"type": "scatter", "xKey": numeric_cols[0], "yKey": numeric_cols[1], "title": "Scatter"}

        # Categorical + numeric
        if categorical_cols and numeric_cols:
            if self._is_proportional(results, numeric_cols[0]):
                return {"type": "pie", "xKey": categorical_cols[0], "yKey": numeric_cols[0], "title": "Distribution"}
            return {"type": "bar", "xKey": categorical_cols[0], "yKey": numeric_cols[0], "title": "Comparison"}

        return None

    def _find_time_columns(self, columns, results):
        time_keywords = ["date", "time", "timestamp", "year", "month", "day"]
        found = []
        for col in columns:
            if any(kw in col.lower() for kw in time_keywords):
                found.append(col)
                continue
            for row in results[:3]:
                val = row.get(col)
                if isinstance(val, str) and re.search(r"\d{4}[-/]\d{1,2}", val):
                    found.append(col)
                    break
        return found

    def _find_numeric_columns(self, columns, results):
        found = []
        for col in columns:
            for row in results[:3]:
                val = row.get(col)
                if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
                    found.append(col)
                    break
        return found

    def _is_proportional(self, results, col):
        try:
            total = sum(float(r.get(col, 0)) for r in results)
            return 95 <= total <= 105
        except (ValueError, TypeError):
            return False

    def _clean_data(self, results):
        """Remove internal summary rows."""
        return [r for r in results if not any(k.startswith("_") for k in r)]
