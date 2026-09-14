"""Real subprocess execution for the sandbox and replay tooling.

Every command is run with a working directory, a timeout and full output
capture. Commands are always given as argument lists (never a shell string),
so there is no shell interpretation or injection surface. On timeout or a
missing executable the result is returned with a non-zero ``returncode`` so
callers can record the failure as trace data instead of crashing.

The executor records real wall-clock duration; no metrics are fabricated.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Outcome of one executed command."""

    cmd: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timeout_s: float | None

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def output_tail(self, limit: int = 2000) -> str:
        """Combined output shortened for trace payloads / terminal display."""
        combined = (self.stdout or "") + (self.stderr or "")
        return (combined or "<no output>")[-limit:]


def run_command(
    cmd: Sequence[str],
    cwd: str | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run ``cmd`` (an argument list) in ``cwd`` and capture its output.

    Never fails on a non-zero exit code: the outcome is returned as a
    :class:`CommandResult` so tracing and repair loops can inspect it.
    """
    argv = [str(part) for part in cmd]
    raised: str | None = None
    start = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            timeout=timeout,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        returncode, stdout, stderr = proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        returncode = -1
        stdout = _decode(exc.stdout)
        stderr = _decode(exc.stderr)
        stderr += f"\n[timed out after {timeout}s]"
        raised = "timeout"
    except FileNotFoundError:
        returncode = -9
        stdout = ""
        stderr = f"command not found: {' '.join(argv)}"
        raised = "not found"
    duration_s = time.monotonic() - start

    result = CommandResult(
        cmd=argv,
        cwd=cwd or ".",
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        duration_s=duration_s,
        timeout_s=timeout,
    )
    if raised is not None:
        result.stderr = f"{stderr}\n[command failed ({raised}) in {result.cwd}]"
    return result


def _decode(data: str | bytes | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data
