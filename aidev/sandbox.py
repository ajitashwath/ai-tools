"""Real test-driven sandbox for coding-agent experiments and replay.

:class:`IsolatedSandbox` copies a repository into a private directory so the
primary working copy is never touched, then :class:`SandboxAgent` runs a
traced loop: baseline tests, deterministic repair steps (plain Python repair
scripts executed with the sandbox root as the working directory) until tests
pass or the iteration budget is exhausted.

Every executed command is recorded as a span with its real duration, exit
code and output tail. The agent makes no fabricated model-metric claims: a
``model`` name is attached to the run so arena/diagnosis reports can group it,
but TTFT/throughput/token metrics are only stored when a real model call
produces them.

Repair scripts are ordinary Python files that mutate the sandbox copy (e.g.
``Path(...).write_text``); the sandbox reports which files actually changed by
hashing the tree before and after.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from aidev.executor import CommandResult, run_command
from aidev.trace import Tracer

_IGNORED = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".egg-info")

_IGNORED_NAMES = (".git", "__pycache__", ".pytest_cache", ".egg-info")


@dataclass
class SandboxResult:
    """Outcome of a sandboxed agent run."""

    repo_path: str
    task: str
    model: str
    passed: bool
    decision: str  # "approve" | "needs_changes"
    iterations: int
    before: CommandResult
    after: CommandResult
    changed_files: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        status = "passed" if self.passed else "still failing"
        return (
            f"decision={self.decision} ({status}) after {self.iterations} "
            f"repair iterations; changed: {', '.join(self.changed_files) or 'none'}"
        )


class IsolatedSandbox:
    """Private working copy of a repo with traced command execution.

    If ``keep_dir`` is given the sandbox lives there (and is recreated fresh);
    otherwise a temporary directory is used and cleaned up by :meth:`cleanup`.
    """

    def __init__(
        self,
        repo_path: str,
        *,
        tracer: Tracer | None = None,
        timeout: float = 60.0,
        keep_dir: str | None = None,
    ) -> None:
        self.repo_path = str(Path(repo_path).resolve())
        self._tracer = tracer
        self.timeout = timeout
        self._tmp: tempfile.TemporaryDirectory | None = None
        if keep_dir:
            root = Path(keep_dir)
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True, exist_ok=True)
            self.root = root
        else:
            self._tmp = tempfile.TemporaryDirectory(prefix="aidev-sandbox-")
            self.root = Path(self._tmp.name)
        self._copy()
        self._before = self._snapshot()

    def _copy(self) -> None:
        dst = self.root / "repo"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(self.repo_path, dst, ignore=_IGNORED)
        self.root = dst

    def _snapshot(self) -> dict[str, str]:
        snap: dict[str, str] = {}
        for path in self.root.rglob("*"):
            if any(part in _IGNORED_NAMES for part in path.parts):
                continue
            if path.is_file():
                rel = path.relative_to(self.root)
                snap[str(rel)] = hashlib.sha1(path.read_bytes()).hexdigest()
        return snap

    def changed_files(self) -> list[str]:
        """Files whose content changed since the sandbox was created."""
        after = self._snapshot()
        changed = {name for name, h in after.items() if self._before.get(name) != h}
        changed.update(name for name in self._before if name not in after)
        return sorted(changed)

    def run(
        self,
        cmd: list[str],
        *,
        timeout: float | None = None,
        name: str | None = None,
    ) -> CommandResult:
        """Execute ``cmd`` inside the sandbox, tracing it as a span."""
        result = run_command(cmd, cwd=str(self.root), timeout=timeout or self.timeout)
        if self._tracer and name:
            with self._tracer.span(name) as span:
                span.set_inputs({"cmd": list(result.cmd), "cwd": str(self.root)})
                span.set_outputs(
                    {
                        "returncode": result.returncode,
                        "duration_s": round(result.duration_s, 4),
                        "stdout_tail": result.stdout[-500:],
                        "stderr_tail": result.stderr[-500:],
                    }
                )
                if not result.ok:
                    span.set_error((result.stderr or result.stdout or "command failed")[-300:])
        return result

    def run_tests(self, name: str = "test_run") -> CommandResult:
        """Run the test suite; prefers pytest, falls back to unittest."""
        result = self.run([sys.executable, "-m", "pytest", "-q", "--tb=short"], name=name)
        if result.returncode in (2, 4):  # pytest args/collection errors -> try unittest
            result = self.run([sys.executable, "-m", "unittest", "discover", "-v"], name=name)
        return result

    def stage_repair_script(self, script_path: str) -> str:
        """Copy ``script_path`` into the sandbox root with its basename kept.

        Returns the basename to pass to :meth:`run`. Keeping the original name
        means scripts that resolve sibling files via ``Path(__file__)`` stay
        inside the sandbox root — they can never mutate the source repo.
        """
        src = Path(script_path)
        dst = self.root / src.name
        if dst.exists():
            dst.unlink()
        shutil.copy2(src, dst)
        return src.name

    def cleanup(self) -> None:
        """Remove the sandbox directory (a no-op when ``keep_dir`` was given)."""
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None


class SandboxAgent:
    """Test-driven repair loop that runs entirely inside an isolated sandbox.

    ``repair_scripts`` are Python files applied in the sandbox root while
    tests fail, up to ``max_iterations`` rounds. The agent never touches the
    original repository and never fabricates a result: ``passed`` is ``True``
    only when the final traced test run exits zero.
    """

    def __init__(
        self,
        sandbox: IsolatedSandbox,
        tracer: Tracer,
        *,
        model: str = "demo",
        max_iterations: int = 4,
        original_span_id: str | None = None,
    ) -> None:
        self.sandbox = sandbox
        self._tracer = tracer
        self.model = model
        self.max_iterations = max_iterations
        self._original_span_id = original_span_id

    def run(self, task: str, repair_scripts: list[str] | None = None) -> SandboxResult:
        scripts = list(repair_scripts or [])
        with self._tracer.trace(
            "coding_agent", inputs={"repo": self.sandbox.repo_path, "task": task}
        ) as root:
            root.set_model(self.model)
            root.set_operation("coding_agent")
            root.set_metadata("repo", self.sandbox.repo_path)
            root.set_metadata("task", task)
            root.set_metadata("is_sandboxed", True)
            if self._original_span_id:
                root.set_metadata("original_span_id", self._original_span_id)

            # Repair scripts are copied into the sandbox root and executed
            # there, so __file__-relative or cwd-relative paths in the script
            # can only touch the isolated copy, never the original repo.
            staged: list[str] = []
            for script in scripts:
                staged.append(self.sandbox.stage_repair_script(str(script)))

            before = self.sandbox.run_tests("test_run:baseline")
            if not before.ok:
                root.set_error(f"baseline tests failed (exit {before.returncode})")

            iterations = 0
            after = before
            if not before.ok:
                for _ in range(self.max_iterations):
                    if not staged:
                        break
                    iterations += 1
                    for script in staged:
                        rep = self.sandbox.run(
                            [sys.executable, script],
                            name=f"repair:attempt_{iterations}",
                        )
                        root.set_metadata(f"repair_{iterations}_status", rep.returncode)
                    after = self.sandbox.run_tests(f"test_run:attempt_{iterations}")
                    if after.ok:
                        break

            if not after.ok:
                root.set_error(
                    f"tests still failing after {iterations} repair iterations "
                    f"(exit {after.returncode})"
                )

            changed = self.sandbox.changed_files()
            decision = "approve" if after.ok else "needs_changes"
            root.set_outputs(
                {
                    "decision": decision,
                    "passed": after.ok,
                    "iterations": iterations,
                    "baseline_exit": before.returncode,
                    "final_exit": after.returncode,
                    "changed_files": changed,
                }
            )
            return SandboxResult(
                repo_path=self.sandbox.repo_path,
                task=task,
                model=self.model,
                passed=after.ok,
                decision=decision,
                iterations=iterations,
                before=before,
                after=after,
                changed_files=changed,
            )


__all__ = ["IsolatedSandbox", "SandboxAgent", "SandboxResult"]
