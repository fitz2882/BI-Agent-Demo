"""Pipeline Orchestrator - runs the full MAKER agent pipeline.

Flow:
  Entry -> ComplexityAnalyzer -> RetrievalAgent (File Search / local fallback)
  -> TableSelector (voting) -> JoinArchitect (voting) -> SqlSynthesizer (voting)
  -> Executor -> Formatter + Visualization
"""

import logging
import time
from typing import Dict, Any, Optional

from .config import AgentConfig
from .state import MAKERState
from .complexity_analyzer import ComplexityAnalyzer
from .retrieval_agent import RetrievalAgent
from .table_selector import TableSelector
from .join_architect import JoinArchitect
from .sql_synthesizer import SqlSynthesizer
from .executor import ExecutorAgent
from .formatter import FormatterAgent
from .visualization import VisualizationAgent

logger = logging.getLogger(__name__)

MAX_SQL_RETRIES = 2


class Pipeline:
    """Orchestrates the full MAKER agent pipeline."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig.from_env()
        self.complexity = ComplexityAnalyzer()
        self.retrieval = RetrievalAgent(self.config)
        self.table_selector = TableSelector(self.config)
        self.join_architect = JoinArchitect(self.config)
        self.sql_synth = SqlSynthesizer(self.config)
        self.executor = ExecutorAgent(self.config)
        self.formatter = FormatterAgent(self.config)
        self.viz = VisualizationAgent()

    def run(self, question: str) -> Dict[str, Any]:
        """Run the full pipeline and return the response."""
        start = time.time()

        # 1. Initialize state
        state = MAKERState(user_question=question.strip())
        state.log_step("EntryAgent", f"Received question (trace_id={state.trace_id})")
        logger.info("Pipeline started: trace_id=%s", state.trace_id)

        # 2. Complexity analysis
        state = self.complexity.analyze(state)

        # 3. Schema retrieval (File Search or local fallback)
        state = self.retrieval.retrieve(state)

        # 4. Table selection (voting)
        state = self.table_selector.select(state)

        # 5. Join architecture (voting)
        state = self.join_architect.determine_joins(state)

        # 6-7. SQL synthesis + execution (with retry loop)
        for attempt in range(MAX_SQL_RETRIES + 1):
            state = self.sql_synth.synthesize(state)
            state = self.executor.execute(state)

            if not state.step_outputs.execution_error:
                break
            if attempt < MAX_SQL_RETRIES:
                logger.info("SQL retry %d: %s", attempt + 1, state.step_outputs.execution_error)
                state.log_step("Pipeline", f"SQL retry {attempt + 1}")

        # 8. Format results
        answer = self.formatter.format(state)

        # 9. Visualization
        chart_spec = self.viz.generate(state)

        elapsed_ms = int((time.time() - start) * 1000)
        state.execution_time_ms = elapsed_ms
        state.log_step("Pipeline", f"Complete in {elapsed_ms}ms")

        return {
            "trace_id": state.trace_id,
            "answer": answer,
            "sql": state.step_outputs.final_sql,
            "results": state.query_results or [],
            "chart": chart_spec,
            "steps": state.agent_steps,
            "execution_time_ms": elapsed_ms,
            "complexity": {
                "score": state.complexity_score,
                "k_threshold": state.k_threshold,
            },
        }
