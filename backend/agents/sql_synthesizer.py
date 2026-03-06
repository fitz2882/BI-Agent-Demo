"""SQL Synthesizer - generates the final SQL query using voting consensus."""

import logging
from .state import MAKERState
from .config import AgentConfig
from .voting_subnetwork import VotingSubNetwork

logger = logging.getLogger(__name__)


class SqlSynthesizer:
    def __init__(self, config: AgentConfig):
        self.voting = VotingSubNetwork(config, name="SqlSynthesizer")

    def synthesize(self, state: MAKERState) -> MAKERState:
        schema_ddl = state.schema_context.get("ddl", "")
        tables = state.step_outputs.table_selection or ""
        joins = state.step_outputs.join_logic or ""

        error_feedback = ""
        if state.step_outputs.execution_error:
            error_feedback = f"""
IMPORTANT: A previous SQL attempt failed with this error:
{state.step_outputs.execution_error}
Please fix the issue and generate a corrected query.
"""

        prompt = f"""Generate a complete SQL query to answer the user's question.

Question: {state.user_question}
Selected Tables: {tables}
Join Logic: {joins}

Schema:
{schema_ddl}

Business Rules:
{chr(10).join('- ' + r for r in state.schema_context.get('business_rules', []))}
{error_feedback}
Rules:
- Generate a complete, executable SQLite-compatible SQL query
- Use only the selected tables and join logic
- Reference only columns from the schema
- Query must be read-only (SELECT only)
- No INSERT, UPDATE, DELETE, DROP, or ALTER statements
- Use SQLite date functions (e.g., date(), strftime()) not MySQL-specific ones
- Output ONLY the SQL query, no explanation or markdown

Output: Complete SQL SELECT statement"""

        def normalize(resp: str) -> str:
            # Strip markdown code fences if present
            text = resp.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines).strip()
            return text

        winner, low_conf = self.voting.execute(prompt, state, step="sql", normalizer=normalize)
        state.step_outputs.final_sql = winner
        state.log_step("SqlSynthesizer", f"Generated SQL: {winner[:100]}...")
        logger.info("SQL synthesized (low_confidence=%s)", low_conf)
        return state
