"""Offline tests for pipeline reliability fixes. No API key or network needed.

Run from the repo root:  pytest tests/test_reliability.py -v
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from agents.config import AgentConfig  # noqa: E402
from agents.state import MAKERState  # noqa: E402
from agents.voting_subnetwork import VotingSubNetwork, ValidatorAgent, VotingError  # noqa: E402
from agents.executor import ExecutorAgent, display_rows  # noqa: E402
from agents.formatter import FormatterAgent  # noqa: E402
from agents.visualization import VisualizationAgent  # noqa: E402
from agents.pipeline import Pipeline  # noqa: E402


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "t.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE orders (id INTEGER, order_month TEXT, total REAL, updated_at TEXT)")
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?)",
        [(i, f"2024-{(i % 12) + 1:02d}", float(i * 10), "2024-01-01") for i in range(1, 31)],
    )
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def config(db_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_FILE_SEARCH_STORE", raising=False)
    return AgentConfig(google_api_key="test-key", db_path=db_path, max_retry_batches=3)


def scripted_workers(answers_by_call):
    """Return a fake generate_batch that yields scripted answers per call."""
    calls = iter(answers_by_call)

    def fake(self, prompt, state, batch_size=None):
        return list(next(calls))

    return fake


# -- 1. Voting loop always terminates -------------------------------------------------

def test_voting_raises_instead_of_looping_when_every_worker_fails(config, monkeypatch):
    calls = {"n": 0}

    def all_fail(self, prompt, state, batch_size=None):
        calls["n"] += 1
        if calls["n"] > 10:
            raise AssertionError("voting loop did not stop")
        return []  # every worker errored

    monkeypatch.setattr("agents.voting_subnetwork.WorkerPool.generate_batch", all_fail)
    voting = VotingSubNetwork(config, name="TableSelector")
    with pytest.raises(VotingError):
        voting.execute("p", MAKERState(user_question="q", k_threshold=2), step="tables")
    assert calls["n"] == config.max_retry_batches


def test_voting_returns_low_confidence_at_cap(config, monkeypatch):
    monkeypatch.setattr(
        "agents.voting_subnetwork.WorkerPool.generate_batch",
        scripted_workers([["aa", "bb"], ["aa", "bb"], ["bb", "aa"]]),
    )
    voting = VotingSubNetwork(config, name="TableSelector")
    winner, low_conf = voting.execute("p", MAKERState(user_question="q", k_threshold=2), step="tables")
    assert winner in {"aa", "bb"}
    assert low_conf is True


# -- 5. Validator uses whole-word checks ----------------------------------------------

def test_validator_allows_columns_that_contain_write_keywords():
    v = ValidatorAgent()
    state = MAKERState(user_question="q")
    ok = "SELECT id, updated_at, is_deleted FROM orders"
    bad = ["DELETE FROM orders", "SELECT 1; DROP TABLE orders", "SELECT * FROM x; UPDATE x SET a=1"]
    assert v.validate_batch([ok] + bad, state, "sql") == [ok]


# -- 2. SQL errors are reported as errors ---------------------------------------------

def test_formatter_reports_sql_error_not_empty_results(config):
    state = MAKERState(user_question="q")
    state.step_outputs.execution_error = "no such column: totl"
    state.query_results = []
    answer = FormatterAgent(config).format(state)
    assert "couldn't build a query" in answer
    assert "no such column" in answer
    assert "No results matched" not in answer


# -- 4. Charts see every row ----------------------------------------------------------

def test_executor_keeps_all_rows_and_chart_uses_them(config):
    state = MAKERState(user_question="total by month", complexity_score=0.2)
    state.step_outputs.final_sql = "SELECT order_month, SUM(total) AS revenue FROM orders GROUP BY order_month"
    state = ExecutorAgent(config).execute(state)
    assert len(state.query_results) == 12

    many = MAKERState(user_question="all orders")
    many.step_outputs.final_sql = "SELECT id, order_month, total FROM orders"
    many = ExecutorAgent(config).execute(many)
    assert len(many.query_results) == 30
    spec = VisualizationAgent().generate(many)
    assert spec is not None and len(spec["data"]) == 30
    # The UI table is still trimmed.
    assert len(display_rows(many.query_results)) == 11


# -- End to end: error surfaced + low confidence surfaced ----------------------------

def _pipeline(config, monkeypatch, worker_script):
    monkeypatch.setattr(
        "agents.voting_subnetwork.WorkerPool.generate_batch", scripted_workers(worker_script)
    )
    monkeypatch.setattr(FormatterAgent, "_format_multi", lambda self, s: "summary")
    monkeypatch.setattr(FormatterAgent, "_format_single", lambda self, s: "single")
    return Pipeline(config)


def test_pipeline_surfaces_sql_error_after_retries(config, monkeypatch):
    bad_sql = "SELECT totl FROM orders"
    script = [["orders", "orders"]] + [[bad_sql, bad_sql]] * 3  # tables, then 3 SQL attempts
    result = _pipeline(config, monkeypatch, script).run("How many orders?")
    assert result["error"] and "no such column" in result["error"]
    assert "couldn't build a query" in result["answer"]


def test_pipeline_surfaces_low_confidence(config, monkeypatch):
    good = "SELECT COUNT(*) AS n FROM orders"
    alt = "SELECT COUNT(id) AS n FROM orders"
    script = [["orders", "orders"]] + [[good, alt]] * 3
    result = _pipeline(config, monkeypatch, script).run("How many orders?")
    assert result["error"] is None
    assert result["low_confidence_steps"] == ["SqlSynthesizer"]
    assert result["answer"] == "single"


# -- Model config: one configurable model, no sampling params ------------------------

def test_workers_use_configured_model_without_temperature(config):
    from agents.voting_subnetwork import WorkerPool

    seen = []

    class FakeResp:
        text = "orders"

    def fake_generate(**kwargs):
        seen.append(kwargs)
        return FakeResp()

    pool = WorkerPool(config.model_copy(update={"gemini_model": "gemini-test-model"}))
    pool.client.models.generate_content = fake_generate
    out = pool.generate_batch("p", MAKERState(user_question="q"), batch_size=3)
    assert out == ["orders"] * 3
    assert all(k["model"] == "gemini-test-model" for k in seen)
    assert all("config" not in k or getattr(k["config"], "temperature", None) is None for k in seen)


def test_voting_error_includes_last_model_error(config, monkeypatch):
    from agents.voting_subnetwork import WorkerPool

    def boom(**kwargs):
        raise RuntimeError("404 model not found")

    voting = VotingSubNetwork(config, name="JoinArchitect")
    voting.workers.client.models.generate_content = boom
    with pytest.raises(VotingError, match="404 model not found"):
        voting.execute("p", MAKERState(user_question="q", k_threshold=2), step="joins")
