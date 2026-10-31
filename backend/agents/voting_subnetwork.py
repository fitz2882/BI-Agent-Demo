"""Voting Sub-Network - the core MAKER consensus pattern.

Implements: Workers -> Validator -> VoteTally -> Consensus (ahead-by-K).

This pattern is reused by TableSelector, JoinArchitect, and SqlSynthesizer
to achieve consensus through parallel generation and ahead-by-K voting.
"""

import logging
import re
from typing import List, Dict, Optional, Callable
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from google import genai
from google.genai import types

from .state import MAKERState
from .config import AgentConfig

logger = logging.getLogger(__name__)

# Write/DDL keywords that must never appear in a generated query.
# Matched as whole words so column names like `updated_at` or `is_deleted` pass.
WRITE_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
_WRITE_RE = re.compile(r"\b(" + "|".join(WRITE_KEYWORDS) + r")\b")


class VotingError(RuntimeError):
    """Raised when a voting step cannot produce any valid candidate."""


class WorkerPool:
    """Spawns parallel workers using Gemini Flash with graduated temperatures."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.worker_count = config.worker_batch_size
        self.temperatures = config.worker_temperatures
        self.client = genai.Client(api_key=config.google_api_key)

    def generate_batch(
        self, prompt: str, state: MAKERState, batch_size: Optional[int] = None
    ) -> List[str]:
        count = batch_size or self.worker_count
        responses: List[str] = []

        def _run_one(idx: int) -> str:
            temp = self.temperatures[idx % len(self.temperatures)]
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temp),
            )
            return (response.text or "").strip()

        with ThreadPoolExecutor(max_workers=count) as executor:
            futures = {executor.submit(_run_one, i): i for i in range(count)}
            for future in as_completed(futures):
                try:
                    text = future.result()
                    if text:
                        responses.append(text)
                except Exception as e:
                    logger.warning("Worker %d failed: %s", futures[future], e)

        logger.info("Generated %d/%d responses (trace=%s)", len(responses), count, state.trace_id)
        return responses


class ValidatorAgent:
    """Filters out invalid responses before voting."""

    def validate_batch(self, responses: List[str], state: MAKERState, step: str) -> List[str]:
        valid = []
        for r in responses:
            if not r or len(r.strip()) < 2:
                continue
            # Basic SQL injection guard for sql step
            if step == "sql":
                upper = r.upper()
                if _WRITE_RE.search(upper):
                    logger.warning("Rejected write operation in SQL response")
                    continue
                if not upper.strip().startswith("SELECT"):
                    continue
            valid.append(r)
        logger.info("Validation: %d/%d valid for step=%s", len(valid), len(responses), step)
        return valid


class VoteTallyAgent:
    """Counts votes for each unique response."""

    def tally(self, responses: List[str]) -> Dict[str, int]:
        return dict(Counter(responses))


class ConsensusAgent:
    """Applies ahead-by-K logic to select a winner."""

    def check(self, votes: Dict[str, int], k: int) -> tuple[Optional[str], bool]:
        """Returns (winner_or_None, needs_regeneration)."""
        if not votes:
            return None, True

        sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)

        # Single candidate with >= K votes
        if len(sorted_votes) == 1:
            if sorted_votes[0][1] >= k:
                return sorted_votes[0][0], False
            return None, True

        leader_votes = sorted_votes[0][1]
        second_votes = sorted_votes[1][1]

        if leader_votes - second_votes >= k:
            return sorted_votes[0][0], False

        return None, True


class VotingSubNetwork:
    """Complete voting sub-network: Workers -> Validator -> VoteTally -> Consensus."""

    def __init__(self, config: AgentConfig, name: str = "voting"):
        self.config = config
        self.name = name
        self.workers = WorkerPool(config)
        self.validator = ValidatorAgent()
        self.tally = VoteTallyAgent()
        self.consensus = ConsensusAgent()

    def execute(
        self,
        prompt: str,
        state: MAKERState,
        step: str,
        normalizer: Optional[Callable[[str], str]] = None,
    ) -> tuple[str, bool]:
        """Run voting until consensus or safety valve.

        Returns (winner, low_confidence).
        """
        accumulated: Dict[str, int] = {}
        batch = 0

        while True:
            batch += 1
            logger.info("[%s] Voting batch %d (K=%d)", self.name, batch, state.k_threshold)

            # Dynamic batch size = K
            responses = self.workers.generate_batch(prompt, state, batch_size=state.k_threshold)

            if normalizer:
                responses = [normalizer(r) for r in responses]

            valid = self.validator.validate_batch(responses, state, step)
            if valid:
                batch_votes = self.tally.tally(valid)
                for resp, count in batch_votes.items():
                    accumulated[resp] = accumulated.get(resp, 0) + count

                winner, _ = self.consensus.check(accumulated, state.k_threshold)
                if winner:
                    state.log_step(
                        f"VotingSubNetwork({self.name})",
                        f"Consensus after {batch} batch(es), {sum(accumulated.values())} total votes",
                    )
                    return winner, False

            # Safety valve: stop after max_retry_batches, whatever happened.
            if batch >= self.config.max_retry_batches:
                if accumulated:
                    best = max(accumulated, key=accumulated.get)
                    logger.warning("[%s] Max batches reached, selecting top vote getter", self.name)
                    state.log_step(
                        f"VotingSubNetwork({self.name})",
                        f"No consensus after {batch} batches, top vote selected (low confidence)",
                    )
                    return best, True
                # Every worker failed or every answer was rejected: fail loudly
                # instead of looping forever.
                logger.error("[%s] No valid responses after %d batches", self.name, batch)
                state.log_step(f"VotingSubNetwork({self.name})", f"No valid responses after {batch} batches")
                raise VotingError(
                    f"{self.name} got no valid answers from the model after {batch} attempts. "
                    "Check the API key and try again."
                )
