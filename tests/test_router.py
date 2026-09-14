"""Tests for model routing driven by real arena scores."""

import time

import pytest

from aidev.model_arena import ModelArena, ModelInfo, Provider
from aidev.model_routing import ModelRouter, RoutingCriteria
from aidev.storage import TraceSQLite
from aidev.trace import Tracer


@pytest.fixture()
def db(tmp_path):
    store = TraceSQLite(str(tmp_path / "router.db"))
    tracer = Tracer(storage=store)

    # Two models with real measured data: gpt-4o is fast, claude-3 is slow.
    for i in range(2):
        with tracer.trace(f"gpt-{i}") as t:
            t.set_model("gpt-4o", 200)
            t.set_ttft(0.1)
            t.set_tokens_per_sec(70.0)
            t.set_total_tokens(200)
            time.sleep(0.02)
    with tracer.trace("claude") as t:
        t.set_model("claude-3", 120)
        t.set_ttft(0.8)
        t.set_tokens_per_sec(10.0)
        t.set_total_tokens(120)
        time.sleep(0.08)
    tracer.end()
    yield store
    store.close()


def _arena(db: TraceSQLite) -> ModelArena:
    return ModelArena(db)


def _arena_with_unmeasured_llama(db: TraceSQLite) -> ModelArena:
    arena = ModelArena(db)
    # llama-3 is registered in the arena but has NO traces: its scores are
    # all None, so it must never win a data-backed routing criterion.
    arena.register_model(
        ModelInfo(name="llama-3", provider=Provider.LOCAL, family="llama-3", context_window=0)
    )
    return arena


def test_latency_criteria_picks_fastest(db):
    result = ModelRouter(_arena(db)).route(criteria=RoutingCriteria.LATENCY)
    assert result.selected_model == "gpt-4o"
    assert "claude-3" in result.rejected_models


def test_throughput_criteria_picks_highest(db):
    result = ModelRouter(_arena(db)).route(criteria=RoutingCriteria.THROUGHPUT)
    assert result.selected_model == "gpt-4o"


def test_balanced_picks_best_blended(db):
    result = ModelRouter(_arena(db)).route(criteria=RoutingCriteria.BALANCED)
    assert result.selected_model == "gpt-4o"
    assert result.metrics_comparison["selection_type"] == "balanced"
    assert "candidate_metrics" in result.metrics_comparison


def test_rejected_model_is_excluded(db):
    result = ModelRouter(_arena(db)).route(
        criteria=RoutingCriteria.THROUGHPUT,
        rejected=["gpt-4o"],
    )
    assert result.selected_model == "claude-3"


def test_task_keyword_inference_uses_substring(db):
    router = ModelRouter(_arena(db))
    result = router.route_for_task("write a summarization pipeline")
    assert result.criteria_used == RoutingCriteria.THROUGHPUT

    result = router.route_for_task("write code to fix the bug")
    assert result.criteria_used == RoutingCriteria.LATENCY

    # Unmatched task falls back to the explicit default.
    result = router.route_for_task("something totally unrelated", criteria=RoutingCriteria.COST)
    assert result.criteria_used == RoutingCriteria.COST


def test_no_candidates_raises(db):
    router = ModelRouter(_arena(db))
    with pytest.raises(ValueError):
        router.route(criteria=RoutingCriteria.LATENCY, rejected=["gpt-4o", "claude-3"])


def test_route_never_hallucinates_scores(db):
    router = ModelRouter(_arena_with_unmeasured_llama(db))
    result = router.route(criteria=RoutingCriteria.LATENCY)
    # llama-3 has no traces -> it must never be "the fastest" or "the best".
    assert result.selected_model != "llama-3"

    balanced = router.route(criteria=RoutingCriteria.BALANCED)
    assert balanced.selected_model != "llama-3"
