# TODO — `cyclopts/`

Baseline pure-CLI framework. No web layer.

## Contract

Every solution must expose the same two operations:

**`ping`** — no-op, returns `{"status": "ok"}`

**`calculate`** — binary arithmetic on two floats:
- inputs: `x: float`, `y: float`, `op: str` (one of `add`, `sub`, `mul`, `div`, default `add`)
- returns: `{"op": op, "x": x, "y": y, "result": result}`
- errors: division by zero and unknown op must be handled and reported cleanly

## Goal

Use [cyclopts](https://github.com/BrianPugh/cyclopts) as the canonical baseline: a normal
CLI framework doing a normal operation. If this cold-start is close to the FastAPI shim,
the web-API route is a reasonable trade-off; if it is dramatically faster, import cost is
the problem to solve.

## Commands to implement

```
python -m cyclopts_cli ping
# → {"status": "ok"}

python -m cyclopts_cli calculate <x> <y> [--op add|sub|mul|div]
# → {"op": ..., "x": ..., "y": ..., "result": ...}
```

## Notes

- Use `add_completion=False` on `cyclopts.App` to prevent shell autocomplete logic
  from running in the agent context.
- Output must be JSON on stdout (same shape as all other solutions).
- Wire into the benchmark via `--solution-dir cyclopts`.
