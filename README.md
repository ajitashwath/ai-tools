# AI DevTools
Local-first AI debugging and experimentation platform. Make AI systems as inspectable as web applications are through browser DevTools.

## Core Loop
**RUN → INSPECT → UNDERSTAND → REPLAY → MODIFY → COMPARE → IMPROVE**

## Philosophy
- **Local-first**: Everything runs on one developer device. No Kafka, Kubernetes, Redis, or PostgreSQL.
- **Provider-agnostic**: Works with OpenAI, Ollama, local models/subprocesses. Never hard-coded around a single provider.
- **Provider failure does not prevent startup**: Core application works without any provider.
- **Deterministic diagnostics**: Detect patterns (repeated inspections, test failures, context bloat, etc.), never ML predictions.
- **No fabrication**: Never fake metrics or claim false capabilities.
- **Real workloads**: Benchmarks from actual execution, not toy tasks.
- **Simple over complex**: Prefer working simple architecture over complex distributed systems.

## Quick Start

```bash
# 1. Initialize
aidev init

# 2. Start a traced execution
aidev trace my_agent

# 2. Start the API server
aidev serve

# 3. Open the UI
#    Visit http://localhost:5174/ in your browser

# 4. Basic workflow
#    - Trace execution with: with trace("agent"): run_agent()
#    - View traces in the UI
#    - Compare two traces
#    - Replay a trace with modified parameters
#    - Diagnose anti-patterns
#    - Get performance optimizations
```

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
    t.set_ttft(0.5)           # Time To First Token
    t.set_tokens_per_sec(60.0) # Throughput
    t.set_stop_reason("end_seq")  # stop reason
    t.set_total_tokens(350)   # Total token count

# Nested spans
with trace("outer") as outer:
    with trace("inner") as inner:
        inner.set_error("something went wrong")

# SDK also supports:
# - Span IDs and parent relationships
# - Timing and status
# - Metadata and errors
# - Tool calls
# - Model information
# - Token counts
```

## Directory Structure

```
E:\ai-tools\
├── aidev/                      # Python package
│   ├── __init__.py            # Package exports
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
│   │   ├── App.tsx            # Router + pages
│   │   ├── pages/TraceListPage.tsx   # Trace list with hierarchy
│   │   ├── pages/TraceDetailPage.tsx  # Span detail view
│   │   ├── App.css           # Dark-themed UI styles
│   │   ├── main.tsx          # Vite entry point
│   │   └── index.css         # Global styles
│   ├── package.json           # Dependencies (react, vite, react-router-dom)
│   ├── vite.config.ts         # Vite config
│   └── dist/                  # Built UI files
├── pyproject.toml              # Package configuration
├── traces.db                   # Auto-created SQLite database
└── README.md                   # This file
```
