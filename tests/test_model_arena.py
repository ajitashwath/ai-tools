"""Tests for the real model arena (scores computed from traced spans)."""

import time

import pytest

from aidev.model_arena import ModelArena, Provider, create_arena
from aidev.storage import TraceSQLite
from aidev.trace import SpanStatus, Tracer


@pytest.fixture()
def db(tmp_path):
    store = TraceSQLite(str(tmp_path / "arena.db"))
    yield store
    store.close()


def _seed(db: TraceSQLite) -> None:
    tracer = Tracer(storage=db)
    for i in range(3):
        with tracer.trace(f"run-gpt-{i}") as t:
            t.set_model("gpt-4o", 200)
            t.set_ttft(0.2)
            t.set_tokens_per_sec(50.0)
            t.set_total_tokens(200)
            time.sleep(0.005)
    with tracer.trace("run-gpt-fail") as t:
        t.set_model("gpt-4o", 400)
        t.set_total_tokens(400)
        t.set_error("boom")
        time.sleep(0.005)
    with tracer.trace("run-claude") as t:
        t.set_model("claude-3", 120)
        t.set_ttft(0.5)
        t.set_tokens_per_sec(12.0)
        t.set_total_tokens(120)
        time.sleep(0.005)
    tracer.end()


def test_arena_auto_registers_models_from_db(db):
    _seed(db)
    arena = create_arena(db)
    assert set(arena._models) == {"gpt-4o", "claude-3"}
    assert arena._models["gpt-4o"].provider == Provider.OPENAI
    assert arena._models["claude-3"].provider == Provider.ANTHROPIC


def test_compute_score_uses_traced_metrics(db):
    _seed(db)
    score = ModelArena(db).compute_score("gpt-4o")
    assert score.total_tokens == 1000
    assert score.error_rate == pytest.approx(0.25)
    assert score.success_rate == pytest.approx(0.75)
    assert score.avg_latency > 0
    assert score.avg_ttft == pytest.approx(0.2)
    assert score.avg_tokens_per_sec == pytest.approx(50.0)


def test_compute_score_empty_model_returns_none_fields(db):
    arena = ModelArena(db)
    score = arena.compute_score("gpt-4o")
    assert score.model_name == "gpt-4o"
    assert score.avg_latency is None
    assert score.total_tokens is None


def test_storage_model_filters(db):
    _seed(db)
    assert set(db.get_models()) == {"gpt-4o", "claude-3"}
    spans = db.get_spans_by_model("gpt-4o")
    assert len(spans) == 4
    assert all(s.model == "gpt-4o" for s in spans)
    assert any(s.status == SpanStatus.ERROR for s in spans)
