# TODO — `falcon/`

Lightweight ASGI framework.

## Contract

Every solution must expose the same two operations:

**`ping`** — no-op, returns `{"status": "ok"}`

**`calculate`** — binary arithmetic on two floats:
- inputs: `x: float`, `y: float`, `op: str` (one of `add`, `sub`, `mul`, `div`, default `add`)
- returns: `{"op": op, "x": x, "y": y, "result": result}`
- errors: division by zero and unknown op must be handled and reported cleanly

## Goal

Use [Falcon](https://falcon.readthedocs.io/) in ASGI mode (`falcon.asgi.App`) with
`falcon.testing.TestClient`. Falcon has ~3 direct dependencies and no pydantic or anyio
at import time, so cold-start is expected to be significantly lower than FastAPI.

## Routes to implement

```
GET /ping
# → {"status": "ok"}

GET /calculate?x=&y=&op=
# → {"op": ..., "x": ..., "y": ..., "result": ...}
```

## Notes

- No built-in type coercion — parse and cast query params manually.
- Use `falcon.testing.TestClient` (in-process, no socket).
- Wire into the benchmark via `--solution-dir falcon`.
