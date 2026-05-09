---
name: Benchmark All Solutions
overview: Simplify `benchmark/bench.py` to fairly compare all five CLI solutions (fastapi-testclient, cyclopts, falcon, robyn, starlette) via subprocess cold-start timing only — one flat table, no per-framework in-process complexity.
todos:
  - id: solution-commands
    content: Add SOLUTION_COMMANDS list with ping/calculate subprocess args for every solution
    status: completed
  - id: remove-inprocess
    content: Remove in-process benchmark functions and overhead waterfall (bench_import, bench_app_init, bench_client_init, bench_per_request, print_overhead_breakdown, _inject_solution_site_packages)
    status: completed
  - id: update-args
    content: Replace --solution-dir with optional --solution filter; remove --no-subprocess
    status: completed
  - id: update-main
    content: Rewrite main() to loop over all solutions, skip missing venvs with a warning, run ping+calculate per solution, and print one flat table
    status: completed
  - id: update-docstring
    content: Update module docstring and banner from FastAPI-specific to generic
    status: completed
isProject: false
---

# Benchmark: Cover All Solutions (Simplified)

Only file changed: [`benchmark/bench.py`](benchmark/bench.py)

## Core idea

The only **fair** cross-solution metric is subprocess cold-start: that is what a real user waits for. Drop the FastAPI-specific in-process breakdown entirely — it cannot be applied uniformly across async and sync frameworks without significant complexity.

## What gets removed

- `bench_import`, `bench_app_init`, `bench_client_init`, `bench_per_request`
- `print_overhead_breakdown`
- `_inject_solution_site_packages`
- `--solution-dir` / `--no-subprocess` CLI flags

## What gets added / changed

### `SOLUTION_COMMANDS`

A plain list of dicts — no dataclass needed:

```python
SOLUTION_COMMANDS = [
    {
        "name": "fastapi-testclient",
        "ping":      ["-m", "fastapi_cli.cli", "/ping"],
        "calculate": ["-m", "fastapi_cli.cli", "/calculate", "x=10", "y=3"],
    },
    {
        "name": "cyclopts",
        "ping":      ["-m", "cyclopts_cli", "ping"],
        "calculate": ["-m", "cyclopts_cli", "calculate", "10", "3"],
    },
    {
        "name": "falcon",
        "ping":      ["-m", "falcon_cli.cli", "/ping"],
        "calculate": ["-m", "falcon_cli.cli", "GET", "/calculate", "x=10", "y=3"],
    },
    {
        "name": "robyn",
        "ping":      ["-m", "robyn_cli.cli", "/ping"],
        "calculate": ["-m", "robyn_cli.cli", "GET", "/calculate", "x=10", "y=3"],
    },
    {
        "name": "starlette",
        "ping":      ["-m", "starlette_cli.cli", "GET", "/ping"],
        "calculate": ["-m", "starlette_cli.cli", "GET", "/calculate", "x=10", "y=3"],
    },
]
```

### Updated CLI args

```
--runs N       measurement repetitions (default 20)
--warmup N     throw-away warmup runs (default 3)
--solution X   run only the named solution (optional filter)
```

### `main()` flow

```
baselines (sys.executable):  python -c pass  |  stdlib-only
for each solution in SOLUTION_COMMANDS:
    find REPO_ROOT/<name>/.venv/bin/python  → skip + warn if missing
    bench_subprocess  /ping
    bench_subprocess  /calculate x=10 y=3
print_report(all samples)
print key insight: fastest vs slowest cold-start
```

Baselines use `sys.executable` (the benchmark's own interpreter) since we only need bare startup overhead, not a per-solution comparison of the interpreter itself.

### Result: one flat table

```
benchmark                                    n    min      mean     median   p95      max
─────────────────────────────────────────────────────────────────────────────────────────
subprocess: python -c pass  (baseline)      20   ...
subprocess: stdlib only  (no framework)     20   ...
fastapi-testclient /ping                    20   ...
fastapi-testclient /calculate x=10 y=3     20   ...
cyclopts ping                               20   ...
cyclopts calculate 10 3                     20   ...
falcon /ping                                20   ...
...
```
