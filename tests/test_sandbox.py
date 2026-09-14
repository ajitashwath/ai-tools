"""End-to-end tests for the real sandbox: isolation, tracing, repair loop."""

from pathlib import Path

import pytest

from aidev.sandbox import IsolatedSandbox, SandboxAgent
from aidev.storage import TraceSQLite
from aidev.trace import Tracer

SAMPLE_REPO = Path(__file__).resolve().parent.parent / "demo" / "sample_repo"
REPAIR_SCRIPT = SAMPLE_REPO / "repair.py"


@pytest.fixture()
def storage(tmp_path):
    store = TraceSQLite(str(tmp_path / "sandbox.db"))
    yield store
    store.close()


def test_sandbox_isolates_repo_copy():
    original = (SAMPLE_REPO / "calc.py").read_text(encoding="utf-8")
    tracer = Tracer()
    sb = IsolatedSandbox(str(SAMPLE_REPO), tracer=tracer, keep_dir=None)
    try:
        # The isolated copy exists and the original was never touched.
        assert (sb.root / "calc.py").exists()
        assert (sb.root / "calc.py").read_text(encoding="utf-8") == original
    finally:
        sb.cleanup()


def test_agent_repairs_broken_sample(storage):
    tracer = Tracer(storage=storage)
    sb = IsolatedSandbox(str(SAMPLE_REPO), tracer=tracer, keep_dir=None)
    try:
        agent = SandboxAgent(sb, tracer, model="demo-gpt", max_iterations=2)
        result = agent.run("fix the failing calc tests", [str(REPAIR_SCRIPT)])

        assert result.passed is True
        assert result.decision == "approve"
        assert "calc.py" in result.changed_files
        assert result.iterations == 1
    finally:
        sb.cleanup()


def test_agent_reports_failure_without_repair(storage):
    tracer = Tracer(storage=storage)
    sb = IsolatedSandbox(str(SAMPLE_REPO), tracer=tracer, keep_dir=None)
    try:
        agent = SandboxAgent(sb, tracer, model="demo-gpt", max_iterations=2)
        result = agent.run("fix the failing calc tests", [])

        assert result.passed is False
        assert result.decision == "needs_changes"
        assert result.iterations == 0
    finally:
        sb.cleanup()


def test_agent_traces_every_step(storage):
    tracer = Tracer(storage=storage)
    sb = IsolatedSandbox(str(SAMPLE_REPO), tracer=tracer, keep_dir=None)
    try:
        agent = SandboxAgent(sb, tracer, model="demo-gpt")
        agent.run("fix the failing calc tests", [str(REPAIR_SCRIPT)])
    finally:
        sb.cleanup()
    tracer.end()

    names = {s.name for s in tracer.spans}
    assert "coding_agent" in names  # root span
    assert "test_run:baseline" in names
    assert "test_run:attempt_1" in names
    assert "repair:attempt_1" in names

    root = next(s for s in tracer.spans if s.name == "coding_agent")
    assert root.model == "demo-gpt"
    assert root.outputs["decision"] == "approve"

    # All persisted into a real DB that the dashboard can read.
    persisted = storage.get_all_spans()
    assert len(persisted) >= len(tracer.spans)
