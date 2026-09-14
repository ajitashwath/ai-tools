# AI DevTools demo pack

This folder contains a deterministic demo data generator. It exercises the
real tracing SDK, SQLite persistence, FastAPI API, and React dashboard without
requiring an API key or an external model.

For a clean isolated demo, run from the repo root:

```powershell
python demo\seed_demo.py --db demo\demo.db --reset
$env:AIDEV_DB_PATH = "demo\demo.db"
python -m uvicorn aidev.server:app --host 127.0.0.1 --port 18003
```

In a second terminal:

```powershell
Set-Location ui
npm run dev
```

Open <http://localhost:5174/>. The dashboard should show one successful and
one failed review, with child spans visible beneath each root trace. Open a
trace to show inputs, outputs, model metrics, metadata, and errors.

## Sandbox demo (real test execution, no API key)

```powershell
# Baseline: tests FAIL. Repair applied in an isolated copy. Final: tests PASS.
python -m aidev sandbox demo\sample_repo "fix the failing calc tests" demo-gpt `
  --repair demo\sample_repo\repair.py
```

Every step (baseline, repair, final run) is traced and appears in the
dashboard. The original `demo/sample_repo` is never modified.

## Analysis demo

```powershell
python -m aidev diagnose   # anti-patterns in the seeded runs
python -m aidev optimize   # benchmark + prioritized recommendations
python -m aidev arena      # real model scores + routing per criterion
```

The API uses `traces.db` by default. Set `AIDEV_DB_PATH` as shown above to
point it at the isolated demo database.

For a clean demo after running the seeder more than once, use:

```powershell
python demo\seed_demo.py --reset
```

This removes only spans tagged as the demo’s successful/failed review
scenarios and keeps unrelated traces.
