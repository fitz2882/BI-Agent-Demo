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


_EQ_PAIR_RE = re.compile(r"([a-z_][\w]*\.[a-z_][\w]*)=([a-z_][\w]*\.[a-z_][\w]*)")


def canonical_sql(text: str) -> str:
    """Vote key for SQL and JOIN answers.

    Two answers that differ only in formatting should count as the same vote.
    This ignores code fences, a trailing semicolon, whitespace, keyword case,
    identifier quotes, optional AS / INNER / OUTER keywords and the side order
    of `a.x = b.y` join conditions. Text inside single-quoted string literals
    is kept exactly, since 'Books' and 'books' are different filters.
    """
    t = text.strip()
    if t.startswith("```"):
        t = "\n".join(l for l in t.split("\n") if not l.strip().startswith("```"))
    t = t.strip().rstrip(";").strip()

    parts = re.split(r"('(?:[^']|'')*')", t)
    out = []
    for i, part in enumerate(parts):
        if i % 2:  # string literal: keep as-is
            out.append(part)
            continue
        p = part.lower().replace('"', "").replace("`", "")
        p = re.sub(r"\s+", " ", p)
        p = re.sub(r"(?<=[\w)]) as (?=\w)", " ", p)
        p = re.sub(r"\binner join\b", "join", p)
        p = re.sub(r"\b(left|right|full) outer join\b", r"\1 join", p)
        p = re.sub(r"\s*([(),=<>+*/-])\s*", r"\1", p)
        p = _EQ_PAIR_RE.sub(lambda m: "=".join(sorted(m.groups())), p)
        out.append(p)
    return "".join(out).strip()


class VotingError(RuntimeError):
    """Raised when a voting step cannot produce any valid candidate."""


class WorkerPool:
    """Spawns parallel Gemini workers.

    Gemini 3.x models no longer accept sampling parameters (temperature, top_p,
    top_k), so workers use the model's default sampling. Each call samples
    independently, which gives the vote its diversity.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.worker_count = config.worker_batch_size
        self.client = genai.Client(api_key=config.google_api_key)
        self.last_error: Optional[str] = None

    def generate_batch(
        self, prompt: str, state: MAKERState, batch_size: Optional[int] = None
    ) -> List[str]:
        count = batch_size or self.worker_count
        responses: List[str] = []

        def _run_one(idx: int) -> str:
            response = self.client.models.generate_content(
                model=self.config.gemini_model,
                contents=prompt,
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
                    self.last_error = str(e)
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
        vote_key: Optional[Callable[[str], str]] = None,
    ) -> tuple[str, bool]:
        """Run voting until consensus or safety valve.

        Votes are counted by `vote_key(answer)`, so answers that mean the same
        thing share one tally. SQL and JOIN steps default to `canonical_sql`.
        The winner returned is the first real answer seen for the winning key.

        Returns (winner, low_confidence).
        """
        if vote_key is None:
            vote_key = canonical_sql if step in ("sql", "joins") else (lambda s: s)
        accumulated: Dict[str, int] = {}
        examples: Dict[str, str] = {}
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
                keys = []
                for resp in valid:
                    key = vote_key(resp)
                    examples.setdefault(key, resp)
                    keys.append(key)
                batch_votes = self.tally.tally(keys)
                for key, count in batch_votes.items():
                    accumulated[key] = accumulated.get(key, 0) + count

                winner, _ = self.consensus.check(accumulated, state.k_threshold)
                if winner:
                    state.log_step(
                        f"VotingSubNetwork({self.name})",
                        f"Consensus after {batch} batch(es), {sum(accumulated.values())} total votes",
                    )
                    return examples[winner], False

            # Safety valve: stop after max_retry_batches, whatever happened.
            if batch >= self.config.max_retry_batches:
                if accumulated:
                    best = max(accumulated, key=accumulated.get)
                    logger.warning("[%s] Max batches reached, selecting top vote getter", self.name)
                    state.log_step(
                        f"VotingSubNetwork({self.name})",
                        f"No consensus after {batch} batches, top vote selected (low confidence)",
                    )
                    return examples[best], True
                # Every worker failed or every answer was rejected: fail loudly
                # instead of looping forever.
                logger.error("[%s] No valid responses after %d batches", self.name, batch)
                state.log_step(f"VotingSubNetwork({self.name})", f"No valid responses after {batch} batches")
                detail = self.workers.last_error
                raise VotingError(
                    f"{self.name} got no valid answers from {self.config.gemini_model} "
                    f"after {batch} attempts. "
                    + (f"Last model error: {detail[:300]}" if detail else "Check the API key and model name.")
                )
