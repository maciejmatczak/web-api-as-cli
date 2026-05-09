# TODO — `robyn/`

Rust-backed ASGI framework wildcard.

## Contract

Every solution must expose the same two operations:

**`ping`** — no-op, returns `{"status": "ok"}`

**`calculate`** — binary arithmetic on two floats:
- inputs: `x: float`, `y: float`, `op: str` (one of `add`, `sub`, `mul`, `div`, default `add`)
- returns: `{"op": op, "x": x, "y": y, "result": result}`
- errors: division by zero and unknown op must be handled and reported cleanly

## Goal

Use [Robyn](https://robyn.tech/) with its `TestClient` from `robyn.testing`. Robyn runs
on a Rust runtime via pyo3, which makes it fast at serving but the `.so` extension load
time is an unknown at cold-start. Treat as an experiment — the Rust backing may or may
not help with the CLI use case.

## Routes to implement

```
GET /ping
# → {"status": "ok"}

GET /calculate?x=&y=&op=
# → {"op": ..., "x": ..., "y": ..., "result": ...}
```

## Notes

- Verify that `robyn.testing.TestClient` works in-process without starting a real server.
- The Rust `.so` extension load time is the key unknown — measure carefully.
- Wire into the benchmark via `--solution-dir robyn`.
