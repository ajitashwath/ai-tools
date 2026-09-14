"""Tests for aidev.executor.run_command."""

import sys

from aidev.executor import run_command


def test_run_success_captures_stdout():
    result = run_command([sys.executable, "-c", "print('hello world')"])
    assert result.ok
    assert "hello world" in result.stdout


def test_run_captures_stderr_and_exit_code():
    result = run_command([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert not result.ok
    assert result.returncode == 3


def test_run_respects_timeout():
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        timeout=0.3,
    )
    assert result.returncode == -1
    assert "timed out" in result.stderr
    assert 0 < result.duration_s < 10


def test_run_missing_command():
    result = run_command(["definitely-not-a-real-command-xyzq"])
    assert result.returncode == -9
    assert "not found" in result.stderr


def test_run_uses_cwd(tmp_path):
    (tmp_path / "marker.txt").write_text("x", encoding="utf-8")
    result = run_command(
        [sys.executable, "-c", "import os; print(os.path.exists('marker.txt'))"],
        cwd=str(tmp_path),
    )
    assert result.ok
    assert "True" in result.stdout


def test_output_tail():
    result = run_command([sys.executable, "-c", "print('a' * 100)"])
    assert len(result.output_tail(10)) <= 10
