# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Pytest suite (`tests/`) covering storage, tracer SDK, and FastAPI routes.
- GitHub Actions CI for backend (ruff + pytest) and UI (lint + build).
- `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates.
- `CHANGELOG.md` following Keep a Changelog.
- **Real sandbox** (`aidev/executor.py` + `aidev/sandbox.py`): isolated repo
  copy, real subprocess execution with timeout/capture, and a test-driven
  repair loop that applies deterministic repair scripts and re-runs the test
  suite. Every step is traced. Bundled `demo/sample_repo` demo fixture that the
  sandbox actually fixes.
- **Real replay**: `aidev replay <id>` re-executes a stored run inside a
  sandbox when the span carries a repo path, linking the new run back to the
  original and printing a comparison.
- New CLI commands: `aidev diagnose`, `aidev optimize`, `aidev arena` now
  analyze real traced data (previously these modules were not wired to the CLI
  or the database).
- `ModelArena` computes scores from real traced spans (`get_spans_by_model`);
  `ModelRouter` auto-registers models from the DB, and routing works on
  measured data.
- `python -m aidev` works as a CLI alias (`aidev/__main__.py`).

### Changed

- The `trace()` SDK helper now persists to `traces.db` by default, matching the
  documented quickstart.
- `POST /api/spans` finalizes the span and pushes live updates to connected
  WebSocket clients (`/ws`) instead of requiring polling.
- Fixed `ModelRouter` balanced scoring picking the *worst* candidate
  (`min` → `max`) and task-keyword inference requiring an exact match instead
  of a substring.
- `set_inputs()` added to the SDK span context for traced tool calls.

### Fixed

- Deduplicated SQLite row→`Span` mapping into a single `_row_to_span` helper.
- Made `TraceSQLite` thread-safe (`threading.Lock` + WAL journal mode).
- Consolidated CORS to a single `CORSMiddleware` scoped to local dev origins.
- `POST /api/spans` now honors `parent_id` instead of always creating root spans.
- Canonical ports: API `127.0.0.1:18003`, UI dev server `localhost:5174`.
- Working `aidev` console script via explicit `aidev.cli:main`.

### Removed

- Dead `_add_children` helper in `aidev/server.py`.
- Scratch scripts `debug2.py` / `test_server.py` (replaced by real tests).
- Committed SQLite databases (`traces.db`, `aidev/traces.db`, `ui/traces.db`,
  `demo/demo.db`); `*.db` is now gitignored.
