# AI DevTools project walkthrough

> Companion to the [README](../README.md) (quick start + philosophy) and the
> [demo guide](../demo/README.md) (offline demo setup). This document is the
> deep dive: architecture, module map, API surface, demo talk track, and
> known limitations.

## What this project is

AI DevTools is a local-first observability tool for AI-agent executions. Its
main value is making an agent run inspectable: record a run as spans, persist
those spans locally, expose them through an API, and inspect the result in a
browser dashboard.

The core story is:

`RUN -> INSPECT -> UNDERSTAND -> REPLAY -> MODIFY -> COMPARE -> IMPROVE`

The fully wired end-to-end paths today are:

- `RUN -> INSPECT -> UNDERSTAND`: SDK traces → SQLite → API → React dashboard.
- `REPLAY` (real): `aidev replay <id>` re-executes a stored run in an
  isolated sandbox when the span recorded a repo path, then compares.
- `IMPROVE` (real): `aidev sandbox` runs a traced, test-driven repair loop;
  `aidev diagnose`, `aidev optimize`, and `aidev arena` analyze real traced
  data (deterministic, not ML).

Model arena and router are now driven by real traced metrics from the
database (latency, throughput, error/success rates).

## Architecture

```text
Instrumented agent code
        |
        v
aidev.trace.Tracer / Span
        |
        v
aidev.storage.TraceSQLite  --->  traces.db
        |
        v
aidev.server (FastAPI + WebSocket)
        |
        +--> /api/spans
        +--> /api/spans/{id}
        +--> /ws
        |
        v
ui (React + TypeScript + Vite)
        |
        +--> trace list with parent/child hierarchy
        +--> trace detail page
```

## File-by-file map

- `aidev/trace.py`: SDK primitives. `Span` holds timing, status, inputs,
  outputs, model, token, throughput, and error data. `Tracer` creates root and
  nested spans using Python context managers.
- `aidev/storage.py`: SQLite schema and persistence. Spans are upserted while
  they start and again when they finish, so the database can observe partial
  execution as well as completed execution.
- `aidev/server.py`: FastAPI lifecycle, REST endpoints, WebSocket endpoint,
  CORS, and optional serving of `ui/dist`.
- `aidev/cli.py`: Click commands for initialization, server startup, tracing,
  sandbox, replay, comparison, diagnosis, optimization, and arena reporting.
- `aidev/executor.py`: real subprocess runner (arg-list commands, timeout,
  output capture, wall-clock durations; never a shell string).
- `aidev/sandbox.py`: `IsolatedSandbox` (private repo copy + traced command
  execution + change detection) and `SandboxAgent` (test-driven repair loop).
- `aidev/model_diagnosis.py`: deterministic anti-pattern checks such as
  repeated inspections, repeated tool calls, repeated test failures, context
  bloat, exploration, retries, and unchanged actions.
- `aidev/performance_optimization.py`: calculates latency, TTFT,
  throughput, token, error, and p95 metrics and turns thresholds into
  recommendations.
- `aidev/model_arena.py`: model registration and metric-based comparison,
  with scores computed from real traced spans.
- `aidev/model_routing.py`: criteria-based selection from registered models.
- `ui/src/App.tsx`: routes `/` and `/trace/:id`.
- `ui/src/pages/TraceListPage.tsx`: fetches spans, refreshes through the
  WebSocket connection, builds the parent/child tree, and links to details.
- `ui/src/pages/TraceDetailPage.tsx`: displays the selected span’s execution
  metadata, inputs, outputs, model metrics, and errors.
- `demo/seed_demo.py`: deterministic, offline demo data using the real SDK.<br>
- `demo/sample_repo/`: intentionally-broken fixture the real sandbox repairs.

## Five-minute demo script

1. Follow [demo/README.md](../demo/README.md) to seed the demo database and
   start the API (`127.0.0.1:18003`) and UI (`localhost:5174`).
2. Explain the two root spans: one approved review and one failed review.
3. Expand the child rows and point out inspection/test activity.
4. Open the failed trace and show status, duration, model, token count, TTFT,
   throughput, metadata, outputs, and the repeated test error.
5. Run the real sandbox against the bundled broken fixture:
   `python -m aidev sandbox demo\sample_repo "fix the failing calc tests" demo-gpt --repair demo\sample_repo\repair.py`
   Show the baseline (tests failing) → repair applied → final test run passing,
   with all steps visible as new spans in the dashboard.
6. `python -m aidev diagnose` — the failed review surfaces as repeated test
   failures / excessive retries at high severity.
7. `python -m aidev arena` — routes by latency, throughput, and reliability
   from the demo's traced metrics.

If the seeder has been run repeatedly and the list is cluttered, run
`python demo\seed_demo.py --reset` once before starting the demo. This keeps
unrelated traces and refreshes only the demo scenarios.

## What to say during the demo

“The agent is instrumented with a context manager. Every root run and nested
operation becomes a span. A span is saved locally in SQLite, then FastAPI
serves the trace data to a small React dashboard. Because the data is local,
the workflow works without Kafka, Redis, PostgreSQL, or a model-provider key.
The important engineering detail is that failures are data too: the failed
review is visible with its child test attempts and error information.”

## API surface

- `GET /api/spans`: all spans, including nested spans, ordered by start time.
- `GET /api/spans/{span_id}`: one span by ID.
- `POST /api/spans`: creates a root span from a name and optional inputs.
- `WS /ws`: accepts `get_spans` and returns a `spans_update` message.
- `/docs`: FastAPI’s generated API documentation.

## Current limitations to disclose

- The CLI `replay` command re-executes a stored run in a sandbox **only when a
  repo is recorded and still exists**; otherwise it honestly records a fresh
  traced shell (arbitrary code can’t be re-run without the repo).
- The `sandbox` repair loop applies deterministic repair scripts — it is not an
  LLM that writes fixes from scratch. It measures real test outcomes and never
  fabricates a result.
- The model arena and router read real traced data but are CLI/reporting
  surfaces only — routing is not yet integrated into a live request path.
- Diagnosis and optimization are deterministic threshold-based analysis
  utilities; they are not machine-learned recommendations.
- The UI is a focused trace viewer, not yet a full replay/compare/diagnosis
  control center.

## Validation commands

```powershell
python -m compileall -q aidev
pytest -q
ruff check aidev tests
ruff format --check aidev tests
Set-Location ui
npm run lint
npm run build
```

Pytest covers storage, the tracer SDK, and the API routes; ruff covers lint
and format; the UI build validates TypeScript and the production bundle.
