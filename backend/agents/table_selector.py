"""Table Selector - identifies which tables are needed using voting consensus."""

import logging
from .state import MAKERState
from .config import AgentConfig
from .voting_subnetwork import VotingSubNetwork

logger = logging.getLogger(__name__)


class TableSelector:
    def __init__(self, config: AgentConfig):
        self.voting = VotingSubNetwork(config, name="TableSelector")

    def select(self, state: MAKERState) -> MAKERState:
        schema_ddl = state.schema_context.get("ddl", "")
        tables = state.schema_context.get("tables", [])

        prompt = f"""Given the user question and database schema, identify the minimum set of tables needed to answer the question.

Question: {state.user_question}

Available tables: {', '.join(tables)}

Schema:
{schema_ddl}

Rules:
- Only include tables directly needed to answer the question
- Use exact table names from the schema
- Separate table names with commas
- No additional text or explanation
- Output ONLY the comma-separated table names

Output format: table1,table2,table3"""

        def normalize(resp: str) -> str:
            # Normalize table names: lowercase, strip, sort
            names = sorted(set(t.strip().lower() for t in resp.split(",") if t.strip()))
            return ",".join(names)

        winner, low_conf = self.voting.execute(prompt, state, step="tables", normalizer=normalize)
        state.step_outputs.table_selection = winner
        state.log_step("TableSelector", f"Selected tables: {winner}")
        logger.info("Table selection: %s (low_confidence=%s)", winner, low_conf)
        return state
