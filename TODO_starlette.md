# TODO — `starlette/`

FastAPI minus the FastAPI layer.

## Contract

Every solution must expose the same two operations:

**`ping`** — no-op, returns `{"status": "ok"}`

**`calculate`** — binary arithmetic on two floats:
- inputs: `x: float`, `y: float`, `op: str` (one of `add`, `sub`, `mul`, `div`, default `add`)
- returns: `{"op": op, "x": x, "y": y, "result": result}`
- errors: division by zero and unknown op must be handled and reported cleanly

## Goal

Use bare [Starlette](https://www.starlette.io/) with its own `TestClient` (backed by
`httpx`). FastAPI is a thin wrapper on top of Starlette, so this isolates how much of
the ~210 ms cold-start is FastAPI itself versus the Starlette/anyio/httpx stack underneath.

## Routes to implement

```
GET /ping
# → {"status": "ok"}

GET /calculate?x=&y=&op=
# → {"op": ..., "x": ..., "y": ..., "result": ...}
```

## Notes

- No Pydantic — parse and cast query params manually from `request.query_params`.
- Use `starlette.testclient.TestClient` (same class FastAPI re-exports).
- Wire into the benchmark via `--solution-dir starlette`.
