# AI DevTools

![CI](../../actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)

Web apps have browser DevTools. AI agents have log files. AI DevTools closes
that gap: a **local-first tracing and debugging platform** that records every
agent run as inspectable spans — timing, inputs, outputs, model metrics,
errors — and serves them to a small React dashboard. No Kafka, no Postgres,
no API keys required.

## Core Loop

**RUN → INSPECT → UNDERSTAND → REPLAY → MODIFY → COMPARE → IMPROVE**

## Screenshot

> *Dashboard preview — trace list with parent/child hierarchy.*
>
> ![AI DevTools dashboard](docs/screenshot.png)
>
> *(Placeholder: run the demo below and screenshot your own.)*

## Quick Start

Prerequisites: Python ≥ 3.10. For UI development: Node 20+.

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Initialize (creates traces.db in the current directory)
aidev init

# 3. Start the API server (http://127.0.0.1:18003)
aidev serve

# 4. In another terminal, start the UI (http://localhost:5174)
cd ui && npm install && npm run dev

# 5. Trace something and watch it appear in the dashboard
aidev trace my_agent
```

End-to-end in SDK code:

```python
from aidev import trace

with trace("agent") as t:
    t.set_model("gpt-4o", 400)
    run_agent()
```

Want realistic data without a model key? Seed the deterministic demo:

```bash
python demo/seed_demo.py --db demo/demo.db --reset
AIDEV_DB_PATH=demo/demo.db aidev serve
```

See [demo/README.md](demo/README.md) for the full demo walkthrough.

## Ports

| Service | Address |
|---------|---------|
| API server (`aidev serve` / uvicorn) | `http://127.0.0.1:18003` |
| UI dev server (`npm run dev` in `ui/`) | `http://localhost:5174` |

The React UI calls the API at `127.0.0.1:18003` (see `ui/src/api.ts`).
The production UI build is also served directly by the API from `ui/dist`.

## CLI Commands

| Command | Description |
|---------|-------------|
| `aidev init` | Initialize AI DevTools (creates `traces.db`) |
| `aidev trace <name>` | Start a traced execution |
| `aidev serve` | Start the API server |
| `aidev replay <id>` | Replay a traced execution (isolated repo) |
| `aidev compare <id1> <id2>` | Compare two traced runs |
| `aidev sandbox <repo> <task> <model>` | Coding-agent sandbox experiment |

## SDK Usage

```python
from aidev import trace

# Basic trace
with trace("agent") as t:
    run_agent()

# With rich metadata
with trace("agent") as t:
    t.set_metadata("system_prompt", "You are a coding agent")
    t.set_model("gpt-4o", 400)
    t.set_operation("code_generation")
    t.set_ttft(0.5)             # Time To First Token
    t.set_tokens_per_sec(60.0)  # Throughput
    t.set_stop_reason("end_seq")
    t.set_total_tokens(350)

# Nested spans
with trace("outer") as outer:
    with trace("inner") as inner:
        inner.set_error("something went wrong")
```

## Data files

`traces.db` (and `demo/demo.db`) are **generated locally** by `aidev init`
and the demo seeder — they are gitignored and never committed. Point the API
at a different database with the `AIDEV_DB_PATH` environment variable.

## Project Structure

```
.
├── aidev/                      # Python package
│   ├── trace.py                # Tracer SDK (Span, Tracer, trace())
│   ├── storage.py              # TraceSQLite (SQLite persistence)
│   ├── server.py               # FastAPI backend (+ WebSocket)
│   ├── cli.py                  # CLI: aidev init/trace/serve/replay/compare/sandbox
│   ├── model_arena.py          # Model comparison across providers
│   ├── model_routing.py        # Automatic model selection by criteria
│   ├── model_diagnosis.py      # Deterministic agent diagnostics
│   └── performance_optimization.py # Benchmark + optimization recommendations
├── ui/                         # React + TypeScript UI
│   ├── src/
│   │   ├── api.ts             # Shared API config, types, fetch helpers
│   │   ├── App.tsx            # Router + pages
│   │   ├── pages/TraceListPage.tsx   # Trace list with hierarchy
│   │   └── pages/TraceDetailPage.tsx # Span detail view
│   └── vite.config.ts         # Vite config (dev server on :5174)
├── tests/                      # Pytest suite (storage, trace, server)
├── demo/                       # Deterministic offline demo seeder
├── docs/                       # Deep dives (see docs/ below)
└── pyproject.toml              # Package configuration
```

## Docs

- [docs/PROJECT_WALKTHROUGH.md](docs/PROJECT_WALKTHROUGH.md) — architecture,
  file-by-file map, API surface, demo script, and current limitations.
- [demo/README.md](demo/README.md) — running the offline demo.
- [CHANGELOG.md](CHANGELOG.md) — release history (Keep a Changelog).

## Philosophy

- **Local-first**: Everything runs on one developer device. No Kafka, Kubernetes, Redis, or PostgreSQL.
- **Provider-agnostic**: Works with OpenAI, Ollama, local models/subprocesses. Never hard-coded around a single provider.
- **Provider failure does not prevent startup**: Core application works without any provider.
- **Deterministic diagnostics**: Detect patterns (repeated inspections, test failures, context bloat, etc.), never ML predictions.
- **No fabrication**: Never fake metrics or claim false capabilities.
- **Real workloads**: Benchmarks from actual execution, not toy tasks.
- **Simple over complex**: Prefer working simple architecture over complex distributed systems.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, code style, and the
release process. TL;DR:

```bash
pip install -e ".[dev]"
pytest -q && ruff check aidev tests && ruff format --check aidev tests
```

## License

MIT — see [LICENSE](LICENSE).
