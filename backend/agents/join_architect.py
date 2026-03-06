"""Join Architect - determines JOIN clauses using voting consensus."""

import logging
from .state import MAKERState
from .config import AgentConfig
from .voting_subnetwork import VotingSubNetwork

logger = logging.getLogger(__name__)


class JoinArchitect:
    def __init__(self, config: AgentConfig):
        self.voting = VotingSubNetwork(config, name="JoinArchitect")

    def determine_joins(self, state: MAKERState) -> MAKERState:
        schema_ddl = state.schema_context.get("ddl", "")
        tables = state.step_outputs.table_selection or ""

        # Single table = no joins needed
        if "," not in tables:
            state.step_outputs.join_logic = "NO_JOINS"
            state.log_step("JoinArchitect", "Single table, no joins needed")
            return state

        prompt = f"""Given the selected tables and schema, determine the JOIN clauses needed.

Question: {state.user_question}
Selected Tables: {tables}

Schema:
{schema_ddl}

Rules:
- Use proper SQL JOIN syntax
- Reference only the selected tables
- Use column names from the schema
- If only one table, output "NO_JOINS"
- Output ONLY the JOIN clause(s), nothing else

Output format: JOIN clause string (e.g., "INNER JOIN order_items ON orders.id = order_items.order_id")"""

        winner, low_conf = self.voting.execute(prompt, state, step="joins")
        state.step_outputs.join_logic = winner
        state.log_step("JoinArchitect", f"Join logic: {winner[:80]}...")
        logger.info("Join logic determined (low_confidence=%s)", low_conf)
        return state
