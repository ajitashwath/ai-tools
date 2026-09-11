# Contributing to AI DevTools

Thanks for considering a contribution. This project is local-first and
deterministic by design — please keep it that way (no new network services,
no ML-based heuristics, no fabricated metrics).

## Development setup

```bash
# Backend (Python >= 3.10)
pip install -e ".[dev]"

# UI (Node 20+)
cd ui && npm ci
```

## Running things

```bash
aidev init                        # creates traces.db locally (never commit it)
aidev serve                       # API at http://127.0.0.1:18003
cd ui && npm run dev              # UI at http://localhost:5174
pytest -q                         # backend tests
ruff check aidev tests && ruff format --check aidev tests
```

The demo seed script gives you realistic data without an API key:

```bash
python demo/seed_demo.py --db demo/demo.db --reset
AIDEV_DB_PATH=demo/demo.db aidev serve
```

## Code style

- Python: `ruff check` + `ruff format` (line length 100). No exceptions in CI.
- TypeScript: `npm run lint` (oxlint) must be clean; `npm run build` must pass.
- One CORS setup, one port constant, one row-mapping helper — check for
  existing helpers before adding new ones (`aidev/storage.py::_row_to_span`,
  `ui/src/api.ts`).

## Tests

- New backend behavior needs a pytest covering it; use `tmp_path` fixtures
  for SQLite files — never hardcode paths, never commit `.db` files.
- API changes need a `TestClient` test in `tests/test_server.py`. Note the
  lifespan handler reinitializes module storage on client entry, so inject
  test doubles *after* entering the `TestClient` context (see existing fixture).
- Keep the UI free of duplicated API config — extend `ui/src/api.ts`.

## PR expectations

- One logical change per PR; describe what was wrong and why the fix is correct.
- Update `CHANGELOG.md` under `[Unreleased]`.
- Keep `README.md` (quick start + philosophy) and `docs/` (deep dives) from
  duplicating each other; see "Docs consolidation" below.

## Release process

1. Bump `aidev` version in `pyproject.toml` **and** the UI version in
   `ui/package.json` together — they release as one unit (`0.1.0` currently).
2. Move `CHANGELOG.md` entries from `[Unreleased]` to a new version section.
3. Tag the commit `v<version>` (e.g. `v0.2.0`).

## Code of conduct

Be kind and professional. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
