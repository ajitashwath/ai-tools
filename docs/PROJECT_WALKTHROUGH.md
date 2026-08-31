# AI DevTools project walkthrough

## What this project is

AI DevTools is a local-first observability tool for AI-agent executions. Its
main value is making an agent run inspectable: record a run as spans, persist
those spans locally, expose them through an API, and inspect the result in a
browser dashboard.

The core story is:

`RUN -> INSPECT -> UNDERSTAND -> REPLAY -> MODIFY -> COMPARE -> IMPROVE`

The currently reliable end-to-end path is `RUN -> INSPECT -> UNDERSTAND`.
Replay, model routing, model arena, optimization, diagnosis, and sandbox
modules exist as Python building blocks, but they are not all wired into the
browser or the CLI yet.

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
  comparison, replay, and sandbox experiments.
- `aidev/model_diagnosis.py`: deterministic anti-pattern checks such as
  repeated inspections, repeated tool calls, repeated test failures, context
  bloat, exploration, retries, and unchanged actions.
- `aidev/performance_optimization.py`: calculates latency, TTFT,
  throughput, token, error, and p95 metrics and turns thresholds into
  recommendations.
- `aidev/model_arena.py`: model registration and metric-based comparison.
- `aidev/model_routing.py`: criteria-based selection from registered models.
- `ui/src/App.tsx`: routes `/` and `/trace/:id`.
- `ui/src/pages/TraceListPage.tsx`: fetches spans, refreshes through the
  WebSocket connection, builds the parent/child tree, and links to details.
- `ui/src/pages/TraceDetailPage.tsx`: displays the selected span’s execution
  metadata, inputs, outputs, model metrics, and errors.
- `demo/seed_demo.py`: deterministic, offline demo data using the real SDK.

## Five-minute demo script

1. From the repository root, run `python demo\\seed_demo.py --db
   demo\\demo.db --reset`.
2. Point the API at the isolated demo database with
   `$env:AIDEV_DB_PATH = "demo\\demo.db"`, then start it with `python -m
   uvicorn aidev.server:app --host 127.0.0.1 --port 18003`.
3. Start the UI in another terminal with `Set-Location ui; npm run dev`.
4. Open `http://localhost:5174/`.
5. Explain the two root spans: one approved review and one failed review.
6. Expand the child rows and point out inspection/test activity.
7. Open the failed trace and show status, duration, model, token count, TTFT,
   throughput, metadata, outputs, and the repeated test error.
8. Run `python -c "from aidev.server import app; print(app.title)"` if you
   want to show that the API is independently importable.

If the seeder has been run repeatedly and the list is cluttered, run
`python demo\\seed_demo.py --reset` once before starting the demo. This keeps
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

- The CLI `replay` command creates an isolated temporary copy when a repo path
  is present, but the actual re-execution is still a placeholder.
- The CLI `trace` command records a short root span; application code should
  use the SDK context manager for nested spans and richer metadata.
- The `sandbox` command verifies repository/Docker conditions and describes
  the intended isolation flow; it does not run a coding agent yet.
- The model arena and router are callable Python modules, not dashboard
  features, and their automatic data registration is incomplete.
- Diagnosis and optimization are deterministic threshold-based analysis
  utilities; they are not machine-learned recommendations.
- The UI is a focused trace viewer, not yet a full replay/compare/diagnosis
  control center.

## Validation commands

```powershell
python -m compileall -q aidev
python test_server.py
Set-Location ui
npm run build
```

The first two validate the Python package and API smoke path. The UI build
validates TypeScript and the production bundle.
