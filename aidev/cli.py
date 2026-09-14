from __future__ import annotations

from pathlib import Path

import click

from aidev.model_diagnosis import AgentDiagnosis
from aidev.performance_optimization import PerformanceOptimizer
from aidev.server import API_HOST, API_PORT
from aidev.storage import TraceSQLite
from aidev.trace import Tracer

DEFAULT_DB_PATH = "traces.db"


@click.group()
def cli():
    """AI DevTools - local-first AI debugging and experimentation."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@cli.command()
def init():
    """Initialize AI DevTools in the current directory."""
    db = TraceSQLite(DEFAULT_DB_PATH)
    db.close()
    click.echo("Initialized AI DevTools. traces.db created.")


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@cli.command()
def serve():
    """Start the AI DevTools API server."""
    import uvicorn

    uvicorn.run("aidev.server:app", host=API_HOST, port=API_PORT)


# ---------------------------------------------------------------------------
# trace
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("name")
def trace(name: str):
    """Start a traced execution (stored in traces.db).

    Example: aidev trace my_agent
    """
    click.echo(f"Starting trace: {name}")
    storage = TraceSQLite(DEFAULT_DB_PATH)
    tracer = Tracer(storage=storage)
    try:
        with tracer.trace(name) as t:
            click.echo(f"Trace started: {t.id}")
    finally:
        storage.close()


# ---------------------------------------------------------------------------
# sandbox
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.argument("task")
@click.argument("model")
@click.option(
    "--repair",
    type=click.Path(exists=True),
    help="Path to a deterministic repair script applied while tests fail.",
)
@click.option("--max-iterations", default=4, type=int, help="Repair iterations before giving up.")
@click.option("--timeout", default=60.0, type=float, help="Per-command timeout in seconds.")
@click.option("--db", default=DEFAULT_DB_PATH, help="Database to record spans in.")
@click.option(
    "--keep-dir",
    default=None,
    help="Keep the sandbox copy at this path instead of cleaning it up.",
)
def sandbox(
    repo_path: str,
    task: str,
    model: str,
    repair: str | None,
    max_iterations: int,
    timeout: float,
    db: str,
    keep_dir: str | None,
):
    """Run a coding-agent sandbox experiment with real test execution.

    Every operation is traced: baseline tests, repair script execution, and
    final test run. The agent works on an isolated copy of the repository so
    the original is never touched.

    Example:
        aidev sandbox demo\\sample_repo "fix the failing calc tests" demo-gpt
          --repair demo\\sample_repo\\repair.py
    """
    from aidev.sandbox import IsolatedSandbox, SandboxAgent

    storage = TraceSQLite(db)
    tracer = Tracer(storage=storage)
    result = None
    sb = None
    try:
        click.echo("=== AI DevTools Sandbox ===")
        click.echo(f"Repository: {repo_path}")
        click.echo(f"Task: {task}")
        click.echo(f"Model: {model}")
        click.echo("")

        sb = IsolatedSandbox(repo_path, tracer=tracer, timeout=timeout, keep_dir=keep_dir)
        click.echo(f"Isolated working copy: {sb.root}")

        agent = SandboxAgent(
            sb,
            tracer,
            model=model,
            max_iterations=max_iterations,
        )

        scripts = [Path(repair).resolve()] if repair else []
        click.echo(f"Repair scripts: {[str(s) for s in scripts] or 'none'}")
        click.echo("")

        result = agent.run(task, repair_scripts=[str(s) for s in scripts])

        click.echo("--- Test run summary ---")
        baseline = f"({_fmt(result.before.duration_s)})"
        final = f"({_fmt(result.after.duration_s)})"
        click.echo(f"Baseline exit code : {result.before.returncode}  {baseline}")
        click.echo(f"Final exit code    : {result.after.returncode}  {final}")
        click.echo(f"Iterations         : {result.iterations}")
        click.echo(f"Changed files      : {result.changed_files or 'none'}")
        click.echo(f"Decision           : {result.decision}")
        click.echo("")
        if result.passed:
            click.echo("PASS: All tests passing.")
        else:
            click.echo("FAIL: Tests still failing after repair attempts.")
            if result.before.stdout or result.before.stderr:
                click.echo("--- Baseline test output ---")
                tail = result.before.stdout or result.before.stderr
                click.echo(tail[-600:])
    finally:
        if sb is not None:
            sb.cleanup()
        tracer.end()
        storage.close()


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("trace_id")
@click.option(
    "--repo",
    default=None,
    type=click.Path(exists=True),
    help="Override repo path (default: use stored span inputs).",
)
@click.option("--repair", type=click.Path(exists=True), help="Repair script to apply.")
@click.option("--db", default=DEFAULT_DB_PATH)
def replay(trace_id: str, repo: str | None, repair: str | None, db: str):
    """Replay a traced execution inside an isolated sandbox.

    When the stored span carries a repo_path in its inputs, the replay runs
    the same task in an isolated copy and records a fresh traced run
    linked back to the original span. Without a repo_path the replay
    creates a fresh traced shell (honest: it cannot re-execute arbitrary code).
    """
    from aidev.sandbox import IsolatedSandbox, SandboxAgent

    storage = TraceSQLite(db)
    try:
        span = storage.get_by_id(trace_id)
        if span is None:
            click.echo(f"Error: Span '{trace_id}' not found", err=True)
            storage.close()
            return

        inputs = span.inputs if isinstance(span.inputs, dict) else {}
        stored_repo = inputs.get("repo_path") or inputs.get("repo")
        repo_path = repo or (stored_repo if isinstance(stored_repo, str) else None)
        task = inputs.get("task") or f"replay of {span.name}"
        model = span.model or "demo"

        click.echo("=== AI DevTools Replay ===")
        click.echo(f"Original span : {span.name}  (id={span.id})")
        click.echo(f"Original model: {model}")

        repo_issue = None
        if not repo_path:
            repo_issue = "No repo path recorded on this span."
        elif not Path(repo_path).exists():
            repo_issue = f"The recorded repo path '{repo_path}' no longer exists."

        if repo_issue:
            click.echo(
                f"\n{repo_issue}\n"
                "The original execution cannot be re-run in a sandbox, so this\n"
                "replay creates a fresh traced shell instead (honest: arbitrary\n"
                "code can't be re-executed without a repo)."
            )
            tracer = Tracer(storage=storage)
            with tracer.trace(f"replay:{span.name}", inputs={"original_span_id": span.id}) as t:
                t.set_model(model, span.model_token_count)
                t.set_metadata("original_span_id", span.id)
                t.set_metadata("replayed_without_repo", True)
                t.set_outputs({"note": "no repo available; created a fresh traced run"})
            tracer.end()
            click.echo("Replay complete.")
            storage.close()
            return

        click.echo(f"Replay repo   : {repo_path}")
        click.echo("")

        tracer = Tracer(storage=storage)
        sb = IsolatedSandbox(repo_path, tracer=tracer, keep_dir=None, timeout=60.0)
        agent = SandboxAgent(
            sb,
            tracer,
            model=model,
            max_iterations=4,
            original_span_id=span.id,
        )
        scripts = [str(Path(repair).resolve())] if repair else []
        result = agent.run(task, repair_scripts=scripts)

        click.echo("--- Comparison ---")
        click.echo(
            f"Original status: {span.status.value}  "
            f"(latency {span.end_time - span.start_time:.3f}s, "
            f"tokens {span.total_tokens or 'N/A'})"
        )
        click.echo(f"Replay result  : {result.decision}  (latency {result.after.duration_s:.3f}s)")
        if span.status.value == "ok" and not result.passed:
            click.echo("Note: original passed but replay did not — input divergence.")
        click.echo("")
        if result.passed:
            click.echo("PASS: Tests passing in the replay.")
        else:
            click.echo("FAIL: Tests still failing.")
        click.echo(f"Changed files: {result.changed_files or 'none'}")
        click.echo(f"Replay complete. Span {tracer.spans[0].id} saved.")
    finally:
        storage.close()


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("trace_id_1")
@click.argument("trace_id_2")
@click.option("--db", default=DEFAULT_DB_PATH)
def compare(trace_id_1: str, trace_id_2: str, db: str):
    """Compare two traced executions side by side.

    Example: aidev compare span-abc123 span-def456
    """
    storage = TraceSQLite(db)
    try:
        span1 = storage.get_by_id(trace_id_1)
        span2 = storage.get_by_id(trace_id_2)
        if span1 is None:
            click.echo(f"Error: Span '{trace_id_1}' not found", err=True)
            return
        if span2 is None:
            click.echo(f"Error: Span '{trace_id_2}' not found", err=True)
            return

        click.echo(f"=== Comparison: {span1.name} vs {span2.name} ===\n")

        click.echo("Status:")
        click.echo(f"  {span1.name}: {span1.status.value}")
        click.echo(f"  {span2.name}: {span2.status.value}")
        click.echo(f"  {'Same' if span1.status.value == span2.status.value else 'Different'}\n")

        lat1 = _latency(span1)
        lat2 = _latency(span2)
        _print_metric_pair("Latency", f"{lat1:.2f}s", f"{lat2:.2f}s")
        _print_metric_pair(
            "Tokens",
            f"{span1.total_tokens}" if span1.total_tokens is not None else "N/A",
            f"{span2.total_tokens}" if span2.total_tokens is not None else "N/A",
        )
        _print_metric_pair("TTFT", _fmt(span1.ttft), _fmt(span2.ttft))
        _print_metric_pair(
            "Tokens/s",
            f"{span1.tokens_per_sec:.1f}" if span1.tokens_per_sec is not None else "N/A",
            f"{span2.tokens_per_sec:.1f}" if span2.tokens_per_sec is not None else "N/A",
        )
        _print_metric_pair("Model", span1.model or "—", span2.model or "—")

        click.echo("Errors:")
        click.echo(f"  {span1.name}: {len(span1.errors)} error(s)")
        click.echo(f"  {span2.name}: {len(span2.errors)} error(s)")
        click.echo("\n=== Comparison complete ===")
    finally:
        storage.close()


def _latency(span) -> float | None:
    if span.end_time > span.start_time:
        return span.end_time - span.start_time
    return None


def _fmt(v: float | None) -> str:
    return f"{v:.2f}s" if v is not None else "N/A"


def _print_metric_pair(label: str, a: str, b: str) -> None:
    click.echo(f"{label}:")
    click.echo(f"  A: {a}")
    click.echo(f"  B: {b}\n")


# ---------------------------------------------------------------------------
# diagnose
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--db", default=DEFAULT_DB_PATH, help="Database to read spans from.")
@click.option("--root", default=None, help="Restrict diagnosis to descendants of this root span.")
def diagnose(db: str, root: str | None):
    """Run deterministic anti-pattern diagnostics on recorded spans."""
    storage = TraceSQLite(db)
    try:
        all_spans = storage.get_all_spans()
        if root:
            root_span = storage.get_by_id(root)
            if root_span is None:
                click.echo(f"Error: Root span '{root}' not found", err=True)
                return
            ids = {root}
            changed = True
            while changed:
                changed = False
                for s in all_spans:
                    if s.parent_id in ids and s.id not in ids:
                        ids.add(s.id)
                        changed = True
            spans = [s for s in all_spans if s.id in ids]
            click.echo(f"Diagnosing {len(spans)} span(s) under root '{root_span.name}':")
        else:
            spans = all_spans
            click.echo(f"Diagnosing all {len(spans)} span(s):")

        result = AgentDiagnosis().diagnose(spans, agent_id=root or "global")
        if not result.detected_patterns:
            click.echo("  No anti-patterns detected.")
        else:
            click.echo(f"  Severity: {result.severity}")
            for pattern in result.detected_patterns:
                click.echo(f"  - {pattern}")
            click.echo("  Recommendations:")
            for rec in result.recommendations:
                click.echo(f"    * {rec}")
    finally:
        storage.close()


# ---------------------------------------------------------------------------
# optimize
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--db", default=DEFAULT_DB_PATH)
@click.option("--model", default=None, help="Restrict analysis to a specific model name.")
def optimize(db: str, model: str | None):
    """Benchmark performance and print optimization recommendations."""
    storage = TraceSQLite(db)
    try:
        spans = storage.get_spans_by_model(model) if model else storage.get_all_spans()
        opt = PerformanceOptimizer()
        bench = opt.benchmark(spans, model_name=model)
        recs = opt.optimize(bench)

        click.echo(f"=== Performance Benchmark ({bench.model_name}) ===")
        click.echo(f"Total runs      : {bench.total_runs}")
        click.echo(f"Avg latency     : {_fmt(bench.avg_latency_s)}")
        click.echo(f"Avg TTFT        : {_fmt(bench.avg_ttft_s)}")
        speed = f"{bench.avg_tokens_per_sec:.1f}" if bench.avg_tokens_per_sec is not None else "N/A"
        click.echo(f"Avg tokens/s    : {speed}")
        click.echo(f"Total tokens    : {bench.total_tokens or 'N/A'}")
        click.echo(f"Error count     : {bench.error_count}")
        click.echo("")

        if not recs:
            click.echo("No optimization recommendations (nothing to improve).")
        else:
            click.echo(f"{len(recs)} recommendation(s):")
            for r in recs:
                click.echo(f"  [{r.priority.upper()}] {r.category}: {r.description}")
                click.echo(f"    Expected: {r.expected_improvement}")
                for step in r.actionable_steps:
                    click.echo(f"      - {step}")
    finally:
        storage.close()


# ---------------------------------------------------------------------------
# arena
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--db", default=DEFAULT_DB_PATH)
def arena(db: str):
    """List model arena scores and routing recommendations per criteria."""
    from aidev.model_arena import create_arena
    from aidev.model_routing import ModelRouter, RoutingCriteria

    storage = TraceSQLite(db)
    try:
        ar = create_arena(storage)
        router = ModelRouter(ar)

        models = list(ar._models.keys())
        if not models:
            click.echo("No models recorded in the database yet.")
            storage.close()
            return

        click.echo("=== Model Arena ===\n")
        for name in models:
            score = ar.compute_score(name)
            speed = (
                f"{score.avg_tokens_per_sec:.1f}" if score.avg_tokens_per_sec is not None else "N/A"
            )
            error_rate = f"{score.error_rate:.2%}" if score.error_rate is not None else "N/A"
            success_rate = f"{score.success_rate:.2%}" if score.success_rate is not None else "N/A"
            click.echo(f"  {name}:")
            click.echo(f"    avg_latency   : {_fmt(score.avg_latency)}")
            click.echo(f"    avg_ttft      : {_fmt(score.avg_ttft)}")
            click.echo(f"    tokens/s      : {speed}")
            click.echo(f"    error_rate    : {error_rate}")
            click.echo(f"    success_rate  : {success_rate}")
            click.echo(f"    total_tokens  : {score.total_tokens or 'N/A'}")
            click.echo("")

        click.echo("=== Routing Recommendations ===\n")
        for criteria in RoutingCriteria:
            try:
                result = router.route(criteria=criteria)
                click.echo(f"  {criteria.value:12s} -> {result.selected_model}")
                click.echo(f"               {result.reasoning[:120]}")
            except ValueError as exc:
                click.echo(f"  {criteria.value:12s} -> (error: {exc})")
    finally:
        storage.close()


def main() -> None:
    """Console-script entry point (see ``pyproject.toml`` ``[project.scripts]``)."""
    cli()


if __name__ == "__main__":
    main()
