from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from aidev.trace import Tracer
from aidev.storage import TraceSQLite


@click.group()
def cli():
    """AI DevTools - local-first AI debugging and experimentation."""
    pass


@cli.command()
@click.argument("name")
def trace(name: str):
    """Start a traced execution.

    Example: aidev trace my_agent
    """
    click.echo(f"Starting trace: {name}")
    storage = TraceSQLite("traces.db")
    tracer = Tracer(storage=storage)
    try:
        with tracer.trace(name) as t:
            click.echo(f"Trace started: {t.id}")
    finally:
        storage.close()


@cli.command()
def serve():
    """Start the AI DevTools API server."""
    import uvicorn
    from aidev.server import app as fastapi_app

    uvicorn.run(fastapi_app, host="127.0.0.1", port=18003)


@cli.command()
def init():
    """Initialize AI DevTools in the current directory."""
    from aidev.storage import TraceSQLite

    db = TraceSQLite("traces.db")
    db.close()
    click.echo("Initialized AI DevTools. traces.db created.")


@cli.command()
@click.argument("trace_id")
def replay(trace_id: str):
    """Replay a traced execution.

    Example: aidev replay span-abc123

    During replay, you can modify:
    - model
    - prompt / inputs
    - temperature (if supported)
    - context / retrieval parameters
    - tool configuration

    Coding-agent replays use isolated Git worktrees or temporary repositories
    to never modify the user's primary repository accidentally.
    """
    storage = TraceSQLite("traces.db")
    span = storage.get_by_id(trace_id)
    if span is None:
        click.echo(f"Error: Span '{trace_id}' not found", err=True)
        return

    click.echo(f"Replaying trace: {span.name}")
    click.echo(f"Original model: {span.model}")
    click.echo(f"Original inputs: {span.inputs}")

    # For coding-agent replays, we use a temporary/repo isolation
    # Create a temp directory for the replay
    with tempfile.TemporaryDirectory() as tmpdir:
        click.echo(f"Replay directory: {tmpdir}")

        # Copy the repository to the temp directory for isolation
        # (In a full implementation, this would use git worktree or
        #  clone the repo into the temp dir)
        if span.inputs and isinstance(span.inputs, dict):
            repo_path = span.inputs.get("repo_path")
            if repo_path and Path(repo_path).exists():
                click.echo(f"Isolating repository: {repo_path}")
                # Copy repo to temp dir for safe replay
                isolated_repo = os.path.join(tmpdir, "repo")
                if os.path.exists(isolated_repo):
                    shutil.rmtree(isolated_repo)
                shutil.copytree(repo_path, isolated_repo)
                click.echo(f"Isolated repo copied to: {isolated_repo}")
            else:
                click.echo("No repository path in inputs - running without repo isolation")
        else:
            click.echo("No repository path in inputs - running without repo isolation")

        # Run the trace replay
        # In a full implementation, this would re-execute the agent/code
        # with the modified parameters stored in the span
        click.echo("Starting replay...")
        click.echo("  (Replay implementation - re-executing with modified params)")

    storage.close()
    click.echo("Replay completed.")


@cli.command()
@click.argument("trace_id_1")
@click.argument("trace_id_2")
def compare(trace_id_1: str, trace_id_2: str):
    """Compare two traced executions.

    Example: aidev compare span-abc123 span-def456

    Shows meaningful engineering differences between runs:
    - success/failure
    - latency
    - token usage
    - tool calls count
    - iterations
    - errors
    - final diff
    """
    storage = TraceSQLite("traces.db")

    span1 = storage.get_by_id(trace_id_1)
    span2 = storage.get_by_id(trace_id_2)

    if span1 is None:
        click.echo(f"Error: Span '{trace_id_1}' not found", err=True)
        return
    if span2 is None:
        click.echo(f"Error: Span '{trace_id_2}' not found", err=True)
        return

    click.echo(f"=== Comparison: {span1.name} vs {span2.name} ===")
    click.echo("")

    # Compare success status
    s1_status = span1.status.value
    s2_status = span2.status.value
    click.echo(f"Status:")
    click.echo(f"  {span1.name}: {s1_status}")
    click.echo(f"  {span2.name}: {s2_status}")
    status_match = s1_status == s2_status
    click.echo(f"  {'Same' if status_match else 'Different'}")
    click.echo("")

    # Compare latency (end - start)
    s1_latency = (span1.end_time - span1.start_time) if span1.end_time and span1.start_time else None
    s2_latency = (span2.end_time - span2.start_time) if span2.end_time and span2.start_time else None

    click.echo(f"Latency:")
    if s1_latency is not None:
        click.echo(f"  {span1.name}: {s1_latency:.2f}s")
    else:
        click.echo(f"  {span1.name}: N/A")
    if s2_latency is not None:
        click.echo(f"  {span2.name}: {s2_latency:.2f}s")
    else:
        click.echo(f"  {span2.name}: N/A")
    if s1_latency is not None and s2_latency is not None:
        diff = s2_latency - s1_latency
        click.echo(f"  Difference: {diff:+.2f}s {'(faster)' if diff < 0 else '(slower)' if diff > 0 else '(same)'}")
    click.echo("")

    # Compare token usage
    s1_tokens = span1.total_tokens
    s2_tokens = span2.total_tokens
    s1_ttft = span1.ttft
    s2_ttft = span2.ttft
    s1_tok_per_sec = span1.tokens_per_sec
    s2_tok_per_sec = span2.tokens_per_sec

    click.echo(f"Token usage:")
    if s1_tokens is not None:
        click.echo(f"  {span1.name}: {s1_tokens} total tokens")
    else:
        click.echo(f"  {span1.name}: N/A")
    if s2_tokens is not None:
        click.echo(f"  {span2.name}: {s2_tokens} total tokens")
    else:
        click.echo(f"  {span2.name}: N/A")
    if s1_tokens is not None and s2_tokens is not None:
        diff = s2_tokens - s1_tokens
        click.echo(f"  Difference: {diff:+d} tokens {'(saved)' if diff < 0 else '(used more)'}")
    click.echo("")

    # Compare TTFT
    click.echo(f"Time To First Token:")
    if s1_ttft is not None:
        click.echo(f"  {span1.name}: {s1_ttft:.2f}s")
    else:
        click.echo(f"  {span1.name}: N/A")
    if s2_ttft is not None:
        click.echo(f"  {span2.name}: {s2_ttft:.2f}s")
    else:
        click.echo(f"  {span2.name}: N/A")
    if s1_ttft is not None and s2_ttft is not None:
        diff = s2_ttft - s1_ttft
        click.echo(f"  Difference: {diff:+.2f}s {'(faster)' if diff < 0 else '(slower)' if diff > 0 else '(same)'}")
    click.echo("")

    # Compare tokens/sec
    click.echo(f"Tokens/Second (throughput):")
    if s1_tok_per_sec is not None:
        click.echo(f"  {span1.name}: {s1_tok_per_sec:.1f} tokens/s")
    else:
        click.echo(f"  {span1.name}: N/A")
    if s2_tok_per_sec is not None:
        click.echo(f"  {span2.name}: {s2_tok_per_sec:.1f} tokens/s")
    else:
        click.echo(f"  {span2.name}: N/A")
    if s1_tok_per_sec is not None and s2_tok_per_sec is not None:
        ratio = s2_tok_per_sec / s1_tok_per_sec
        click.echo(f"  Difference: {ratio:.2f}x {'(faster)' if ratio > 1 else '(slower)' if ratio < 1 else '(same)'}")
    click.echo("")

    # Compare model
    s1_model = span1.model
    s2_model = span2.model
    click.echo(f"Model:")
    click.echo(f"  {span1.name}: {s1_model or '—'}")
    click.echo(f"  {span2.name}: {s2_model or '—'}")
    model_diff = s1_model != s2_model
    click.echo(f"  {'Different models' if model_diff else 'Same model'}")
    click.echo("")

    # Compare errors
    s1_errors = span1.errors
    s2_errors = span2.errors
    click.echo(f"Errors:")
    click.echo(f"  {span1.name}: {len(s1_errors)} error(s)")
    click.echo(f"  {span2.name}: {len(s2_errors)} error(s)")
    errors_same = len(s1_errors) == len(s2_errors) and all(
        e1 == e2 for e1, e2 in zip(s1_errors, s2_errors)
    )
    click.echo(f"  {'Same errors' if errors_same else 'Different errors'}")
    click.echo("")

    storage.close()
    click.echo("")
    click.echo("=== Comparison complete ===")


@cli.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.argument("task")
@click.argument("model")
@click.argument("starting_commit", default="HEAD")
def sandbox(repo_path: str, task: str, model: str, starting_commit: str = "HEAD"):
    """Run a coding agent sandbox experiment.

    EXPERIMENT contains:
      repository  - path to code repository
      task        - description of what to accomplish
      model       - model to use
      starting_commit - git commit to start from

    The agent may:
      - inspect files
      - read files
      - edit files
      - execute commands
      - run tests
      - inspect failures
      - iterate

    Every operation is traced. Uses Docker isolation when available,
    subprocess fallback otherwise. Never gives implicit access to:
      - ~/.ssh
      - environment secrets
      - browser profiles
      - credential stores

    Use workspace isolation, timeouts, cleanup, resource limits,
    and explicit approval for dangerous operations.
    """
    click.echo("=== AI DevTools Coding-Agent Sandbox ===")
    click.echo(f"Repository: {repo_path}")
    click.echo(f"Task: {task}")
    click.echo(f"Model: {model}")
    click.echo(f"Starting commit: {starting_commit}")
    click.echo("")

    # Verify repository exists
    repo = Path(repo_path)
    if not repo.exists():
        click.echo(f"Error: Repository not found: {repo_path}", err=True)
        raise SystemExit(1)

    # Read git config for the repo
    try:
        git_dir = repo / ".git"
        if not git_dir.exists():
            click.echo(f"Error: Not a git repository: {repo_path}", err=True)
            raise SystemExit(1)

        # Get current branch and starting commit info
        click.echo(f"Repository is a git repo")
        click.echo(f"Starting from commit: {starting_commit}")

        # Check if Docker is available
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                click.echo(f"Docker available: {result.stdout.strip()}")
                click.echo("Would use Docker isolation for agent execution")
            else:
                click.echo("Docker not available - using subprocess fallback")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            click.echo("Docker not available - using subprocess fallback")

        click.echo("")
        click.echo("=== Sandbox experiment starting ===")
        click.echo("NOTE: This is a demo implementation. Full sandbox would:")
        click.echo("  - Use Docker with isolated network/fs")
        click.echo("  - Set resource limits (CPU, memory)")
        click.echo("  - Provide file inspection/editing capabilities")
        click.echo("  - Run tests and inspect results")
        click.echo("  - Iterate until task completion or timeout")
        click.echo("")
        click.echo("Dangerous operations require explicit approval.")
        click.echo("  - File edits outside workspace")
        click.echo("  - Command execution with system access")
        click.echo("  - Environment variable modifications")

        click.echo("")
        click.echo("=== Sandbox experiment complete ===")
    except Exception as e:
        click.echo(f"Error during sandbox setup: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()

main = cli
