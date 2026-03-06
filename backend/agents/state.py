"""State Object for the MAKER Framework pipeline.

A rigid JSON structure passed through the agent network holding trace_id,
user question, schema context, and intermediate results.
"""

from typing import List, Optional, Dict, Any, Callable
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr
from uuid import uuid4
import json


class StepOutputs(BaseModel):
    """Intermediate outputs from each agent step."""

    table_selection: Optional[str] = None
    join_logic: Optional[str] = None
    final_sql: Optional[str] = None
    execution_error: Optional[str] = None


class MAKERState(BaseModel):
    """The State Object that passes through the agent pipeline."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    user_question: str = Field(...)
    complexity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    k_threshold: int = Field(default=3, ge=2, le=5)
    schema_context: Dict[str, Any] = Field(default_factory=dict)
    step_outputs: StepOutputs = Field(default_factory=StepOutputs)
    query_results: Optional[List[Dict[str, Any]]] = None
    retry_count: int = Field(default=0, ge=0)
    execution_time_ms: int = Field(default=0, ge=0)
    agent_steps: List[Dict[str, Any]] = Field(default_factory=list)
    _on_step: Optional[Callable[[str, str], None]] = PrivateAttr(default=None)

    def log_step(self, agent: str, detail: str):
        """Record a pipeline step for the UI trace display."""
        self.agent_steps.append({"agent": agent, "detail": detail})
        if self._on_step:
            self._on_step(agent, detail)

    def to_json(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_json(cls, data: dict) -> "MAKERState":
        return cls.model_validate(data)
