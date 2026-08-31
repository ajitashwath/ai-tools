# AI DevTools demo pack

This folder contains a deterministic demo data generator. It exercises the
real tracing SDK, SQLite persistence, FastAPI API, and React dashboard without
requiring an API key or an external model.

For a clean isolated demo, run from `E:\ai-tools`:

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

The API uses `traces.db` by default. Set `AIDEV_DB_PATH` as shown above to
point it at the isolated demo database.

For a clean demo after running the seeder more than once, use:

```powershell
python demo\seed_demo.py --reset
```

This removes only spans tagged as the demo’s successful/failed review
scenarios and keeps unrelated traces.
