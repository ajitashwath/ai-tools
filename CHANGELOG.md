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
