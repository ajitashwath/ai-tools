# sample_repo — sandbox demo fixture

A deliberately broken sample package used to demonstrate the real sandbox:

```powershell
python -m aidev sandbox demo\sample_repo "fix the failing calc tests" demo-gpt `
  --repair demo\sample_repo\repair.py
```

- `calc.py` — contains an intentional bug (`total` skips the first price).
- `test_calc.py` — `pytest` suite that fails on the buggy line.
- `repair.py` — deterministic repair script applied by `SandboxAgent` inside
  the isolated copy; after it runs, the suite passes.

The agent copies the repo to a private directory, so this fixture is never
mutated.