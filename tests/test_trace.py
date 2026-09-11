"""Unit tests for aidev.trace (Tracer SDK)."""

from aidev.trace import Span, SpanStatus, Tracer, trace


def test_trace_context_manager_records_timing_and_ok():
    tracer = Tracer()
    with tracer.trace("agent") as ctx:
        assert ctx.name == "agent"
        assert ctx.id.startswith("span-")
    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.status == SpanStatus.OK
    assert span.end_time >= span.start_time > 0


def test_trace_captures_exception_as_error():
    tracer = Tracer()
    try:
        with tracer.trace("failing"):
            raise ValueError("kaboom")
    except ValueError:
        pass
    span = tracer.spans[0]
    assert span.status == SpanStatus.ERROR
    assert span.errors == ["kaboom"]


def test_nested_span_sets_parent_id():
    tracer = Tracer()
    # Nested (not combined): span() reads the stack at call time, so the
    # parent trace must already be entered.
    with tracer.trace("outer") as outer:  # noqa: SIM117
        with tracer.span("inner") as inner:
            assert inner.parent_id == outer.id
    assert tracer.root_spans == [tracer.spans[0]]
    assert tracer.spans[1].parent_id == tracer.spans[0].id


def test_span_explicit_parent_id():
    tracer = Tracer()
    with tracer.trace("outer"):
        pass
    parent_id = tracer.spans[0].id
    with tracer.span("child", parent_id=parent_id):
        pass
    assert tracer.spans[1].parent_id == parent_id


def test_setters_mutate_span():
    tracer = Tracer()
    with tracer.trace("agent") as ctx:
        ctx.set_metadata("system_prompt", "hi")
        ctx.set_model("gpt-4o", 400)
        ctx.set_operation("code_generation")
        ctx.set_ttft(0.5)
        ctx.set_tokens_per_sec(60.0)
        ctx.set_stop_reason("end_seq")
        ctx.set_total_tokens(350)
        ctx.set_outputs({"done": True})
        ctx.set_error("minor issue")
    span = tracer.spans[0]
    assert span.metadata == {"system_prompt": "hi"}
    assert span.model == "gpt-4o"
    assert span.status == SpanStatus.ERROR
    assert span.errors == ["minor issue"]


def test_tracer_persists_to_storage_on_exit(tmp_path):
    from aidev.storage import TraceSQLite

    store = TraceSQLite(str(tmp_path / "t.db"))
    try:
        tracer = Tracer(storage=store)
        with tracer.trace("persisted"):
            pass
        assert store.get_all_spans()[0].name == "persisted"
    finally:
        store.close()


def test_tracer_end_finalizes_open_spans(tmp_path):
    from aidev.storage import TraceSQLite

    store = TraceSQLite(str(tmp_path / "t.db"))
    try:
        tracer = Tracer(storage=store)
        ctx = tracer.trace("open")
        ctx._span.end_time = 0.0  # simulate unfinished span
        tracer.end()
        assert tracer.spans[0].end_time > 0
    finally:
        store.close()


def test_module_level_trace_helper():
    with trace("quick") as ctx:
        assert isinstance(ctx._span, Span)
