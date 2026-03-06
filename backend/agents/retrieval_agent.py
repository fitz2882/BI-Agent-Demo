"""Retrieval Agent - uses Google File Search to retrieve schema context from the Knowledge Base.

The Retrieval Agent queries a Google File Search vector store containing the
Acme Analytics database documentation, and extracts structured schema context
(tables, columns, business rules, SQL patterns) for downstream agents.

Falls back to the local SchemaProvider if File Search is not configured.
"""

import os
import re
import json
import time
import logging
from typing import Dict, List, Optional, Any

from google import genai
from google.genai import types

from .state import MAKERState
from .config import AgentConfig

logger = logging.getLogger(__name__)


class RetrievalAgent:
    """Retrieves schema context using Google File Search (grounded RAG).

    Responsibilities:
    - Query Google File Search vector store for relevant schema and business rules
    - Extract structured context: tables, columns, business rules, SQL patterns
    - Populate schema_context in the MAKERState
    - Fall back to local SchemaProvider if File Search is unavailable
    """

    SYSTEM_INSTRUCTION = """You are a SQL Schema Extraction Assistant for the Acme Analytics database.

Return ONLY valid JSON that conforms to the provided schema.
Do not wrap the JSON in markdown. Do not add commentary.

Never invent table names, columns, business rules, or SQL patterns.
Only include information present in the provided context from the Knowledge Base.
"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.api_key = config.google_api_key

        # Google File Search store name
        self.corpus_name = os.getenv("GOOGLE_FILE_SEARCH_STORE")

        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-flash-latest"

        if self.corpus_name:
            logger.info("RetrievalAgent initialized with File Search store: %s", self.corpus_name)
        else:
            logger.warning(
                "GOOGLE_FILE_SEARCH_STORE not set. "
                "Retrieval agent will fall back to local schema provider."
            )

    def retrieve(self, state: MAKERState) -> MAKERState:
        """Retrieve schema context and populate the State Object.

        If Google File Search is configured, queries the vector store.
        Otherwise, falls back to the local schema provider.
        """
        trace_id = state.trace_id
        question = state.user_question

        if not self.corpus_name:
            return self._fallback_local(state)

        try:
            logger.info("[%s] Querying Google File Search for schema context", trace_id)
            start = time.time()

            raw_context = self._invoke_file_search(question, trace_id)
            duration_ms = int((time.time() - start) * 1000)
            logger.info("[%s] File Search completed in %dms", trace_id, duration_ms)

            if not raw_context:
                logger.warning("[%s] File Search returned empty context, using fallback", trace_id)
                return self._fallback_local(state)

            # Extract structured schema from the response
            schema_ctx = self._build_schema_context(raw_context)
            state.schema_context = schema_ctx

            table_count = len(schema_ctx.get("tables", []))
            rule_count = len(schema_ctx.get("business_rules", []))
            pattern_count = len(schema_ctx.get("sql_patterns", []))

            state.log_step(
                "RetrievalAgent",
                f"File Search: {table_count} tables, {rule_count} rules, "
                f"{pattern_count} patterns ({duration_ms}ms)",
            )
            return state

        except Exception as e:
            logger.error("[%s] File Search failed: %s — falling back to local", trace_id, e)
            state.log_step("RetrievalAgent", f"File Search error: {e} — using local fallback")
            return self._fallback_local(state)

    # -------------------------------------------------------------------
    # Google File Search
    # -------------------------------------------------------------------

    def _invoke_file_search(self, question: str, trace_id: str) -> Dict[str, Any]:
        """Call Google File Search and return parsed JSON context."""

        prompt = (
            "You are analyzing database schema documentation to help answer a SQL question.\n\n"
            f"Question: {question}\n\n"
            "Use ONLY information present in the retrieved documentation context (grounded via File Search).\n"
            "Do NOT invent table names, column names, or business rules.\n\n"
            "Return ONLY JSON with these keys:\n"
            '- "tables": list of table names relevant to the question\n'
            '- "columns": object mapping table name -> list of column names\n'
            '- "business_rules": list of relevant business rules as strings\n'
            '- "sql_patterns": list of relevant SQL query patterns as strings\n'
        )

        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                safety_settings=safety_settings,
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[self.corpus_name]
                        )
                    )
                ],
            ),
        )

        text = self._extract_text(response)
        if not text:
            return {}

        return self._parse_json(text, trace_id)

    # -------------------------------------------------------------------
    # Response parsing helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _extract_text(response) -> str:
        """Safely extract text from a response that may contain function_call parts."""
        try:
            if hasattr(response, "text") and response.text:
                return response.text
        except (AttributeError, ValueError):
            pass

        try:
            if hasattr(response, "candidates") and response.candidates:
                parts = response.candidates[0].content.parts
                texts = [p.text for p in parts if hasattr(p, "text") and p.text]
                if texts:
                    return "".join(texts)
        except (AttributeError, IndexError):
            pass

        return ""

    @staticmethod
    def _parse_json(text: str, trace_id: str) -> Dict[str, Any]:
        """Leniently parse JSON from LLM response text."""
        text = text.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:\w+)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON object from surrounding text
            match = re.search(r"(\{[\s\S]*\})", text)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            logger.warning("[%s] Could not parse File Search response as JSON", trace_id)
            return {}

    # -------------------------------------------------------------------
    # Schema context builder
    # -------------------------------------------------------------------

    def _build_schema_context(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw File Search JSON into the schema_context format."""
        tables = [t for t in (raw.get("tables") or []) if isinstance(t, str)]
        business_rules = [r for r in (raw.get("business_rules") or []) if isinstance(r, str)]
        sql_patterns = [p for p in (raw.get("sql_patterns") or []) if isinstance(p, str)]

        # Build table_columns from the "columns" field
        table_columns: Dict[str, List[Dict[str, str]]] = {}
        columns_data = raw.get("columns") or raw.get("table_columns") or {}

        if isinstance(columns_data, dict):
            # {"table": ["col1", "col2"]} or {"table": [{"name": "col1", "type": "TEXT"}]}
            for table_name, cols in columns_data.items():
                if not isinstance(cols, list):
                    continue
                cleaned = []
                for c in cols:
                    if isinstance(c, str):
                        cleaned.append({"name": c, "type": ""})
                    elif isinstance(c, dict) and "name" in c:
                        cleaned.append({"name": c["name"], "type": c.get("type", "")})
                if cleaned:
                    table_columns[table_name] = cleaned
        elif isinstance(columns_data, list):
            # [{"table_name": "x", "column_names": ["a", "b"]}]
            for item in columns_data:
                if not isinstance(item, dict):
                    continue
                tname = item.get("table_name")
                cnames = item.get("column_names", [])
                if isinstance(tname, str) and isinstance(cnames, list):
                    table_columns[tname] = [{"name": c, "type": ""} for c in cnames if isinstance(c, str)]

        # Build DDL from table_columns for downstream prompt injection
        ddl_lines = []
        for tname in tables:
            cols = table_columns.get(tname, [])
            if cols:
                col_defs = ", ".join(f'{c["name"]} {c["type"]}'.strip() for c in cols)
                ddl_lines.append(f"CREATE TABLE {tname} ({col_defs});")
            else:
                ddl_lines.append(f"-- Table: {tname} (columns not specified)")

        return {
            "tables": tables,
            "table_columns": table_columns,
            "business_rules": business_rules,
            "sql_patterns": sql_patterns,
            "ddl": "\n".join(ddl_lines),
        }

    # -------------------------------------------------------------------
    # Local fallback
    # -------------------------------------------------------------------

    def _fallback_local(self, state: MAKERState) -> MAKERState:
        """Use the hardcoded SchemaProvider as a fallback."""
        from .schema_provider import SchemaProvider

        provider = SchemaProvider()
        state = provider.retrieve(state)
        # Amend the step log to note it was a fallback
        if state.agent_steps and state.agent_steps[-1]["agent"] == "SchemaProvider":
            state.agent_steps[-1]["agent"] = "RetrievalAgent"
            state.agent_steps[-1]["detail"] = (
                "Local fallback: " + state.agent_steps[-1]["detail"]
            )
        return state
