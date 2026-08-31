"""Create realistic local traces for the AI DevTools walkthrough.

Run from the repository root:
    python demo/seed_demo.py

The script uses the real SDK and SQLite storage. It does not call an external
model provider, so the demo is deterministic and works offline.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from aidev.storage import TraceSQLite
from aidev.trace import Tracer


def reset_demo_data(storage: TraceSQLite) -> int:
    """Remove demo roots and all of their descendants, leaving other traces."""
    spans = storage.get_all_spans()
    ids_to_delete = {
        span.id
        for span in spans
        if span.metadata.get("scenario") in {"successful review", "failed review"}
    }

    changed = True
    while changed:
        changed = False
        for span in spans:
            if span.parent_id in ids_to_delete and span.id not in ids_to_delete:
                ids_to_delete.add(span.id)
                changed = True

    storage.delete_spans(list(ids_to_delete))
    return len(ids_to_delete)


def seed(db_path: str, reset: bool = False) -> None:
    storage = TraceSQLite(db_path)
    if reset:
        print(f"Removed {reset_demo_data(storage)} existing demo spans")
    tracer = Tracer(storage=storage)

    with tracer.trace(
        "code_review_agent",
        inputs={"repo": "demo-repo", "task": "review PR #42"},
    ) as root:
        root.set_metadata("scenario", "successful review")
        root.set_model("demo-gpt", 420)
        root.set_operation("code_generation")
        root.set_ttft(0.32)
        root.set_tokens_per_sec(58.0)
        root.set_total_tokens(420)
        with tracer.span("inspect_repository") as inspect:
            inspect.set_metadata("tool", "read_file")
            inspect.set_metadata("file_path", "src/payments.py")
            inspect.set_outputs({"lines": 184, "language": "python"})
        with tracer.span("run_tests") as tests:
            tests.set_metadata("tool", "pytest")
            tests.set_outputs({"passed": 24, "failed": 0})
        root.set_outputs({"decision": "approve", "comments": 2})

    with tracer.trace(
        "code_review_agent_failed",
        inputs={"repo": "demo-repo", "task": "review PR #43"},
    ) as root:
        root.set_metadata("scenario", "failed review")
        root.set_model("demo-gpt", 12600)
        root.set_operation("code_generation")
        root.set_ttft(0.91)
        root.set_tokens_per_sec(14.0)
        root.set_total_tokens(12600)
        for attempt in range(1, 4):
            with tracer.span(f"test_attempt_{attempt}") as attempt_span:
                attempt_span.set_metadata("tool", "pytest")
                attempt_span.set_metadata("attempt", attempt)
                attempt_span.set_error("pytest failed: test_payment_total")
                attempt_span.set_outputs({"passed": 23, "failed": 1})
                time.sleep(0.01)
        root.set_error("review stopped after repeated test failures")
        root.set_outputs({"decision": "needs_changes", "comments": 5})

    tracer.end()
    storage.close()
    print(f"Seeded demo traces into {Path(db_path).resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="traces.db", help="SQLite database path")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="remove existing demo traces before creating a fresh demo pair",
    )
    args = parser.parse_args()
    seed(args.db, reset=args.reset)


if __name__ == "__main__":
    main()
