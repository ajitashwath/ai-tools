"""Unit tests for aidev.storage.TraceSQLite."""

import threading

import pytest

from aidev.storage import TraceSQLite, _row_to_span
from aidev.trace import Span, SpanStatus, Tracer


@pytest.fixture()
def db(tmp_path):
    store = TraceSQLite(str(tmp_path / "test.db"))
    yield store
    store.close()


def _make_span(name="root", **kwargs):
    tracer = Tracer()
    with tracer.trace(name):
        pass
    span = tracer.spans[0]
    span.name = name
    for key, value in kwargs.items():
        setattr(span, key, value)
    return span


def test_save_and_get_by_id_round_trip(db):
    span = _make_span(
        "agent",
        metadata={"k": "v"},
        errors=["boom"],
        inputs={"q": 1},
        outputs={"a": 2},
        model="gpt-4o",
        model_token_count=400,
        operation="code_generation",
        ttft=0.5,
        tokens_per_sec=60.0,
        stop_reason="end_seq",
        total_tokens=350,
    )
    db.save(span)

    loaded = db.get_by_id(span.id)
    assert loaded is not None
    assert loaded.id == span.id
    assert loaded.name == "agent"
    assert loaded.status == SpanStatus.OK
    assert loaded.metadata == {"k": "v"}
    assert loaded.errors == ["boom"]
    assert loaded.inputs == {"q": 1}
    assert loaded.outputs == {"a": 2}
    assert loaded.model == "gpt-4o"
    assert loaded.operation == "code_generation"
    assert loaded.total_tokens == 350


def test_get_by_id_missing_returns_none(db):
    assert db.get_by_id("does-not-exist") is None


def test_root_spans_children_and_all(db):
    tracer = Tracer(storage=db)
    with tracer.trace("root-a"):
        with tracer.span("child-a1"):
            pass
    with tracer.trace("root-b"):
        pass

    roots = db.get_root_spans()
    assert {s.name for s in roots} == {"root-a", "root-b"}

    all_spans = db.get_all_spans()
    assert len(all_spans) == 3
    # Ordered by start_time
    assert [s.start_time for s in all_spans] == sorted(s.start_time for s in all_spans)

    root_a = next(s for s in roots if s.name == "root-a")
    children = db.get_children(root_a.id)
    assert [c.name for c in children] == ["child-a1"]
    assert db.get_children("no-such-parent") == []


def test_save_is_upsert(db):
    span = _make_span("v1")
    db.save(span)
    span.name = "v2"
    db.save(span)
    assert db.get_by_id(span.id).name == "v2"
    assert len(db.get_all_spans()) == 1


def test_delete_spans(db):
    s1, s2 = _make_span("one"), _make_span("two")
    db.save_all([s1, s2])
    db.delete_spans([])  # no-op, must not raise
    db.delete_spans([s1.id])
    assert db.get_by_id(s1.id) is None
    assert db.get_by_id(s2.id) is not None


def test_row_to_span_defaults_for_null_json_columns(db):
    span = _make_span("bare")  # empty metadata/errors, None inputs/outputs
    db.save(span)
    loaded = db.get_by_id(span.id)
    assert loaded.metadata == {}
    assert loaded.errors == []
    assert loaded.inputs is None
    assert loaded.outputs is None


def test_concurrent_writes_do_not_corrupt(tmp_path):
    """Exercise the lock: concurrent saves from threads must all persist."""
    store = TraceSQLite(str(tmp_path / "concurrent.db"))
    try:
        spans = [_make_span(f"span-{i}") for i in range(20)]

        def save_one(span: Span):
            store.save(span)

        threads = [threading.Thread(target=save_one, args=(s,)) for s in spans]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(store.get_all_spans()) == 20
    finally:
        store.close()


def test_row_to_span_helper_parses_status():
    span = _make_span("x")
    span.status = SpanStatus.ERROR
    row = (
        span.id,
        span.name,
        None,
        span.start_time,
        span.end_time,
        "error",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    assert _row_to_span(row).status == SpanStatus.ERROR
